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
from collections.abc import Iterator
from test.util import memory_redis, UNUSED_REDIS
from typing import cast

import pytest
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


@pytest.fixture(name="fast_queue")
def fixture_fast_queue(monkeypatch: pytest.MonkeyPatch) -> Iterator[TaskQueue]:
    """
    A task queue whose worker heartbeats expire after `FAST_HEARTBEAT`
    seconds and whose cleaner thread runs accordingly often, so a worker that
    stops sending heartbeats is noticed within a test.

    Yields:
        TaskQueue: The queue.
    """
    monkeypatch.setattr(queue_module, "Redis", memory_redis)
    monkeypatch.setattr(queue_module, "HEARTBEAT", FAST_HEARTBEAT)
    yield TaskQueue(cast(SessionStore, None), UNUSED_REDIS)


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


@pytest.mark.xfail(
    strict=True,
    reason=(
        "pop_task gives up on a namespace after one cancelled entry: a bid "
        "that meets cancelled tasks at the head of the queue returns nothing "
        "(or only after its full timeout) although a live task waits behind "
        "them"))
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
