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
"""Shared fixtures. Every store is backed by redipy's in-memory runtime so the
tests need no Redis server."""
from collections.abc import Iterator
from test.util import ADMIN_EMAIL, ADMIN_PW, memory_redis, UNUSED_REDIS
from typing import cast

import pytest
from scattermind.system.session.session import SessionStore

from swai_server.auction import queue as queue_module
from swai_server.auction.queue import TaskQueue
from swai_server.system.user import redis as user_redis_module
from swai_server.system.user.manager import hash_password
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


@pytest.fixture(name="user_mng")
def fixture_user_mng(
        monkeypatch: pytest.MonkeyPatch,
        admin_pw_hash: str) -> Iterator[RedisUserManager]:
    """
    A user manager on an empty in-memory redis with an admin configured.

    Yields:
        RedisUserManager: The user manager.
    """
    monkeypatch.setattr(user_redis_module, "Redis", memory_redis)
    yield RedisUserManager(
        admin_email=ADMIN_EMAIL, admin_pw=admin_pw_hash, cfg=UNUSED_REDIS)


@pytest.fixture(name="sec_ctx")
def fixture_sec_ctx(user_mng: RedisUserManager) -> SecureContext:
    """
    The permission layer the server uses, on top of `user_mng`.

    Returns:
        SecureContext: The secure context.
    """
    return SecureContext(user_mng)
