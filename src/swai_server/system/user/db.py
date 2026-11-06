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
from scattermind.system.names import UName
from sqlalchemy.dialects.postgresql import insert as pg_insert

from swai.system.user import CapabilityName, WorkerToken
from swai_server.system.db.db import DEFAULT_SCHEMA
from swai_server.system.user.manager import (
    as_capability,
    HashPassword,
    ResetToken,
    SessionToken,
    UserInfo,
    UserManager,
)


CAPABILITY_LENGTH = 40


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
    sa.Column(
        "created",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now()),  # pylint: disable=not-callable
    # NOTE: the unique constraint is what makes concurrent registrations of
    # the same email safe
    sa.UniqueConstraint("email", name="users_email_key"),
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
    sa.Column("token", sa.Text, primary_key=True),
    sa.Column(
        "user_id",
        sa.BigInteger,
        sa.ForeignKey(USERS.c.id, ondelete="CASCADE"),
        nullable=False),
    sa.Column("expires", sa.DateTime(timezone=True), nullable=False),
    sa.Index("user_reset_tokens_user_id_idx", "user_id"),
    sa.Index("user_reset_tokens_expires_idx", "expires"),
)


# NOTE: sessions and worker tokens are keyed by email rather than by user id
# because the admin (configured in the environment) has no row in USERS but
# logs in and can register workers like everybody else. deleting a user
# removes them explicitly
SESSIONS = sa.Table(
    "user_sessions",
    METADATA,
    sa.Column("token", sa.Text, primary_key=True),
    sa.Column("email", sa.Text, nullable=False),
    sa.Column(
        "created",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now()),  # pylint: disable=not-callable
    sa.Index("user_sessions_email_idx", "email"),
)


WORKER_TOKENS = sa.Table(
    "user_worker_tokens",
    METADATA,
    sa.Column("email", sa.Text, primary_key=True),
    sa.Column("token", sa.Text, nullable=False),
    sa.Column(
        "created",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now()),  # pylint: disable=not-callable
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
        self.init_db()

    def init_db(self) -> None:
        """
        Creates the schema and the tables if they do not exist yet. Existing
        tables are left as they are.
        """
        with self._engine.begin() as conn:
            if self._schema != DEFAULT_SCHEMA:
                conn.execute(sa.schema.CreateSchema(
                    self._schema, if_not_exists=True))
            METADATA.create_all(conn, checkfirst=True)

    def close(self) -> None:
        """Closes all connections."""
        self._engine.dispose()

    def do_login(self, email: UName) -> SessionToken | None:
        token: SessionToken = uuid.uuid4().hex
        with self._engine.begin() as conn:
            conn.execute(sa.insert(SESSIONS).values(
                token=token, email=email.get()))
        return token

    def logout(self, token: SessionToken) -> None:
        with self._engine.begin() as conn:
            conn.execute(sa.delete(SESSIONS).where(SESSIONS.c.token == token))

    def get_sessions_for_user(self, email: UName) -> Iterable[SessionToken]:
        with self._engine.connect() as conn:
            tokens = conn.execute(
                sa.select(SESSIONS.c.token)
                .where(SESSIONS.c.email == email.get())
                .order_by(SESSIONS.c.token)).scalars().all()
        yield from tokens

    def do_create_user(self, email: UName, display_name: str) -> bool:
        if self.is_admin(email):
            raise ValueError("cannot set info for admin")
        # NOTE: of two concurrent registrations for the same email the second
        # waits for the first and then inserts nothing
        with self._engine.begin() as conn:
            res = conn.execute(
                pg_insert(USERS)
                .values(email=email.get(), display_name=display_name)
                .on_conflict_do_nothing(index_elements=[USERS.c.email])
                .returning(USERS.c.id)).first()
        return res is not None

    def do_delete_user(self, email: UName) -> bool:
        with self._engine.begin() as conn:
            # NOTE: capabilities and reset tokens are removed by the cascade
            res = conn.execute(
                sa.delete(USERS)
                .where(USERS.c.email == email.get())
                .returning(USERS.c.id)).first()
            conn.execute(
                sa.delete(SESSIONS).where(SESSIONS.c.email == email.get()))
            conn.execute(
                sa.delete(WORKER_TOKENS)
                .where(WORKER_TOKENS.c.email == email.get()))
        return res is not None

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
                token=reset_token,
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
                    RESET_TOKENS.c.token == reset_token,
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
                    RESET_TOKENS.c.token == reset_token,
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

    def get_email(self, token: SessionToken) -> UName | None:
        with self._engine.connect() as conn:
            res = conn.execute(
                sa.select(SESSIONS.c.email, USERS.c.id)
                .select_from(SESSIONS.outerjoin(
                    USERS, USERS.c.email == SESSIONS.c.email))
                .where(SESSIONS.c.token == token)).first()
        if res is None:
            return None
        email = UName(res.email)
        if self.is_admin(email):
            return email
        if res.id is None:
            # NOTE: the account is gone
            return None
        return email

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
            self, email: UName, worker_token: WorkerToken) -> None:
        stmt = pg_insert(WORKER_TOKENS).values(
            email=email.get(), token=worker_token)
        with self._engine.begin() as conn:
            conn.execute(stmt.on_conflict_do_update(
                index_elements=[WORKER_TOKENS.c.email],
                set_={
                    "token": stmt.excluded.token,
                    "created": _now(),
                }))

    def get_worker_token(self, email: UName) -> WorkerToken | None:
        stmt = sa.select(WORKER_TOKENS.c.token).where(
            WORKER_TOKENS.c.email == email.get())
        with self._engine.connect() as conn:
            return conn.execute(stmt).scalar_one_or_none()
