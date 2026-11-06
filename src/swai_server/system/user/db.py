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

from scattermind.system.base import UserId
from scattermind.system.names import UName

from swai.system.user import CapabilityName, WorkerToken
from swai_server.system.db.db import DBConnector
from swai_server.system.user.manager import (
    HashPassword,
    ResetToken,
    SessionToken,
    UserInfo,
    UserManager,
)


PW_RESET_EXPIRE = 24.0 * 60.0 * 60.0  # 24h
PW_RESET_COOLDOWN = 1.0 * 60.0  # 1min


class DBUserManager(UserManager):
    def __init__(
            self,
            *,
            admin_email: UName | None,
            admin_pw: str | None,
            db: DBConnector) -> None:
        super().__init__(admin_email=admin_email, admin_pw=admin_pw)
        self._db = db
        # self._admin_hash = (
        #     None if admin_email is None else self._userhash(admin_email))

    def do_login(self, email: UName) -> SessionToken | None:
        raise NotImplementedError()

    def logout(self, token: SessionToken) -> None:
        raise NotImplementedError()

    def get_sessions_for_user(self, email: UName) -> Iterable[SessionToken]:
        raise NotImplementedError()

    def do_create_user(self, email: UName, display_name: str) -> bool:
        raise NotImplementedError()

    def do_generate_reset_token(self, email: UName) -> ResetToken | None:
        raise NotImplementedError()

    def get_email_for_reset_token(
            self, reset_token: ResetToken) -> UName | None:
        raise NotImplementedError()

    def set_password_hash(
            self,
            email: UName,
            hashpw: HashPassword,
            reset_token: ResetToken) -> None:
        raise NotImplementedError()

    def get_password_hash(self, email: UName) -> HashPassword | None:
        raise NotImplementedError()

    def get_email(self, token: SessionToken) -> UName | None:
        raise NotImplementedError()

    def do_get_user_info(self, email: UName) -> UserInfo:
        raise NotImplementedError()

    def do_has_capability(
            self,
            email: UName,
            capability: CapabilityName) -> bool:
        raise NotImplementedError()

    def do_set_capability(
            self,
            email: UName,
            capability: CapabilityName,
            *,
            has: bool) -> None:
        raise NotImplementedError()

    def do_list_capabilities(self, email: UName) -> set[CapabilityName]:
        raise NotImplementedError()

    def do_list_users(self) -> Iterable[UName]:
        raise NotImplementedError()

    def store_worker_token(
            self, user_id: UserId, worker_token: WorkerToken) -> None:
        raise NotImplementedError()

    def get_worker_token(self, user_id: UserId) -> WorkerToken | None:
        raise NotImplementedError()
