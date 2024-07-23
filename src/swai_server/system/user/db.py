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
