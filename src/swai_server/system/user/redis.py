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
"""A user manager that keeps accounts in redis.

An account is stored under its account key (see `derive_account_key`):
`info:<key>` (email, display name, password hash, user id), `perm:<key>`
(capabilities), `sess:<key>` (the hashes of the session tokens, see
`hash_token`), and `cooldown:<key>`. The emails point to their account
through `email:<hash of the email>`, the user ids through `uid:<user id>`
(which keeps user ids unique), and the worker token is `worker:<user id>`.
Reset tokens are `reset:<hash of the token>` and hold the email. A pending
email change is `change:<key>` (the hash of its token) and `change_to:<key>`
(the new email), both expiring.
"""
import uuid
from collections.abc import Iterable
from typing import cast

from redipy import Redis, RedisConfig
from redipy.script import ExecFunction, FnContext, RedisHash, RedisVar
from scattermind.system.base import UserId
from scattermind.system.names import UName
from scattermind.system.util import get_short_hash, short_hash_size

from swai.system.user import CapabilityName, WorkerToken
from swai_server.system.user.manager import (
    AccountIds,
    AccountKey,
    as_capability,
    derive_account_key,
    derive_user_id,
    EmailChange,
    EmailChangeToken,
    hash_token,
    HashPassword,
    random_account_key,
    random_user_id,
    ResetToken,
    SessionToken,
    UserInfo,
    UserManager,
)


STORE_VERSION = 3
"""The layout version of the store. 1 (no version stored): accounts were
keyed by the hash of their current email and had no stored user id. 2:
session and reset tokens were stored as they are. 3: the layout described
in the module docstring."""


CREATE_EMAIL_TAKEN = 0
CREATE_OK = 1
CREATE_ID_TAKEN = 2


class RedisUserManager(UserManager):
    def __init__(
            self,
            *,
            admin_email: UName | None,
            admin_pw: str | None,
            cfg: RedisConfig) -> None:
        super().__init__(admin_email=admin_email, admin_pw=admin_pw)
        self._redis = Redis("redis", cfg=cfg, redis_module="users")
        self._admin_key = (
            None if admin_email is None else derive_account_key(admin_email))
        self._create_user = self._create_user_script()
        self._login = self._login_script()
        self._generate_reset_token = self._generate_reset_token_script()
        self._delete_user = self._delete_user_script()
        self._change_email = self._change_email_script()
        self._request_email_change = self._request_email_change_script()
        self._take_email_change = self._take_email_change_script()
        self.migrate()

    # *** scripts ***

    def _create_user_script(self) -> ExecFunction:
        ctx = FnContext()
        email_key = RedisVar(ctx.add_key("email"))
        info = RedisHash(ctx.add_key("info"))
        uid = RedisVar(ctx.add_key("uid"))
        email = ctx.add_arg("email")
        display_name = ctx.add_arg("display_name")
        account_key = ctx.add_arg("account_key")
        user_id = ctx.add_arg("user_id")
        res = ctx.add_local(CREATE_EMAIL_TAKEN)
        b_free, _ = ctx.if_(email_key.exists().eq_(0))
        b_ok, b_taken = b_free.if_(
            info.exists().eq_(0).and_(uid.exists().eq_(0)))
        b_ok.add(info.hset({
            "email": email,
            "display_name": display_name,
            "hashpw": "",
            "user_id": user_id,
        }))
        b_ok.add(email_key.set_value(account_key))
        b_ok.add(uid.set_value(account_key))
        b_ok.add(res.assign(CREATE_OK))
        b_taken.add(res.assign(CREATE_ID_TAKEN))
        ctx.set_return_value(res)
        return self._redis.register_script(ctx)

    def _login_script(self) -> ExecFunction:
        ctx = FnContext()
        info = RedisHash(ctx.add_key("info"))
        sess = RedisVar(ctx.add_key("sess"))
        email = ctx.add_arg("email")
        token = ctx.add_arg("token")
        res = ctx.add_local(False)
        # NOTE: the email is checked in the same step so that no session can
        # be added after a concurrent email change logged the account out
        b_then, _ = ctx.if_(info.hget("email").eq_(email))
        b_then.add(sess.redis_fn("sadd", token))
        b_then.add(res.assign(True))
        ctx.set_return_value(res)
        return self._redis.register_script(ctx)

    def _generate_reset_token_script(self) -> ExecFunction:
        ctx = FnContext()
        info = RedisHash(ctx.add_key("info"))
        cooldown = RedisVar(ctx.add_key("cooldown"))
        reset = RedisVar(ctx.add_key("reset"))
        email = ctx.add_arg("email")
        expire_ms = ctx.add_arg("expire_ms")
        cooldown_ms = ctx.add_arg("cooldown_ms")
        res = ctx.add_local(False)
        b_then, _ = ctx.if_(
            info.hget("email").eq_(email).and_(cooldown.exists().eq_(0)))
        # NOTE: RedisVar.set_value only takes a constant expiration so the
        # set calls are spelled out to read the expiration from the arguments
        b_then.add(reset.redis_fn("set", email, "PX", expire_ms))
        b_then.add(cooldown.redis_fn("set", "1", "PX", cooldown_ms))
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
        email_key = RedisVar(ctx.add_key("email"))
        uid = RedisVar(ctx.add_key("uid"))
        change = RedisVar(ctx.add_key("change"))
        change_to = RedisVar(ctx.add_key("change_to"))
        email = ctx.add_arg("email")
        res = ctx.add_local(False)
        b_then, _ = ctx.if_(info.hget("email").eq_(email))
        b_then.add(info.delete())
        b_then.add(perm.delete())
        b_then.add(sess.delete())
        b_then.add(cooldown.delete())
        b_then.add(worker.delete())
        b_then.add(email_key.delete())
        b_then.add(uid.delete())
        b_then.add(change.delete())
        b_then.add(change_to.delete())
        b_then.add(res.assign(True))
        ctx.set_return_value(res)
        return self._redis.register_script(ctx)

    def _change_email_script(self) -> ExecFunction:
        ctx = FnContext()
        info = RedisHash(ctx.add_key("info"))
        old_key = RedisVar(ctx.add_key("old"))
        new_key = RedisVar(ctx.add_key("new"))
        sess = RedisVar(ctx.add_key("sess"))
        cooldown = RedisVar(ctx.add_key("cooldown"))
        change = RedisVar(ctx.add_key("change"))
        change_to = RedisVar(ctx.add_key("change_to"))
        email = ctx.add_arg("email")
        new_email = ctx.add_arg("new_email")
        account_key = ctx.add_arg("account_key")
        res = ctx.add_local(False)
        # NOTE: checking that the new email is free and taking it is one step,
        # so of two changes to the same email only one succeeds
        b_then, _ = ctx.if_(
            info.hget("email").eq_(email).and_(new_key.exists().eq_(0)))
        b_then.add(new_key.set_value(account_key))
        b_then.add(old_key.delete())
        b_then.add(info.hset({"email": new_email}))
        b_then.add(sess.delete())
        b_then.add(cooldown.delete())
        b_then.add(change.delete())
        b_then.add(change_to.delete())
        b_then.add(res.assign(True))
        ctx.set_return_value(res)
        return self._redis.register_script(ctx)

    def _request_email_change_script(self) -> ExecFunction:
        ctx = FnContext()
        info = RedisHash(ctx.add_key("info"))
        new_key = RedisVar(ctx.add_key("new"))
        change = RedisVar(ctx.add_key("change"))
        change_to = RedisVar(ctx.add_key("change_to"))
        email = ctx.add_arg("email")
        new_email = ctx.add_arg("new_email")
        token_hash = ctx.add_arg("token_hash")
        expire_ms = ctx.add_arg("expire_ms")
        res = ctx.add_local(False)
        # NOTE: the email is checked in the same step so that a pending change
        # always belongs to the account's current email: changing the email
        # (or deleting the account) drops it in one step as well. the new
        # email is checked again when the change is confirmed
        b_then, _ = ctx.if_(
            info.hget("email").eq_(email).and_(new_key.exists().eq_(0)))
        # NOTE: overwriting replaces a pending change (and its token)
        b_then.add(change.redis_fn("set", token_hash, "PX", expire_ms))
        b_then.add(change_to.redis_fn("set", new_email, "PX", expire_ms))
        b_then.add(res.assign(True))
        ctx.set_return_value(res)
        return self._redis.register_script(ctx)

    def _take_email_change_script(self) -> ExecFunction:
        ctx = FnContext()
        change = RedisVar(ctx.add_key("change"))
        change_to = RedisVar(ctx.add_key("change_to"))
        token_hash = ctx.add_arg("token_hash")
        res = ctx.add_local("")
        b_then, _ = ctx.if_(change.get_value().eq_(token_hash))
        b_then.add(res.assign(change_to.get_value()))
        b_then.add(change.delete())
        b_then.add(change_to.delete())
        ctx.set_return_value(res)
        return self._redis.register_script(ctx)

    # *** keys ***

    @staticmethod
    def _key_email(email: UName) -> str:
        return f"email:{get_short_hash(email.get())}"

    @staticmethod
    def _key_info(account_key: AccountKey | None) -> str:
        return f"info:{'' if account_key is None else account_key}"

    @staticmethod
    def _key_uid(user_id: UserId) -> str:
        return f"uid:{user_id.to_parseable()}"

    @staticmethod
    def _key_perm(account_key: AccountKey) -> str:
        return f"perm:{account_key}"

    @staticmethod
    def _key_session(account_key: AccountKey | None) -> str:
        return f"sess:{'' if account_key is None else account_key}"

    @staticmethod
    def _key_pw_cooldown(account_key: AccountKey) -> str:
        return f"cooldown:{account_key}"

    @staticmethod
    def _key_pw_reset_prefix() -> str:
        return "reset:"

    @classmethod
    def _key_pw_reset(cls, reset_token: ResetToken) -> str:
        return f"{cls._key_pw_reset_prefix()}{hash_token(reset_token)}"

    @staticmethod
    def _key_email_change(account_key: AccountKey) -> str:
        return f"change:{account_key}"

    @staticmethod
    def _key_email_change_to(account_key: AccountKey) -> str:
        return f"change_to:{account_key}"

    @staticmethod
    def _key_worker(user_id: UserId) -> str:
        return f"worker:{user_id.to_parseable()}"

    @staticmethod
    def _key_version() -> str:
        return "meta:version"

    @staticmethod
    def _session_token(account_key: AccountKey) -> SessionToken:
        return f"{account_key}{uuid.uuid4().hex}"

    @staticmethod
    def _email_change_token(account_key: AccountKey) -> EmailChangeToken:
        # NOTE: like a session token the token starts with the account key so
        # that the pending change can be found without an index
        return f"{account_key}{uuid.uuid4().hex}"

    @staticmethod
    def _extract_account_key(token: SessionToken) -> AccountKey:
        return token[:short_hash_size()]

    # *** migration ***

    def migrate(self) -> None:
        """
        Brings a store of an older version up to date, once, when the server
        starts. Every step can run again if a previous run was interrupted.
        Version 1 to 2: accounts keep their key (the hash of their email) and
        get the user id derived from their email stored, and their email and
        user id point to them. So their chats, worker token and workers stay
        theirs. Version 2 to 3: all sessions and reset tokens are dropped
        (they were stored as they are; now their hashes are).
        """
        redis = self._redis
        raw_version = redis.get_value(self._key_version())
        version = 1 if raw_version is None else int(raw_version)
        if version >= STORE_VERSION:
            return
        if version < 2:
            self._migrate_v1_to_v2()
        if version < 3:
            self._migrate_v2_to_v3()
        redis.set_value(self._key_version(), f"{STORE_VERSION}")

    def _migrate_v1_to_v2(self) -> None:
        redis = self._redis
        prefix = self._key_info(None)
        for key in list(redis.keys(match=f"{prefix}*", block=False)):
            account_key = key.removeprefix(prefix)
            raw_email = redis.hget(key, "email")
            if raw_email is None:
                continue
            email = UName(raw_email)
            user_id_str = redis.hget(key, "user_id")
            if user_id_str is None:
                user_id = derive_user_id(email)
                redis.hset(key, {"user_id": user_id.to_parseable()})
            else:
                user_id = UserId.parse(user_id_str)
            redis.set_value(
                self._key_email(email), account_key, mode="if_missing")
            redis.set_value(
                self._key_uid(user_id), account_key, mode="if_missing")

    def _migrate_v2_to_v3(self) -> None:
        # NOTE: session and reset tokens were kept as they are; the store has
        # their hashes now. the old entries could never match a hash (and
        # could be read from the store), so they are removed: everybody logs
        # in again and outstanding reset links stop working, once
        redis = self._redis
        for prefix in (
                self._key_session(None),
                self._key_pw_reset_prefix(),
                self._key_pw_cooldown(""),
                ):
            for key in list(redis.keys(match=f"{prefix}*", block=False)):
                redis.delete(key)

    # *** accounts ***

    def _account_key(self, email: UName) -> AccountKey | None:
        if self.is_admin(email):
            return self._admin_key
        account_key = self._redis.get_value(self._key_email(email))
        if account_key is None:
            return None
        # NOTE: guards against a stale pointer and a collision of the hash
        if self._redis.hget(self._key_info(account_key), "email") != (
                email.get()):
            return None
        return account_key

    def do_get_ids(self, email: UName) -> AccountIds | None:
        account_key = self._account_key(email)
        if account_key is None:
            return None
        user_id_str = self._redis.hget(self._key_info(account_key), "user_id")
        if user_id_str is None:
            return None
        return {
            "user_id": UserId.parse(user_id_str),
            "account_key": account_key,
        }

    def do_create_user(self, email: UName, display_name: str) -> bool:
        if self.is_admin(email):
            raise ValueError("cannot set info for admin")
        # NOTE: the ids derived from the email belong to another account if
        # an account with this email had its email changed. then the new
        # account gets random ids: it must not get that account's chats
        account_key = derive_account_key(email)
        user_id = derive_user_id(email)
        for _ in range(3):
            res = int(cast(int, self._create_user(
                keys={
                    "email": self._key_email(email),
                    "info": self._key_info(account_key),
                    "uid": self._key_uid(user_id),
                },
                args={
                    "email": email.get(),
                    "display_name": display_name,
                    "account_key": account_key,
                    "user_id": user_id.to_parseable(),
                })))
            if res == CREATE_OK:
                return True
            if res == CREATE_EMAIL_TAKEN:
                return False
            account_key = random_account_key()
            user_id = random_user_id()
        raise ValueError(f"could not find free ids for {email}")

    def do_delete_user(self, email: UName) -> bool:
        ids = self.get_ids(email)
        if ids is None:
            return False
        account_key = ids["account_key"]
        res = self._delete_user(
            keys={
                "info": self._key_info(account_key),
                "perm": self._key_perm(account_key),
                "sess": self._key_session(account_key),
                "cooldown": self._key_pw_cooldown(account_key),
                "worker": self._key_worker(ids["user_id"]),
                "email": self._key_email(email),
                "uid": self._key_uid(ids["user_id"]),
                "change": self._key_email_change(account_key),
                "change_to": self._key_email_change_to(account_key),
            },
            args={
                "email": email.get(),
            })
        # NOTE: no new reset token can be issued for the account anymore
        # (issuing one checks the account in the same script)
        self._remove_reset_tokens(email)
        return bool(res)

    def do_change_email(self, email: UName, new_email: UName) -> bool:
        account_key = self._account_key(email)
        if account_key is None:
            return False
        res = self._change_email(
            keys={
                "info": self._key_info(account_key),
                "old": self._key_email(email),
                "new": self._key_email(new_email),
                "sess": self._key_session(account_key),
                "cooldown": self._key_pw_cooldown(account_key),
                "change": self._key_email_change(account_key),
                "change_to": self._key_email_change_to(account_key),
            },
            args={
                "email": email.get(),
                "new_email": new_email.get(),
                "account_key": account_key,
            })
        if not res:
            return False
        # NOTE: a reset link sent to the old address must not work anymore
        self._remove_reset_tokens(email)
        return True

    def do_request_email_change(
            self, email: UName, new_email: UName) -> EmailChangeToken | None:
        account_key = self._account_key(email)
        if account_key is None or account_key == self._admin_key:
            return None
        token = self._email_change_token(account_key)
        res = self._request_email_change(
            keys={
                "info": self._key_info(account_key),
                "new": self._key_email(new_email),
                "change": self._key_email_change(account_key),
                "change_to": self._key_email_change_to(account_key),
            },
            args={
                "email": email.get(),
                "new_email": new_email.get(),
                "token_hash": hash_token(token),
                "expire_ms": int(self.email_change_expire() * 1000.0),
            })
        if not res:
            return None
        return token

    def take_email_change(self, token: EmailChangeToken) -> EmailChange | None:
        account_key = self._extract_account_key(token)
        if not account_key or account_key == self._admin_key:
            return None
        # NOTE: a pending change belongs to the account's current email (see
        # _request_email_change_script): if the email changes after it is
        # read here the change is gone and the script finds nothing
        email = self._redis.hget(self._key_info(account_key), "email")
        if email is None:
            return None
        new_email = self._take_email_change(
            keys={
                "change": self._key_email_change(account_key),
                "change_to": self._key_email_change_to(account_key),
            },
            args={
                "token_hash": hash_token(token),
            })
        if not new_email:
            return None
        return {
            "email": UName(email),
            "new_email": UName(f"{new_email}"),
        }

    def _remove_reset_tokens(self, email: UName) -> None:
        # NOTE: reset tokens are only found by token. there are few of them
        # (they expire after a day) so going through all of them is cheap.
        # a token must not outlive its account (or the account's email): it
        # would be good for a new account with the same email
        pat = f"{self._key_pw_reset_prefix()}*"
        for key in list(self._redis.keys(match=pat, block=False)):
            if self._redis.get_value(key) == email.get():
                self._redis.delete(key)

    # *** sessions ***

    def do_login(self, email: UName) -> SessionToken | None:
        account_key = self._account_key(email)
        if account_key is None:
            return None
        token = self._session_token(account_key)
        if account_key == self._admin_key and self.is_admin(email):
            self._redis.sadd(self._key_session(account_key), hash_token(token))
            return token
        if not self._login(
                keys={
                    "info": self._key_info(account_key),
                    "sess": self._key_session(account_key),
                },
                args={
                    "email": email.get(),
                    "token": hash_token(token),
                }):
            return None
        return token

    def logout(self, token: SessionToken) -> None:
        account_key = self._extract_account_key(token)
        self._redis.srem(self._key_session(account_key), hash_token(token))

    def count_sessions(self, email: UName) -> int:
        account_key = self._account_key(email)
        if account_key is None:
            return 0
        return self._redis.scard(self._key_session(account_key))

    def logout_everywhere(self, email: UName) -> None:
        account_key = self._account_key(email)
        if account_key is None:
            return
        self._redis.delete(self._key_session(account_key))

    def get_email(self, token: SessionToken) -> UName | None:
        account_key = self._extract_account_key(token)
        if not self._redis.sismember(
                self._key_session(account_key), hash_token(token)):
            return None
        if account_key == self._admin_key:
            return self.get_admin()
        res = self._redis.hget(self._key_info(account_key), "email")
        if res is None:
            return None
        return UName(res)

    # *** passwords ***

    def do_generate_reset_token(self, email: UName) -> ResetToken | None:
        reset_token: ResetToken = uuid.uuid4().hex
        account_key = self._account_key(email)
        if account_key is None:
            # NOTE: an account key nobody has (the same number of redis calls
            # as for an account: no difference in how long the check takes)
            account_key = derive_account_key(email)
        # NOTE: one script call whether or not the account exists: no token
        # for unknown emails
        res = self._generate_reset_token(
            keys={
                "info": self._key_info(account_key),
                "cooldown": self._key_pw_cooldown(account_key),
                "reset": self._key_pw_reset(reset_token),
            },
            args={
                "email": email.get(),
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
        account_key = self._account_key(email)
        reset_key = self._key_pw_reset(reset_token)
        with self._redis.pipeline() as pipe:
            if account_key is not None:
                pipe.delete(self._key_pw_cooldown(account_key))
            pipe.delete(reset_key)
        if account_key is None or account_key == self._admin_key:
            # NOTE: a token for an email without an account (tokens like this
            # used to be issued) must not create the account
            return False
        self._redis.hset(self._key_info(account_key), {"hashpw": hashpw})
        return True

    def get_password_hash(self, email: UName) -> HashPassword | None:
        account_key = self._account_key(email)
        if account_key is None or account_key == self._admin_key:
            return None
        return self._redis.hget(self._key_info(account_key), "hashpw")

    # *** info and capabilities ***

    def do_get_user_info(self, email: UName) -> UserInfo:
        account_key = self._account_key(email)
        display_name = (
            None
            if account_key is None
            else self._redis.hget(self._key_info(account_key), "display_name"))
        if display_name is None:
            raise KeyError(f"unknown user {email}")
        return {
            "email": email,
            "display_name": display_name,
            "capabilities": self.list_capabilities(email),
        }

    def do_has_capability(
            self,
            email: UName,
            capability: CapabilityName) -> bool:
        account_key = self._account_key(email)
        if account_key is None:
            return False
        return self._redis.sismember(self._key_perm(account_key), capability)

    def do_set_capability(
            self,
            email: UName,
            capability: CapabilityName,
            *,
            has: bool) -> None:
        account_key = self._account_key(email)
        if account_key is None:
            return
        if has:
            self._redis.sadd(self._key_perm(account_key), capability)
        else:
            self._redis.srem(self._key_perm(account_key), capability)

    def do_list_capabilities(self, email: UName) -> set[CapabilityName]:
        account_key = self._account_key(email)
        if account_key is None:
            return set()
        return {
            as_capability(cap)
            for cap in self._redis.smembers(self._key_perm(account_key))
        }

    def do_list_users(self) -> Iterable[UName]:
        pat = f"{self._key_info(None)}*"
        emails: list[str] = []
        for key in self._redis.keys(match=pat, block=False):
            name = self._redis.hget(key, "email")
            if name is not None:
                emails.append(name)
        yield from (UName(email) for email in sorted(emails))

    # *** worker tokens ***

    def store_worker_token(
            self, user_id: UserId, worker_token: WorkerToken) -> None:
        self._redis.set_value(self._key_worker(user_id), worker_token)

    def get_worker_token(self, user_id: UserId) -> WorkerToken | None:
        return self._redis.get_value(self._key_worker(user_id))
