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
"""Tests for a new prompt that interrupts the previous answer of a chat. The
server side runs `start_llama_response` on the auction queue; the worker side
runs the llama node's prompt execution with a stand-in for the llama.cpp model,
on its own copy of the session as a remote worker would."""
import os
import threading
import time
from collections.abc import Callable, Iterator
from test.util import memory_redis, UNUSED_REDIS
from typing import Any, cast

import pytest
from redipy import Redis
from scattermind.system.base import TaskId, UserId
from scattermind.system.client.client import ComputeTask
from scattermind.system.names import GNamespace, UName
from scattermind.system.response import ResponseObject, TaskStatus
from scattermind.system.session import blob_disk, kv_redis, user_redis
from scattermind.system.session.blob_disk import DiskSessionBlob
from scattermind.system.session.kv_redis import RedisSessionKeyValue
from scattermind.system.session.session import Session, SessionStore
from scattermind.system.session.user_redis import RedisSessionUser

from swai.smind.llama_session import (
    get_active_task,
    get_model_output,
    get_visible_messages,
    handle_model_output,
    VisibleMessage,
)
from swai.smind.nodes.node_llama import execute_prompt
from swai_server.auction.queue import TaskQueue
from swai_server.smind import server_api
from swai_server.smind.server_api import init_llama, start_llama_response


NS = GNamespace("llama")
USER = UName("user@example.com")
WORKER_USER = UName("bee@example.com")
WORKER = "w1"

SHORT_WAIT = 0.2
"""Interrupt timeout for tests where the old task does not stop in time."""
SOME_TIME = 5.0
"""Upper bound for something that is expected to happen; waits end as soon as
it does."""


def make_store(*, blob_path: str, cache_path: str) -> SessionStore:
    return SessionStore(
        RedisSessionUser(UNUSED_REDIS),
        DiskSessionBlob(UNUSED_REDIS, disk_path=blob_path),
        RedisSessionKeyValue(UNUSED_REDIS),
        cache_path=cache_path,
        is_shared=False)


Stores = tuple[SessionStore, SessionStore]


@pytest.fixture(name="stores")
def fixture_stores(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[Stores]:
    """
    The server's and a worker's session store. Both see the same session
    values and blobs (one in-memory redis and one blob folder) but each has
    its own local copy of the session folders, like a remote worker.

    Yields:
        tuple[SessionStore, SessionStore]: The server and the worker store.
    """
    redis = Redis("memory")

    def shared_redis(*_args: Any, **_kwargs: Any) -> Redis:
        return redis

    for module in (blob_disk, kv_redis, user_redis):
        monkeypatch.setattr(module, "Redis", shared_redis)
    blob_path = os.path.join(tmp_path, "blobs")
    yield (
        make_store(
            blob_path=blob_path,
            cache_path=os.path.join(tmp_path, "server")),
        make_store(
            blob_path=blob_path,
            cache_path=os.path.join(tmp_path, "worker")),
    )


@pytest.fixture(name="queue")
def fixture_queue(monkeypatch: pytest.MonkeyPatch) -> Iterator[TaskQueue]:
    """
    A task queue on an empty in-memory redis.

    Yields:
        TaskQueue: The queue.
    """
    # pylint: disable=import-outside-toplevel
    from swai_server.auction import queue as queue_module

    monkeypatch.setattr(queue_module, "Redis", memory_redis)
    yield TaskQueue(cast(SessionStore, None), UNUSED_REDIS)


def new_chat(stores: Stores) -> Session:
    server_store, _ = stores
    session, _ = init_llama(server_store, UserId.create(USER))
    return session


def history(session: Session) -> list[VisibleMessage]:
    """The chat as the client sees it after a reload, without the greeting.
    """
    return get_visible_messages(session)[1:]


def pop(queue: TaskQueue, *, timeout: float = 0.05) -> TaskId | None:
    task = queue.pop_task(
        [NS], user_email=WORKER_USER, worker_name=WORKER, timeout=timeout)
    if task is None:
        return None
    _, task_id, _ = task
    return task_id


def finish(
        queue: TaskQueue,
        task_id: TaskId,
        status: TaskStatus = "ready") -> None:
    response: ResponseObject = {
        "ns": NS,
        "status": status,
        "result": None,
        "duration": 1.0,
        "retries": 0,
        "error": None,
        "fmt": None,
    }
    queue.set_result(
        task_id,
        user_email=WORKER_USER,
        worker_name=WORKER,
        response=response)


class FakeTask:
    """Stands in for the scattermind task the node receives."""
    def __init__(self, task_id: TaskId) -> None:
        self._task_id = task_id

    def is_valid(self) -> bool:
        return True

    def get_task_id(self) -> TaskId:
        return self._task_id


class FakeModel:
    """
    Stands in for the llama.cpp model: streams the given chunks. `before`
    is called before a chunk is produced, so a test can stall the model.
    """
    def __init__(
            self,
            chunks: list[str],
            *,
            before: Callable[[int], None] | None = None) -> None:
        self._chunks = chunks
        self._before = before
        self.chat: list[Any] | None = None

    def set_seed(self, seed: int) -> None:
        pass

    def create_chat_completion(
            self, messages: list[Any], **_kwargs: Any) -> Iterator[Any]:
        self.chat = list(messages)
        for ix, chunk in enumerate(self._chunks):
            if self._before is not None:
                self._before(ix)
            yield {"choices": [{"delta": {"content": chunk}}]}


def run_worker(
        stores: Stores,
        queue: TaskQueue,
        session: Session,
        task_id: TaskId,
        *,
        prompt: str,
        model: FakeModel) -> str:
    """What the provider and the llama node do with a task they bid on."""
    _, worker_store = stores
    worker_session = worker_store.get_session(session.get_session_id())
    with Session.get_local_folders([worker_session]) as cache_dirs:
        res = execute_prompt(
            cast(Any, model),
            prompt,
            cache_dir=cache_dirs[0],
            session=worker_session,
            task=cast(ComputeTask, FakeTask(task_id)))
    finish(queue, task_id)
    return res


def start_worker(*args: Any, **kwargs: Any) -> threading.Thread:
    th = threading.Thread(
        target=run_worker, args=args, kwargs=kwargs, daemon=True)
    th.start()
    return th


def wait_for_output(session: Session, task_id: TaskId) -> str:
    text, _ = get_model_output(session, (task_id, 0), timeout=SOME_TIME)
    assert text
    return text


def test_answer_without_interruption(
        stores: Stores, queue: TaskQueue) -> None:
    """Baseline: a finished answer is stored as is."""
    session = new_chat(stores)
    task_id = start_llama_response(queue, NS, "hi", session)
    assert task_id is not None
    assert pop(queue) == task_id
    run_worker(
        stores,
        queue,
        session,
        task_id,
        prompt="hi",
        model=FakeModel(["Hello", " there"]))
    assert history(session) == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "Hello there"},
    ]
    assert get_active_task(session) is None


def test_interrupt_stops_running_answer(
        stores: Stores, queue: TaskQueue) -> None:
    """A worker that stops when asked stores its answer so far, marked as
    cut off, exactly once; the new prompt follows it."""
    session = new_chat(stores)
    prev_id = start_llama_response(queue, NS, "hi", session)
    assert prev_id is not None
    assert pop(queue) == prev_id

    def before(_ix: int) -> None:
        time.sleep(0.01)

    th = start_worker(
        stores,
        queue,
        session,
        prev_id,
        prompt="hi",
        model=FakeModel(
            ["Hello", " there"] + [" and on"] * 1000, before=before))
    assert wait_for_output(session, prev_id).startswith("Hello")
    start = time.monotonic()
    task_id = start_llama_response(queue, NS, "next", session)
    # the worker stopped right away; no need to wait for the timeout
    assert time.monotonic() - start < server_api.INTERRUPT_TIMEOUT
    th.join(SOME_TIME)
    assert not th.is_alive()
    assert task_id is not None
    assert get_active_task(session) == task_id
    msgs = history(session)
    assert [msg["role"] for msg in msgs] == ["user", "assistant", "user"]
    assert msgs[0]["content"] == "hi"
    assert msgs[1]["content"].startswith("Hello there")
    assert msgs[1]["content"].endswith(" …")
    assert msgs[2]["content"] == "next"


def test_interrupt_vanished_worker(
        stores: Stores,
        queue: TaskQueue,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A worker that does not stop in time loses its task: the server waits
    only `INTERRUPT_TIMEOUT`, stores what was streamed so far (marked as cut
    off) and moves on. When the worker comes back, neither its history nor
    its result count."""
    monkeypatch.setattr(server_api, "INTERRUPT_TIMEOUT", SHORT_WAIT)
    session = new_chat(stores)
    prev_id = start_llama_response(queue, NS, "hi", session)
    assert prev_id is not None
    assert pop(queue) == prev_id
    release = threading.Event()

    def before(ix: int) -> None:
        if ix == 2:
            # the worker stalls (or loses its connection) for a while
            release.wait(SOME_TIME)

    th = start_worker(
        stores,
        queue,
        session,
        prev_id,
        prompt="hi",
        model=FakeModel(["Hello", " there", " and more"], before=before))
    assert wait_for_output(session, prev_id) == "Hello there"
    start = time.monotonic()
    task_id = start_llama_response(queue, NS, "next", session)
    assert time.monotonic() - start < SOME_TIME
    assert task_id is not None
    expected: list[VisibleMessage] = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "Hello there …"},
        {"role": "user", "content": "next"},
    ]
    assert history(session) == expected
    assert get_active_task(session) == task_id
    # the old task is gone from the queue
    assert queue.get_status(prev_id) == "unknown"
    # the worker comes back and finishes its task
    release.set()
    th.join(SOME_TIME)
    assert not th.is_alive()
    assert history(session) == expected
    assert get_active_task(session) == task_id
    assert queue.get_status(prev_id) == "unknown"
    assert queue.get_result(prev_id) is None
    # the next bid gets the new task, not the old one
    assert pop(queue) == task_id
    assert pop(queue) is None


def test_interrupt_task_that_started_late(
        stores: Stores,
        queue: TaskQueue,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A worker that took the task but only starts working on it after it was
    replaced leaves the chat alone."""
    monkeypatch.setattr(server_api, "INTERRUPT_TIMEOUT", SHORT_WAIT)
    session = new_chat(stores)
    prev_id = start_llama_response(queue, NS, "hi", session)
    assert prev_id is not None
    assert pop(queue) == prev_id
    task_id = start_llama_response(queue, NS, "next", session)
    assert task_id is not None
    expected: list[VisibleMessage] = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "…"},
        {"role": "user", "content": "next"},
    ]
    assert history(session) == expected
    model = FakeModel(["Hello"])
    assert run_worker(
        stores, queue, session, prev_id, prompt="hi", model=model) == ""
    assert model.chat is None
    assert history(session) == expected
    assert get_active_task(session) == task_id
    assert queue.get_result(prev_id) is None


def test_interrupt_queued_task(
        stores: Stores,
        queue: TaskQueue,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A task no worker took yet is dropped from the queue; the model sees
    that its turn was cut off before the new prompt."""
    monkeypatch.setattr(server_api, "INTERRUPT_TIMEOUT", SHORT_WAIT)
    session = new_chat(stores)
    prev_id = start_llama_response(queue, NS, "hi", session)
    assert prev_id is not None
    task_id = start_llama_response(queue, NS, "next", session)
    assert task_id is not None
    assert pop(queue) == task_id
    assert pop(queue) is None
    model = FakeModel(["Sure"])
    run_worker(stores, queue, session, task_id, prompt="next", model=model)
    assert model.chat is not None
    assert [msg["content"] for msg in model.chat[-3:]] == [
        "hi", "…", "next"]
    assert history(session)[-1] == {"role": "assistant", "content": "Sure"}


def test_cancel_without_prompt(
        stores: Stores,
        queue: TaskQueue,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty prompt only stops the running answer."""
    monkeypatch.setattr(server_api, "INTERRUPT_TIMEOUT", SHORT_WAIT)
    session = new_chat(stores)
    prev_id = start_llama_response(queue, NS, "hi", session)
    assert prev_id is not None
    assert pop(queue) == prev_id
    handle_model_output(session, prev_id, [], "Hel")
    assert start_llama_response(queue, NS, "", session) is None
    assert get_active_task(session) is None
    assert history(session) == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "Hel …"},
    ]
