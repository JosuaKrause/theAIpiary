# Copyright (c) 2024 Josua Krause - All Rights Reserved
#
# THE CONTENTS OF THIS PROJECT ARE PROPRIETARY AND CONFIDENTIAL.
# UNAUTHORIZED COPYING, TRANSFERRING OR REPRODUCTION OF THE CONTENTS OF
# THIS PROJECT, VIA ANY MEDIUM IS STRICTLY PROHIBITED.
#
# The receipt or possession of the source code and/or any parts thereof does
# not convey or imply any right to use them for any purpose other than the
# purpose for which they were provided to you.
#
# The software is provided "AS IS", without warranty of any kind, express or
# implied, including but not limited to the warranties of merchantability,
# fitness for a particular purpose and non infringement. In no event shall the
# authors or copyright holders be liable for any claim, damages or other
# liability, whether in an action of contract, tort or otherwise, arising from,
# out of or in connection with the software or the use or other dealings in the
# software.
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the software.
from collections.abc import Iterable
from typing import Literal

from quick_server import PreventDefaultResponse
from scattermind.system.base import UserId
from scattermind.system.names import UName

from swai.system.user.manager import (
    CAP_CHANGE_CAPABILITIES,
    CAP_CREATE_USER,
    CAP_LIST_USERS,
    CAP_LOGOUT_OTHER_USER,
    CAP_READ_CHAT,
    CAP_REGISTER_OTHER_WORKER,
    CAP_REGISTER_OWN_WORKER,
    CAP_RESET_OTHER_PW,
    CAP_RESET_OWN_PW,
    CAP_WRITE_CHAT,
    CAPABILITIES,
    CapabilityName,
    SessionToken,
    UserManager,
    WorkerToken,
)


CanAct = Literal["ok", "denied", "invalid"]


class SecureContext:
    def __init__(self, user_mng: UserManager) -> None:
        self._user_mng = user_mng

    def can_act(
            self,
            who: SessionToken,
            *,
            name: UName | None,
            own_capability: CapabilityName | None = None,
            admin_capability: CapabilityName | None = None) -> CanAct:
        user_mng = self._user_mng
        who_name = user_mng.get_name(who)
        if who_name is None:
            return "invalid"
        if who_name == name:
            if own_capability is None:
                return "ok"  # same user and no special capability required
            if user_mng.has_capability(who_name, own_capability):
                return "ok"  # same user with capability
            return "denied"
        if admin_capability is None:
            # admin user without special privilege
            return "denied"
        if user_mng.has_capability(who_name, admin_capability):
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

    def ensure_can_act(
            self,
            who: SessionToken,
            name: UName | None,
            *,
            own_capability: CapabilityName | None = None,
            admin_capability: CapabilityName | None = None) -> None:
        self._handle_can_act(self.can_act(
            who,
            name=name,
            own_capability=own_capability,
            admin_capability=admin_capability))

    def login(self, name: UName, password: str) -> SessionToken | None:
        return self._user_mng.login(name, password)

    def logout(self, token: SessionToken) -> None:
        self._user_mng.logout(token)

    def logout_user(self, who: SessionToken, name: UName) -> None:
        self.ensure_can_act(who, name, admin_capability=CAP_LOGOUT_OTHER_USER)
        self.force_logout_user(name)

    def get_active_users(
            self, who: SessionToken) -> Iterable[tuple[UName, bool]]:
        self.ensure_can_act(who, name=None, admin_capability=CAP_LIST_USERS)
        user_mng = self._user_mng
        for name in user_mng.list_users():
            is_active = False
            for _ in user_mng.get_sessions_for_user(name):
                is_active = True
                break
            yield (name, is_active)

    def create_user(self, who: SessionToken, name: UName, email: str) -> bool:
        self.ensure_can_act(who, name=None, admin_capability=CAP_CREATE_USER)
        return self._user_mng.create_user(name, email)

    def generate_reset_token(self, who: SessionToken, name: UName) -> str:
        self.ensure_can_act(
            who,
            name=name,
            own_capability=CAP_RESET_OWN_PW,
            admin_capability=CAP_RESET_OTHER_PW)
        return self._user_mng.generate_reset_token(name)

    def set_password(self, password: str, reset_token: str) -> UName | None:
        return self._user_mng.set_password(password, reset_token)

    def get_name(self, token: SessionToken) -> UName | None:
        return self._user_mng.get_name(token)

    def get_email(self, who: SessionToken, name: UName) -> str | None:
        self.ensure_can_act(who, name=name, admin_capability=CAP_LIST_USERS)
        return self._user_mng.get_email(name)

    def get_user_id(self, who: SessionToken, name: UName) -> UserId:
        self.ensure_can_act(who, name=name)
        return self._user_mng.get_user_id(name)

    def can_read_chat(
            self, who: SessionToken, user_id: UserId | None) -> CanAct:
        user_mng = self._user_mng
        name = user_mng.get_name(who)
        if name is None:
            return "invalid"
        own_user_id = user_mng.get_user_id(name)
        if (
                user_id != own_user_id
                and not self.can_act(
                    who, name=None, admin_capability=CAP_READ_CHAT)):
            return "denied"
        return "ok"

    def ensure_can_read_chat(
            self, who: SessionToken, user_id: UserId | None) -> None:
        self._handle_can_act(self.can_read_chat(who, user_id))

    def can_write_chat(
            self, who: SessionToken, user_id: UserId | None) -> CanAct:
        user_mng = self._user_mng
        name = user_mng.get_name(who)
        if name is None:
            return "invalid"
        own_user_id = user_mng.get_user_id(name)
        if (
                user_id != own_user_id
                and not self.can_act(
                    who, name=None, admin_capability=CAP_WRITE_CHAT)):
            return "denied"
        return "ok"

    def ensure_can_write_chat(
            self, who: SessionToken, user_id: UserId | None) -> None:
        self._handle_can_act(self.can_write_chat(who, user_id))

    def has_capability(
            self,
            who: SessionToken,
            name: UName,
            capability: CapabilityName) -> bool:
        self.ensure_can_act(
            who,
            name,
            own_capability=CAP_CHANGE_CAPABILITIES,
            admin_capability=CAP_CHANGE_CAPABILITIES)
        return self._user_mng.has_capability(name, capability)

    def set_capability(
            self,
            who: SessionToken,
            name: UName,
            capability: CapabilityName,
            *,
            has: bool) -> None:
        self.ensure_can_act(
            who,
            name,
            own_capability=CAP_CHANGE_CAPABILITIES,
            admin_capability=CAP_CHANGE_CAPABILITIES)
        self._user_mng.set_capability(name, capability, has=has)

    def list_capabilities(
            self,
            who: SessionToken,
            name: UName) -> set[CapabilityName]:
        self.ensure_can_act(
            who,
            name,
            own_capability=CAP_CHANGE_CAPABILITIES,
            admin_capability=CAP_CHANGE_CAPABILITIES)
        return self._user_mng.list_capabilities(name)

    def list_users(self, who: SessionToken) -> list[UName]:
        self.ensure_can_act(who, None, admin_capability=CAP_LIST_USERS)
        return list(self._user_mng.list_users())

    def create_worker_token(
            self, who: SessionToken, name: UName) -> WorkerToken:
        self.ensure_can_act(
            who,
            name,
            own_capability=CAP_REGISTER_OWN_WORKER,
            admin_capability=CAP_REGISTER_OTHER_WORKER)
        return self._user_mng.create_worker_token(name)

    def ensure_worker_token(
            self, name: UName, worker_token: WorkerToken) -> None:
        if not self._user_mng.is_correct_worker_token(name, worker_token):
            raise PreventDefaultResponse(401, "invalid worker token")

    def force_logout_user(self, name: UName) -> None:
        user_mng = self._user_mng
        for session_token in user_mng.get_sessions_for_user(name):
            user_mng.logout(session_token)

    def force_maybe_create_admin(self) -> str | None:
        user_mng = self._user_mng
        if any(True for _ in user_mng.list_users()):
            return None
        name = UName("admin")
        if not user_mng.create_user(name, "-"):
            return None
        for cap in CAPABILITIES:
            user_mng.set_capability(name, cap, has=True)
        return user_mng.generate_reset_token(name)
