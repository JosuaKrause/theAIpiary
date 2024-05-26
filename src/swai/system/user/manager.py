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
import hmac
import uuid
from collections.abc import Iterable
from typing import cast, get_args, Literal, TypeAlias

import bcrypt
from scattermind.system.base import UserId
from scattermind.system.names import UName
from scattermind.system.util import get_text_hash


SessionToken: TypeAlias = str
ResetToken: TypeAlias = str
RawPassword: TypeAlias = str
HashPassword: TypeAlias = str
WorkerToken: TypeAlias = str


INVALID_WORKER_TOKEN: WorkerToken = uuid.UUID(
    "87f3fabee0ca4feaa42d8f40e5cdc303").hex


CapabilityName = Literal[
    "change_capabilities",
    "reset_own_password",
    "reset_other_password",
    "logout_other_user",
    "create_user",
    "list_users",
    "write_chat",
    "read_chat",
    "register_own_worker",
    "register_other_worker",
]
CAPABILITIES: tuple[CapabilityName] = get_args(CapabilityName)
CAP_CHANGE_CAPABILITIES: CapabilityName = "change_capabilities"
CAP_RESET_OWN_PW: CapabilityName = "reset_own_password"
CAP_RESET_OTHER_PW: CapabilityName = "reset_other_password"
CAP_LOGOUT_OTHER_USER: CapabilityName = "logout_other_user"
CAP_CREATE_USER: CapabilityName = "create_user"
CAP_LIST_USERS: CapabilityName = "list_users"
CAP_WRITE_CHAT: CapabilityName = "write_chat"
CAP_READ_CHAT: CapabilityName = "read_chat"
CAP_REGISTER_OWN_WORKER: CapabilityName = "register_own_worker"
CAP_REGISTER_OTHER_WORKER: CapabilityName = "register_other_worker"


def as_capability(capability: str) -> CapabilityName:
    if capability not in CAPABILITIES:
        raise ValueError(f"{capability=} is invalid: {CAPABILITIES}")
    return cast(CapabilityName, capability)


def hash_password(password: RawPassword) -> HashPassword:
    return bcrypt.hashpw(
        get_text_hash(password).encode("utf-8"),
        bcrypt.gensalt(12)).decode("utf-8")


def check_password(password: RawPassword, hashpw: HashPassword | None) -> bool:
    if not hashpw:
        return False
    return bcrypt.checkpw(
        get_text_hash(password).encode("utf-8"),
        hashpw.encode("utf-8"))


class UserManager:
    def __init__(
            self,
            *,
            admin_email: UName | None,
            admin_pw: RawPassword | None) -> None:
        self._admin_email = admin_email
        self._admin_pw = admin_pw

    def get_admin(self) -> UName | None:
        if not self._admin_pw:
            return None
        return self._admin_email

    def is_admin(self, email: UName) -> bool:
        return bool(self._admin_pw) and self._admin_email == email

    def is_admin_login(self, email: UName, password: RawPassword) -> bool:
        if not self.is_admin(email):
            return False
        return check_password(password, self._admin_pw)

    def login(
            self, email: UName, password: RawPassword) -> SessionToken | None:
        if self.is_admin_login(email, password):
            return self.do_login(email)
        hashpw = self.get_password_hash(email)
        if not check_password(password, hashpw):
            return None
        return self.do_login(email)

    def do_login(self, email: UName) -> SessionToken | None:
        raise NotImplementedError()

    def logout(self, token: SessionToken) -> None:
        raise NotImplementedError()

    def get_sessions_for_user(self, email: UName) -> Iterable[SessionToken]:
        raise NotImplementedError()

    def create_user(self, email: UName, display_name: str) -> bool:
        raise NotImplementedError()

    def generate_reset_token(self, email: UName) -> ResetToken:
        raise NotImplementedError()

    def get_email_for_reset_token(
            self, reset_token: ResetToken) -> UName | None:
        raise NotImplementedError()

    def set_password(
            self,
            password: RawPassword,
            reset_token: ResetToken) -> UName | None:
        email = self.get_email_for_reset_token(reset_token)
        if email is None:
            return None
        self.set_password_hash(email, hash_password(password), reset_token)
        return email

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

    def get_display_name(self, email: UName) -> str | None:
        raise NotImplementedError()

    def get_user_id(self, email: UName) -> UserId:
        return UserId.create(email)

    def has_capability(self, email: UName, capability: CapabilityName) -> bool:
        if self.is_admin(email):
            return True
        return self.do_has_capability(email, capability)

    def do_has_capability(
            self,
            email: UName,
            capability: CapabilityName) -> bool:
        raise NotImplementedError()

    def set_capability(
            self,
            email: UName,
            capability: CapabilityName,
            *,
            has: bool) -> None:
        if self.is_admin(email):
            return
        self.do_set_capability(email, capability, has=has)

    def do_set_capability(
            self,
            email: UName,
            capability: CapabilityName,
            *,
            has: bool) -> None:
        raise NotImplementedError()

    def list_capabilities(self, email: UName) -> set[CapabilityName]:
        if self.is_admin(email):
            return set(CAPABILITIES)
        return self.do_list_capabilities(email)

    def do_list_capabilities(self, email: UName) -> set[CapabilityName]:
        raise NotImplementedError()

    def list_users(self) -> Iterable[UName]:
        admin_email = self.get_admin()
        if admin_email is not None:
            yield admin_email
        yield from self.do_list_users()

    def do_list_users(self) -> Iterable[UName]:
        raise NotImplementedError()

    def create_worker_token(self, email: UName) -> WorkerToken:
        user_id = self.get_user_id(email)
        worker_token: WorkerToken | None = None
        while worker_token is None:
            worker_token = uuid.uuid4().hex
            if hmac.compare_digest(INVALID_WORKER_TOKEN, worker_token):
                worker_token = None
        self.store_worker_token(user_id, worker_token)
        return worker_token

    def is_correct_worker_token(
            self, email: UName, worker_token: WorkerToken) -> bool:
        user_id = self.get_user_id(email)
        expected_token = self.get_worker_token(user_id)
        if expected_token is None:
            # NOTE: no shortcut for missing tokens
            expected_token = INVALID_WORKER_TOKEN
        return hmac.compare_digest(expected_token, worker_token)

    def store_worker_token(
            self, user_id: UserId, worker_token: WorkerToken) -> None:
        raise NotImplementedError()

    def get_worker_token(self, user_id: UserId) -> WorkerToken | None:
        raise NotImplementedError()
