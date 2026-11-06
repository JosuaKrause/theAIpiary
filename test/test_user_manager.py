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
kept by the redis user manager."""
import time
import uuid
from test.util import ADMIN_EMAIL, ADMIN_PW, memory_redis, UNUSED_REDIS
from typing import cast

import pytest
from scattermind.system.base import UserId
from scattermind.system.names import UName
from scattermind.system.util import get_short_hash

from swai.system.user import CAP_CREATE_USER, CAP_LIST_USERS, CAPABILITIES
from swai_server.system.user import redis as user_redis_module
from swai_server.system.user.loader import load_user_manager, UserManagerModule
from swai_server.system.user.manager import (
    as_capability,
    check_password,
    hash_password,
    INVALID_WORKER_TOKEN,
)
from swai_server.system.user.redis import RedisUserManager


ALICE = UName("alice@example.com")
BOB = UName("bob@example.com")


def invite(user_mng: RedisUserManager, email: UName, password: str) -> None:
    """
    Creates an account and sets its password through the reset token that
    the invitation email carries.

    Args:
        user_mng (RedisUserManager): The user manager.
        email (UName): The new account.
        password (str): The password the new user picks.
    """
    assert user_mng.create_user(email, f"display {email.get()}")
    reset_token = user_mng.generate_reset_token(email)
    assert reset_token is not None
    assert user_mng.set_password(password, reset_token) == email


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


def test_create_user(user_mng: RedisUserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    assert user_mng.get_user_info(ALICE) == {
        "email": ALICE,
        "display_name": "Alice",
        "capabilities": set(),
    }


def test_create_user_twice(user_mng: RedisUserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    assert not user_mng.create_user(ALICE, "Mallory")
    assert user_mng.get_user_info(ALICE)["display_name"] == "Alice"


def test_create_user_rejects_admin_and_empty_name(
        user_mng: RedisUserManager) -> None:
    assert not user_mng.create_user(ADMIN_EMAIL, "Mallory")
    assert not user_mng.create_user(ALICE, "")
    assert set(user_mng.list_users()) == {ADMIN_EMAIL}


def test_list_users(user_mng: RedisUserManager) -> None:
    assert list(user_mng.list_users()) == [ADMIN_EMAIL]
    user_mng.create_user(ALICE, "Alice")
    user_mng.create_user(BOB, "Bob")
    users = list(user_mng.list_users())
    assert users[0] == ADMIN_EMAIL
    assert sorted(user.get() for user in users[1:]) == [
        ALICE.get(),
        BOB.get(),
    ]


def test_user_id(user_mng: RedisUserManager) -> None:
    assert user_mng.get_user_id(ALICE) == UserId.create(ALICE)
    assert user_mng.get_user_id(ALICE) == user_mng.get_user_id(ALICE)
    assert user_mng.get_user_id(ALICE) != user_mng.get_user_id(BOB)


# *** invitations and password resets ***


def test_new_user_cannot_log_in_before_setting_password(
        user_mng: RedisUserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    assert user_mng.login(ALICE, "") is None
    assert user_mng.login(ALICE, "guess") is None


def test_invite_then_login(user_mng: RedisUserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    reset_token = user_mng.generate_reset_token(ALICE)
    assert reset_token is not None
    assert user_mng.get_email_for_reset_token(reset_token) == ALICE
    assert user_mng.set_password("alice pw", reset_token) == ALICE
    token = user_mng.login(ALICE, "alice pw")
    assert token is not None
    assert user_mng.get_email(token) == ALICE
    assert user_mng.login(ALICE, "wrong pw") is None


def test_reset_token_is_single_use(user_mng: RedisUserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    reset_token = user_mng.generate_reset_token(ALICE)
    assert reset_token is not None
    assert user_mng.set_password("first", reset_token) == ALICE
    assert user_mng.get_email_for_reset_token(reset_token) is None
    assert user_mng.set_password("second", reset_token) is None


def test_reset_token_cooldown(user_mng: RedisUserManager) -> None:
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
        user_mng: RedisUserManager,
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(user_redis_module, "PW_RESET_COOLDOWN", 0.05)
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
        user_mng: RedisUserManager,
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(user_redis_module, "PW_RESET_EXPIRE", 0.05)
    assert user_mng.create_user(ALICE, "Alice")
    reset_token = user_mng.generate_reset_token(ALICE)
    assert reset_token is not None
    time.sleep(0.1)
    assert user_mng.get_email_for_reset_token(reset_token) is None
    assert user_mng.set_password("pw", reset_token) is None


def test_unknown_reset_token(user_mng: RedisUserManager) -> None:
    assert user_mng.get_email_for_reset_token(uuid.uuid4().hex) is None
    assert user_mng.set_password("pw", uuid.uuid4().hex) is None


def test_no_reset_token_for_admin(user_mng: RedisUserManager) -> None:
    # the admin password comes from the environment, not from redis
    assert user_mng.generate_reset_token(ADMIN_EMAIL) is None


@pytest.mark.xfail(
    strict=True,
    reason=(
        "generate_reset_token issues tokens for emails without an account; "
        "the unauthenticated /user/reset_password_token endpoint then fails "
        "with a KeyError in force_user_info, and set_password with such a "
        "token raises KeyError as well"))
def test_no_reset_token_for_unknown_user(user_mng: RedisUserManager) -> None:
    assert user_mng.generate_reset_token(UName("nobody@example.com")) is None


def test_password_change(user_mng: RedisUserManager) -> None:
    invite(user_mng, ALICE, "old pw")
    reset_token = user_mng.generate_reset_token(ALICE)
    assert reset_token is not None
    assert user_mng.set_password("new pw", reset_token) == ALICE
    assert user_mng.login(ALICE, "old pw") is None
    assert user_mng.login(ALICE, "new pw") is not None


# *** sessions ***


def test_unknown_user_cannot_log_in(user_mng: RedisUserManager) -> None:
    assert user_mng.login(BOB, "pw") is None
    assert not list(user_mng.get_sessions_for_user(BOB))


def test_sessions(user_mng: RedisUserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    first = user_mng.do_login(ALICE)
    second = user_mng.do_login(ALICE)
    assert first is not None
    assert second is not None
    assert first != second
    assert user_mng.get_email(first) == ALICE
    assert user_mng.get_email(second) == ALICE
    assert list(user_mng.get_sessions_for_user(ALICE)) == sorted(
        [first, second])
    user_mng.logout(first)
    assert user_mng.get_email(first) is None
    assert user_mng.get_email(second) == ALICE
    assert list(user_mng.get_sessions_for_user(ALICE)) == [second]


def test_sessions_are_per_user(user_mng: RedisUserManager) -> None:
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


def test_forged_session_token(user_mng: RedisUserManager) -> None:
    """A session token starts with the account's public hash; the random
    remainder is what makes it a secret."""
    assert user_mng.create_user(ALICE, "Alice")
    token = user_mng.do_login(ALICE)
    assert token is not None
    assert token.startswith(get_short_hash(ALICE.get()))
    forged = f"{get_short_hash(ALICE.get())}{uuid.uuid4().hex}"
    assert user_mng.get_email(forged) is None
    assert user_mng.get_email("") is None
    assert user_mng.get_email("not a token") is None


def test_logout_unknown_token(user_mng: RedisUserManager) -> None:
    user_mng.logout("not a token")
    user_mng.logout("")


# *** admin ***


def test_admin_login(user_mng: RedisUserManager) -> None:
    assert user_mng.get_admin() == ADMIN_EMAIL
    assert user_mng.is_admin(ADMIN_EMAIL)
    assert not user_mng.is_admin(ALICE)
    token = user_mng.login(ADMIN_EMAIL, ADMIN_PW)
    assert token is not None
    assert user_mng.get_email(token) == ADMIN_EMAIL
    assert user_mng.login(ADMIN_EMAIL, "wrong") is None


def test_forged_admin_session_token(user_mng: RedisUserManager) -> None:
    forged = f"{get_short_hash(ADMIN_EMAIL.get())}{uuid.uuid4().hex}"
    assert user_mng.get_email(forged) is None


def test_admin_logout(user_mng: RedisUserManager) -> None:
    token = user_mng.do_login(ADMIN_EMAIL)
    assert token is not None
    assert user_mng.get_email(token) == ADMIN_EMAIL
    user_mng.logout(token)
    assert user_mng.get_email(token) is None


def test_admin_has_every_capability(user_mng: RedisUserManager) -> None:
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


def test_no_admin_without_password(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without `ADMIN_PW` the admin account does not exist."""
    monkeypatch.setattr(user_redis_module, "Redis", memory_redis)
    user_mng = RedisUserManager(
        admin_email=ADMIN_EMAIL, admin_pw=None, cfg=UNUSED_REDIS)
    assert user_mng.get_admin() is None
    assert not user_mng.is_admin(ADMIN_EMAIL)
    assert user_mng.login(ADMIN_EMAIL, "") is None
    assert user_mng.login(ADMIN_EMAIL, ADMIN_PW) is None
    forged = f"{get_short_hash(ADMIN_EMAIL.get())}{uuid.uuid4().hex}"
    assert user_mng.get_email(forged) is None
    assert not list(user_mng.list_users())
    assert not user_mng.has_capability(ADMIN_EMAIL, CAP_CREATE_USER)


# *** capabilities ***


def test_capabilities(user_mng: RedisUserManager) -> None:
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


def test_worker_token(user_mng: RedisUserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    assert user_mng.create_user(BOB, "Bob")
    token = user_mng.create_worker_token(ALICE)
    assert token != INVALID_WORKER_TOKEN
    assert user_mng.is_correct_worker_token(ALICE, token)
    assert not user_mng.is_correct_worker_token(ALICE, uuid.uuid4().hex)
    assert not user_mng.is_correct_worker_token(BOB, token)


def test_new_worker_token_replaces_old(user_mng: RedisUserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    old = user_mng.create_worker_token(ALICE)
    new = user_mng.create_worker_token(ALICE)
    assert old != new
    assert not user_mng.is_correct_worker_token(ALICE, old)
    assert user_mng.is_correct_worker_token(ALICE, new)


def test_no_worker_token(user_mng: RedisUserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    assert not user_mng.is_correct_worker_token(ALICE, uuid.uuid4().hex)
    assert not user_mng.is_correct_worker_token(ALICE, "")


def test_invalid_worker_token_constant_is_rejected(
        user_mng: RedisUserManager) -> None:
    assert user_mng.create_user(ALICE, "Alice")
    assert not user_mng.is_correct_worker_token(ALICE, INVALID_WORKER_TOKEN)
    assert not user_mng.is_correct_worker_token(
        UName("nobody@example.com"), INVALID_WORKER_TOKEN)


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


def test_load_unknown_user_manager() -> None:
    module = cast(UserManagerModule, {"name": "ldap", "cfg": UNUSED_REDIS})
    with pytest.raises(ValueError, match="unknown"):
        load_user_manager(module, admin_email=None, admin_pw=None)
