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
import hashlib
import hmac
import uuid
from collections.abc import Iterable
from typing import cast, TypeAlias, TypedDict

import bcrypt
from scattermind.system.base import UserId
from scattermind.system.names import UName
from scattermind.system.util import get_short_hash, get_text_hash

from swai.system.user import (
    CAP_REGISTER_OWN_WORKER,
    CAPABILITIES,
    CapabilityName,
    WorkerToken,
)


SessionToken: TypeAlias = str
ResetToken: TypeAlias = str
AccountKey: TypeAlias = str
RawPassword: TypeAlias = str
HashPassword: TypeAlias = str


INVALID_WORKER_TOKEN: WorkerToken = uuid.UUID(
    "87f3fabee0ca4feaa42d8f40e5cdc303").hex


DEFAULT_CAPABILITIES: set[CapabilityName] = {
    CAP_REGISTER_OWN_WORKER,
}


PW_RESET_EXPIRE = 24.0 * 60.0 * 60.0  # 24h
PW_RESET_COOLDOWN = 1.0 * 60.0  # 1min


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


def hash_token(token: str) -> str:
    """
    What the stores keep of a session or reset token: its SHA-256, so that
    reading the store is not enough to log in or set a password. The tokens
    are random (122 bits of a uuid4), so a plain fast hash is enough: salts
    and slow key derivation protect secrets that can be guessed, like
    passwords, and nobody can guess a token to test against its hash.

    Args:
        token (str): The token as the user presents it.

    Returns:
        str: The hex digest.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def derive_user_id(email: UName) -> UserId:
    """
    The user id an account gets when it is created: derived from its email
    the way it always was (chats and worker tokens hang off it). The id is
    stored with the account and stays when the email changes.

    Args:
        email (UName): The email at creation.

    Returns:
        UserId: The user id.
    """
    return UserId.create(email)


def derive_account_key(email: UName) -> AccountKey:
    """
    The account key an account gets when it is created: derived from its
    email the way it always was. It is the prefix of the account's queue
    worker ids (and the key of the account in the redis store). It is stored
    with the account and stays when the email changes.

    Args:
        email (UName): The email at creation.

    Returns:
        AccountKey: The account key.
    """
    return get_short_hash(email.get())


def random_user_id() -> UserId:
    """
    A user id for an account whose derived user id belongs to another
    account already (whose email was changed away from this one).

    Returns:
        UserId: A new random user id.
    """
    return UserId(uuid.uuid4())


def random_account_key() -> AccountKey:
    """
    An account key for an account whose derived account key belongs to
    another account already (whose email was changed away from this one).

    Returns:
        AccountKey: A new random account key.
    """
    return get_short_hash(uuid.uuid4().hex)


AccountIds = TypedDict('AccountIds', {
    "user_id": UserId,
    "account_key": AccountKey,
})


UserInfo = TypedDict('UserInfo', {
    "email": UName,
    "display_name": str,
    "capabilities": set[CapabilityName],
})


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

    @staticmethod
    def reset_expire() -> float:
        """
        How long a password reset token stays valid.

        Returns:
            float: The time in seconds.
        """
        return PW_RESET_EXPIRE

    @staticmethod
    def reset_cooldown() -> float:
        """
        How long after a password reset token was issued no further token is
        issued for the same account (unless the token gets used).

        Returns:
            float: The time in seconds.
        """
        return PW_RESET_COOLDOWN

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

    def count_sessions(self, email: UName) -> int:
        raise NotImplementedError()

    def logout_everywhere(self, email: UName) -> None:
        raise NotImplementedError()

    def create_user(self, email: UName, display_name: str) -> bool:
        if self.is_admin(email):
            return False
        if not email.get() or not display_name:
            return False
        return self.do_create_user(email, display_name)

    def do_create_user(self, email: UName, display_name: str) -> bool:
        raise NotImplementedError()

    def delete_user(self, email: UName) -> bool:
        """
        Deletes an account with everything the user manager keeps for it:
        the account itself (password and display name), capabilities,
        sessions, reset tokens and the cooldown, and the worker token. The
        admin account cannot be deleted.

        Args:
            email (UName): The account.

        Returns:
            bool: Whether the account existed.
        """
        if self.is_admin(email):
            return False
        return self.do_delete_user(email)

    def do_delete_user(self, email: UName) -> bool:
        raise NotImplementedError()

    def generate_reset_token(self, email: UName) -> ResetToken | None:
        if self.is_admin(email):
            return None
        return self.do_generate_reset_token(email)

    def do_generate_reset_token(self, email: UName) -> ResetToken | None:
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
        if not self.set_password_hash(
                email, hash_password(password), reset_token):
            return None
        return email

    def set_password_hash(
            self,
            email: UName,
            hashpw: HashPassword,
            reset_token: ResetToken) -> bool:
        raise NotImplementedError()

    def get_password_hash(self, email: UName) -> HashPassword | None:
        raise NotImplementedError()

    def get_email(self, token: SessionToken) -> UName | None:
        raise NotImplementedError()

    def get_user_info(self, email: UName) -> UserInfo:
        if self.is_admin(email):
            return {
                "email": email,
                "display_name": "admin",
                "capabilities": self.list_capabilities(email),
            }
        return self.do_get_user_info(email)

    def do_get_user_info(self, email: UName) -> UserInfo:
        raise NotImplementedError()

    def get_ids(self, email: UName) -> AccountIds | None:
        """
        The stored ids of an account. The admin is configured by email and
        has the ids derived from it.

        Args:
            email (UName): The current email of the account.

        Returns:
            AccountIds | None: The ids or None if there is no such account.
        """
        if self.is_admin(email):
            return {
                "user_id": derive_user_id(email),
                "account_key": derive_account_key(email),
            }
        return self.do_get_ids(email)

    def do_get_ids(self, email: UName) -> AccountIds | None:
        raise NotImplementedError()

    def get_user_id(self, email: UName) -> UserId | None:
        ids = self.get_ids(email)
        return None if ids is None else ids["user_id"]

    def get_account_key(self, email: UName) -> AccountKey | None:
        ids = self.get_ids(email)
        return None if ids is None else ids["account_key"]

    def change_email(self, email: UName, new_email: UName) -> bool:
        """
        Changes the email of an account in one step. The account keeps its
        ids (and so its chats, worker token and workers), all its sessions
        end, and outstanding reset tokens and the reset cooldown are
        dropped. The admin's email cannot be changed and cannot be taken.

        Args:
            email (UName): The current email.
            new_email (UName): The new email.

        Returns:
            bool: Whether the email was changed. It is not if the account does
                not exist or the new email belongs to an account already.
        """
        if self.is_admin(email) or self.is_admin(new_email):
            return False
        if email == new_email:
            return False
        return self.do_change_email(email, new_email)

    def do_change_email(self, email: UName, new_email: UName) -> bool:
        raise NotImplementedError()

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

    def create_worker_token(self, email: UName) -> WorkerToken | None:
        user_id = self.get_user_id(email)
        if user_id is None:
            return None
        worker_token: WorkerToken | None = None
        while worker_token is None:
            worker_token = uuid.uuid4().hex
            if hmac.compare_digest(INVALID_WORKER_TOKEN, worker_token):
                worker_token = None
        self.store_worker_token(user_id, worker_token)
        return worker_token

    def is_correct_worker_token(
            self, email: UName, worker_token: WorkerToken) -> bool:
        # NOTE: providers send the current email of the account; the token
        # belongs to the account's user id
        user_id = self.get_user_id(email)
        expected_token = (
            None if user_id is None else self.get_worker_token(user_id))
        if expected_token is None:
            # NOTE: no shortcut for missing tokens (same timing as a mismatch)
            hmac.compare_digest(INVALID_WORKER_TOKEN, worker_token)
            return False
        return hmac.compare_digest(expected_token, worker_token)

    def store_worker_token(
            self, user_id: UserId, worker_token: WorkerToken) -> None:
        raise NotImplementedError()

    def get_worker_token(self, user_id: UserId) -> WorkerToken | None:
        raise NotImplementedError()
