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
"""Utility functions for unit tests."""
import contextlib
import os
from collections.abc import Iterable, Iterator
from typing import Any, cast, TYPE_CHECKING, TypeVar

import pytest
import sqlalchemy as sa
from redipy import Redis, RedisConfig
from scattermind.system.names import UName
from scattermind.system.util import to_bool

from swai_server.system.user.db import DBUserManager, EMAIL_CHANGES
from swai_server.system.user.manager import UserManager
from swai_server.system.user.redis import RedisUserManager


if TYPE_CHECKING:
    from scattermind.system.base import TaskId
    from scattermind.system.config.config import Config
    from scattermind.system.response import ResponseObject


T = TypeVar('T')


IS_GH_ACTION: bool | None = None
"""Lookup value whether the current process is run by github actions."""


def is_github_action() -> bool:
    """
    Whether the current process is run by github actions.

    Returns:
        bool: True, if the execution happens from a github actions runner.
    """
    global IS_GH_ACTION  # pylint: disable=global-statement

    if IS_GH_ACTION is None:
        IS_GH_ACTION = to_bool(os.getenv("GITHUB_ACTIONS"))
    return IS_GH_ACTION


def skip_on_gha_if(condition: bool, reason: str) -> None:
    """
    Instructs the test to be skipped if it is run on github actions.

    Args:
        condition (bool): If True, the test will be skipped on github actions.
        reason (str): The reason for the skip.
    """
    if is_github_action() and condition:
        pytest.skip(reason)


def wait_for_tasks(
        config: 'Config',
        tasks: list[tuple['TaskId', T]],
        *,
        timeout: float = 5.0,
        ) -> Iterable[tuple['TaskId', 'ResponseObject', T]]:
    """
    Wait for scattermind tasks to complete. The function does not check by
    itself whether the expected result was returned. But the function ensures
    that all tasks were returned.

    Args:
        config (Config): The configuration.
        tasks (list[tuple[TaskId, T]]): A list of tasks and expected results.
        timeout (float, optional): The maximum time to wait for any task
            to complete. Defaults to 5.0.

    Yields:
        tuple[TaskId, ResponseObject, T]: The task, its response, and the
            expected result.
    """
    task_ids: list['TaskId'] = []
    expected: dict['TaskId', T] = {}
    for task_id, expected_result in tasks:
        assert task_id not in expected
        expected[task_id] = expected_result
        task_ids.append(task_id)
    seen: set['TaskId'] = set()
    for task_id, response in config.wait_for(task_ids, timeout=timeout):
        expected_result = expected[task_id]
        yield task_id, response, expected_result
        seen.add(task_id)
    assert seen == set(task_ids)


ADMIN_EMAIL = UName("admin")
"""The admin account name (the name `make create-admin-pw` suggests)."""
ADMIN_PW = "admin password"
"""The admin's raw password."""
TEST_POSTGRES_URL = "TEST_POSTGRES_URL"
"""The environment variable with the connection URL of the Postgres server
for the tests of the Postgres user store. Every test uses a fresh schema
that is dropped afterwards."""
UNUSED_REDIS: RedisConfig = {
    "host": "localhost",
    "port": 1,
    "passwd": "",
}
"""A server config that is never connected to: the stores are constructed
with it but their redis is replaced by a memory runtime."""


def memory_redis(*_args: Any, **_kwargs: Any) -> Redis:
    """
    Stands in for `redipy.Redis` in the modules under test: whatever
    connection parameters the module passes, it gets a fresh memory runtime.

    Returns:
        Redis: A new, empty in-memory redis.
    """
    return Redis("memory")


class StrictDelete:
    """
    Wraps a redis or a redis pipeline so that `delete` without keys fails,
    as it does on a real redis (`DEL` needs at least one key) but not on
    redipy's memory runtime.
    """
    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def delete(self, *keys: str) -> Any:
        """
        Deletes the keys.

        Args:
            *keys (str): The keys.

        Returns:
            Any: The result of the inner delete.
        """
        if not keys:
            raise ValueError("wrong number of arguments for 'del' command")
        return self._inner.delete(*keys)

    @contextlib.contextmanager
    def pipeline(self) -> Iterator['StrictDelete']:
        """
        Starts a pipeline whose `delete` is strict as well.

        Yields:
            StrictDelete: The pipeline.
        """
        with self._inner.pipeline() as pipe:
            yield StrictDelete(pipe)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def strict_memory_redis(*_args: Any, **_kwargs: Any) -> Redis:
    """
    Like `memory_redis` but `delete` without keys fails like on a real
    redis.

    Returns:
        Redis: A new, empty in-memory redis.
    """
    return cast(Redis, StrictDelete(Redis("memory")))


def stored_email_changes(user_mng: UserManager) -> list[str]:
    """
    The token hashes the store keeps for pending email changes.

    Args:
        user_mng (UserManager): The user manager.

    Returns:
        list[str]: The stored token hashes, sorted.
    """
    # pylint: disable=protected-access
    if isinstance(user_mng, RedisUserManager):
        redis = user_mng._redis
        res: list[str] = []
        for key in redis.keys(match="change:*", block=False):
            value = redis.get_value(key)
            if value is None:
                # NOTE: the memory runtime lists expired keys
                continue
            # the new email is kept next to it, for the same account
            assert redis.get_value(f"change_to:{key.removeprefix('change:')}")
            res.append(value)
        return sorted(res)
    assert isinstance(user_mng, DBUserManager)
    with user_mng._engine.connect() as conn:
        return sorted(conn.execute(
            sa.select(EMAIL_CHANGES.c.token_hash)).scalars())
