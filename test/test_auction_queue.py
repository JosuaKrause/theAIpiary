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
"""Tests for the auction queue that hands chat tasks to workers."""
import threading
import time
from collections.abc import Callable, Iterator
from test.util import memory_redis, UNUSED_REDIS
from typing import Any, cast

import pytest
from redipy import Redis
from scattermind.api.api import task_input_to_redis
from scattermind.system.base import TaskId
from scattermind.system.names import GNamespace, UName
from scattermind.system.response import ResponseObject, TaskStatus
from scattermind.system.session.session import SessionStore

from swai.system.base import get_worker_id
from swai_server.auction import queue as queue_module
from swai_server.auction.queue import (
    HEARTBEAT,
    redis_to_task_worker,
    task_worker_to_redis,
    TaskQueue,
)


NS_A = GNamespace("alpha")
NS_B = GNamespace("beta")
ALICE = UName("alice@example.com")
BOB = UName("bob@example.com")

FAST_HEARTBEAT = 0.5
"""Heartbeat lifetime for tests where a worker has to vanish. The cleaner
thread then runs every `FAST_HEARTBEAT / 2` seconds."""
NO_TASK = 0.05
"""Bid timeout for a pop that is expected to find nothing."""
SOME_TASK = 5.0
"""Bid timeout for a pop that is expected to receive a task eventually. It is
an upper bound only: the pop returns as soon as the task arrives."""


@pytest.fixture(name="queue_redis")
def fixture_queue_redis(monkeypatch: pytest.MonkeyPatch) -> Redis:
    """
    The in-memory redis that the next `TaskQueue` created in the test runs
    on. Tests use it to look at the raw state (e.g. leftover keys) or to
    interleave other work with the queue's redis calls.

    Returns:
        Redis: The redis of the queue under test.
    """
    redis = memory_redis()
    monkeypatch.setattr(
        queue_module, "Redis", lambda *_args, **_kwargs: redis)
    return redis


@pytest.fixture(name="fast_queue")
def fixture_fast_queue(
        monkeypatch: pytest.MonkeyPatch,
        queue_redis: Redis) -> Iterator[TaskQueue]:
    """
    A task queue whose worker heartbeats expire after `FAST_HEARTBEAT`
    seconds and whose cleaner thread runs accordingly often, so a worker that
    stops sending heartbeats is noticed within a test. It runs on
    `queue_redis`.

    Yields:
        TaskQueue: The queue.
    """
    assert queue_redis is not None  # NOTE: requested so the queue uses it
    monkeypatch.setattr(queue_module, "HEARTBEAT", FAST_HEARTBEAT)
    yield TaskQueue(cast(SessionStore, None), UNUSED_REDIS)


@pytest.fixture(name="quiet_queue")
def fixture_quiet_queue(queue_redis: Redis) -> TaskQueue:
    """
    A task queue on `queue_redis` whose cleaner thread never runs on its
    own: a test calls `requeue_unavailable_worker_tasks` itself, so that it
    alone decides when the cleaner runs.

    Returns:
        TaskQueue: The queue.
    """
    assert queue_redis is not None  # NOTE: requested so the queue uses it
    queue = TaskQueue(cast(SessionStore, None), UNUSED_REDIS)
    # NOTE: the cleaner thread waits for HEARTBEAT / 2 (5min) unless woken
    queue.start_cleaner = lambda: None  # type: ignore[method-assign]
    return queue


def leftover_keys(redis: Redis, kind: str) -> list[str]:
    """
    All keys of one kind that the queue keeps per task (or per namespace).

    Args:
        redis (Redis): The redis of the queue.
        kind (str): The kind, e.g., "worker" or "status".

    Returns:
        list[str]: The keys.
    """
    return sorted(redis.keys(match=f"{kind}:*", block=True))


def enqueue(queue: TaskQueue, ns: GNamespace, prompt: str) -> TaskId:
    return queue.enqueue_task(ns, {"prompt": prompt})


def pop(
        queue: TaskQueue,
        nss: list[GNamespace],
        *,
        user: UName = ALICE,
        worker: str = "w1",
        timeout: float = NO_TASK) -> TaskId | None:
    task = queue.pop_task(
        nss, user_email=user, worker_name=worker, timeout=timeout)
    if task is None:
        return None
    _, task_id, _ = task
    return task_id


def response(status: TaskStatus = "ready") -> ResponseObject:
    return {
        "ns": NS_A,
        "status": status,
        "result": None,
        "duration": 1.5,
        "retries": 0,
        "error": None,
        "fmt": None,
    }


def finish(
        queue: TaskQueue,
        task_id: TaskId,
        *,
        user: UName = ALICE,
        worker: str = "w1",
        status: TaskStatus = "ready") -> None:
    queue.set_result(
        task_id,
        user_email=user,
        worker_name=worker,
        response=response(status))


# *** task worker serialization ***


def test_task_worker_roundtrip() -> None:
    worker_id = get_worker_id(ALICE, "w1")
    text = task_worker_to_redis({"ns": NS_A, "worker_id": worker_id})
    res = redis_to_task_worker(text)
    assert res is not None
    assert res["ns"] == NS_A
    assert res["worker_id"] == worker_id


@pytest.mark.parametrize("text", [None, ""])
def test_task_worker_missing(text: str | None) -> None:
    assert redis_to_task_worker(text) is None


def test_worker_id() -> None:
    assert get_worker_id(ALICE, "w1") == get_worker_id(ALICE, "w1")
    # the same worker name under two accounts is two workers
    assert get_worker_id(ALICE, "w1") != get_worker_id(BOB, "w1")
    assert get_worker_id(ALICE, "w1") != get_worker_id(ALICE, "w2")
    with pytest.raises(ValueError, match="cannot be empty"):
        get_worker_id(ALICE, "")


# *** enqueue and pop ***


def test_enqueue_and_pop(task_queue: TaskQueue) -> None:
    task_id = enqueue(task_queue, NS_A, "hello")
    assert task_queue.get_status(task_id) == "wait"
    task = task_queue.pop_task(
        [NS_A], user_email=ALICE, worker_name="w1", timeout=NO_TASK)
    assert task is not None
    ns, popped_id, input_str = task
    assert ns == NS_A
    assert popped_id == task_id
    assert input_str == task_input_to_redis({"prompt": "hello"})
    assert task_queue.get_status(task_id) == "busy"
    # a task is handed out only once
    assert pop(task_queue, [NS_A], worker="w2") is None


def test_pop_empty_times_out(task_queue: TaskQueue) -> None:
    start = time.monotonic()
    assert pop(task_queue, [NS_A, NS_B], timeout=0.2) is None
    assert time.monotonic() - start >= 0.2


def test_pop_without_namespaces(task_queue: TaskQueue) -> None:
    enqueue(task_queue, NS_A, "hello")
    assert pop(task_queue, []) is None


def test_fifo_within_namespace(task_queue: TaskQueue) -> None:
    task_ids = [enqueue(task_queue, NS_A, f"p{ix}") for ix in range(5)]
    popped = [pop(task_queue, [NS_A]) for _ in task_ids]
    assert popped == task_ids
    assert pop(task_queue, [NS_A]) is None


def test_worker_only_receives_its_namespaces(task_queue: TaskQueue) -> None:
    task_b = enqueue(task_queue, NS_B, "for b")
    assert pop(task_queue, [NS_A]) is None
    assert pop(task_queue, [NS_A, NS_B]) == task_b


def test_namespace_order_is_priority(task_queue: TaskQueue) -> None:
    """A worker lists its namespaces in order of preference: it drains the
    first one before it takes anything from the next, regardless of which
    task waited longer."""
    task_b = enqueue(task_queue, NS_B, "older")
    task_a1 = enqueue(task_queue, NS_A, "newer")
    task_a2 = enqueue(task_queue, NS_A, "newest")
    assert pop(task_queue, [NS_A, NS_B]) == task_a1
    assert pop(task_queue, [NS_A, NS_B]) == task_a2
    assert pop(task_queue, [NS_A, NS_B]) == task_b

    task_b = enqueue(task_queue, NS_B, "b")
    task_a = enqueue(task_queue, NS_A, "a")
    assert pop(task_queue, [NS_B, NS_A]) == task_b
    assert pop(task_queue, [NS_B, NS_A]) == task_a


def test_pop_waits_for_new_task(task_queue: TaskQueue) -> None:
    """A bid blocks until a task is enqueued, and returns as soon as one is
    rather than when the bid times out."""
    res: list[TaskId | None] = []
    started = threading.Event()

    def bid() -> None:
        started.set()
        res.append(pop(task_queue, [NS_A], timeout=SOME_TASK))

    th = threading.Thread(target=bid, daemon=True)
    start = time.monotonic()
    th.start()
    started.wait()
    time.sleep(0.1)
    task_id = enqueue(task_queue, NS_A, "late")
    th.join(SOME_TASK + 1.0)
    assert not th.is_alive()
    assert res == [task_id]
    assert time.monotonic() - start < SOME_TASK


def test_concurrent_workers_get_distinct_tasks(task_queue: TaskQueue) -> None:
    task_ids = {enqueue(task_queue, NS_A, f"p{ix}") for ix in range(30)}
    received: dict[str, list[TaskId]] = {}

    def work(name: str) -> None:
        mine: list[TaskId] = []
        received[name] = mine
        while True:
            task_id = pop(task_queue, [NS_A], worker=name, timeout=0.2)
            if task_id is None:
                return
            mine.append(task_id)

    ths = [
        threading.Thread(target=work, args=(f"w{ix}",), daemon=True)
        for ix in range(4)
    ]
    for th in ths:
        th.start()
    for th in ths:
        th.join(10.0)
        assert not th.is_alive()
    all_received = [
        task_id for tasks in received.values() for task_id in tasks
    ]
    assert len(all_received) == len(task_ids)
    assert set(all_received) == task_ids


def test_cleared_task_is_skipped(task_queue: TaskQueue) -> None:
    stale = enqueue(task_queue, NS_A, "cancelled")
    task_id = enqueue(task_queue, NS_A, "wanted")
    task_queue.clear_task(stale)
    assert task_queue.get_status(stale) == "unknown"
    assert pop(task_queue, [NS_A], timeout=0.5) == task_id
    assert task_queue.get_status(stale) == "unknown"


def test_bid_is_not_delayed_by_cancelled_tasks(task_queue: TaskQueue) -> None:
    """`start_llama_response` clears a task that is still queued when the
    user sends a new prompt, so cancelled entries at the head of a queue are
    an ordinary state."""
    stale = [enqueue(task_queue, NS_A, f"cancelled {ix}") for ix in range(2)]
    task_id = enqueue(task_queue, NS_A, "wanted")
    for stale_id in stale:
        task_queue.clear_task(stale_id)
    start = time.monotonic()
    assert pop(task_queue, [NS_A], timeout=1.0) == task_id
    assert time.monotonic() - start < 0.5


def test_cancelled_tasks_keep_namespace_priority(
        task_queue: TaskQueue) -> None:
    """A cancelled entry at the head of the preferred namespace does not make
    the bid fall through to the next namespace while a live task waits in
    the preferred one."""
    stale = enqueue(task_queue, NS_A, "cancelled")
    task_a = enqueue(task_queue, NS_A, "wanted first")
    task_b = enqueue(task_queue, NS_B, "wanted second")
    task_queue.clear_task(stale)
    assert pop(task_queue, [NS_A, NS_B]) == task_a
    assert pop(task_queue, [NS_A, NS_B]) == task_b


def test_bid_drains_cancelled_tasks(
        quiet_queue: TaskQueue, queue_redis: Redis) -> None:
    """A bid that only finds cancelled tasks removes all of them and returns
    nothing; a task enqueued afterwards is handed out right away."""
    for ix in range(5):
        quiet_queue.clear_task(enqueue(quiet_queue, NS_A, f"cancelled {ix}"))
    assert pop(quiet_queue, [NS_A]) is None
    assert queue_redis.llen(TaskQueue.queue_key(NS_A)) == 0
    assert not leftover_keys(queue_redis, "status")
    task_id = enqueue(quiet_queue, NS_A, "wanted")
    assert pop(quiet_queue, [NS_A]) == task_id


def test_concurrent_bids_and_cancels(
        quiet_queue: TaskQueue, queue_redis: Redis) -> None:
    """Several workers bid while the queue holds runs of cancelled tasks and
    while users cancel further tasks. No task is handed out twice, no live
    task is lost, no task cancelled before the bids is handed out, and
    nothing of a cancelled task is left behind."""
    nss = [NS_A, NS_B]
    task_ids = [
        enqueue(quiet_queue, nss[ix % 2], f"p{ix}") for ix in range(80)
    ]
    # runs of cancelled entries at and behind the head of both queues
    cancelled_before = {
        task_id for ix, task_id in enumerate(task_ids) if ix % 8 < 4
    }
    for task_id in cancelled_before:
        quiet_queue.clear_task(task_id)
    cancelled_during = [
        task_id for ix, task_id in enumerate(task_ids) if ix % 8 == 5
    ]
    received: dict[str, list[TaskId]] = {}
    go = threading.Event()

    def work(name: str) -> None:
        mine: list[TaskId] = []
        received[name] = mine
        go.wait()
        while True:
            task_id = pop(quiet_queue, nss, worker=name, timeout=0.2)
            if task_id is None:
                return
            mine.append(task_id)

    def cancel() -> None:
        go.wait()
        for task_id in cancelled_during:
            quiet_queue.clear_task(task_id)

    ths = [
        threading.Thread(target=work, args=(f"w{ix}",), daemon=True)
        for ix in range(4)
    ]
    ths.append(threading.Thread(target=cancel, daemon=True))
    for th in ths:
        th.start()
    go.set()
    for th in ths:
        th.join(10.0)
        assert not th.is_alive()
    all_received = [
        task_id for tasks in received.values() for task_id in tasks
    ]
    assert len(all_received) == len(set(all_received))
    live = set(task_ids) - cancelled_before - set(cancelled_during)
    assert live <= set(all_received)
    assert set(all_received) <= live | set(cancelled_during)
    for ns in nss:
        assert queue_redis.llen(TaskQueue.queue_key(ns)) == 0
    for task_id in [*cancelled_before, *cancelled_during]:
        assert quiet_queue.get_status(task_id) == "unknown"
        assert queue_redis.get_value(
            TaskQueue.task_worker_key(task_id)) is None


def test_cancel_during_bid_leaves_nothing_behind(
        quiet_queue: TaskQueue,
        queue_redis: Redis,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A user cancels a task at the moment a bid reads its input. Whatever
    the bid then returns, the cancelled task must not come back to life as
    busy, and the worker's late result is dropped."""
    task_id = enqueue(quiet_queue, NS_A, "hello")
    input_key = TaskQueue.input_key(task_id)
    original = queue_redis.get_value
    cancelled = False

    def get_value_then_cancel(key: str) -> str | None:
        nonlocal cancelled
        res = original(key)
        if key == input_key and not cancelled:
            cancelled = True
            quiet_queue.clear_task(task_id)
        return res

    monkeypatch.setattr(queue_redis, "get_value", get_value_then_cancel)
    pop(quiet_queue, [NS_A])
    if not cancelled:
        # NOTE: the bid never read the input on its own; the earliest the
        # user can cancel is right after the bid
        quiet_queue.clear_task(task_id)
    monkeypatch.setattr(queue_redis, "get_value", original)
    assert quiet_queue.get_status(task_id) == "unknown"
    assert not leftover_keys(queue_redis, "worker")
    finish(quiet_queue, task_id)
    assert quiet_queue.get_result(task_id) is None
    assert quiet_queue.get_status(task_id) == "unknown"


class SimulatedCrash(Exception):
    """The server process dies in the middle of a redis interaction."""


def test_crash_during_bid_does_not_lose_task(
        fast_queue: TaskQueue,
        queue_redis: Redis,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The server dies at the first write after a bid took a task off the
    queue. The task must not be lost: it is either still queued or assigned
    to the bidding worker, so that the cleaner hands it to the next worker
    once the first one is gone."""
    task_id = enqueue(fast_queue, NS_A, "hello")
    original = queue_redis.set_value
    crashed = False

    def crash(*args: Any, **kwargs: Any) -> Any:
        nonlocal crashed
        if not crashed:
            crashed = True
            raise SimulatedCrash()
        return original(*args, **kwargs)

    monkeypatch.setattr(queue_redis, "set_value", crash)
    try:
        pop(fast_queue, [NS_A], worker="w1")
    except SimulatedCrash:
        pass
    monkeypatch.setattr(queue_redis, "set_value", original)
    # w1 never reports back
    assert pop(fast_queue, [NS_A], worker="w2", timeout=SOME_TASK) == task_id
    assert fast_queue.get_status(task_id) == "busy"


# *** status ***


def test_status_of_unknown_tasks(task_queue: TaskQueue) -> None:
    assert task_queue.get_status(None) == "unknown"
    assert task_queue.get_status(TaskId.create()) == "unknown"


def test_set_status(task_queue: TaskQueue) -> None:
    task_id = enqueue(task_queue, NS_A, "hello")
    task_queue.set_status(task_id, "error")
    assert task_queue.get_status(task_id) == "error"


# *** results ***


def test_result_from_assigned_worker(task_queue: TaskQueue) -> None:
    task_id = enqueue(task_queue, NS_A, "hello")
    assert pop(task_queue, [NS_A], worker="w1") == task_id
    assert task_queue.get_result(task_id) is None
    finish(task_queue, task_id, worker="w1")
    assert task_queue.get_status(task_id) == "ready"
    res = task_queue.get_result(task_id)
    assert res is not None
    assert res["status"] == "ready"
    assert res["ns"] == NS_A
    assert res["duration"] == 1.5
    res_wait = task_queue.wait_for(task_id, timeout=NO_TASK)
    assert res_wait is not None
    assert res_wait["status"] == "ready"


def test_result_status_is_taken_from_response(task_queue: TaskQueue) -> None:
    task_id = enqueue(task_queue, NS_A, "hello")
    assert pop(task_queue, [NS_A]) == task_id
    finish(task_queue, task_id, status="error")
    assert task_queue.get_status(task_id) == "error"


def test_result_from_other_worker_is_ignored(task_queue: TaskQueue) -> None:
    task_id = enqueue(task_queue, NS_A, "hello")
    assert pop(task_queue, [NS_A], user=ALICE, worker="w1") == task_id
    # a different worker name, and the same worker name under another account
    finish(task_queue, task_id, user=ALICE, worker="w2")
    finish(task_queue, task_id, user=BOB, worker="w1")
    assert task_queue.get_status(task_id) == "busy"
    assert task_queue.get_result(task_id) is None
    # the assigned worker can still deliver
    finish(task_queue, task_id, user=ALICE, worker="w1")
    assert task_queue.get_status(task_id) == "ready"


def test_result_for_unassigned_task_is_ignored(task_queue: TaskQueue) -> None:
    task_id = enqueue(task_queue, NS_A, "hello")
    finish(task_queue, task_id)
    assert task_queue.get_status(task_id) == "wait"
    assert task_queue.get_result(task_id) is None


def test_second_result_is_ignored(task_queue: TaskQueue) -> None:
    task_id = enqueue(task_queue, NS_A, "hello")
    assert pop(task_queue, [NS_A]) == task_id
    finish(task_queue, task_id, status="ready")
    finish(task_queue, task_id, status="error")
    assert task_queue.get_status(task_id) == "ready"


def test_wait_for_blocks_until_result(task_queue: TaskQueue) -> None:
    task_id = enqueue(task_queue, NS_A, "hello")
    assert pop(task_queue, [NS_A]) == task_id

    def deliver() -> None:
        time.sleep(0.1)
        finish(task_queue, task_id)

    th = threading.Thread(target=deliver, daemon=True)
    th.start()
    res = task_queue.wait_for(task_id, timeout=SOME_TASK)
    th.join()
    assert res is not None
    assert res["status"] == "ready"


def test_wait_for_times_out(task_queue: TaskQueue) -> None:
    task_id = enqueue(task_queue, NS_A, "hello")
    assert task_queue.wait_for(task_id, timeout=NO_TASK) is None


def test_clear_task(task_queue: TaskQueue) -> None:
    task_id = enqueue(task_queue, NS_A, "hello")
    assert pop(task_queue, [NS_A]) == task_id
    task_queue.clear_task(task_id)
    assert task_queue.get_status(task_id) == "unknown"
    # the worker's late result is dropped since the task is no longer
    # assigned to it
    finish(task_queue, task_id)
    assert task_queue.get_result(task_id) is None
    assert task_queue.get_status(task_id) == "unknown"


# *** workers ***


def test_heartbeat_and_worker_info(task_queue: TaskQueue) -> None:
    wait = task_queue.heartbeat(
        user_email=ALICE, worker_name="w1", worker_status="idle")
    # a worker is asked to report back twice per heartbeat lifetime
    assert wait == HEARTBEAT * 0.5
    worker_id = get_worker_id(ALICE, "w1")
    info = task_queue.get_worker_info(worker_id)
    assert info == {
        "worker_id": worker_id,
        "email": ALICE,
        "status": "idle",
    }


def test_unknown_worker(task_queue: TaskQueue) -> None:
    info = task_queue.get_worker_info(get_worker_id(BOB, "ghost"))
    assert info["email"] is None
    assert info["status"] == "unknown"


def test_pop_marks_worker_busy(task_queue: TaskQueue) -> None:
    task_queue.heartbeat(
        user_email=ALICE, worker_name="w1", worker_status="idle")
    enqueue(task_queue, NS_A, "hello")
    assert pop(task_queue, [NS_A], worker="w1") is not None
    info = task_queue.get_worker_info(get_worker_id(ALICE, "w1"))
    assert info["status"] == "busy"


def test_get_all_workers(task_queue: TaskQueue) -> None:
    assert not list(task_queue.get_all_workers())
    task_queue.heartbeat(
        user_email=ALICE, worker_name="w1", worker_status="idle")
    task_queue.heartbeat(
        user_email=BOB, worker_name="w1", worker_status="backedup")
    workers = {
        info["worker_id"]: (info["email"], info["status"])
        for info in task_queue.get_all_workers()
    }
    assert workers == {
        get_worker_id(ALICE, "w1"): (ALICE, "idle"),
        get_worker_id(BOB, "w1"): (BOB, "backedup"),
    }


def test_worker_goes_offline_when_heartbeat_expires(
        fast_queue: TaskQueue) -> None:
    fast_queue.heartbeat(
        user_email=ALICE, worker_name="w1", worker_status="idle")
    worker_id = get_worker_id(ALICE, "w1")
    assert fast_queue.get_worker_info(worker_id)["status"] == "idle"
    time.sleep(FAST_HEARTBEAT + 0.1)
    info = fast_queue.get_worker_info(worker_id)
    # the account association outlives the heartbeat
    assert info["email"] == ALICE
    assert info["status"] == "offline"


# *** workers that disappear ***


def test_busy_worker_keeps_its_task(task_queue: TaskQueue) -> None:
    task_id = enqueue(task_queue, NS_A, "hello")
    assert pop(task_queue, [NS_A], worker="w1") == task_id
    task_queue.requeue_unavailable_worker_tasks()
    assert task_queue.get_status(task_id) == "busy"
    assert pop(task_queue, [NS_A], worker="w2") is None


def test_offline_heartbeat_requeues_task(task_queue: TaskQueue) -> None:
    """A worker that announces it goes offline wakes the cleaner, which puts
    its task back on the queue right away."""
    task_id = enqueue(task_queue, NS_A, "hello")
    assert pop(task_queue, [NS_A], worker="w1") == task_id
    task_queue.heartbeat(
        user_email=ALICE, worker_name="w1", worker_status="offline")
    start = time.monotonic()
    assert pop(task_queue, [NS_A], worker="w2", timeout=SOME_TASK) == task_id
    # far sooner than the cleaner's regular interval
    assert time.monotonic() - start < SOME_TASK
    assert task_queue.get_status(task_id) == "busy"


def test_offline_heartbeat_while_cleaner_is_busy(
        task_queue: TaskQueue, monkeypatch: pytest.MonkeyPatch) -> None:
    """An offline heartbeat that arrives while the cleaner is in the middle of
    a run still wakes it once that run ends, instead of being lost until the
    cleaner's regular interval."""
    in_run = threading.Event()
    release = threading.Event()
    original = TaskQueue.requeue_unavailable_worker_tasks
    calls = 0

    def slow_requeue(self: TaskQueue) -> None:
        nonlocal calls
        if self is not task_queue:
            # NOTE: the cleaner threads of queues from earlier tests keep
            # running; they must not count as this queue's cleaner runs
            original(self)
            return
        calls += 1
        original(self)
        if calls == 1:
            # the scan is done; the cleaner is still busy finishing its run
            in_run.set()
            release.wait(SOME_TASK)

    monkeypatch.setattr(
        TaskQueue, "requeue_unavailable_worker_tasks", slow_requeue)
    # wake the cleaner so that it is busy with its first run
    task_queue.heartbeat(
        user_email=BOB, worker_name="other", worker_status="offline")
    assert in_run.wait(SOME_TASK)
    task_id = enqueue(task_queue, NS_A, "hello")
    assert pop(task_queue, [NS_A], worker="w1") == task_id
    task_queue.heartbeat(
        user_email=ALICE, worker_name="w1", worker_status="offline")
    release.set()
    assert pop(task_queue, [NS_A], worker="w2", timeout=SOME_TASK) == task_id


def test_vanished_worker_task_goes_to_next_worker(
        fast_queue: TaskQueue) -> None:
    """A worker that stops sending heartbeats loses its task to the next
    bidder; its late result is dropped and the new worker's is kept."""
    task_id = enqueue(fast_queue, NS_A, "hello")
    assert pop(fast_queue, [NS_A], worker="w1") == task_id
    assert pop(fast_queue, [NS_A], worker="w2", timeout=SOME_TASK) == task_id
    finish(fast_queue, task_id, worker="w1", status="error")
    assert fast_queue.get_status(task_id) == "busy"
    assert fast_queue.get_result(task_id) is None
    finish(fast_queue, task_id, worker="w2", status="ready")
    assert fast_queue.get_status(task_id) == "ready"
    res = fast_queue.get_result(task_id)
    assert res is not None
    assert res["status"] == "ready"


def test_requeued_task_goes_first(fast_queue: TaskQueue) -> None:
    """A task taken back from a vanished worker has waited longest, so it is
    put at the head of its queue, not the tail."""
    first = enqueue(fast_queue, NS_A, "first")
    assert pop(fast_queue, [NS_A], worker="w1") == first
    later = [enqueue(fast_queue, NS_A, f"later {ix}") for ix in range(3)]
    time.sleep(FAST_HEARTBEAT * 2.5)  # several cleaner runs
    popped: list[TaskId] = []
    for _ in range(4):
        task_id = pop(fast_queue, [NS_A], worker="w2")
        assert task_id is not None
        popped.append(task_id)
        finish(fast_queue, task_id, worker="w2")
    assert popped == [first, *later]


def test_completed_task_is_not_requeued(fast_queue: TaskQueue) -> None:
    task_id = enqueue(fast_queue, NS_A, "hello")
    assert pop(fast_queue, [NS_A], worker="w1") == task_id
    fast_queue.set_status(task_id, "ready")
    time.sleep(FAST_HEARTBEAT * 2.5)  # several cleaner runs
    assert fast_queue.get_status(task_id) == "ready"
    assert pop(fast_queue, [NS_A], worker="w2") is None


def test_cleaner_drops_assignment_of_completed_task(
        quiet_queue: TaskQueue, queue_redis: Redis) -> None:
    """A completed task that is still assigned to a vanished worker (e.g.,
    the server died in `set_result` after storing the status) and an
    assignment whose task no longer exists are removed by the cleaner rather
    than rescanned forever. The completed task's result stays available."""
    done = enqueue(quiet_queue, NS_A, "done")
    assert pop(quiet_queue, [NS_A], worker="w1") == done
    quiet_queue.set_status(done, "ready")
    orphan = TaskId.create()
    queue_redis.set_value(
        TaskQueue.task_worker_key(orphan),
        task_worker_to_redis({
            "ns": NS_A,
            "worker_id": get_worker_id(ALICE, "w1"),
        }))
    quiet_queue.heartbeat(
        user_email=ALICE, worker_name="w1", worker_status="offline")
    quiet_queue.requeue_unavailable_worker_tasks()
    assert not leftover_keys(queue_redis, "worker")
    assert quiet_queue.get_status(done) == "ready"
    assert quiet_queue.get_status(orphan) == "unknown"
    assert pop(quiet_queue, [NS_A], worker="w2") is None


@pytest.mark.parametrize("lookup", ["get_worker_info", "get_status"])
def test_cleaner_does_not_revive_task_cancelled_meanwhile(
        quiet_queue: TaskQueue,
        queue_redis: Redis,
        monkeypatch: pytest.MonkeyPatch,
        lookup: str) -> None:
    """The user cancels a task while the cleaner is deciding what to do with
    it: right after the cleaner looked up the task's worker or the task's
    status, but before it puts the task back on the queue. The cleaner must
    not bring the task back."""
    task_id = enqueue(quiet_queue, NS_A, "hello")
    assert pop(quiet_queue, [NS_A], worker="w1") == task_id
    quiet_queue.heartbeat(
        user_email=ALICE, worker_name="w1", worker_status="offline")
    original = getattr(TaskQueue, lookup)
    cancelled = False

    def lookup_then_cancel(self: TaskQueue, arg: object) -> object:
        nonlocal cancelled
        res = original(self, arg)
        if not cancelled:
            cancelled = True
            quiet_queue.clear_task(task_id)
        return res

    monkeypatch.setattr(TaskQueue, lookup, lookup_then_cancel)
    quiet_queue.requeue_unavailable_worker_tasks()
    monkeypatch.setattr(TaskQueue, lookup, original)
    if not cancelled:
        # NOTE: the cleaner does not do this lookup outside of an atomic
        # step; the earliest the user can cancel is right after the run
        quiet_queue.clear_task(task_id)
    assert quiet_queue.get_status(task_id) == "unknown"
    assert not leftover_keys(queue_redis, "worker")
    # a stale queue entry is fine as long as no bid hands the task out
    assert pop(quiet_queue, [NS_A], worker="w2") is None
    assert queue_redis.llen(TaskQueue.queue_key(NS_A)) == 0
    assert not leftover_keys(queue_redis, "status")


def finish_with_interleaved(
        queue: TaskQueue,
        redis: Redis,
        monkeypatch: pytest.MonkeyPatch,
        task_id: TaskId,
        action: Callable[[], None]) -> None:
    """
    Worker w1 delivers its result for the task while `action` runs at the
    moment `set_result` has read the task's assignment, i.e., after the check
    that the result comes from the assigned worker. If `set_result` never
    reads the assignment on its own (it checks and writes in one atomic step)
    `action` runs right after `set_result` instead.

    Args:
        queue (TaskQueue): The queue.
        redis (Redis): The redis of the queue.
        monkeypatch (pytest.MonkeyPatch): For installing the hook.
        task_id (TaskId): The task.
        action (Callable[[], None]): What runs in between.
    """
    worker_key = TaskQueue.task_worker_key(task_id)
    original = redis.get_value
    fired = False

    def get_value_then_act(key: str) -> str | None:
        nonlocal fired
        res = original(key)
        if key == worker_key and not fired:
            fired = True
            action()
        return res

    monkeypatch.setattr(redis, "get_value", get_value_then_act)
    finish(queue, task_id, worker="w1")
    monkeypatch.setattr(redis, "get_value", original)
    if not fired:
        action()


def test_result_and_requeue_do_not_interleave(
        quiet_queue: TaskQueue,
        queue_redis: Redis,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The cleaner takes the task back from a worker it believes is gone just
    as that worker delivers its result. Either the result counts and the task
    is not handed out again, or the result is dropped and the task is back
    on the queue; a completed task must not be computed a second time."""
    task_id = enqueue(quiet_queue, NS_A, "hello")
    assert pop(quiet_queue, [NS_A], worker="w1") == task_id
    quiet_queue.heartbeat(
        user_email=ALICE, worker_name="w1", worker_status="offline")
    finish_with_interleaved(
        quiet_queue,
        queue_redis,
        monkeypatch,
        task_id,
        quiet_queue.requeue_unavailable_worker_tasks)
    if quiet_queue.get_result(task_id) is not None:
        assert quiet_queue.get_status(task_id) == "ready"
        assert pop(quiet_queue, [NS_A], worker="w2") is None
    else:
        assert quiet_queue.get_status(task_id) == "wait"
        assert pop(quiet_queue, [NS_A], worker="w2") == task_id
    assert quiet_queue.get_status(task_id) in ("ready", "busy")


def test_result_and_cancel_do_not_interleave(
        quiet_queue: TaskQueue,
        queue_redis: Redis,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The user cancels a task (e.g., by sending a new prompt) just as the
    worker delivers its result. Nothing of the cancelled task may come back:
    no status, no result, no assignment."""
    task_id = enqueue(quiet_queue, NS_A, "hello")
    assert pop(quiet_queue, [NS_A], worker="w1") == task_id
    finish_with_interleaved(
        quiet_queue,
        queue_redis,
        monkeypatch,
        task_id,
        lambda: quiet_queue.clear_task(task_id))
    assert quiet_queue.get_status(task_id) == "unknown"
    assert quiet_queue.get_result(task_id) is None
    assert not leftover_keys(queue_redis, "worker")
    assert not leftover_keys(queue_redis, "output")
