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
from collections.abc import Iterable
from typing import Literal

from quick_server import PreventDefaultResponse
from scattermind.system.base import UserId
from scattermind.system.names import UName

from swai.system.user import (
    CAP_CHANGE_CAPABILITIES,
    CAP_CREATE_USER,
    CAP_DELETE_USER,
    CAP_LIST_USERS,
    CAP_LOGOUT_OTHER_USER,
    CAP_REGISTER_OTHER_WORKER,
    CAP_REGISTER_OWN_WORKER,
    CapabilityName,
    WorkerToken,
)
from swai_server.system.user.manager import (
    RawPassword,
    ResetToken,
    SessionToken,
    UserInfo,
    UserManager,
)


CanAct = Literal["ok", "denied", "invalid"]


class SecureContext:
    def __init__(self, user_mng: UserManager) -> None:
        self._user_mng = user_mng

    def can_act(
            self,
            who: SessionToken,
            *,
            email: UName | None,
            own_capability: CapabilityName | None = None,
            admin_capability: CapabilityName | None = None) -> CanAct:
        user_mng = self._user_mng
        who_email = user_mng.get_email(who)
        if who_email is None:
            return "invalid"
        if who_email == email:
            if own_capability is None:
                return "ok"  # same user and no special capability required
            if user_mng.has_capability(who_email, own_capability):
                return "ok"  # same user with capability
            return "denied"
        if admin_capability is None:
            # admin user without special privilege
            return "denied"
        if user_mng.has_capability(who_email, admin_capability):
            # admin user with capability
            return "ok"
        return "denied"

    @staticmethod
    def _handle_can_act(can_act: CanAct) -> None:
        if can_act == "denied":
            raise PreventDefaultResponse(403, "operation not allowed")
        if can_act == "invalid":
            raise PreventDefaultResponse(401, "must be logged in")
        if can_act != "ok":
            raise RuntimeError(f"invalid response {can_act=}")

    def is_allowed(
            self,
            who: SessionToken,
            *,
            email: UName | None,
            own_capability: CapabilityName | None = None,
            admin_capability: CapabilityName | None = None) -> bool:
        return self.can_act(
            who,
            email=email,
            own_capability=own_capability,
            admin_capability=admin_capability) == "ok"

    def ensure_can_act(
            self,
            who: SessionToken,
            *,
            email: UName | None,
            own_capability: CapabilityName | None = None,
            admin_capability: CapabilityName | None = None) -> None:
        self._handle_can_act(self.can_act(
            who,
            email=email,
            own_capability=own_capability,
            admin_capability=admin_capability))

    def login(
            self, email: UName, password: RawPassword) -> SessionToken | None:
        return self._user_mng.login(email, password)

    def logout(self, token: SessionToken) -> None:
        self._user_mng.logout(token)

    def logout_user(self, who: SessionToken, email: UName) -> None:
        self.ensure_can_act(
            who, email=email, admin_capability=CAP_LOGOUT_OTHER_USER)
        self.force_logout_user(email)

    def get_active_users(
            self, who: SessionToken) -> Iterable[tuple[UName, bool]]:
        self.ensure_can_act(who, email=None, admin_capability=CAP_LIST_USERS)
        user_mng = self._user_mng
        for email in user_mng.list_users():
            is_active = False
            for _ in user_mng.get_sessions_for_user(email):
                is_active = True
                break
            yield (email, is_active)

    def create_user(
            self, who: SessionToken, email: UName, display_name: str) -> bool:
        self.ensure_can_act(who, email=None, admin_capability=CAP_CREATE_USER)
        return self._user_mng.create_user(email, display_name)

    def generate_reset_token(self, email: UName) -> ResetToken | None:
        return self._user_mng.generate_reset_token(email)

    def ensure_not_admin(self, email: UName) -> None:
        """
        Refuses operations that would delete or demote the admin account.

        Args:
            email (UName): The account to act on.
        """
        if self._user_mng.is_admin(email):
            raise PreventDefaultResponse(
                403, "the admin account cannot be changed")

    def send_reset_token(
            self, who: SessionToken, email: UName) -> ResetToken | None:
        """
        Issues a password reset token for an account on behalf of a user
        that may create accounts (the same token the invitation email
        carries). Unlike the public reset request, the caller learns whether
        a token was issued.

        Args:
            who (SessionToken): The session of the acting user.
            email (UName): The account.

        Returns:
            ResetToken | None: The token or None if the account does not
                exist, is the admin, or got a token within the cooldown.
        """
        self.ensure_can_act(who, email=email, admin_capability=CAP_CREATE_USER)
        return self._user_mng.generate_reset_token(email)

    def delete_user(self, who: SessionToken, email: UName) -> bool:
        """
        Deletes an account (see `UserManager.delete_user`). Requires the
        delete capability. Neither the own account nor the admin account can
        be deleted this way.

        Args:
            who (SessionToken): The session of the acting user.
            email (UName): The account.

        Returns:
            bool: Whether the account existed.
        """
        # NOTE: no target email: the capability is needed for every account
        self.ensure_can_act(who, email=None, admin_capability=CAP_DELETE_USER)
        if self._user_mng.get_email(who) == email:
            raise PreventDefaultResponse(
                403, "cannot delete the own account")
        self.ensure_not_admin(email)
        return self._user_mng.delete_user(email)

    def set_password(
            self,
            password: RawPassword,
            reset_token: ResetToken) -> UName | None:
        return self._user_mng.set_password(password, reset_token)

    def get_email(self, token: SessionToken) -> UName | None:
        return self._user_mng.get_email(token)

    def get_user_info(self, who: SessionToken, email: UName) -> UserInfo:
        self.ensure_can_act(who, email=email, admin_capability=CAP_LIST_USERS)
        return self.force_user_info(email)

    def force_user_info(self, email: UName) -> UserInfo:
        return self._user_mng.get_user_info(email)

    def get_user_id(self, who: SessionToken, email: UName) -> UserId:
        self.ensure_can_act(who, email=email)
        return self.force_user_id(email)

    def force_user_id(self, email: UName) -> UserId:
        return self._user_mng.get_user_id(email)

    def is_admin(self, email: UName) -> bool:
        return self._user_mng.is_admin(email)

    def can_read_chat(
            self, who: SessionToken, user_id: UserId | None) -> CanAct:
        user_mng = self._user_mng
        email = user_mng.get_email(who)
        if email is None:
            return "invalid"
        own_user_id = user_mng.get_user_id(email)
        if user_id != own_user_id:
            return "denied"
        return "ok"

    def ensure_can_read_chat(
            self, who: SessionToken, user_id: UserId | None) -> None:
        self._handle_can_act(self.can_read_chat(who, user_id))

    def can_write_chat(
            self, who: SessionToken, user_id: UserId | None) -> CanAct:
        user_mng = self._user_mng
        email = user_mng.get_email(who)
        if email is None:
            return "invalid"
        own_user_id = user_mng.get_user_id(email)
        if user_id != own_user_id:
            return "denied"
        return "ok"

    def ensure_can_write_chat(
            self, who: SessionToken, user_id: UserId | None) -> None:
        self._handle_can_act(self.can_write_chat(who, user_id))

    def has_capability(
            self,
            who: SessionToken,
            email: UName,
            capability: CapabilityName) -> bool:
        self.ensure_can_act(
            who,
            email=email,
            own_capability=CAP_CHANGE_CAPABILITIES,
            admin_capability=CAP_CHANGE_CAPABILITIES)
        return self._user_mng.has_capability(email, capability)

    def set_capability(
            self,
            who: SessionToken,
            email: UName,
            capability: CapabilityName,
            *,
            has: bool) -> None:
        self.ensure_can_act(
            who,
            email=email,
            own_capability=CAP_CHANGE_CAPABILITIES,
            admin_capability=CAP_CHANGE_CAPABILITIES)
        # NOTE: the admin has every capability; refusing makes it visible
        # that the change did not happen
        self.ensure_not_admin(email)
        self.force_capability(email, capability, has=has)

    def force_capability(
            self,
            email: UName,
            capability: CapabilityName,
            *,
            has: bool) -> None:
        self._user_mng.set_capability(email, capability, has=has)

    def list_capabilities(
            self,
            who: SessionToken,
            email: UName) -> set[CapabilityName]:
        self.ensure_can_act(
            who,
            email=email,
            own_capability=CAP_CHANGE_CAPABILITIES,
            admin_capability=CAP_CHANGE_CAPABILITIES)
        return self._user_mng.list_capabilities(email)

    def maybe_list_capabilities(
            self,
            who: SessionToken,
            email: UName) -> set[CapabilityName]:
        if not self.is_allowed(
                who,
                email=email,
                own_capability=CAP_CHANGE_CAPABILITIES,
                admin_capability=CAP_CHANGE_CAPABILITIES):
            return set()
        return self._user_mng.list_capabilities(email)

    def list_users(self, who: SessionToken) -> list[UName]:
        self.ensure_can_act(who, email=None, admin_capability=CAP_LIST_USERS)
        return list(self._user_mng.list_users())

    def create_worker_token(
            self, who: SessionToken, email: UName) -> WorkerToken:
        self.ensure_can_act(
            who,
            email=email,
            own_capability=CAP_REGISTER_OWN_WORKER,
            admin_capability=CAP_REGISTER_OTHER_WORKER)
        return self._user_mng.create_worker_token(email)

    def ensure_worker_token(
            self, email: UName, worker_token: WorkerToken) -> None:
        if not self._user_mng.is_correct_worker_token(email, worker_token):
            raise PreventDefaultResponse(401, "invalid worker token")

    def force_logout_user(self, email: UName) -> None:
        user_mng = self._user_mng
        for session_token in user_mng.get_sessions_for_user(email):
            user_mng.logout(session_token)

    def secure_email(
            self, who: SessionToken, email: UName | None) -> UName | None:
        if self.is_allowed(who, email=email, admin_capability=CAP_LIST_USERS):
            return email
        return None
