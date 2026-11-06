# Copyright (C) 2024 Josua Krause
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for accounts, passwords, sessions, capabilities and worker tokens as
kept by the user managers. Unless a test names a backend it runs against
both the redis and the Postgres user manager."""
import hashlib
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from test.util import ADMIN_EMAIL, ADMIN_PW, memory_redis, UNUSED_REDIS
from typing import Any, cast

import pytest
import sqlalchemy as sa
from redipy import Redis
from scattermind.system.base import UserId
from scattermind.system.names import UName
from scattermind.system.session.session import SessionStore
from scattermind.system.util import get_short_hash

from swai.system.user import CAP_CREATE_USER, CAP_LIST_USERS, CAPABILITIES
from swai_server.config import config_template, select_user_store
from swai_server.system.db.db import create_db_engine
from swai_server.system.user import manager as user_manager_module
from swai_server.system.user import redis as user_redis_module
from swai_server.system.user.db import (
    DBUserManager,
    RESET_TOKENS,
    SESSIONS,
    USERS,
)
from swai_server.system.user.loader import load_user_manager, UserManagerModule
from swai_server.system.user.manager import (
    as_capability,
    check_password,
    derive_account_key,
    derive_user_id,
    hash_password,
    INVALID_WORKER_TOKEN,
    UserManager,
)
from swai_server.system.user.redis import RedisUserManager


ALICE = UName("alice@example.com")
BOB = UName("bob@example.com")
NOBODY = UName("nobody@example.com")
SOME_TIME = 5.0


def invite(user_mng: UserManager, email: UName, password: str) -> None:
    """
    Creates an account and sets its password through the reset token that
    the invitation email carries.

    Args:
        user_mng (UserManager): The user manager.
        email (UName): The new account.
        password (str): The password the new user picks.
    """
    assert user_mng.create_user(email, f"display {email.get()}")
    reset_token = user_mng.generate_reset_token(email)
    assert reset_token is not None
    assert user_mng.set_password(password, reset_token) == email


def worker_token_for(user_mng: UserManager, email: UName) -> str:
    """
    Creates a worker token for an existing account.

    Args:
        user_mng (UserManager): The user manager.
        email (UName): The account.

    Returns:
        str: The worker token.
    """
    worker_token = user_mng.create_worker_token(email)
    assert worker_token is not None
    return worker_token


# *** passwords ***


def test_password_hash_roundtrip() -> None:
    hashpw = hash_password("correct horse")
    assert hashpw != "correct horse"
    assert check_password("correct horse", hashpw)
    assert not check_password("Correct horse", hashpw)
    assert not check_password("correct horse ", hashpw)


def test_password_hash_is_salted() -> None:
    first = hash_password("same")
    second = hash_password("same")
    assert first != second
    assert first.startswith("$2b$12$")


@pytest.mark.parametrize("hashpw", [None, ""])
def test_check_password_without_hash(hashpw: str | None) -> None:
    # an account whose password was never set cannot be logged into
    assert not check_password("", hashpw)
    assert not check_password("anything", hashpw)


def test_long_passwords_are_not_truncated() -> None:
    """bcrypt reads only 72 bytes; the password is hashed before bcrypt sees
    it, so a difference past byte 72 still matters."""
    prefix = "a" * 72
    hashpw = hash_password(f"{prefix}1")
    assert check_password(f"{prefix}1", hashpw)
    assert not check_password(f"{prefix}2", hashpw)


def test_as_capability() -> None:
    for cap in CAPABILITIES:
        assert as_capability(cap) == cap
    with pytest.raises(ValueError, match="is invalid"):
        as_capability("rule_the_world")


# *** accounts ***


def test_create_user(user_mng: UserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    assert user_mng.get_user_info(ALICE) == {
        "email": ALICE,
        "display_name": "Alice",
        "capabilities": set(),
    }


def test_create_user_twice(user_mng: UserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    assert not user_mng.create_user(ALICE, "Mallory")
    assert user_mng.get_user_info(ALICE)["display_name"] == "Alice"


def test_create_user_rejects_admin_and_empty_name(
        user_mng: UserManager) -> None:
    assert not user_mng.create_user(ADMIN_EMAIL, "Mallory")
    assert not user_mng.create_user(ALICE, "")
    assert set(user_mng.list_users()) == {ADMIN_EMAIL}


class PausingRedis:
    """
    Wraps a redis so that every call made from the paused thread, including
    calls of registered scripts, is followed by a pause until the test lets
    the thread continue. This opens a window between any two redis calls of
    the paused thread for another thread to act in.
    """
    def __init__(self, inner: Redis) -> None:
        self._inner = inner
        self._paused_thread: int | None = None
        self._in_pause = threading.Event()
        self._resume = threading.Event()

    def pause_current_thread(self) -> None:
        """Pauses the calling thread after each of its redis calls."""
        self._paused_thread = threading.get_ident()

    def wait_for_pause(self) -> bool:
        """
        Waits until the paused thread is stopped after a redis call.

        Returns:
            bool: Whether the thread got stopped in time.
        """
        return self._in_pause.wait(SOME_TIME)

    def resume(self) -> None:
        """Lets the paused thread continue without further pauses."""
        self._resume.set()

    def _pause(self) -> None:
        if threading.get_ident() != self._paused_thread:
            return
        self._in_pause.set()
        assert self._resume.wait(SOME_TIME)

    def _wrap(self, fun: Callable[..., Any]) -> Callable[..., Any]:
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            res = fun(*args, **kwargs)
            if callable(res):
                # a registered script
                return self._wrap(res)
            self._pause()
            return res

        return wrapped

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._inner, name)
        if not callable(attr):
            return attr
        return self._wrap(attr)


def test_concurrent_create_user_redis(
        monkeypatch: pytest.MonkeyPatch, admin_pw_hash: str) -> None:
    """Two registrations for the same email at the same time: exactly one
    succeeds and its info is kept, no matter where the other one gets in."""
    redis = PausingRedis(memory_redis())
    monkeypatch.setattr(user_redis_module, "Redis", lambda *_a, **_kw: redis)
    user_mng = RedisUserManager(
        admin_email=ADMIN_EMAIL, admin_pw=admin_pw_hash, cfg=UNUSED_REDIS)
    results: dict[str, bool] = {}

    def create_first() -> None:
        redis.pause_current_thread()
        results["first"] = user_mng.create_user(ALICE, "First")

    first = threading.Thread(target=create_first, daemon=True)
    first.start()
    # the first creation is stopped right after its first redis call
    assert redis.wait_for_pause()
    results["second"] = user_mng.create_user(ALICE, "Second")
    redis.resume()
    first.join(SOME_TIME)
    assert not first.is_alive()
    assert sorted(results.values()) == [False, True]
    winner = "First" if results["first"] else "Second"
    assert user_mng.get_user_info(ALICE)["display_name"] == winner
    assert list(user_mng.list_users()) == [ADMIN_EMAIL, ALICE]


def test_list_users(user_mng: UserManager) -> None:
    assert list(user_mng.list_users()) == [ADMIN_EMAIL]
    user_mng.create_user(ALICE, "Alice")
    user_mng.create_user(BOB, "Bob")
    users = list(user_mng.list_users())
    assert users[0] == ADMIN_EMAIL
    assert sorted(user.get() for user in users[1:]) == [
        ALICE.get(),
        BOB.get(),
    ]


def test_user_id(user_mng: UserManager) -> None:
    """An account gets the ids derived from its email when it is created
    (the ids its chats and workers always had); an email without an account
    has none."""
    assert user_mng.get_user_id(ALICE) is None
    assert user_mng.get_ids(ALICE) is None
    assert user_mng.create_user(ALICE, "Alice")
    assert user_mng.create_user(BOB, "Bob")
    assert user_mng.get_ids(ALICE) == {
        "user_id": UserId.create(ALICE),
        "account_key": get_short_hash(ALICE.get()),
    }
    assert user_mng.get_user_id(ALICE) == UserId.create(ALICE)
    assert user_mng.get_account_key(ALICE) == get_short_hash(ALICE.get())
    assert user_mng.get_user_id(ALICE) != user_mng.get_user_id(BOB)
    # the admin has the ids derived from the configured email
    assert user_mng.get_ids(ADMIN_EMAIL) == {
        "user_id": UserId.create(ADMIN_EMAIL),
        "account_key": get_short_hash(ADMIN_EMAIL.get()),
    }


# *** invitations and password resets ***


def test_new_user_cannot_log_in_before_setting_password(
        user_mng: UserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    assert user_mng.login(ALICE, "") is None
    assert user_mng.login(ALICE, "guess") is None


def test_invite_then_login(user_mng: UserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    reset_token = user_mng.generate_reset_token(ALICE)
    assert reset_token is not None
    assert user_mng.get_email_for_reset_token(reset_token) == ALICE
    assert user_mng.set_password("alice pw", reset_token) == ALICE
    token = user_mng.login(ALICE, "alice pw")
    assert token is not None
    assert user_mng.get_email(token) == ALICE
    assert user_mng.login(ALICE, "wrong pw") is None


def test_reset_token_is_single_use(user_mng: UserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    reset_token = user_mng.generate_reset_token(ALICE)
    assert reset_token is not None
    assert user_mng.set_password("first", reset_token) == ALICE
    assert user_mng.get_email_for_reset_token(reset_token) is None
    assert user_mng.set_password("second", reset_token) is None


def test_reset_token_cooldown(user_mng: UserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    first = user_mng.generate_reset_token(ALICE)
    assert first is not None
    # no second email within the cooldown, and the first token stays good
    assert user_mng.generate_reset_token(ALICE) is None
    assert user_mng.get_email_for_reset_token(first) == ALICE
    # using the token lifts the cooldown
    assert user_mng.set_password("pw", first) == ALICE
    second = user_mng.generate_reset_token(ALICE)
    assert second is not None
    assert second != first


def test_reset_cooldown_expires(
        user_mng: UserManager,
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(user_manager_module, "PW_RESET_COOLDOWN", 0.05)
    assert user_mng.create_user(ALICE, "Alice")
    first = user_mng.generate_reset_token(ALICE)
    assert first is not None
    time.sleep(0.1)
    second = user_mng.generate_reset_token(ALICE)
    assert second is not None
    # an unused older token is not revoked by a newer one
    assert user_mng.get_email_for_reset_token(first) == ALICE
    assert user_mng.get_email_for_reset_token(second) == ALICE


def test_reset_token_expires(
        user_mng: UserManager,
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(user_manager_module, "PW_RESET_EXPIRE", 0.05)
    assert user_mng.create_user(ALICE, "Alice")
    reset_token = user_mng.generate_reset_token(ALICE)
    assert reset_token is not None
    time.sleep(0.1)
    assert user_mng.get_email_for_reset_token(reset_token) is None
    assert user_mng.set_password("pw", reset_token) is None


def test_unknown_reset_token(user_mng: UserManager) -> None:
    assert user_mng.get_email_for_reset_token(uuid.uuid4().hex) is None
    assert user_mng.set_password("pw", uuid.uuid4().hex) is None


def test_no_reset_token_for_admin(user_mng: UserManager) -> None:
    # the admin password comes from the environment, not from redis
    assert user_mng.generate_reset_token(ADMIN_EMAIL) is None


def test_no_reset_token_for_unknown_user(user_mng: UserManager) -> None:
    assert user_mng.generate_reset_token(BOB) is None
    # asking for an unknown account leaves no cooldown behind: once the
    # account exists the first request gets a token right away
    assert user_mng.create_user(BOB, "Bob")
    reset_token = user_mng.generate_reset_token(BOB)
    assert reset_token is not None
    assert user_mng.set_password("bob pw", reset_token) == BOB
    assert user_mng.login(BOB, "bob pw") is not None


def test_reset_token_for_vanished_account(
        redis_user_mng: RedisUserManager) -> None:
    """A reset token whose account does not exist (e.g., one issued for an
    unknown email before such tokens were refused) is refused cleanly and
    does not create the account."""
    user_mng = redis_user_mng
    reset_token = uuid.uuid4().hex
    # pylint: disable=protected-access
    user_mng._redis.set_value(
        user_mng._key_pw_reset(reset_token), BOB.get())
    assert user_mng.get_email_for_reset_token(reset_token) == BOB
    assert user_mng.set_password("pw", reset_token) is None
    assert user_mng.get_email_for_reset_token(reset_token) is None
    assert user_mng.login(BOB, "pw") is None
    assert list(user_mng.list_users()) == [ADMIN_EMAIL]


def test_reset_token_of_deleted_account(user_mng: UserManager) -> None:
    """A reset token does not outlive its account: neither for the deleted
    account nor for a new account with the same email."""
    assert user_mng.create_user(BOB, "Bob")
    reset_token = user_mng.generate_reset_token(BOB)
    assert reset_token is not None
    assert user_mng.delete_user(BOB)
    assert user_mng.get_email_for_reset_token(reset_token) is None
    assert user_mng.set_password("pw", reset_token) is None
    assert list(user_mng.list_users()) == [ADMIN_EMAIL]
    assert user_mng.create_user(BOB, "New Bob")
    assert user_mng.get_email_for_reset_token(reset_token) is None
    assert user_mng.set_password("pw", reset_token) is None
    assert user_mng.login(BOB, "pw") is None


def test_password_change(user_mng: UserManager) -> None:
    invite(user_mng, ALICE, "old pw")
    reset_token = user_mng.generate_reset_token(ALICE)
    assert reset_token is not None
    assert user_mng.set_password("new pw", reset_token) == ALICE
    assert user_mng.login(ALICE, "old pw") is None
    assert user_mng.login(ALICE, "new pw") is not None


# *** sessions ***


def test_unknown_user_cannot_log_in(user_mng: UserManager) -> None:
    assert user_mng.login(BOB, "pw") is None
    assert user_mng.count_sessions(BOB) == 0


def test_sessions(user_mng: UserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    first = user_mng.do_login(ALICE)
    second = user_mng.do_login(ALICE)
    assert first is not None
    assert second is not None
    assert first != second
    assert user_mng.get_email(first) == ALICE
    assert user_mng.get_email(second) == ALICE
    assert user_mng.count_sessions(ALICE) == 2
    user_mng.logout(first)
    assert user_mng.get_email(first) is None
    assert user_mng.get_email(second) == ALICE
    assert user_mng.count_sessions(ALICE) == 1


def test_sessions_are_per_user(user_mng: UserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    assert user_mng.create_user(BOB, "Bob")
    alice = user_mng.do_login(ALICE)
    bob = user_mng.do_login(BOB)
    assert alice is not None
    assert bob is not None
    assert user_mng.get_email(alice) == ALICE
    assert user_mng.get_email(bob) == BOB
    user_mng.logout(alice)
    assert user_mng.get_email(bob) == BOB


def test_forged_session_token(user_mng: UserManager) -> None:
    """A session token starts with the account's public hash; the random
    remainder is what makes it a secret."""
    assert user_mng.create_user(ALICE, "Alice")
    token = user_mng.do_login(ALICE)
    assert token is not None
    if isinstance(user_mng, RedisUserManager):
        assert token.startswith(get_short_hash(ALICE.get()))
    forged = f"{get_short_hash(ALICE.get())}{uuid.uuid4().hex}"
    assert user_mng.get_email(forged) is None
    assert user_mng.get_email("") is None
    assert user_mng.get_email("not a token") is None


def test_logout_unknown_token(user_mng: UserManager) -> None:
    user_mng.logout("not a token")
    user_mng.logout("")


# *** admin ***


def test_admin_login(user_mng: UserManager) -> None:
    assert user_mng.get_admin() == ADMIN_EMAIL
    assert user_mng.is_admin(ADMIN_EMAIL)
    assert not user_mng.is_admin(ALICE)
    token = user_mng.login(ADMIN_EMAIL, ADMIN_PW)
    assert token is not None
    assert user_mng.get_email(token) == ADMIN_EMAIL
    assert user_mng.login(ADMIN_EMAIL, "wrong") is None


def test_forged_admin_session_token(user_mng: UserManager) -> None:
    forged = f"{get_short_hash(ADMIN_EMAIL.get())}{uuid.uuid4().hex}"
    assert user_mng.get_email(forged) is None


def test_admin_logout(user_mng: UserManager) -> None:
    token = user_mng.do_login(ADMIN_EMAIL)
    assert token is not None
    assert user_mng.get_email(token) == ADMIN_EMAIL
    user_mng.logout(token)
    assert user_mng.get_email(token) is None


def test_admin_has_every_capability(user_mng: UserManager) -> None:
    for cap in CAPABILITIES:
        assert user_mng.has_capability(ADMIN_EMAIL, cap)
    assert user_mng.list_capabilities(ADMIN_EMAIL) == set(CAPABILITIES)
    user_mng.set_capability(ADMIN_EMAIL, CAP_CREATE_USER, has=False)
    assert user_mng.has_capability(ADMIN_EMAIL, CAP_CREATE_USER)
    assert user_mng.get_user_info(ADMIN_EMAIL) == {
        "email": ADMIN_EMAIL,
        "display_name": "admin",
        "capabilities": set(CAPABILITIES),
    }


@pytest.fixture(name="no_admin_user_mng", params=["redis", "postgres"])
def fixture_no_admin_user_mng(
        request: pytest.FixtureRequest,
        monkeypatch: pytest.MonkeyPatch) -> Iterator[UserManager]:
    """
    A user manager with an admin email but without an admin password, once
    for each backend.

    Yields:
        UserManager: The user manager.
    """
    if request.param == "redis":
        monkeypatch.setattr(user_redis_module, "Redis", memory_redis)
        yield RedisUserManager(
            admin_email=ADMIN_EMAIL, admin_pw=None, cfg=UNUSED_REDIS)
        return
    postgres_url = request.getfixturevalue("postgres_url")
    pg_schema = request.getfixturevalue("pg_schema")
    user_mng = DBUserManager(
        admin_email=ADMIN_EMAIL,
        admin_pw=None,
        engine=create_db_engine(postgres_url, schema=pg_schema),
        schema=pg_schema)
    try:
        yield user_mng
    finally:
        user_mng.close()


def test_no_admin_without_password(no_admin_user_mng: UserManager) -> None:
    """Without `ADMIN_PW` the admin account does not exist."""
    user_mng = no_admin_user_mng
    assert user_mng.get_admin() is None
    assert not user_mng.is_admin(ADMIN_EMAIL)
    assert user_mng.login(ADMIN_EMAIL, "") is None
    assert user_mng.login(ADMIN_EMAIL, ADMIN_PW) is None
    forged = f"{get_short_hash(ADMIN_EMAIL.get())}{uuid.uuid4().hex}"
    assert user_mng.get_email(forged) is None
    assert not list(user_mng.list_users())
    assert not user_mng.has_capability(ADMIN_EMAIL, CAP_CREATE_USER)


# *** capabilities ***


def test_capabilities(user_mng: UserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    assert user_mng.create_user(BOB, "Bob")
    assert not user_mng.has_capability(ALICE, CAP_CREATE_USER)
    user_mng.set_capability(ALICE, CAP_CREATE_USER, has=True)
    user_mng.set_capability(ALICE, CAP_LIST_USERS, has=True)
    assert user_mng.has_capability(ALICE, CAP_CREATE_USER)
    assert user_mng.list_capabilities(ALICE) == {
        CAP_CREATE_USER,
        CAP_LIST_USERS,
    }
    assert user_mng.get_user_info(ALICE)["capabilities"] == {
        CAP_CREATE_USER,
        CAP_LIST_USERS,
    }
    # granting twice is harmless; capabilities are per user
    user_mng.set_capability(ALICE, CAP_CREATE_USER, has=True)
    assert not user_mng.list_capabilities(BOB)
    user_mng.set_capability(ALICE, CAP_CREATE_USER, has=False)
    assert not user_mng.has_capability(ALICE, CAP_CREATE_USER)
    assert user_mng.list_capabilities(ALICE) == {CAP_LIST_USERS}
    # revoking what was never granted is harmless as well
    user_mng.set_capability(BOB, CAP_CREATE_USER, has=False)
    assert not user_mng.list_capabilities(BOB)


# *** worker tokens ***


def test_worker_token(user_mng: UserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    assert user_mng.create_user(BOB, "Bob")
    token = worker_token_for(user_mng, ALICE)
    assert token != INVALID_WORKER_TOKEN
    assert user_mng.is_correct_worker_token(ALICE, token)
    assert not user_mng.is_correct_worker_token(ALICE, uuid.uuid4().hex)
    assert not user_mng.is_correct_worker_token(BOB, token)


def test_new_worker_token_replaces_old(user_mng: UserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    old = worker_token_for(user_mng, ALICE)
    new = worker_token_for(user_mng, ALICE)
    assert old != new
    assert not user_mng.is_correct_worker_token(ALICE, old)
    assert user_mng.is_correct_worker_token(ALICE, new)


def test_no_worker_token_for_unknown_user(user_mng: UserManager) -> None:
    assert user_mng.create_worker_token(BOB) is None
    assert not user_mng.is_correct_worker_token(BOB, uuid.uuid4().hex)


def test_no_worker_token(user_mng: UserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    assert not user_mng.is_correct_worker_token(ALICE, uuid.uuid4().hex)
    assert not user_mng.is_correct_worker_token(ALICE, "")


def test_invalid_worker_token_constant_is_rejected(
        user_mng: UserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    assert not user_mng.is_correct_worker_token(ALICE, INVALID_WORKER_TOKEN)
    assert not user_mng.is_correct_worker_token(
        UName("nobody@example.com"), INVALID_WORKER_TOKEN)


# *** deleting accounts ***


def test_delete_user(user_mng: UserManager) -> None:
    """Deleting an account removes everything that belongs to it and nothing
    of other accounts."""
    invite(user_mng, ALICE, "alice pw")
    invite(user_mng, BOB, "bob pw")
    for email in (ALICE, BOB):
        user_mng.set_capability(email, CAP_LIST_USERS, has=True)
    alice_session = user_mng.login(ALICE, "alice pw")
    bob_session = user_mng.login(BOB, "bob pw")
    assert alice_session is not None
    assert bob_session is not None
    alice_worker = worker_token_for(user_mng, ALICE)
    bob_worker = worker_token_for(user_mng, BOB)
    alice_reset = user_mng.generate_reset_token(ALICE)
    assert alice_reset is not None

    assert user_mng.delete_user(ALICE)

    assert list(user_mng.list_users()) == [ADMIN_EMAIL, BOB]
    assert user_mng.login(ALICE, "alice pw") is None
    assert user_mng.get_password_hash(ALICE) is None
    assert user_mng.get_email(alice_session) is None
    assert user_mng.count_sessions(ALICE) == 0
    assert not user_mng.list_capabilities(ALICE)
    assert not user_mng.has_capability(ALICE, CAP_LIST_USERS)
    assert not user_mng.is_correct_worker_token(ALICE, alice_worker)
    assert user_mng.get_email_for_reset_token(alice_reset) is None
    # the other account is untouched
    assert user_mng.get_email(bob_session) == BOB
    assert user_mng.login(BOB, "bob pw") is not None
    assert user_mng.list_capabilities(BOB) == {CAP_LIST_USERS}
    assert user_mng.is_correct_worker_token(BOB, bob_worker)
    # deleting again does nothing
    assert not user_mng.delete_user(ALICE)


def test_recreate_deleted_user(user_mng: UserManager) -> None:
    """A new account with the email of a deleted one starts from scratch:
    nothing of the old account carries over, not even the reset cooldown."""
    invite(user_mng, ALICE, "alice pw")
    user_mng.set_capability(ALICE, CAP_CREATE_USER, has=True)
    session = user_mng.login(ALICE, "alice pw")
    assert session is not None
    worker_token = worker_token_for(user_mng, ALICE)
    assert user_mng.generate_reset_token(ALICE) is not None
    assert user_mng.delete_user(ALICE)

    assert user_mng.create_user(ALICE, "New Alice")
    assert user_mng.get_user_info(ALICE) == {
        "email": ALICE,
        "display_name": "New Alice",
        "capabilities": set(),
    }
    assert user_mng.login(ALICE, "alice pw") is None
    assert user_mng.get_email(session) is None
    assert not user_mng.is_correct_worker_token(ALICE, worker_token)
    assert user_mng.generate_reset_token(ALICE) is not None


def test_admin_cannot_be_deleted(user_mng: UserManager) -> None:
    token = user_mng.do_login(ADMIN_EMAIL)
    assert token is not None
    assert not user_mng.delete_user(ADMIN_EMAIL)
    assert user_mng.get_email(token) == ADMIN_EMAIL
    assert user_mng.login(ADMIN_EMAIL, ADMIN_PW) is not None


def test_delete_unknown_user(user_mng: UserManager) -> None:
    assert not user_mng.delete_user(BOB)
    assert list(user_mng.list_users()) == [ADMIN_EMAIL]


# *** stored tokens ***


def stored_sessions(user_mng: UserManager, email: UName) -> list[str]:
    """
    The values the store keeps for the sessions of an account.

    Args:
        user_mng (UserManager): The user manager.
        email (UName): The account.

    Returns:
        list[str]: The stored values.
    """
    account_key = user_mng.get_account_key(email)
    assert account_key is not None
    if isinstance(user_mng, RedisUserManager):
        # pylint: disable=protected-access
        return sorted(user_mng._redis.smembers(f"sess:{account_key}"))
    assert isinstance(user_mng, DBUserManager)
    # pylint: disable=protected-access
    with user_mng._engine.connect() as conn:
        return sorted(conn.execute(
            sa.select(SESSIONS.c.token_hash)
            .where(SESSIONS.c.account_key == account_key)).scalars())


def stored_reset_tokens(user_mng: UserManager) -> list[str]:
    """
    The values the store keeps for the outstanding reset tokens.

    Args:
        user_mng (UserManager): The user manager.

    Returns:
        list[str]: The stored values.
    """
    if isinstance(user_mng, RedisUserManager):
        # pylint: disable=protected-access
        return sorted(
            key.removeprefix("reset:")
            for key in user_mng._redis.keys(match="reset:*", block=False))
    assert isinstance(user_mng, DBUserManager)
    # pylint: disable=protected-access
    with user_mng._engine.connect() as conn:
        return sorted(conn.execute(
            sa.select(RESET_TOKENS.c.token_hash)).scalars())


def sha256(text: str) -> str:
    """
    The SHA-256 of a text.

    Args:
        text (str): The text.

    Returns:
        str: The hex digest.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("email", [ALICE, ADMIN_EMAIL])
def test_session_tokens_are_stored_hashed(
        user_mng: UserManager, email: UName) -> None:
    """The store only has the hash of a session token: reading the store
    is not enough to log in."""
    if email != ADMIN_EMAIL:
        assert user_mng.create_user(email, "Alice")
    token = user_mng.do_login(email)
    assert token is not None
    stored = stored_sessions(user_mng, email)
    assert stored == [sha256(token)]
    assert token not in stored
    assert user_mng.get_email(token) == email
    for value in stored:
        assert user_mng.get_email(value) is None
    assert user_mng.count_sessions(email) == 1
    user_mng.logout(stored[0])
    assert user_mng.get_email(token) == email
    user_mng.logout(token)
    assert user_mng.get_email(token) is None
    assert not stored_sessions(user_mng, email)


def test_reset_tokens_are_stored_hashed(user_mng: UserManager) -> None:
    """The store only has the hash of a reset token: reading the store is
    not enough to set a password."""
    assert user_mng.create_user(ALICE, "Alice")
    reset_token = user_mng.generate_reset_token(ALICE)
    assert reset_token is not None
    stored = stored_reset_tokens(user_mng)
    assert stored == [sha256(reset_token)]
    assert reset_token not in stored
    assert user_mng.get_email_for_reset_token(stored[0]) is None
    assert user_mng.set_password("pw", stored[0]) is None
    assert user_mng.set_password("pw", reset_token) == ALICE
    assert not stored_reset_tokens(user_mng)


def test_logout_everywhere(user_mng: UserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    assert user_mng.create_user(BOB, "Bob")
    tokens = [user_mng.do_login(ALICE) for _ in range(3)]
    bob = user_mng.do_login(BOB)
    assert user_mng.count_sessions(ALICE) == 3
    user_mng.logout_everywhere(ALICE)
    assert user_mng.count_sessions(ALICE) == 0
    for token in tokens:
        assert token is not None
        assert user_mng.get_email(token) is None
    assert bob is not None
    assert user_mng.get_email(bob) == BOB
    assert user_mng.count_sessions(NOBODY) == 0
    user_mng.logout_everywhere(NOBODY)


# *** changing the email ***


CAROL = UName("carol@example.com")


def test_change_email(user_mng: UserManager) -> None:
    """The account keeps everything but its email; it is logged out, and
    only the new email logs in."""
    invite(user_mng, ALICE, "alice pw")
    user_mng.set_capability(ALICE, CAP_LIST_USERS, has=True)
    session = user_mng.login(ALICE, "alice pw")
    assert session is not None
    worker_token = worker_token_for(user_mng, ALICE)
    ids = user_mng.get_ids(ALICE)

    assert user_mng.change_email(ALICE, CAROL)

    assert user_mng.get_ids(CAROL) == ids
    assert user_mng.get_ids(ALICE) is None
    assert list(user_mng.list_users()) == [ADMIN_EMAIL, CAROL]
    assert user_mng.get_user_info(CAROL) == {
        "email": CAROL,
        "display_name": f"display {ALICE.get()}",
        "capabilities": {CAP_LIST_USERS},
    }
    # logged out everywhere
    assert user_mng.get_email(session) is None
    assert user_mng.count_sessions(CAROL) == 0
    # the password stays; only the new email logs in
    assert user_mng.login(ALICE, "alice pw") is None
    new_session = user_mng.login(CAROL, "alice pw")
    assert new_session is not None
    assert user_mng.get_email(new_session) == CAROL
    # the worker token stays and goes with the new email
    assert user_mng.is_correct_worker_token(CAROL, worker_token)
    assert not user_mng.is_correct_worker_token(ALICE, worker_token)
    # the old email is free again
    assert user_mng.create_user(ALICE, "New Alice")
    assert user_mng.login(ALICE, "alice pw") is None


def test_change_email_drops_reset_tokens(user_mng: UserManager) -> None:
    """A reset link sent to the old address does not work after the change,
    and the new address can get one right away."""
    assert user_mng.create_user(ALICE, "Alice")
    reset_token = user_mng.generate_reset_token(ALICE)
    assert reset_token is not None
    assert user_mng.change_email(ALICE, CAROL)
    assert user_mng.get_email_for_reset_token(reset_token) is None
    assert user_mng.set_password("pw", reset_token) is None
    assert user_mng.login(CAROL, "pw") is None
    new_token = user_mng.generate_reset_token(CAROL)
    assert new_token is not None
    assert user_mng.set_password("pw", new_token) == CAROL
    assert user_mng.login(CAROL, "pw") is not None


def test_change_email_refused(user_mng: UserManager) -> None:
    invite(user_mng, ALICE, "alice pw")
    assert user_mng.create_user(BOB, "Bob")
    ids = user_mng.get_ids(ALICE)
    session = user_mng.login(ALICE, "alice pw")
    # the new email is taken, by an account or by the admin
    assert not user_mng.change_email(ALICE, BOB)
    assert not user_mng.change_email(ALICE, ADMIN_EMAIL)
    # the admin's email cannot change; unknown accounts have no email
    assert not user_mng.change_email(ADMIN_EMAIL, CAROL)
    assert not user_mng.change_email(NOBODY, CAROL)
    # no change at all
    assert not user_mng.change_email(ALICE, ALICE)
    # nothing happened
    assert user_mng.get_ids(ALICE) == ids
    assert user_mng.get_user_info(BOB)["display_name"] == "Bob"
    assert session is not None
    assert user_mng.get_email(session) == ALICE
    assert set(user_mng.list_users()) == {ADMIN_EMAIL, ALICE, BOB}


def test_change_email_back_and_forth(user_mng: UserManager) -> None:
    invite(user_mng, ALICE, "alice pw")
    ids = user_mng.get_ids(ALICE)
    assert user_mng.change_email(ALICE, CAROL)
    assert user_mng.change_email(CAROL, ALICE)
    assert user_mng.get_ids(ALICE) == ids
    assert user_mng.get_ids(CAROL) is None
    assert user_mng.login(ALICE, "alice pw") is not None
    assert user_mng.login(CAROL, "alice pw") is None


def test_reused_email_gets_new_ids(user_mng: UserManager) -> None:
    """A new account with the former email of another account cannot have
    the ids derived from that email: they belong to the other account (with
    its chats and workers)."""
    assert user_mng.create_user(ALICE, "Alice")
    alice_ids = user_mng.get_ids(ALICE)
    assert user_mng.change_email(ALICE, CAROL)
    assert user_mng.create_user(ALICE, "New Alice")
    new_ids = user_mng.get_ids(ALICE)
    assert new_ids is not None
    assert alice_ids is not None
    assert new_ids["user_id"] != alice_ids["user_id"]
    assert new_ids["account_key"] != alice_ids["account_key"]
    assert user_mng.get_ids(CAROL) == alice_ids
    # the two accounts do not mix
    user_mng.set_capability(ALICE, CAP_CREATE_USER, has=True)
    assert not user_mng.has_capability(CAROL, CAP_CREATE_USER)
    alice = user_mng.do_login(ALICE)
    carol = user_mng.do_login(CAROL)
    assert alice is not None
    assert carol is not None
    assert user_mng.get_email(alice) == ALICE
    assert user_mng.get_email(carol) == CAROL
    token = worker_token_for(user_mng, ALICE)
    assert not user_mng.is_correct_worker_token(CAROL, token)
    # deleting one leaves the other
    assert user_mng.delete_user(CAROL)
    assert user_mng.get_ids(ALICE) == new_ids
    assert user_mng.get_email(alice) == ALICE


def test_concurrent_change_email_redis(
        monkeypatch: pytest.MonkeyPatch, admin_pw_hash: str) -> None:
    """Two accounts changing to the same email at the same time: one change
    is stopped after its first redis call, the other completes, and then the
    first must fail."""
    redis = PausingRedis(memory_redis())
    monkeypatch.setattr(user_redis_module, "Redis", lambda *_a, **_kw: redis)
    user_mng = RedisUserManager(
        admin_email=ADMIN_EMAIL, admin_pw=admin_pw_hash, cfg=UNUSED_REDIS)
    assert user_mng.create_user(ALICE, "Alice")
    assert user_mng.create_user(BOB, "Bob")
    bob_ids = user_mng.get_ids(BOB)
    results: dict[str, bool] = {}

    def change_first() -> None:
        redis.pause_current_thread()
        results["first"] = user_mng.change_email(ALICE, CAROL)

    first = threading.Thread(target=change_first, daemon=True)
    first.start()
    assert redis.wait_for_pause()
    results["second"] = user_mng.change_email(BOB, CAROL)
    redis.resume()
    first.join(SOME_TIME)
    assert not first.is_alive()
    assert results == {"first": False, "second": True}
    assert user_mng.get_ids(CAROL) == bob_ids
    assert user_mng.get_user_info(ALICE)["display_name"] == "Alice"
    assert set(user_mng.list_users()) == {ADMIN_EMAIL, ALICE, CAROL}


@pytest.mark.parametrize("first_commits", [True, False])
def test_concurrent_change_email_postgres(
        postgres_user_mng: DBUserManager,
        postgres_url: str,
        pg_schema: str,
        first_commits: bool) -> None:
    """A change to an email that is not committed yet makes a second change
    to the same email wait: it fails if the first commits and succeeds if
    the first rolls back."""
    user_mng = postgres_user_mng
    assert user_mng.create_user(ALICE, "Alice")
    assert user_mng.create_user(BOB, "Bob")
    bob_ids = user_mng.get_ids(BOB)
    engine = create_db_engine(postgres_url, schema=pg_schema)
    results: dict[str, bool] = {}

    def change_second() -> None:
        results["second"] = user_mng.change_email(BOB, CAROL)

    try:
        with engine.connect() as conn:
            # NOTE: what the first change does before its transaction ends
            conn.execute(
                sa.update(USERS)
                .where(USERS.c.email == ALICE.get())
                .values(email=CAROL.get()))
            second = threading.Thread(target=change_second, daemon=True)
            second.start()
            wait_for_lock_waiter(engine)
            assert "second" not in results
            if first_commits:
                conn.commit()
            else:
                conn.rollback()
        second.join(SOME_TIME)
        assert not second.is_alive()
    finally:
        engine.dispose()
    assert results == {"second": not first_commits}
    if first_commits:
        assert user_mng.get_ids(BOB) == bob_ids
        assert set(user_mng.list_users()) == {ADMIN_EMAIL, BOB, CAROL}
    else:
        assert user_mng.get_ids(CAROL) == bob_ids
        assert set(user_mng.list_users()) == {ADMIN_EMAIL, ALICE, CAROL}


def test_chats_follow_the_account(
        user_mng: UserManager, session_store: SessionStore) -> None:
    """Chats belong to the account's user id, which the email change does
    not touch."""
    assert user_mng.create_user(ALICE, "Alice")
    user_id = user_mng.get_user_id(ALICE)
    assert user_id is not None
    chat = session_store.create_new_session(
        user_id, copy_from=None).get_session_id()
    assert user_mng.change_email(ALICE, CAROL)
    new_user_id = user_mng.get_user_id(CAROL)
    assert new_user_id == user_id
    assert [
        session.get_session_id()
        for session in session_store.get_sessions(new_user_id)
    ] == [chat]
    assert session_store.get_user(chat) == new_user_id


# *** stores from before the stored ids ***


def legacy_redis_account(
        redis: Redis, email: UName, hashpw: str) -> tuple[str, str]:
    """
    Writes an account the way the redis store kept it before the ids were
    stored: keyed by the hash of the email, without a user id.

    Args:
        redis (Redis): The redis of the user store.
        email (UName): The email.
        hashpw (str): The password hash.

    Returns:
        tuple[str, str]: A session token and the worker token of the
            account.
    """
    userhash = get_short_hash(email.get())
    redis.hset(f"info:{userhash}", {
        "email": email.get(),
        "display_name": f"display {email.get()}",
        "hashpw": hashpw,
    })
    redis.sadd(f"perm:{userhash}", CAP_LIST_USERS)
    session = f"{userhash}{uuid.uuid4().hex}"
    redis.sadd(f"sess:{userhash}", session)
    worker_token = uuid.uuid4().hex
    redis.set_value(
        f"worker:{UserId.create(email).to_parseable()}", worker_token)
    return session, worker_token


def test_migrate_redis(
        monkeypatch: pytest.MonkeyPatch,
        admin_pw_hash: str,
        session_store: SessionStore) -> None:
    """Accounts from before the stored ids get, once on startup, the ids
    derived from their email: the ids their chats, worker token and workers
    already have. Then they work like any other account. Sessions and reset
    tokens from before the hashed tokens are dropped."""
    redis = memory_redis()
    monkeypatch.setattr(user_redis_module, "Redis", lambda *_a, **_kw: redis)
    hashpw = hash_password("alice pw")
    session, worker_token = legacy_redis_account(redis, ALICE, hashpw)
    legacy_redis_account(redis, BOB, hash_password("bob pw"))
    plain_reset = uuid.uuid4().hex
    redis.set_value(f"reset:{plain_reset}", ALICE.get())
    redis.set_value(f"cooldown:{get_short_hash(ALICE.get())}", plain_reset)
    chat = session_store.create_new_session(
        UserId.create(ALICE), copy_from=None).get_session_id()

    user_mng = RedisUserManager(
        admin_email=ADMIN_EMAIL, admin_pw=admin_pw_hash, cfg=UNUSED_REDIS)

    assert redis.get_value("meta:version") == "3"
    assert user_mng.get_ids(ALICE) == {
        "user_id": UserId.create(ALICE),
        "account_key": get_short_hash(ALICE.get()),
    }
    assert list(user_mng.list_users()) == [ADMIN_EMAIL, ALICE, BOB]
    # the plain tokens are gone and do not work
    assert user_mng.get_email(session) is None
    assert user_mng.get_email_for_reset_token(plain_reset) is None
    assert not redis.keys(match="sess:*", block=False)
    assert not redis.keys(match="reset:*", block=False)
    # no cooldown left from the dropped reset token
    assert user_mng.generate_reset_token(ALICE) is not None
    assert user_mng.login(ALICE, "alice pw") is not None
    assert user_mng.list_capabilities(ALICE) == {CAP_LIST_USERS}
    assert user_mng.is_correct_worker_token(ALICE, worker_token)
    user_id = user_mng.get_user_id(ALICE)
    assert user_id is not None
    assert [
        sess.get_session_id() for sess in session_store.get_sessions(user_id)
    ] == [chat]
    # and its email can change now
    assert user_mng.change_email(ALICE, CAROL)
    assert user_mng.is_correct_worker_token(CAROL, worker_token)
    assert user_mng.get_user_id(CAROL) == UserId.create(ALICE)
    # starting again does not migrate again
    again = RedisUserManager(
        admin_email=ADMIN_EMAIL, admin_pw=admin_pw_hash, cfg=UNUSED_REDIS)
    assert list(again.list_users()) == [ADMIN_EMAIL, BOB, CAROL]
    assert again.get_ids(CAROL) == user_mng.get_ids(CAROL)


LEGACY_METADATA = sa.MetaData()
"""The Postgres tables before the ids were stored."""
sa.Table(
    "users",
    LEGACY_METADATA,
    sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
    sa.Column("email", sa.Text, nullable=False),
    sa.Column("display_name", sa.Text, nullable=False),
    sa.Column("hashpw", sa.Text, nullable=True),
    sa.Column("reset_cooldown", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "created",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now()),  # pylint: disable=not-callable
    sa.UniqueConstraint("email", name="users_email_key"),
)
sa.Table(
    "user_capabilities",
    LEGACY_METADATA,
    sa.Column(
        "user_id",
        sa.BigInteger,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True),
    sa.Column("capability", sa.String(40), primary_key=True),
)
sa.Table(
    "user_reset_tokens",
    LEGACY_METADATA,
    sa.Column("token", sa.Text, primary_key=True),
    sa.Column(
        "user_id",
        sa.BigInteger,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False),
    sa.Column("expires", sa.DateTime(timezone=True), nullable=False),
    sa.Index("user_reset_tokens_user_id_idx", "user_id"),
    sa.Index("user_reset_tokens_expires_idx", "expires"),
)
sa.Table(
    "user_sessions",
    LEGACY_METADATA,
    sa.Column("token", sa.Text, primary_key=True),
    sa.Column("email", sa.Text, nullable=False),
    sa.Column(
        "created",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now()),  # pylint: disable=not-callable
    sa.Index("user_sessions_email_idx", "email"),
)
sa.Table(
    "user_worker_tokens",
    LEGACY_METADATA,
    sa.Column("email", sa.Text, primary_key=True),
    sa.Column("token", sa.Text, nullable=False),
    sa.Column(
        "created",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now()),  # pylint: disable=not-callable
)


def test_migrate_postgres(
        postgres_url: str,
        pg_schema: str,
        admin_pw_hash: str,
        session_store: SessionStore) -> None:
    """Tables from before the stored ids are brought up to date once on
    startup; the accounts keep their chats and worker tokens, and so does
    the admin. Sessions and reset tokens from before the hashed tokens are
    dropped."""
    engine = create_db_engine(postgres_url, schema=pg_schema)
    tables = LEGACY_METADATA.tables
    sessions = {
        ALICE: uuid.uuid4().hex,
        ADMIN_EMAIL: uuid.uuid4().hex,
    }
    worker_tokens = {
        ALICE: uuid.uuid4().hex,
        ADMIN_EMAIL: uuid.uuid4().hex,
    }
    plain_reset = uuid.uuid4().hex
    row_ids: dict[UName, int] = {}
    try:
        with engine.begin() as conn:
            conn.execute(sa.schema.CreateSchema(pg_schema))
            LEGACY_METADATA.create_all(conn)
            for email, name, hashpw in [
                    (ALICE, "Alice", hash_password("alice pw")),
                    (BOB, "Bob", None),
                    ]:
                row_ids[email] = conn.execute(
                    sa.insert(tables["users"])
                    .values(
                        email=email.get(), display_name=name, hashpw=hashpw)
                    .returning(tables["users"].c.id)).scalar_one()
                conn.execute(sa.insert(tables["user_capabilities"]).values(
                    user_id=row_ids[email], capability=CAP_LIST_USERS))
            alice_row = row_ids[ALICE]
            for email, token in sessions.items():
                conn.execute(sa.insert(tables["user_sessions"]).values(
                    token=token, email=email.get()))
            for email, token in worker_tokens.items():
                conn.execute(sa.insert(tables["user_worker_tokens"]).values(
                    email=email.get(), token=token))
            conn.execute(sa.insert(tables["user_reset_tokens"]).values(
                token=plain_reset,
                user_id=alice_row,
                expires=sa.text("now() + interval '1 hour'")))
    finally:
        engine.dispose()
    chat = session_store.create_new_session(
        UserId.create(ALICE), copy_from=None).get_session_id()

    user_mng = DBUserManager(
        admin_email=ADMIN_EMAIL,
        admin_pw=admin_pw_hash,
        engine=create_db_engine(postgres_url, schema=pg_schema),
        schema=pg_schema)
    try:
        assert user_mng.get_ids(ALICE) == {
            "user_id": UserId.create(ALICE),
            "account_key": get_short_hash(ALICE.get()),
        }
        assert list(user_mng.list_users()) == [ADMIN_EMAIL, ALICE, BOB]
        # the plain tokens are gone and do not work
        for email, token in sessions.items():
            assert user_mng.get_email(token) is None
            assert user_mng.count_sessions(email) == 0
        assert user_mng.get_email_for_reset_token(plain_reset) is None
        assert not stored_reset_tokens(user_mng)
        assert user_mng.login(ALICE, "alice pw") is not None
        assert user_mng.list_capabilities(BOB) == {CAP_LIST_USERS}
        for email, token in worker_tokens.items():
            assert user_mng.is_correct_worker_token(email, token)
        user_id = user_mng.get_user_id(ALICE)
        assert user_id is not None
        assert [
            sess.get_session_id()
            for sess in session_store.get_sessions(user_id)
        ] == [chat]
        assert user_mng.change_email(ALICE, CAROL)
        assert user_mng.is_correct_worker_token(
            CAROL, worker_tokens[ALICE])
        assert user_mng.create_user(UName("dave@example.com"), "Dave")
    finally:
        user_mng.close()
    # starting again does not migrate again
    again = DBUserManager(
        admin_email=ADMIN_EMAIL,
        admin_pw=admin_pw_hash,
        engine=create_db_engine(postgres_url, schema=pg_schema),
        schema=pg_schema)
    try:
        assert set(again.list_users()) == {
            ADMIN_EMAIL, BOB, CAROL, UName("dave@example.com")}
        assert again.get_user_id(CAROL) == UserId.create(ALICE)
    finally:
        again.close()


# *** Postgres ***


def wait_for_lock_waiter(engine: sa.Engine) -> None:
    """
    Waits until a connection of the database waits for a lock.

    Args:
        engine (sa.Engine): Any engine of the database.
    """
    deadline = time.monotonic() + SOME_TIME
    with engine.connect() as conn:
        while time.monotonic() < deadline:
            waiting = conn.execute(sa.text(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE wait_event_type = 'Lock' "
                "AND datname = current_database()")).scalar_one()
            if waiting:
                return
            time.sleep(0.01)
    raise AssertionError("no connection is waiting for a lock")


@pytest.mark.parametrize("first_commits", [True, False])
def test_concurrent_create_user_postgres(
        postgres_user_mng: DBUserManager,
        postgres_url: str,
        pg_schema: str,
        first_commits: bool) -> None:
    """A registration that is not committed yet makes a second registration
    for the same email wait: it fails if the first one commits and succeeds
    if the first one rolls back."""
    user_mng = postgres_user_mng
    engine = create_db_engine(postgres_url, schema=pg_schema)
    results: dict[str, bool] = {}

    def create_second() -> None:
        results["second"] = user_mng.create_user(ALICE, "Second")

    try:
        with engine.connect() as conn:
            conn.execute(sa.insert(USERS).values(
                email=ALICE.get(),
                display_name="First",
                user_id=derive_user_id(ALICE).to_parseable(),
                account_key=derive_account_key(ALICE)))
            second = threading.Thread(target=create_second, daemon=True)
            second.start()
            wait_for_lock_waiter(engine)
            assert "second" not in results
            if first_commits:
                conn.commit()
            else:
                conn.rollback()
        second.join(SOME_TIME)
        assert not second.is_alive()
    finally:
        engine.dispose()
    assert results["second"] is not first_commits
    winner = "First" if first_commits else "Second"
    assert user_mng.get_user_info(ALICE)["display_name"] == winner
    assert list(user_mng.list_users()) == [ADMIN_EMAIL, ALICE]


def test_concurrent_reset_token_use_postgres(
        postgres_user_mng: DBUserManager,
        postgres_url: str,
        pg_schema: str) -> None:
    """Of two uses of the same reset token at the same time only one sets
    the password: the second waits for the first and then finds the token
    gone."""
    user_mng = postgres_user_mng
    assert user_mng.create_user(ALICE, "Alice")
    reset_token = user_mng.generate_reset_token(ALICE)
    assert reset_token is not None
    engine = create_db_engine(postgres_url, schema=pg_schema)
    results: dict[str, bool] = {}

    def use_second() -> None:
        results["second"] = user_mng.set_password_hash(
            ALICE, hash_password("second"), reset_token)

    try:
        with engine.connect() as conn:
            # NOTE: holds the token row the way the first use does until its
            # transaction ends
            conn.execute(
                sa.select(RESET_TOKENS.c.token_hash)
                .where(RESET_TOKENS.c.token_hash == sha256(reset_token))
                .with_for_update())
            second = threading.Thread(target=use_second, daemon=True)
            second.start()
            wait_for_lock_waiter(engine)
            assert "second" not in results
            conn.execute(
                sa.delete(RESET_TOKENS)
                .where(RESET_TOKENS.c.token_hash == sha256(reset_token)))
            conn.commit()
        second.join(SOME_TIME)
        assert not second.is_alive()
    finally:
        engine.dispose()
    assert results == {"second": False}
    assert user_mng.login(ALICE, "second") is None


def test_concurrent_reset_token_requests_postgres(
        postgres_user_mng: DBUserManager,
        postgres_url: str,
        pg_schema: str) -> None:
    """A reset request that waits for another one of the same account sees
    its cooldown afterwards."""
    user_mng = postgres_user_mng
    assert user_mng.create_user(ALICE, "Alice")
    engine = create_db_engine(postgres_url, schema=pg_schema)
    results: dict[str, str | None] = {}

    def request_second() -> None:
        results["second"] = user_mng.generate_reset_token(ALICE)

    try:
        with engine.connect() as conn:
            # NOTE: what the first request does before its transaction ends
            conn.execute(
                sa.update(USERS)
                .where(USERS.c.email == ALICE.get())
                .values(reset_cooldown=sa.text("now() + interval '1 hour'")))
            second = threading.Thread(target=request_second, daemon=True)
            second.start()
            wait_for_lock_waiter(engine)
            conn.commit()
        second.join(SOME_TIME)
        assert not second.is_alive()
    finally:
        engine.dispose()
    assert results == {"second": None}


def test_postgres_schema_is_created_once(
        postgres_user_mng: DBUserManager,
        postgres_url: str,
        pg_schema: str,
        admin_pw_hash: str) -> None:
    """Starting the server again keeps the existing tables and accounts."""
    invite(postgres_user_mng, ALICE, "alice pw")
    again = DBUserManager(
        admin_email=ADMIN_EMAIL,
        admin_pw=admin_pw_hash,
        engine=create_db_engine(postgres_url, schema=pg_schema),
        schema=pg_schema)
    try:
        assert list(again.list_users()) == [ADMIN_EMAIL, ALICE]
        assert again.login(ALICE, "alice pw") is not None
    finally:
        again.close()


# *** loader ***


def test_load_user_manager(
        monkeypatch: pytest.MonkeyPatch,
        admin_pw_hash: str) -> None:
    monkeypatch.setattr(user_redis_module, "Redis", memory_redis)
    user_mng = load_user_manager(
        {"name": "redis", "cfg": UNUSED_REDIS},
        admin_email=ADMIN_EMAIL,
        admin_pw=admin_pw_hash)
    assert isinstance(user_mng, RedisUserManager)
    assert user_mng.get_admin() == ADMIN_EMAIL


def test_load_postgres_user_manager(
        monkeypatch: pytest.MonkeyPatch,
        postgres_url: str,
        pg_schema: str,
        admin_pw_hash: str) -> None:
    """The Postgres user manager reads its connection from the PG*
    settings and creates its tables in the configured schema."""
    url = sa.make_url(postgres_url)
    monkeypatch.setenv("PGHOST", f"{url.host}")
    monkeypatch.setenv("PGPORT", f"{url.port or 5432}")
    monkeypatch.setenv("PGUSER", f"{url.username}")
    monkeypatch.setenv("PGPASSWORD", f"{url.password or ''}")
    monkeypatch.setenv("PGDATABASE", f"{url.database}")
    user_mng = load_user_manager(
        {"name": "postgres", "schema": pg_schema},
        admin_email=ADMIN_EMAIL,
        admin_pw=admin_pw_hash)
    assert isinstance(user_mng, DBUserManager)
    try:
        assert user_mng.get_admin() == ADMIN_EMAIL
        assert user_mng.create_user(ALICE, "Alice")
        assert list(user_mng.list_users()) == [ADMIN_EMAIL, ALICE]
    finally:
        user_mng.close()
    engine = sa.create_engine(postgres_url)
    try:
        assert set(sa.inspect(engine).get_table_names(schema=pg_schema)) == {
            "users",
            "user_capabilities",
            "user_reset_tokens",
            "user_sessions",
            "user_store_meta",
            "user_worker_tokens",
        }
    finally:
        engine.dispose()


def test_select_user_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """`USER_STORE` switches to Postgres without editing the config file."""
    config = config_template()
    monkeypatch.delenv("USER_STORE", raising=False)
    assert select_user_store(config) == config
    monkeypatch.setenv("USER_STORE", "redis")
    assert select_user_store(config) == config
    monkeypatch.setenv("USER_STORE", "postgres")
    selected = select_user_store(config)
    assert selected["user_mng"] == {"name": "postgres"}
    assert selected["task_queue"] == config["task_queue"]
    assert config["user_mng"]["name"] == "redis"
    monkeypatch.setenv("USER_STORE", "ldap")
    with pytest.raises(ValueError, match="not supported"):
        select_user_store(config)


def test_load_unknown_user_manager() -> None:
    module = cast(UserManagerModule, {"name": "ldap", "cfg": UNUSED_REDIS})
    with pytest.raises(ValueError, match="unknown"):
        load_user_manager(module, admin_email=None, admin_pw=None)
