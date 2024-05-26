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
import uuid
from collections.abc import Iterable
from typing import cast, TypeAlias, TypedDict

from redipy import Redis, RedisConfig
from scattermind.system.base import UserId
from scattermind.system.names import UName
from scattermind.system.util import get_short_hash, short_hash_size

from swai.system.user.manager import (
    as_capability,
    CapabilityName,
    HashPassword,
    ResetToken,
    SessionToken,
    UserManager,
    WorkerToken,
)


UserHash: TypeAlias = str


UserInfo = TypedDict('UserInfo', {
    "email": str,
    "display_name": str,
    "hashpw": str,
})


PW_RESET_EXPIRE = 24.0 * 60.0 * 60.0  # 24h


class RedisUserManager(UserManager):
    def __init__(
            self,
            *,
            admin_email: UName | None,
            admin_pw: str | None,
            cfg: RedisConfig) -> None:
        super().__init__(admin_email=admin_email, admin_pw=admin_pw)
        self._redis = Redis("redis", cfg=cfg, redis_module="users")
        self._admin_hash = (
            None if admin_email is None else self._userhash(admin_email))

    @staticmethod
    def _userhash(email: UName) -> UserHash:
        return get_short_hash(email.get())

    @classmethod
    def _key_user_info(cls, email: UName) -> str:
        return cls._key_userhash_info(cls._userhash(email))

    @staticmethod
    def _key_userhash_info(userhash: UserHash | None) -> str:
        return f"info:{'' if userhash is None else userhash}"

    @classmethod
    def _key_user_perm(cls, email: UName) -> str:
        return cls._key_userhash_perm(cls._userhash(email))

    @staticmethod
    def _key_userhash_perm(userhash: UserHash) -> str:
        return f"perm:{userhash}"

    @classmethod
    def _key_user_session(cls, email: UName) -> str:
        return cls._key_userhash_session(cls._userhash(email))

    @staticmethod
    def _key_userhash_session(userhash: UserHash) -> str:
        return f"sess:{userhash}"

    @classmethod
    def _key_pw_reset(cls, reset_token: ResetToken) -> str:
        return f"reset:{reset_token}"

    @staticmethod
    def _key_worker(user_id: UserId) -> str:
        return f"worker:{user_id.to_parseable()}"

    @classmethod
    def _session_token(cls, email: UName) -> SessionToken:
        return f"{cls._userhash(email)}{uuid.uuid4().hex}"

    @staticmethod
    def _extract_userhash(token: SessionToken) -> UserHash:
        return token[:short_hash_size()]

    @staticmethod
    def _new_user_info(email: UName, display_name: str) -> UserInfo:
        return {
            "email": email.get(),
            "display_name": display_name,
            "hashpw": "",
        }

    def _get_user_info(self, email: UName) -> UserInfo:
        if self.is_admin(email):
            raise ValueError("cannot read info for admin")
        res = self._redis.hgetall(self._key_user_info(email))
        return {
            "email": res["email"],
            "display_name": res["display_name"],
            "hashpw": res["hashpw"],
        }

    def _set_user_info(self, info: UserInfo) -> None:
        email = UName(info["email"])
        if self.is_admin(email):
            raise ValueError("cannot set info for admin")
        self._redis.hset(self._key_user_info(email), cast(dict, info))

    def do_login(self, email: UName) -> SessionToken | None:
        token = self._session_token(email)
        self._redis.sadd(self._key_user_session(email), token)
        return token

    def logout(self, token: SessionToken) -> None:
        userhash = self._extract_userhash(token)
        self._redis.srem(self._key_userhash_session(userhash), token)

    def get_sessions_for_user(self, email: UName) -> Iterable[SessionToken]:
        yield from sorted(self._redis.smembers(self._key_user_session(email)))

    def do_create_user(self, email: UName, display_name: str) -> bool:
        # FIXME: make script to avoid race condition
        key = self._key_user_info(email)
        if self._redis.exists(key):
            return False
        self._set_user_info(self._new_user_info(email, display_name))
        return True

    def do_generate_reset_token(self, email: UName) -> ResetToken:
        reset_token = uuid.uuid4().hex
        self._redis.set_value(
            self._key_pw_reset(reset_token),
            email.get(),
            expire_in=PW_RESET_EXPIRE)
        return reset_token

    def get_email_for_reset_token(
            self, reset_token: ResetToken) -> UName | None:
        reset_key = self._key_pw_reset(reset_token)
        raw_name = self._redis.get_value(reset_key)
        if raw_name is None:
            return None
        return UName(raw_name)

    def set_password_hash(
            self,
            email: UName,
            hashpw: HashPassword,
            reset_token: ResetToken) -> None:
        reset_key = self._key_pw_reset(reset_token)
        self._redis.delete(reset_key)
        info = self._get_user_info(email)
        info["hashpw"] = hashpw
        self._set_user_info(info)

    def get_password_hash(self, email: UName) -> HashPassword | None:
        return self._redis.hget(self._key_user_info(email), "hashpw")

    def _is_logged_in(self, token: SessionToken) -> UserHash | None:
        userhash = self._extract_userhash(token)
        if not self._redis.sismember(
                self._key_userhash_session(userhash), token):
            return None
        return userhash

    def get_email(self, token: SessionToken) -> UName | None:
        if self._extract_userhash(token) == self._admin_hash:
            return self.get_admin()
        userhash = self._is_logged_in(token)
        if userhash is None:
            return None
        res = self._redis.hget(self._key_userhash_info(userhash), "email")
        if res is None:
            return None
        return UName(res)

    def do_get_display_name(self, email: UName) -> str | None:
        return self._redis.hget(self._key_user_info(email), "display_name")

    def do_has_capability(
            self,
            email: UName,
            capability: CapabilityName) -> bool:
        return self._redis.sismember(self._key_user_perm(email), capability)

    def do_set_capability(
            self,
            email: UName,
            capability: CapabilityName,
            *,
            has: bool) -> None:
        if has:
            self._redis.sadd(self._key_user_perm(email), capability)
        else:
            self._redis.srem(self._key_user_perm(email), capability)

    def do_list_capabilities(self, email: UName) -> set[CapabilityName]:
        return {
            as_capability(cap)
            for cap in self._redis.smembers(self._key_user_perm(email))
        }

    def do_list_users(self) -> Iterable[UName]:
        pat = f"{self._key_userhash_info(None)}*"
        for key in sorted(self._redis.keys(match=pat, block=False)):
            name = self._redis.hget(key, "email")
            if name is None:
                continue
            yield UName(name)

    def store_worker_token(
            self, user_id: UserId, worker_token: WorkerToken) -> None:
        self._redis.set_value(self._key_worker(user_id), worker_token)

    def get_worker_token(self, user_id: UserId) -> WorkerToken | None:
        return self._redis.get_value(self._key_worker(user_id))
