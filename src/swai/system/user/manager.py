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
from typing import cast, get_args, Literal, TypeAlias

from scattermind.system.base import UserId
from scattermind.system.names import UName


WorkerToken: TypeAlias = str


CapabilityName = Literal[
    "change_capabilities",
    "reset_own_password",
    "reset_other_password",
    "logout_other_user",
    "create_user",
    "list_users",
    "write_chat",
    "read_chat",
]
CAPABILITIES = get_args(CapabilityName)
CAP_CHANGE_CAPABILITIES: CapabilityName = "change_capabilities"
CAP_RESET_OWN_PW: CapabilityName = "reset_own_password"
CAP_RESET_OTHER_PW: CapabilityName = "reset_other_password"
CAP_LOGOUT_OTHER_USER: CapabilityName = "logout_other_user"
CAP_CREATE_USER: CapabilityName = "create_user"
CAP_LIST_USERS: CapabilityName = "list_users"
CAP_WRITE_CHAT: CapabilityName = "write_chat"
CAP_READ_CHAT: CapabilityName = "read_chat"


def as_capability(capability: str) -> CapabilityName:
    if capability not in CAPABILITIES:
        raise ValueError(f"{capability=} is invalid: {CAPABILITIES}")
    return cast(CapabilityName, capability)


SessionToken: TypeAlias = str


class UserManager:
    def login(self, name: UName, password: str) -> SessionToken | None:
        raise NotImplementedError()

    def logout(self, token: SessionToken) -> None:
        raise NotImplementedError()

    def get_sessions_for_user(self, name: UName) -> Iterable[SessionToken]:
        raise NotImplementedError()

    def create_user(self, name: UName, email: str) -> bool:
        raise NotImplementedError()

    def generate_reset_token(self, name: UName) -> str:
        raise NotImplementedError()

    def set_password(self, password: str, reset_token: str) -> UName | None:
        raise NotImplementedError()

    def get_name(self, token: SessionToken) -> UName | None:
        raise NotImplementedError()

    def get_email(self, name: UName) -> str | None:
        raise NotImplementedError()

    def get_user_id(self, name: UName) -> UserId:
        raise NotImplementedError()

    def has_capability(self, name: UName, capability: CapabilityName) -> bool:
        raise NotImplementedError()

    def set_capability(
            self,
            name: UName,
            capability: CapabilityName,
            *,
            has: bool) -> None:
        raise NotImplementedError()

    def list_capabilities(self, name: UName) -> set[CapabilityName]:
        raise NotImplementedError()

    def list_users(self) -> Iterable[UName]:
        raise NotImplementedError()

    def create_worker_token(self, name: UName) -> WorkerToken:
        raise NotImplementedError()

    def is_correct_worker_token(
            self, name: UName, worker_token: WorkerToken) -> bool:
        raise NotImplementedError()
