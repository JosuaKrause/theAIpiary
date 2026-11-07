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
"""A user manager that keeps accounts in Postgres."""
import datetime
import uuid
from collections.abc import Iterable
from typing import Any

import sqlalchemy as sa
from scattermind.system.base import UserId
from scattermind.system.names import UName
from sqlalchemy.dialects.postgresql import insert as pg_insert

from swai.system.user import CapabilityName, WorkerToken
from swai_server.system.db.db import DEFAULT_SCHEMA
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


CAPABILITY_LENGTH = 40


SCHEMA_VERSION = 3
"""The version of the tables. 1 (no user_store_meta table): accounts had no
stored ids, and sessions and worker tokens were keyed by email. 2: session
and reset tokens were stored as they are. 3: the tables below."""


# NOTE: the tables are defined without a schema; the engine maps them to the
# configured schema (see create_db_engine)
METADATA = sa.MetaData()


USERS = sa.Table(
    "users",
    METADATA,
    sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
    sa.Column("email", sa.Text, nullable=False),
    sa.Column("display_name", sa.Text, nullable=False),
    # NOTE: NULL until the user sets a password through the invitation
    sa.Column("hashpw", sa.Text, nullable=True),
    # NOTE: no new reset token is issued before this time
    sa.Column("reset_cooldown", sa.DateTime(timezone=True), nullable=True),
    # NOTE: the ids stay when the email changes (see derive_user_id and
    # derive_account_key)
    sa.Column("user_id", sa.Text, nullable=False),
    sa.Column("account_key", sa.Text, nullable=False),
    sa.Column(
        "created",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now()),  # pylint: disable=not-callable
    # NOTE: the unique constraint is what makes concurrent registrations of
    # the same email safe
    sa.UniqueConstraint("email", name="users_email_key"),
    sa.UniqueConstraint("user_id", name="users_user_id_key"),
    sa.UniqueConstraint("account_key", name="users_account_key_key"),
)


CAPABILITIES = sa.Table(
    "user_capabilities",
    METADATA,
    sa.Column(
        "user_id",
        sa.BigInteger,
        sa.ForeignKey(USERS.c.id, ondelete="CASCADE"),
        primary_key=True),
    sa.Column("capability", sa.String(CAPABILITY_LENGTH), primary_key=True),
)


RESET_TOKENS = sa.Table(
    "user_reset_tokens",
    METADATA,
    # NOTE: the hash of the token (see hash_token)
    sa.Column("token_hash", sa.Text, primary_key=True),
    sa.Column(
        "user_id",
        sa.BigInteger,
        sa.ForeignKey(USERS.c.id, ondelete="CASCADE"),
        nullable=False),
    sa.Column("expires", sa.DateTime(timezone=True), nullable=False),
    sa.Index("user_reset_tokens_user_id_idx", "user_id"),
    sa.Index("user_reset_tokens_expires_idx", "expires"),
)


# NOTE: at most one pending email change per account; a new request replaces
# it. changing the email or deleting the account removes it
EMAIL_CHANGES = sa.Table(
    "user_email_changes",
    METADATA,
    sa.Column(
        "user_id",
        sa.BigInteger,
        sa.ForeignKey(USERS.c.id, ondelete="CASCADE"),
        primary_key=True),
    # NOTE: the hash of the token (see hash_token)
    sa.Column("token_hash", sa.Text, nullable=False),
    sa.Column("new_email", sa.Text, nullable=False),
    sa.Column("expires", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint(
        "token_hash", name="user_email_changes_token_hash_key"),
    sa.Index("user_email_changes_expires_idx", "expires"),
)


# NOTE: sessions and worker tokens are keyed by the account's ids rather than
# by its row because the admin (configured in the environment) has no row in
# USERS but logs in and can register workers like everybody else. deleting
# a user removes them explicitly
SESSIONS = sa.Table(
    "user_sessions",
    METADATA,
    # NOTE: the hash of the token (see hash_token)
    sa.Column("token_hash", sa.Text, primary_key=True),
    sa.Column("account_key", sa.Text, nullable=False),
    sa.Column(
        "created",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now()),  # pylint: disable=not-callable
    sa.Index("user_sessions_account_key_idx", "account_key"),
)


WORKER_TOKENS = sa.Table(
    "user_worker_tokens",
    METADATA,
    sa.Column("user_id", sa.Text, primary_key=True),
    sa.Column("token", sa.Text, nullable=False),
    sa.Column(
        "created",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now()),  # pylint: disable=not-callable
)


META = sa.Table(
    "user_store_meta",
    METADATA,
    sa.Column("key", sa.Text, primary_key=True),
    sa.Column("value", sa.Text, nullable=False),
)


def _now() -> Any:
    # NOTE: the database clock (the start of the transaction) is used for
    # every expiration so the server's clock does not matter
    return sa.func.now()  # pylint: disable=not-callable


def _in_seconds(seconds: float) -> Any:
    return _now() + sa.literal(
        datetime.timedelta(seconds=seconds), sa.Interval())


def _user_id_of(email: UName) -> Any:
    return sa.select(USERS.c.id).where(
        USERS.c.email == email.get()).scalar_subquery()


class DBUserManager(UserManager):
    def __init__(
            self,
            *,
            admin_email: UName | None,
            admin_pw: str | None,
            engine: sa.Engine,
            schema: str = DEFAULT_SCHEMA) -> None:
        super().__init__(admin_email=admin_email, admin_pw=admin_pw)
        self._engine = engine
        self._schema = schema
        self._admin_key = (
            None if admin_email is None else derive_account_key(admin_email))
        self.init_db()

    # *** schema ***

    def init_db(self) -> None:
        """
        Creates the schema and the tables if they do not exist yet, and
        brings tables of an older version up to date (once, in one
        transaction, when the server starts).
        """
        with self._engine.begin() as conn:
            if self._schema != DEFAULT_SCHEMA:
                conn.execute(sa.schema.CreateSchema(
                    self._schema, if_not_exists=True))
            # NOTE: one server at a time sets up the tables
            conn.execute(
                sa.select(sa.func.pg_advisory_xact_lock(
                    sa.func.hashtext(f"swai_users:{self._schema}"))))
            inspector = sa.inspect(conn)
            if inspector.has_table(USERS.name, schema=self._schema):
                if inspector.has_table(META.name, schema=self._schema):
                    version = int(conn.execute(
                        sa.select(META.c.value)
                        .where(META.c.key == "version")).scalar_one())
                else:
                    version = 1
                if version < 2:
                    self._migrate_v1_to_v2(conn)
                if version < 3:
                    self._migrate_v2_to_v3(conn)
            METADATA.create_all(conn, checkfirst=True)
            conn.execute(
                pg_insert(META)
                .values(key="version", value=f"{SCHEMA_VERSION}")
                .on_conflict_do_update(
                    index_elements=[META.c.key],
                    set_={"value": f"{SCHEMA_VERSION}"}))

    def _table(self, conn: sa.Connection, name: str) -> str:
        quote = conn.dialect.identifier_preparer.quote
        return f"{quote(self._schema)}.{quote(name)}"

    def _migrate_v1_to_v2(self, conn: sa.Connection) -> None:
        """
        Accounts get the ids derived from their email, which are the ids
        they had implicitly: their chats, worker token and workers stay
        theirs. Sessions and worker tokens move from the email to these ids
        (the admin's as well).

        Args:
            conn (sa.Connection): The connection in the migration
                transaction.
        """

        def run(sql: str, **params: str) -> sa.CursorResult:
            return conn.execute(sa.text(sql), params)

        users = self._table(conn, USERS.name)
        sessions = self._table(conn, SESSIONS.name)
        workers = self._table(conn, WORKER_TOKENS.name)
        run(
            f"ALTER TABLE {users} "
            "ADD COLUMN user_id TEXT, ADD COLUMN account_key TEXT")
        for row_id, email in run(f"SELECT id, email FROM {users}").all():
            run(
                f"UPDATE {users} SET user_id = :user_id, "
                "account_key = :account_key WHERE id = :row_id",
                user_id=derive_user_id(UName(email)).to_parseable(),
                account_key=derive_account_key(UName(email)),
                row_id=row_id)
        run(
            f"ALTER TABLE {users} "
            "ALTER COLUMN user_id SET NOT NULL, "
            "ALTER COLUMN account_key SET NOT NULL, "
            "ADD CONSTRAINT users_user_id_key UNIQUE (user_id), "
            "ADD CONSTRAINT users_account_key_key UNIQUE (account_key)")
        run(f"ALTER TABLE {sessions} ADD COLUMN account_key TEXT")
        for (email,) in run(f"SELECT DISTINCT email FROM {sessions}").all():
            run(
                f"UPDATE {sessions} SET account_key = :account_key "
                "WHERE email = :email",
                account_key=derive_account_key(UName(email)),
                email=email)
        run(
            f"ALTER TABLE {sessions} "
            "ALTER COLUMN account_key SET NOT NULL, DROP COLUMN email")
        run(
            "CREATE INDEX user_sessions_account_key_idx "
            f"ON {sessions} (account_key)")
        run(f"ALTER TABLE {workers} ADD COLUMN user_id TEXT")
        for (email,) in run(f"SELECT email FROM {workers}").all():
            run(
                f"UPDATE {workers} SET user_id = :user_id "
                "WHERE email = :email",
                user_id=derive_user_id(UName(email)).to_parseable(),
                email=email)
        run(
            f"ALTER TABLE {workers} DROP COLUMN email, "
            "ALTER COLUMN user_id SET NOT NULL, ADD PRIMARY KEY (user_id)")

    def _migrate_v2_to_v3(self, conn: sa.Connection) -> None:
        """
        Session and reset tokens were stored as they are; the tables have
        their hashes now. The old entries could never match a hash (and
        could be read from the tables), so they are removed: everybody logs
        in again and outstanding reset links stop working, once.

        Args:
            conn (sa.Connection): The connection in the migration
                transaction.
        """
        users = self._table(conn, USERS.name)
        for table in (SESSIONS, RESET_TOKENS):
            name = self._table(conn, table.name)
            conn.execute(sa.text(f"DELETE FROM {name}"))
            conn.execute(sa.text(
                f"ALTER TABLE {name} RENAME COLUMN token TO token_hash"))
        conn.execute(sa.text(f"UPDATE {users} SET reset_cooldown = NULL"))

    def close(self) -> None:
        """Closes all connections."""
        self._engine.dispose()

    # *** accounts ***

    def do_get_ids(self, email: UName) -> AccountIds | None:
        with self._engine.connect() as conn:
            res = conn.execute(
                sa.select(USERS.c.user_id, USERS.c.account_key)
                .where(USERS.c.email == email.get())).first()
        if res is None:
            return None
        return {
            "user_id": UserId.parse(res.user_id),
            "account_key": res.account_key,
        }

    def _account_key(self, email: UName) -> AccountKey | None:
        if self.is_admin(email):
            return self._admin_key
        ids = self.do_get_ids(email)
        return None if ids is None else ids["account_key"]

    def do_create_user(self, email: UName, display_name: str) -> bool:
        if self.is_admin(email):
            raise ValueError("cannot set info for admin")
        # NOTE: the ids derived from the email belong to another account if
        # an account with this email had its email changed. then the new
        # account gets random ids: it must not get that account's chats
        account_key = derive_account_key(email)
        user_id = derive_user_id(email)
        for _ in range(3):
            # NOTE: of two concurrent registrations for the same email the
            # second waits for the first and then inserts nothing
            with self._engine.begin() as conn:
                res = conn.execute(
                    pg_insert(USERS)
                    .values(
                        email=email.get(),
                        display_name=display_name,
                        user_id=user_id.to_parseable(),
                        account_key=account_key)
                    .on_conflict_do_nothing()
                    .returning(USERS.c.id)).first()
                if res is not None:
                    return True
                if conn.execute(
                        sa.select(USERS.c.id)
                        .where(USERS.c.email == email.get())).first():
                    return False
            account_key = random_account_key()
            user_id = random_user_id()
        raise ValueError(f"could not find free ids for {email}")

    def do_delete_user(self, email: UName) -> bool:
        with self._engine.begin() as conn:
            # NOTE: capabilities, reset tokens and a pending email change are
            # removed by the cascade
            res = conn.execute(
                sa.delete(USERS)
                .where(USERS.c.email == email.get())
                .returning(USERS.c.user_id, USERS.c.account_key)).first()
            if res is None:
                return False
            conn.execute(
                sa.delete(SESSIONS)
                .where(SESSIONS.c.account_key == res.account_key))
            conn.execute(
                sa.delete(WORKER_TOKENS)
                .where(WORKER_TOKENS.c.user_id == res.user_id))
        return True

    def do_change_email(self, email: UName, new_email: UName) -> bool:
        with self._engine.begin() as conn:
            try:
                # NOTE: the unique email makes a second change to the same
                # email wait for the first and then fail
                with conn.begin_nested():
                    res = conn.execute(
                        sa.update(USERS)
                        .where(USERS.c.email == email.get())
                        .values(email=new_email.get(), reset_cooldown=None)
                        .returning(USERS.c.id, USERS.c.account_key)).first()
            except sa.exc.IntegrityError:
                return False
            if res is None:
                return False
            conn.execute(
                sa.delete(SESSIONS)
                .where(SESSIONS.c.account_key == res.account_key))
            # NOTE: a reset link sent to the old address must not work anymore
            conn.execute(
                sa.delete(RESET_TOKENS)
                .where(RESET_TOKENS.c.user_id == res.id))
            # NOTE: a pending change was requested for the old email
            conn.execute(
                sa.delete(EMAIL_CHANGES)
                .where(EMAIL_CHANGES.c.user_id == res.id))
        return True

    def do_request_email_change(
            self, email: UName, new_email: UName) -> EmailChangeToken | None:
        token: EmailChangeToken = uuid.uuid4().hex
        with self._engine.begin() as conn:
            conn.execute(
                sa.delete(EMAIL_CHANGES)
                .where(EMAIL_CHANGES.c.expires <= _now()))
            # NOTE: the row lock orders the request with a concurrent email
            # change or deletion of the account (which remove the pending
            # change): a pending change always belongs to the account's
            # current email. the new email is checked again when the change
            # is confirmed
            user_id = conn.execute(
                sa.select(USERS.c.id)
                .where(USERS.c.email == email.get())
                .with_for_update()).scalar_one_or_none()
            if user_id is None:
                return None
            if conn.execute(
                    sa.select(USERS.c.id)
                    .where(USERS.c.email == new_email.get())).first():
                return None
            stmt = pg_insert(EMAIL_CHANGES).values(
                user_id=user_id,
                token_hash=hash_token(token),
                new_email=new_email.get(),
                expires=_in_seconds(self.email_change_expire()))
            # NOTE: a new request replaces the pending change (and its token)
            conn.execute(stmt.on_conflict_do_update(
                index_elements=[EMAIL_CHANGES.c.user_id],
                set_={
                    "token_hash": stmt.excluded.token_hash,
                    "new_email": stmt.excluded.new_email,
                    "expires": stmt.excluded.expires,
                }))
        return token

    def take_email_change(self, token: EmailChangeToken) -> EmailChange | None:
        with self._engine.begin() as conn:
            # NOTE: deleting the row is what makes the token single use: of
            # two concurrent uses only one gets the row back
            res = conn.execute(
                sa.delete(EMAIL_CHANGES)
                .where(
                    EMAIL_CHANGES.c.token_hash == hash_token(token),
                    EMAIL_CHANGES.c.expires > _now())
                .returning(
                    EMAIL_CHANGES.c.user_id,
                    EMAIL_CHANGES.c.new_email)).first()
            if res is None:
                return None
            email = conn.execute(
                sa.select(USERS.c.email)
                .where(USERS.c.id == res.user_id)).scalar_one_or_none()
        if email is None:
            # NOTE: the account was deleted in the meantime
            return None
        return {
            "email": UName(email),
            "new_email": UName(res.new_email),
        }

    # *** sessions ***

    def do_login(self, email: UName) -> SessionToken | None:
        token: SessionToken = uuid.uuid4().hex
        with self._engine.begin() as conn:
            if self.is_admin(email):
                conn.execute(sa.insert(SESSIONS).values(
                    token_hash=hash_token(token),
                    account_key=self._admin_key))
                return token
            # NOTE: the row is locked so that a concurrent email change (which
            # ends all sessions) either comes first and nothing is inserted
            # or waits for the session and then ends it
            res = conn.execute(
                sa.insert(SESSIONS)
                .from_select(
                    ["token_hash", "account_key"],
                    sa.select(
                        sa.literal(hash_token(token)), USERS.c.account_key)
                    .where(USERS.c.email == email.get())
                    .with_for_update(read=True))
                .returning(SESSIONS.c.token_hash)).first()
        return None if res is None else token

    def logout(self, token: SessionToken) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                sa.delete(SESSIONS)
                .where(SESSIONS.c.token_hash == hash_token(token)))

    def count_sessions(self, email: UName) -> int:
        account_key = self._account_key(email)
        if account_key is None:
            return 0
        with self._engine.connect() as conn:
            return conn.execute(
                sa.select(sa.func.count())  # pylint: disable=not-callable
                .select_from(SESSIONS)
                .where(SESSIONS.c.account_key == account_key)).scalar_one()

    def logout_everywhere(self, email: UName) -> None:
        account_key = self._account_key(email)
        if account_key is None:
            return
        with self._engine.begin() as conn:
            conn.execute(
                sa.delete(SESSIONS)
                .where(SESSIONS.c.account_key == account_key))

    def get_email(self, token: SessionToken) -> UName | None:
        with self._engine.connect() as conn:
            res = conn.execute(
                sa.select(SESSIONS.c.account_key, USERS.c.email)
                .select_from(SESSIONS.outerjoin(
                    USERS, USERS.c.account_key == SESSIONS.c.account_key))
                .where(SESSIONS.c.token_hash == hash_token(token))).first()
        if res is None:
            return None
        if res.account_key == self._admin_key:
            return self.get_admin()
        if res.email is None:
            # NOTE: the account is gone
            return None
        return UName(res.email)

    # *** passwords ***

    def do_generate_reset_token(self, email: UName) -> ResetToken | None:
        reset_token: ResetToken = uuid.uuid4().hex
        with self._engine.begin() as conn:
            conn.execute(
                sa.delete(RESET_TOKENS)
                .where(RESET_TOKENS.c.expires <= _now()))
            # NOTE: one statement whether or not the account exists: no token
            # for unknown emails and no difference in how long the check
            # takes. the row lock makes concurrent requests wait and then see
            # the cooldown
            user_id = conn.execute(
                sa.update(USERS)
                .where(
                    USERS.c.email == email.get(),
                    sa.or_(
                        USERS.c.reset_cooldown.is_(None),
                        USERS.c.reset_cooldown <= _now()))
                .values(reset_cooldown=_in_seconds(self.reset_cooldown()))
                .returning(USERS.c.id)).scalar_one_or_none()
            if user_id is None:
                return None
            conn.execute(sa.insert(RESET_TOKENS).values(
                token_hash=hash_token(reset_token),
                user_id=user_id,
                expires=_in_seconds(self.reset_expire())))
        return reset_token

    def get_email_for_reset_token(
            self, reset_token: ResetToken) -> UName | None:
        with self._engine.connect() as conn:
            res = conn.execute(
                sa.select(USERS.c.email)
                .select_from(RESET_TOKENS.join(USERS))
                .where(
                    RESET_TOKENS.c.token_hash == hash_token(reset_token),
                    RESET_TOKENS.c.expires > _now())).scalar_one_or_none()
        if res is None:
            return None
        return UName(res)

    def set_password_hash(
            self,
            email: UName,
            hashpw: HashPassword,
            reset_token: ResetToken) -> bool:
        with self._engine.begin() as conn:
            # NOTE: deleting the token is what makes it single use: of two
            # concurrent uses only one gets the row back
            user_id = conn.execute(
                sa.delete(RESET_TOKENS)
                .where(
                    RESET_TOKENS.c.token_hash == hash_token(reset_token),
                    RESET_TOKENS.c.expires > _now(),
                    RESET_TOKENS.c.user_id == _user_id_of(email))
                .returning(RESET_TOKENS.c.user_id)).scalar_one_or_none()
            if user_id is None:
                return False
            conn.execute(
                sa.update(USERS)
                .where(USERS.c.id == user_id)
                .values(hashpw=hashpw, reset_cooldown=None))
        return True

    def get_password_hash(self, email: UName) -> HashPassword | None:
        with self._engine.connect() as conn:
            return conn.execute(
                sa.select(USERS.c.hashpw)
                .where(USERS.c.email == email.get())).scalar_one_or_none()

    def do_get_user_info(self, email: UName) -> UserInfo:
        with self._engine.connect() as conn:
            display_name = conn.execute(
                sa.select(USERS.c.display_name)
                .where(USERS.c.email == email.get())).scalar_one_or_none()
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
        with self._engine.connect() as conn:
            res = conn.execute(
                sa.select(CAPABILITIES.c.capability)
                .where(
                    CAPABILITIES.c.user_id == _user_id_of(email),
                    CAPABILITIES.c.capability == capability)).first()
        return res is not None

    def do_set_capability(
            self,
            email: UName,
            capability: CapabilityName,
            *,
            has: bool) -> None:
        with self._engine.begin() as conn:
            if has:
                conn.execute(
                    pg_insert(CAPABILITIES)
                    .from_select(
                        ["user_id", "capability"],
                        sa.select(USERS.c.id, sa.literal(capability))
                        .where(USERS.c.email == email.get()))
                    .on_conflict_do_nothing())
            else:
                conn.execute(
                    sa.delete(CAPABILITIES)
                    .where(
                        CAPABILITIES.c.user_id == _user_id_of(email),
                        CAPABILITIES.c.capability == capability))

    def do_list_capabilities(self, email: UName) -> set[CapabilityName]:
        stmt = sa.select(CAPABILITIES.c.capability).where(
            CAPABILITIES.c.user_id == _user_id_of(email))
        with self._engine.connect() as conn:
            caps = conn.execute(stmt).scalars().all()
        return {as_capability(cap) for cap in caps}

    def do_list_users(self) -> Iterable[UName]:
        stmt = sa.select(USERS.c.email).order_by(USERS.c.email)
        with self._engine.connect() as conn:
            emails = conn.execute(stmt).scalars().all()
        yield from (UName(email) for email in emails)

    def store_worker_token(
            self, user_id: UserId, worker_token: WorkerToken) -> None:
        stmt = pg_insert(WORKER_TOKENS).values(
            user_id=user_id.to_parseable(), token=worker_token)
        with self._engine.begin() as conn:
            conn.execute(stmt.on_conflict_do_update(
                index_elements=[WORKER_TOKENS.c.user_id],
                set_={
                    "token": stmt.excluded.token,
                    "created": _now(),
                }))

    def get_worker_token(self, user_id: UserId) -> WorkerToken | None:
        stmt = sa.select(WORKER_TOKENS.c.token).where(
            WORKER_TOKENS.c.user_id == user_id.to_parseable())
        with self._engine.connect() as conn:
            return conn.execute(stmt).scalar_one_or_none()
