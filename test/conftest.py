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
"""Shared fixtures. Redis stores are backed by redipy's in-memory runtime so
the tests need no Redis server. The user manager fixture runs every test
against the Redis store and against the Postgres store; the latter needs a
Postgres server (see `TEST_POSTGRES_URL` in test/util.py)."""
import os
import uuid
from collections.abc import Iterator
from test.util import (
    ADMIN_EMAIL,
    ADMIN_PW,
    is_github_action,
    memory_redis,
    strict_memory_redis,
    TEST_POSTGRES_URL,
    UNUSED_REDIS,
)
from typing import Any, cast

import pytest
import sqlalchemy as sa
from scattermind.system.session import blob_disk as blob_disk_module
from scattermind.system.session import kv_redis as kv_redis_module
from scattermind.system.session import user_redis as session_user_module
from scattermind.system.session.loader import load_session_store
from scattermind.system.session.session import SessionStore

from swai_server.auction import queue as queue_module
from swai_server.auction.queue import TaskQueue
from swai_server.system.db.db import create_db_engine
from swai_server.system.user import redis as user_redis_module
from swai_server.system.user.db import DBUserManager
from swai_server.system.user.manager import hash_password, UserManager
from swai_server.system.user.redis import RedisUserManager
from swai_server.system.user.secure import SecureContext


@pytest.fixture(name="task_queue")
def fixture_task_queue(monkeypatch: pytest.MonkeyPatch) -> Iterator[TaskQueue]:
    """
    A task queue on an empty in-memory redis.

    Yields:
        TaskQueue: The queue.
    """
    monkeypatch.setattr(queue_module, "Redis", memory_redis)
    # NOTE: TaskQueue only keeps the session store; it never calls it
    yield TaskQueue(cast(SessionStore, None), UNUSED_REDIS)


@pytest.fixture(scope="session", name="admin_pw_hash")
def fixture_admin_pw_hash() -> str:
    """
    The admin password the way the server receives it in `ADMIN_PW`: already
    hashed. Computed once since bcrypt is deliberately slow.

    Returns:
        str: The hashed admin password.
    """
    return hash_password(ADMIN_PW)


@pytest.fixture(name="redis_user_mng")
def fixture_redis_user_mng(
        monkeypatch: pytest.MonkeyPatch,
        admin_pw_hash: str) -> Iterator[RedisUserManager]:
    """
    A redis user manager on an empty in-memory redis with an admin
    configured.

    Yields:
        RedisUserManager: The user manager.
    """
    monkeypatch.setattr(user_redis_module, "Redis", memory_redis)
    yield RedisUserManager(
        admin_email=ADMIN_EMAIL, admin_pw=admin_pw_hash, cfg=UNUSED_REDIS)


@pytest.fixture(scope="session", name="postgres_url")
def fixture_postgres_url() -> str:
    """
    The Postgres server for the tests. Without one the Postgres tests are
    skipped locally and fail on github actions (where the workflow provides
    a server), so that they cannot silently stop running.

    Returns:
        str: The connection URL.
    """
    url = os.environ.get(TEST_POSTGRES_URL, "").strip()
    if not url:
        reason = (
            f"the Postgres tests need {TEST_POSTGRES_URL}, e.g., "
            "postgresql+psycopg2://postgres:pw@localhost:5432/postgres "
            "(see the README)")
        if is_github_action():
            pytest.fail(reason)
        pytest.skip(reason)
    return url


@pytest.fixture(name="pg_schema")
def fixture_pg_schema(postgres_url: str) -> Iterator[str]:
    """
    A fresh schema for one test. It is dropped afterwards with everything in
    it.

    Yields:
        str: The name of the schema.
    """
    schema = f"test_{uuid.uuid4().hex}"
    yield schema
    engine = sa.create_engine(postgres_url)
    try:
        with engine.begin() as conn:
            conn.execute(sa.schema.DropSchema(
                schema, cascade=True, if_exists=True))
    finally:
        engine.dispose()


@pytest.fixture(name="postgres_user_mng")
def fixture_postgres_user_mng(
        postgres_url: str,
        pg_schema: str,
        admin_pw_hash: str) -> Iterator[DBUserManager]:
    """
    A Postgres user manager on an empty schema with an admin configured.

    Yields:
        DBUserManager: The user manager.
    """
    user_mng = DBUserManager(
        admin_email=ADMIN_EMAIL,
        admin_pw=admin_pw_hash,
        engine=create_db_engine(postgres_url, schema=pg_schema),
        schema=pg_schema)
    try:
        yield user_mng
    finally:
        user_mng.close()


USER_STORES = ["redis", "postgres"]
"""The user manager backends every user manager test runs against."""


@pytest.fixture(name="user_mng", params=USER_STORES)
def fixture_user_mng(request: pytest.FixtureRequest) -> UserManager:
    """
    An empty user manager with an admin configured, once for each backend.

    Returns:
        UserManager: The user manager.
    """
    return request.getfixturevalue(f"{request.param}_user_mng")


@pytest.fixture(name="sec_ctx")
def fixture_sec_ctx(user_mng: UserManager) -> SecureContext:
    """
    The permission layer the server uses, on top of `user_mng`.

    Returns:
        SecureContext: The secure context.
    """
    return SecureContext(user_mng)


@pytest.fixture(name="session_store")
def fixture_session_store(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Any) -> SessionStore:
    """
    A session store (where chats are kept) on in-memory redis and a
    temporary folder.

    Returns:
        SessionStore: The session store.
    """
    # NOTE: deleting without keys must fail as on a real redis: removing a
    # chat without values does that
    for module in (blob_disk_module, kv_redis_module, session_user_module):
        monkeypatch.setattr(module, "create_redis", strict_memory_redis)
    return load_session_store({
        "user": {"name": "redis", "cfg": UNUSED_REDIS},
        "key_value": {"name": "redis", "cfg": UNUSED_REDIS},
        "blob": {
            "name": "disk",
            "cfg": UNUSED_REDIS,
            "disk_path": os.path.join(tmp_path, "disk"),
        },
        "cache_path": os.path.join(tmp_path, "cache"),
        "is_shared": False,
    })
