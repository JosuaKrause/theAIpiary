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
from typing import cast, TypeAlias, TypedDict

import bcrypt
from redipy import Redis, RedisConfig
from scattermind.system.base import UserId
from scattermind.system.names import UName
from scattermind.system.util import (
    get_short_hash,
    get_text_hash,
    short_hash_size,
)

from swai.system.user.manager import (
    as_capability,
    CapabilityName,
    SessionToken,
    UserManager,
    WorkerToken,
)


UserHash: TypeAlias = str


UserInfo = TypedDict('UserInfo', {
    "name": str,
    "email": str,
    "hashpw": str,
})


PW_RESET_EXPIRE = 24.0 * 60.0 * 60.0  # 24h


INVALID_WORKER_TOKEN: WorkerToken = uuid.UUID(
    "87f3fabee0ca4feaa42d8f40e5cdc303").hex


class RedisUserManager(UserManager):
    def __init__(self, *, cfg: RedisConfig) -> None:
        self._redis = Redis("redis", cfg=cfg, redis_module="users")

    @staticmethod
    def _userhash(name: UName) -> UserHash:
        return get_short_hash(name.get())

    @classmethod
    def _key_user_info(cls, name: UName) -> str:
        return cls._key_userhash_info(cls._userhash(name))

    @staticmethod
    def _key_userhash_info(userhash: UserHash | None) -> str:
        return f"info:{'' if userhash is None else userhash}"

    @classmethod
    def _key_user_perm(cls, name: UName) -> str:
        return cls._key_userhash_perm(cls._userhash(name))

    @staticmethod
    def _key_userhash_perm(userhash: UserHash) -> str:
        return f"perm:{userhash}"

    @classmethod
    def _key_user_session(cls, name: UName) -> str:
        return cls._key_userhash_session(cls._userhash(name))

    @staticmethod
    def _key_userhash_session(userhash: UserHash) -> str:
        return f"sess:{userhash}"

    @classmethod
    def _key_pw_reset(cls, reset_token: str) -> str:
        return f"reset:{reset_token}"

    @staticmethod
    def _key_worker(user_id: UserId) -> str:
        return f"worker:{user_id.to_parseable()}"

    @classmethod
    def _session_token(cls, name: UName) -> SessionToken:
        return f"{cls._userhash(name)}{uuid.uuid4().hex}"

    @staticmethod
    def _extract_userhash(token: SessionToken) -> UserHash:
        return token[:short_hash_size()]

    @staticmethod
    def _new_user_info(name: UName, email: str) -> UserInfo:
        return {
            "name": name.get(),
            "email": email,
            "hashpw": "",
        }

    def _get_user_info(self, name: UName) -> UserInfo:
        res = self._redis.hgetall(self._key_user_info(name))
        return {
            "name": res["name"],
            "email": res["email"],
            "hashpw": res["hashpw"],
        }

    def _set_user_info(self, info: UserInfo) -> None:
        name = UName(info["name"])
        self._redis.hset(self._key_user_info(name), cast(dict, info))

    @staticmethod
    def _hashpw(password: str) -> str:
        return bcrypt.hashpw(
            get_text_hash(password).encode("utf-8"),
            bcrypt.gensalt(12)).decode("utf-8")

    @staticmethod
    def _check_pw(password: str, hashpw: str | None) -> bool:
        if not hashpw:
            return False
        return bcrypt.checkpw(
            get_text_hash(password).encode("utf-8"),
            hashpw.encode("utf-8"))

    def login(self, name: UName, password: str) -> SessionToken | None:
        hashpw = self._redis.hget(self._key_user_info(name), "hashpw")
        if not self._check_pw(password, hashpw):
            return None
        token = self._session_token(name)
        self._redis.sadd(self._key_user_session(name), token)
        return token

    def logout(self, token: SessionToken) -> None:
        userhash = self._extract_userhash(token)
        self._redis.srem(self._key_userhash_session(userhash), token)

    def get_sessions_for_user(self, name: UName) -> Iterable[SessionToken]:
        yield from sorted(self._redis.smembers(self._key_user_session(name)))

    def create_user(self, name: UName, email: str) -> bool:
        # FIXME: make script to avoid race condition
        key = self._key_user_info(name)
        if self._redis.exists(key):
            return False
        self._set_user_info(self._new_user_info(name, email))
        return True

    def generate_reset_token(self, name: UName) -> str:
        reset_token = uuid.uuid4().hex
        self._redis.set_value(
            self._key_pw_reset(reset_token),
            name.get(),
            expire_in=PW_RESET_EXPIRE)
        return reset_token

    def set_password(self, password: str, reset_token: str) -> UName | None:
        reset_key = self._key_pw_reset(reset_token)
        raw_name = self._redis.get_value(reset_key)
        if raw_name is None:
            return None
        name = UName(raw_name)
        self._redis.delete(reset_key)
        info = self._get_user_info(name)
        info["hashpw"] = self._hashpw(password)
        self._set_user_info(info)
        return name

    def _is_logged_in(self, token: SessionToken) -> UserHash | None:
        userhash = self._extract_userhash(token)
        if not self._redis.sismember(
                self._key_userhash_session(userhash), token):
            return None
        return userhash

    def get_name(self, token: SessionToken) -> UName | None:
        userhash = self._is_logged_in(token)
        if userhash is None:
            return None
        res = self._redis.hget(self._key_userhash_info(userhash), "name")
        if res is None:
            return None
        return UName(res)

    def get_email(self, name: UName) -> str | None:
        return self._redis.hget(self._key_user_info(name), "email")

    def get_user_id(self, name: UName) -> UserId:
        return UserId.create(name)

    def has_capability(self, name: UName, capability: CapabilityName) -> bool:
        return self._redis.sismember(self._key_user_perm(name), capability)

    def set_capability(
            self,
            name: UName,
            capability: CapabilityName,
            *,
            has: bool) -> None:
        if has:
            self._redis.sadd(self._key_user_perm(name), capability)
        else:
            self._redis.srem(self._key_user_perm(name), capability)

    def list_capabilities(self, name: UName) -> set[CapabilityName]:
        return {
            as_capability(cap)
            for cap in self._redis.smembers(self._key_user_perm(name))
        }

    def list_users(self) -> Iterable[UName]:
        prefix = self._key_userhash_info(None)
        key = f"{prefix}*"
        for name in sorted(self._redis.keys(match=key, block=False)):
            yield UName(name.removeprefix(prefix))

    def create_worker_token(self, name: UName) -> WorkerToken:
        user_id = self.get_user_id(name)
        worker_token: WorkerToken | None = None
        while worker_token is None:
            worker_token = uuid.uuid4().hex
            if hmac.compare_digest(INVALID_WORKER_TOKEN, worker_token):
                worker_token = None
        self._redis.set_value(self._key_worker(user_id), worker_token)
        return worker_token

    def is_correct_worker_token(
            self, name: UName, worker_token: WorkerToken) -> bool:
        user_id = self.get_user_id(name)
        expected_token: WorkerToken | None = self._redis.get_value(
            self._key_worker(user_id))
        if expected_token is None:
            # NOTE: no shortcut for missing tokens
            expected_token = INVALID_WORKER_TOKEN
        return hmac.compare_digest(expected_token, worker_token)
