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
"""Tests for the permission checks every server endpoint goes through."""
import uuid
from collections.abc import Callable
from test.util import ADMIN_EMAIL, stored_email_changes

import pytest
from quick_server import PreventDefaultResponse
from scattermind.system.names import UName

from swai.system.user import (
    CAP_CHANGE_CAPABILITIES,
    CAP_CHANGE_EMAIL,
    CAP_CREATE_USER,
    CAP_DELETE_USER,
    CAP_LIST_USERS,
    CAP_LOGOUT_OTHER_USER,
    CAP_REGISTER_OTHER_WORKER,
    CAP_REGISTER_OWN_WORKER,
    CAPABILITIES,
    CapabilityName,
)
from swai_server.system.user.manager import SessionToken, UserManager
from swai_server.system.user.secure import SecureContext


ALICE = UName("alice@example.com")
BOB = UName("bob@example.com")
NOT_A_SESSION = "not a session"


def session_for(
        user_mng: UserManager,
        email: UName,
        *capabilities: CapabilityName) -> SessionToken:
    """
    Creates the account (unless it is the admin), grants it the given
    capabilities, and starts a session for it. The password check that
    precedes a session is covered by the user manager tests.

    Args:
        user_mng (UserManager): The user manager.
        email (UName): The account.
        *capabilities (CapabilityName): The capabilities to grant.

    Returns:
        SessionToken: A session of the account.
    """
    if email != ADMIN_EMAIL:
        assert user_mng.create_user(email, f"display {email.get()}")
    for cap in capabilities:
        user_mng.set_capability(email, cap, has=True)
    token = user_mng.do_login(email)
    assert token is not None
    return token


def assert_refused(code: int, call: Callable[[], object]) -> None:
    with pytest.raises(PreventDefaultResponse) as exc_info:
        call()
    assert exc_info.value.code == code


# *** can_act ***


def test_can_act_without_session(sec_ctx: SecureContext) -> None:
    assert sec_ctx.can_act(NOT_A_SESSION, email=ALICE) == "invalid"
    assert not sec_ctx.is_allowed(NOT_A_SESSION, email=ALICE)
    assert_refused(
        401, lambda: sec_ctx.ensure_can_act(NOT_A_SESSION, email=ALICE))


def test_can_act_on_self(
        sec_ctx: SecureContext, user_mng: UserManager) -> None:
    alice = session_for(user_mng, ALICE)
    assert sec_ctx.can_act(alice, email=ALICE) == "ok"
    sec_ctx.ensure_can_act(alice, email=ALICE)
    # an own capability is required even for oneself when it is asked for
    assert sec_ctx.can_act(
        alice, email=ALICE, own_capability=CAP_REGISTER_OWN_WORKER,
    ) == "denied"
    assert_refused(403, lambda: sec_ctx.ensure_can_act(
        alice, email=ALICE, own_capability=CAP_REGISTER_OWN_WORKER))
    user_mng.set_capability(ALICE, CAP_REGISTER_OWN_WORKER, has=True)
    assert sec_ctx.can_act(
        alice, email=ALICE, own_capability=CAP_REGISTER_OWN_WORKER,
    ) == "ok"


def test_can_act_on_others(
        sec_ctx: SecureContext, user_mng: UserManager) -> None:
    alice = session_for(user_mng, ALICE)
    session_for(user_mng, BOB)
    # acting on someone else always needs an explicit admin capability
    assert sec_ctx.can_act(alice, email=BOB) == "denied"
    assert sec_ctx.can_act(
        alice, email=BOB, admin_capability=CAP_LIST_USERS) == "denied"
    # an own capability does not reach other accounts
    user_mng.set_capability(ALICE, CAP_REGISTER_OWN_WORKER, has=True)
    assert sec_ctx.can_act(
        alice,
        email=BOB,
        own_capability=CAP_REGISTER_OWN_WORKER,
        admin_capability=CAP_REGISTER_OTHER_WORKER) == "denied"
    user_mng.set_capability(ALICE, CAP_LIST_USERS, has=True)
    assert sec_ctx.can_act(
        alice, email=BOB, admin_capability=CAP_LIST_USERS) == "ok"
    assert sec_ctx.can_act(alice, email=BOB) == "denied"


def test_admin_can_act_on_anyone(
        sec_ctx: SecureContext, user_mng: UserManager) -> None:
    admin = session_for(user_mng, ADMIN_EMAIL)
    session_for(user_mng, ALICE)
    assert sec_ctx.can_act(
        admin, email=ALICE, admin_capability=CAP_LOGOUT_OTHER_USER) == "ok"
    assert sec_ctx.can_act(
        admin, email=None, admin_capability=CAP_CREATE_USER) == "ok"
    assert sec_ctx.can_act(
        admin, email=ADMIN_EMAIL, own_capability=CAP_REGISTER_OWN_WORKER,
    ) == "ok"
    # but only where an admin capability is defined at all
    assert sec_ctx.can_act(admin, email=ALICE) == "denied"


# *** account management ***


def test_create_user_needs_capability(
        sec_ctx: SecureContext, user_mng: UserManager) -> None:
    alice = session_for(user_mng, ALICE)
    assert_refused(403, lambda: sec_ctx.create_user(alice, BOB, "Bob"))
    assert_refused(
        401, lambda: sec_ctx.create_user(NOT_A_SESSION, BOB, "Bob"))
    assert ALICE in set(user_mng.list_users())
    assert BOB not in set(user_mng.list_users())
    user_mng.set_capability(ALICE, CAP_CREATE_USER, has=True)
    assert sec_ctx.create_user(alice, BOB, "Bob")
    assert not sec_ctx.create_user(alice, BOB, "Bob")
    assert BOB in set(user_mng.list_users())


def test_list_users_needs_capability(
        sec_ctx: SecureContext, user_mng: UserManager) -> None:
    alice = session_for(user_mng, ALICE)
    session_for(user_mng, BOB)
    assert_refused(403, lambda: sec_ctx.list_users(alice))
    assert_refused(403, lambda: list(sec_ctx.get_active_users(alice)))
    user_mng.set_capability(ALICE, CAP_LIST_USERS, has=True)
    assert set(sec_ctx.list_users(alice)) == {ADMIN_EMAIL, ALICE, BOB}


def test_active_users(
        sec_ctx: SecureContext, user_mng: UserManager) -> None:
    admin = session_for(user_mng, ADMIN_EMAIL)
    bob = session_for(user_mng, BOB)
    session_for(user_mng, ALICE)
    user_mng.logout(bob)
    assert dict(sec_ctx.get_active_users(admin)) == {
        ADMIN_EMAIL: True,
        ALICE: True,
        BOB: False,
    }


def test_user_info_access(
        sec_ctx: SecureContext, user_mng: UserManager) -> None:
    alice = session_for(user_mng, ALICE)
    session_for(user_mng, BOB)
    assert sec_ctx.get_user_info(alice, ALICE)["display_name"] == (
        "display alice@example.com")
    assert_refused(403, lambda: sec_ctx.get_user_info(alice, BOB))
    user_mng.set_capability(ALICE, CAP_LIST_USERS, has=True)
    assert sec_ctx.get_user_info(alice, BOB)["email"] == BOB


def test_secure_email(
        sec_ctx: SecureContext, user_mng: UserManager) -> None:
    alice = session_for(user_mng, ALICE)
    assert sec_ctx.secure_email(alice, ALICE) == ALICE
    assert sec_ctx.secure_email(alice, BOB) is None
    assert sec_ctx.secure_email(NOT_A_SESSION, ALICE) is None
    user_mng.set_capability(ALICE, CAP_LIST_USERS, has=True)
    assert sec_ctx.secure_email(alice, BOB) == BOB


def test_user_id_only_for_self(
        sec_ctx: SecureContext, user_mng: UserManager) -> None:
    alice = session_for(user_mng, ALICE)
    admin = session_for(user_mng, ADMIN_EMAIL)
    assert sec_ctx.get_user_id(alice, ALICE) == user_mng.get_user_id(ALICE)
    assert_refused(403, lambda: sec_ctx.get_user_id(alice, BOB))
    assert_refused(403, lambda: sec_ctx.get_user_id(admin, ALICE))


# *** logout ***


def test_logout_self(
        sec_ctx: SecureContext, user_mng: UserManager) -> None:
    first = session_for(user_mng, ALICE)
    second = user_mng.do_login(ALICE)
    assert second is not None
    sec_ctx.logout(first)
    assert sec_ctx.get_email(first) is None
    assert sec_ctx.get_email(second) == ALICE
    # logging out everywhere is allowed on one's own account
    sec_ctx.logout_user(second, ALICE)
    assert sec_ctx.get_email(second) is None
    assert user_mng.count_sessions(ALICE) == 0


def test_logout_other_needs_capability(
        sec_ctx: SecureContext, user_mng: UserManager) -> None:
    alice = session_for(user_mng, ALICE)
    bob = session_for(user_mng, BOB)
    assert_refused(403, lambda: sec_ctx.logout_user(alice, BOB))
    assert sec_ctx.get_email(bob) == BOB
    user_mng.set_capability(ALICE, CAP_LOGOUT_OTHER_USER, has=True)
    sec_ctx.logout_user(alice, BOB)
    assert sec_ctx.get_email(bob) is None
    assert sec_ctx.get_email(alice) == ALICE


def test_force_logout_user(
        sec_ctx: SecureContext, user_mng: UserManager) -> None:
    """The server ends every session of an account once its password has
    been reset."""
    tokens = [session_for(user_mng, ALICE)]
    for _ in range(2):
        token = user_mng.do_login(ALICE)
        assert token is not None
        tokens.append(token)
    bob = session_for(user_mng, BOB)
    sec_ctx.force_logout_user(ALICE)
    for token in tokens:
        assert sec_ctx.get_email(token) is None
    assert sec_ctx.get_email(bob) == BOB


# *** capabilities ***


def test_change_capabilities(
        sec_ctx: SecureContext, user_mng: UserManager) -> None:
    alice = session_for(user_mng, ALICE)
    session_for(user_mng, BOB)
    assert_refused(403, lambda: sec_ctx.set_capability(
        alice, ALICE, CAP_CREATE_USER, has=True))
    assert_refused(403, lambda: sec_ctx.list_capabilities(alice, ALICE))
    assert_refused(
        403, lambda: sec_ctx.has_capability(alice, ALICE, CAP_CREATE_USER))
    assert not user_mng.has_capability(ALICE, CAP_CREATE_USER)
    assert not sec_ctx.maybe_list_capabilities(alice, ALICE)

    user_mng.set_capability(ALICE, CAP_CHANGE_CAPABILITIES, has=True)
    sec_ctx.set_capability(alice, BOB, CAP_CREATE_USER, has=True)
    assert sec_ctx.has_capability(alice, BOB, CAP_CREATE_USER)
    assert sec_ctx.list_capabilities(alice, BOB) == {CAP_CREATE_USER}
    assert sec_ctx.maybe_list_capabilities(alice, BOB) == {CAP_CREATE_USER}
    sec_ctx.set_capability(alice, BOB, CAP_CREATE_USER, has=False)
    assert not sec_ctx.list_capabilities(alice, BOB)


def test_admin_capabilities_cannot_change(
        sec_ctx: SecureContext, user_mng: UserManager) -> None:
    """The admin cannot be demoted, not even by the admin."""
    admin = session_for(user_mng, ADMIN_EMAIL)
    alice = session_for(user_mng, ALICE, CAP_CHANGE_CAPABILITIES)
    for who in (admin, alice):

        def demote(who: SessionToken = who) -> None:
            sec_ctx.set_capability(
                who, ADMIN_EMAIL, CAP_CHANGE_CAPABILITIES, has=False)

        assert_refused(403, demote)
    assert sec_ctx.list_capabilities(admin, ADMIN_EMAIL) == set(CAPABILITIES)


@pytest.mark.parametrize("mode", ["read", "write"])
def test_chat_access(
        sec_ctx: SecureContext,
        user_mng: UserManager,
        mode: str) -> None:
    if mode == "read":
        can = sec_ctx.can_read_chat
        ensure = sec_ctx.ensure_can_read_chat
    else:
        can = sec_ctx.can_write_chat
        ensure = sec_ctx.ensure_can_write_chat
    alice = session_for(user_mng, ALICE)
    admin = session_for(user_mng, ADMIN_EMAIL)
    own = user_mng.get_user_id(ALICE)
    other = user_mng.get_user_id(BOB)
    assert can(alice, own) == "ok"
    ensure(alice, own)
    assert can(alice, other) == "denied"
    # a chat session without a known owner belongs to nobody
    assert can(alice, None) == "denied"
    assert can(NOT_A_SESSION, own) == "invalid"
    # chats are private, the admin included
    assert can(admin, own) == "denied"
    assert_refused(403, lambda: ensure(alice, other))
    assert_refused(401, lambda: ensure(NOT_A_SESSION, own))


# *** worker tokens ***


def test_create_worker_token(
        sec_ctx: SecureContext, user_mng: UserManager) -> None:
    alice = session_for(user_mng, ALICE)
    session_for(user_mng, BOB)
    assert_refused(403, lambda: sec_ctx.create_worker_token(alice, ALICE))
    user_mng.set_capability(ALICE, CAP_REGISTER_OWN_WORKER, has=True)
    token = sec_ctx.create_worker_token(alice, ALICE)
    sec_ctx.ensure_worker_token(ALICE, token)
    assert_refused(401, lambda: sec_ctx.ensure_worker_token(BOB, token))
    assert_refused(
        401, lambda: sec_ctx.ensure_worker_token(ALICE, uuid.uuid4().hex))
    # registering a worker for someone else is a separate capability
    assert_refused(403, lambda: sec_ctx.create_worker_token(alice, BOB))
    user_mng.set_capability(ALICE, CAP_REGISTER_OTHER_WORKER, has=True)
    bob_token = sec_ctx.create_worker_token(alice, BOB)
    sec_ctx.ensure_worker_token(BOB, bob_token)


# *** password reset on behalf of a user ***


def test_send_reset_token_needs_capability(
        sec_ctx: SecureContext, user_mng: UserManager) -> None:
    alice = session_for(user_mng, ALICE)
    session_for(user_mng, BOB)
    assert_refused(403, lambda: sec_ctx.send_reset_token(alice, BOB))
    assert_refused(401, lambda: sec_ctx.send_reset_token(NOT_A_SESSION, BOB))
    user_mng.set_capability(ALICE, CAP_CREATE_USER, has=True)
    reset_token = sec_ctx.send_reset_token(alice, BOB)
    assert reset_token is not None
    assert user_mng.get_email_for_reset_token(reset_token) == BOB
    # the cooldown applies here as well, the admin gets no token, and there
    # is no token for accounts that do not exist
    assert sec_ctx.send_reset_token(alice, BOB) is None
    assert sec_ctx.send_reset_token(alice, ADMIN_EMAIL) is None
    assert sec_ctx.send_reset_token(
        alice, UName("nobody@example.com")) is None


def test_send_reset_token_for_self(
        sec_ctx: SecureContext, user_mng: UserManager) -> None:
    alice = session_for(user_mng, ALICE)
    reset_token = sec_ctx.send_reset_token(alice, ALICE)
    assert reset_token is not None
    assert user_mng.get_email_for_reset_token(reset_token) == ALICE


# *** deleting accounts ***


def test_delete_user_needs_capability(
        sec_ctx: SecureContext, user_mng: UserManager) -> None:
    alice = session_for(user_mng, ALICE)
    bob = session_for(user_mng, BOB)
    assert_refused(403, lambda: sec_ctx.delete_user(alice, BOB))
    assert_refused(401, lambda: sec_ctx.delete_user(NOT_A_SESSION, BOB))
    # other capabilities to manage accounts are not enough
    for cap in CAPABILITIES:
        if cap != CAP_DELETE_USER:
            user_mng.set_capability(ALICE, cap, has=True)
    assert_refused(403, lambda: sec_ctx.delete_user(alice, BOB))
    assert sec_ctx.get_email(bob) == BOB
    user_mng.set_capability(ALICE, CAP_DELETE_USER, has=True)
    assert sec_ctx.delete_user(alice, BOB)
    assert sec_ctx.get_email(bob) is None
    assert BOB not in set(user_mng.list_users())
    assert not sec_ctx.delete_user(alice, BOB)


def test_delete_user_spares_self_and_admin(
        sec_ctx: SecureContext, user_mng: UserManager) -> None:
    admin = session_for(user_mng, ADMIN_EMAIL)
    alice = session_for(user_mng, ALICE, CAP_DELETE_USER)
    # neither oneself (even with the capability) nor the admin
    assert_refused(403, lambda: sec_ctx.delete_user(alice, ALICE))
    assert_refused(403, lambda: sec_ctx.delete_user(alice, ADMIN_EMAIL))
    assert_refused(403, lambda: sec_ctx.delete_user(admin, ADMIN_EMAIL))
    assert sec_ctx.get_email(alice) == ALICE
    assert sec_ctx.get_email(admin) == ADMIN_EMAIL
    assert set(user_mng.list_users()) == {ADMIN_EMAIL, ALICE}
    # the admin can delete anyone else
    assert sec_ctx.delete_user(admin, ALICE)
    assert set(user_mng.list_users()) == {ADMIN_EMAIL}


# *** changing the email ***


CAROL = UName("carol@example.com")


def test_email_change_needs_capability(
        sec_ctx: SecureContext, user_mng: UserManager) -> None:
    alice = session_for(user_mng, ALICE)
    bob = session_for(user_mng, BOB)
    for call in (
            lambda: sec_ctx.request_email_change(alice, BOB, CAROL),
            lambda: sec_ctx.ensure_can_change_email(alice, BOB),
            ):
        assert_refused(403, call)
    assert_refused(
        401, lambda: sec_ctx.request_email_change(NOT_A_SESSION, BOB, CAROL))
    # other capabilities to manage accounts are not enough
    for cap in CAPABILITIES:
        if cap != CAP_CHANGE_EMAIL:
            user_mng.set_capability(ALICE, cap, has=True)
    assert_refused(
        403, lambda: sec_ctx.request_email_change(alice, BOB, CAROL))
    assert not stored_email_changes(user_mng)
    user_mng.set_capability(ALICE, CAP_CHANGE_EMAIL, has=True)
    sec_ctx.ensure_can_change_email(alice, BOB)
    token = sec_ctx.request_email_change(alice, BOB, CAROL)
    assert token is not None
    # nothing changes before the confirmation
    assert sec_ctx.get_email(bob) == BOB
    assert set(user_mng.list_users()) == {ADMIN_EMAIL, ALICE, BOB}
    # taken by the acting user
    assert sec_ctx.request_email_change(alice, BOB, ALICE) is None
    # whoever has the token confirms it, without a session
    assert sec_ctx.confirm_email_change(token) == {
        "email": BOB,
        "new_email": CAROL,
        "changed": True,
    }
    assert sec_ctx.get_email(bob) is None
    assert set(user_mng.list_users()) == {ADMIN_EMAIL, ALICE, CAROL}
    assert sec_ctx.confirm_email_change(token) is None


def test_email_change_spares_self_and_admin(
        sec_ctx: SecureContext, user_mng: UserManager) -> None:
    admin = session_for(user_mng, ADMIN_EMAIL)
    alice = session_for(user_mng, ALICE, CAP_CHANGE_EMAIL)
    for who, email in [
            (alice, ALICE),
            (alice, ADMIN_EMAIL),
            (admin, ADMIN_EMAIL),
            ]:
        with pytest.raises(PreventDefaultResponse) as exc_info:
            sec_ctx.request_email_change(who, email, CAROL)
        assert exc_info.value.code == 403
        with pytest.raises(PreventDefaultResponse) as exc_info:
            sec_ctx.ensure_can_change_email(who, email)
        assert exc_info.value.code == 403
    # nobody can take the admin's email
    assert sec_ctx.request_email_change(admin, ALICE, ADMIN_EMAIL) is None
    assert not stored_email_changes(user_mng)
    assert sec_ctx.get_email(alice) == ALICE
    assert set(user_mng.list_users()) == {ADMIN_EMAIL, ALICE}
    assert sec_ctx.request_email_change(admin, ALICE, CAROL) is not None


# *** invitations through the context ***


def test_invite_through_context(
        sec_ctx: SecureContext, user_mng: UserManager) -> None:
    admin = session_for(user_mng, ADMIN_EMAIL)
    assert sec_ctx.create_user(admin, ALICE, "Alice")
    reset_token = sec_ctx.generate_reset_token(ALICE)
    assert reset_token is not None
    assert sec_ctx.set_password("alice pw", reset_token) == ALICE
    alice = sec_ctx.login(ALICE, "alice pw")
    assert alice is not None
    assert sec_ctx.get_email(alice) == ALICE
    assert sec_ctx.force_user_info(ALICE)["display_name"] == "Alice"
