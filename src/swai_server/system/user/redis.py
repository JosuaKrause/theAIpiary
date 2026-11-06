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
import uuid
from collections.abc import Iterable
from typing import cast, TypeAlias, TypedDict

from redipy import Redis, RedisConfig
from redipy.script import ExecFunction, FnContext, RedisHash, RedisVar
from scattermind.system.names import UName
from scattermind.system.util import get_short_hash, short_hash_size

from swai.system.user import CapabilityName, WorkerToken
from swai_server.system.user.manager import (
    as_capability,
    HashPassword,
    ResetToken,
    SessionToken,
    UserInfo,
    UserManager,
)


UserHash: TypeAlias = str


UserInfoRedis = TypedDict('UserInfoRedis', {
    "email": str,
    "display_name": str,
    "hashpw": str,
})


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
        self._create_user = self._create_user_script()
        self._generate_reset_token = self._generate_reset_token_script()
        self._delete_user = self._delete_user_script()

    def _create_user_script(self) -> ExecFunction:
        ctx = FnContext()
        info = RedisHash(ctx.add_key("info"))
        email = ctx.add_arg("email")
        display_name = ctx.add_arg("display_name")
        res = ctx.add_local(False)
        b_then, _ = ctx.if_(info.exists().eq_(0))
        b_then.add(info.hset({
            "email": email,
            "display_name": display_name,
            "hashpw": "",
        }))
        b_then.add(res.assign(True))
        ctx.set_return_value(res)
        return self._redis.register_script(ctx)

    def _generate_reset_token_script(self) -> ExecFunction:
        ctx = FnContext()
        info = RedisHash(ctx.add_key("info"))
        cooldown = RedisVar(ctx.add_key("cooldown"))
        reset = RedisVar(ctx.add_key("reset"))
        email = ctx.add_arg("email")
        reset_token = ctx.add_arg("reset_token")
        expire_ms = ctx.add_arg("expire_ms")
        cooldown_ms = ctx.add_arg("cooldown_ms")
        res = ctx.add_local(False)
        b_then, _ = ctx.if_(
            info.exists().eq_(1).and_(cooldown.exists().eq_(0)))
        # NOTE: RedisVar.set_value only takes a constant expiration so the
        # set calls are spelled out to read the expiration from the arguments
        b_then.add(reset.redis_fn("set", email, "PX", expire_ms))
        b_then.add(cooldown.redis_fn("set", reset_token, "PX", cooldown_ms))
        b_then.add(res.assign(True))
        ctx.set_return_value(res)
        return self._redis.register_script(ctx)

    def _delete_user_script(self) -> ExecFunction:
        ctx = FnContext()
        info = RedisHash(ctx.add_key("info"))
        perm = RedisVar(ctx.add_key("perm"))
        sess = RedisVar(ctx.add_key("sess"))
        cooldown = RedisVar(ctx.add_key("cooldown"))
        worker = RedisVar(ctx.add_key("worker"))
        res = ctx.add_local(info.exists())
        ctx.add(info.delete())
        ctx.add(perm.delete())
        ctx.add(sess.delete())
        ctx.add(cooldown.delete())
        ctx.add(worker.delete())
        ctx.set_return_value(res)
        return self._redis.register_script(ctx)

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
    def _key_pw_reset(cls, reset_token: ResetToken | None) -> str:
        return f"reset:{'' if reset_token is None else reset_token}"

    @classmethod
    def _key_pw_cooldown(cls, email: UName) -> str:
        return f"cooldown:{cls._userhash(email)}"

    def _key_worker(self, email: UName) -> str:
        user_id = self.get_user_id(email)
        return f"worker:{user_id.to_parseable()}"

    @classmethod
    def _session_token(cls, email: UName) -> SessionToken:
        return f"{cls._userhash(email)}{uuid.uuid4().hex}"

    @staticmethod
    def _extract_userhash(token: SessionToken) -> UserHash:
        return token[:short_hash_size()]

    def _get_user_info(self, email: UName) -> UserInfoRedis:
        if self.is_admin(email):
            raise ValueError("cannot read info for admin")
        res = self._redis.hgetall(self._key_user_info(email))
        return {
            "email": res["email"],
            "display_name": res["display_name"],
            "hashpw": res["hashpw"],
        }

    def _set_user_info(self, info: UserInfoRedis) -> None:
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
        if self.is_admin(email):
            raise ValueError("cannot set info for admin")
        # NOTE: checking for and writing the user in one step so that of two
        # concurrent registrations for the same email only one succeeds
        res = self._create_user(
            keys={
                "info": self._key_user_info(email),
            },
            args={
                "email": email.get(),
                "display_name": display_name,
            })
        return bool(res)

    def do_delete_user(self, email: UName) -> bool:
        # NOTE: removing the account first means that no new reset token can
        # be issued for it (issuing one checks for the account in the same
        # script) while the remaining tokens are looked for below
        res = self._delete_user(
            keys={
                "info": self._key_user_info(email),
                "perm": self._key_user_perm(email),
                "sess": self._key_user_session(email),
                "cooldown": self._key_pw_cooldown(email),
                "worker": self._key_worker(email),
            },
            args={})
        # NOTE: reset tokens are only found by token. there are few of them
        # (they expire after a day) so going through all of them is cheap.
        # a token must not outlive its account: it would be good for a new
        # account with the same email
        pat = f"{self._key_pw_reset(None)}*"
        for key in list(self._redis.keys(match=pat, block=False)):
            if self._redis.get_value(key) == email.get():
                self._redis.delete(key)
        return bool(res)

    def do_generate_reset_token(self, email: UName) -> ResetToken | None:
        reset_token: ResetToken = uuid.uuid4().hex
        # NOTE: one script call whether or not the account exists: no token
        # for unknown emails and no difference in how long the check takes
        res = self._generate_reset_token(
            keys={
                "info": self._key_user_info(email),
                "cooldown": self._key_pw_cooldown(email),
                "reset": self._key_pw_reset(reset_token),
            },
            args={
                "email": email.get(),
                "reset_token": reset_token,
                "expire_ms": int(self.reset_expire() * 1000.0),
                "cooldown_ms": int(self.reset_cooldown() * 1000.0),
            })
        if not res:
            return None
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
            reset_token: ResetToken) -> bool:
        cooldown_key = self._key_pw_cooldown(email)
        reset_key = self._key_pw_reset(reset_token)
        with self._redis.pipeline() as pipe:
            pipe.delete(cooldown_key)
            pipe.delete(reset_key)
        if not self._redis.exists(self._key_user_info(email)):
            # NOTE: a token for an email without an account (tokens like this
            # used to be issued) must not create the account
            return False
        info = self._get_user_info(email)
        info["hashpw"] = hashpw
        self._set_user_info(info)
        return True

    def get_password_hash(self, email: UName) -> HashPassword | None:
        return self._redis.hget(self._key_user_info(email), "hashpw")

    def _is_logged_in(self, token: SessionToken) -> UserHash | None:
        userhash = self._extract_userhash(token)
        if not self._redis.sismember(
                self._key_userhash_session(userhash), token):
            return None
        return userhash

    def get_email(self, token: SessionToken) -> UName | None:
        if self._is_logged_in(token) == self._admin_hash:
            return self.get_admin()
        userhash = self._is_logged_in(token)
        if userhash is None:
            return None
        res = self._redis.hget(self._key_userhash_info(userhash), "email")
        if res is None:
            return None
        return UName(res)

    def do_get_user_info(self, email: UName) -> UserInfo:
        obj = self._get_user_info(email)
        return {
            "email": email,
            "display_name": obj["display_name"],
            "capabilities": self.list_capabilities(email),
        }

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
            self, email: UName, worker_token: WorkerToken) -> None:
        self._redis.set_value(self._key_worker(email), worker_token)

    def get_worker_token(self, email: UName) -> WorkerToken | None:
        return self._redis.get_value(self._key_worker(email))
