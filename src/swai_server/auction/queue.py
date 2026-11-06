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
import json
import threading
from collections.abc import Iterable
from typing import cast, Literal, TypeAlias, TypedDict

from redipy import Redis, RedisConfig
from redipy.script import (
    ExecFunction,
    FnContext,
    JSONType,
    RedisList,
    RedisVar,
    Strs,
)
from scattermind.api.api import InputTypes, task_input_to_redis
from scattermind.system.base import TaskId
from scattermind.system.names import GNamespace, UName
from scattermind.system.response import (
    redis_to_response,
    response_to_redis,
    ResponseObject,
    TASK_COMPLETE,
    TASK_STATUS_BUSY,
    TASK_STATUS_UNKNOWN,
    TASK_STATUS_WAIT,
    TaskStatus,
    to_status,
)
from scattermind.system.session.session import SessionStore
from scattermind.system.util import json_compact

from swai.system.base import (
    get_worker_id,
    to_worker_status,
    WORKER_UNAVAILABLE,
    WorkerId,
    WorkerStatus,
)


HEARTBEAT = 10.0 * 60.0  # 10min
WORKER_GRACE = 30.0 * 24.0 * 60.0 * 60.0  # 1month


InputStr: TypeAlias = str


CleanResult = Literal["requeued", "cleaned"]


def to_millis(seconds: float) -> int:
    """
    Converts a duration for a redis expiration (`PX`) inside a script.

    Args:
        seconds (float): The duration in seconds.

    Returns:
        int: The duration in milliseconds.
    """
    return int(seconds * 1000.0)


WorkerInfo = TypedDict('WorkerInfo', {
    "worker_id": WorkerId,
    "email": UName | None,
    "status": WorkerStatus,
})


TaskWorker = TypedDict('TaskWorker', {
    "worker_id": WorkerId,
    "ns": GNamespace,
})
TaskWorkerJSON = TypedDict('TaskWorkerJSON', {
    "worker_id": WorkerId,
    "ns": str,
})


def redis_to_task_worker(text: str | None) -> TaskWorker | None:
    if not text:
        return None
    obj: TaskWorkerJSON = json.loads(text)
    return {
        "ns": GNamespace(obj["ns"]),
        "worker_id": obj["worker_id"],
    }


def task_worker_to_redis(task_worker: TaskWorker) -> str:
    obj: TaskWorkerJSON = {
        "ns": task_worker["ns"].get(),
        "worker_id": task_worker["worker_id"],
    }
    return json_compact(obj)


# FIXME: replace task queue with scattermind later
class TaskQueue:
    def __init__(self, session_store: SessionStore, cfg: RedisConfig) -> None:
        self._session_store = session_store
        self._redis = Redis(cfg=cfg, redis_module="task")
        self._cleaner_th: threading.Thread | None = None
        self._cleaner_lock = threading.Lock()
        self._cleaner_wake = threading.Event()
        self._pop_task = self._pop_task_script()
        self._clean_task = self._clean_task_script()
        self.start_cleaner()

    def start_cleaner(self) -> None:
        # NOTE: an Event, unlike Condition.notify, is not lost when the cleaner
        # is busy (or not yet waiting) at the moment it is woken
        cleaner_wake = self._cleaner_wake
        with self._cleaner_lock:
            if self._cleaner_th is not None:
                cleaner_wake.set()
                return

            def run() -> None:
                cleaner_freq = HEARTBEAT * 0.5
                while th is self._cleaner_th:
                    cleaner_wake.wait(cleaner_freq)
                    cleaner_wake.clear()
                    self.requeue_unavailable_worker_tasks()

            th = threading.Thread(target=run, daemon=True)
            self._cleaner_th = th
            th.start()

    @staticmethod
    def queue_channel() -> str:
        return "queue"

    @staticmethod
    def queue_key(ns: GNamespace | None) -> str:
        return f"queue:{'' if ns is None else ns.get()}"

    @staticmethod
    def input_key(task_id: TaskId | None) -> str:
        return f"input:{'' if task_id is None else task_id.to_parseable()}"

    @staticmethod
    def output_key(task_id: TaskId | None) -> str:
        return f"output:{'' if task_id is None else task_id.to_parseable()}"

    @staticmethod
    def status_key(task_id: TaskId | None) -> str:
        return f"status:{'' if task_id is None else task_id.to_parseable()}"

    @staticmethod
    def task_worker_key(task_id: TaskId | None) -> str:
        return f"worker:{'' if task_id is None else task_id.to_parseable()}"

    @staticmethod
    def worker_heartbeat_key(worker_id: WorkerId) -> str:
        return f"heartbeat:{worker_id}"

    @staticmethod
    def worker_user_key(worker_id: WorkerId | None) -> str:
        return f"user:{'' if worker_id is None else worker_id}"

    def heartbeat(
            self,
            *,
            user_email: UName,
            worker_name: str,
            worker_status: WorkerStatus) -> float:
        worker_id = get_worker_id(user_email, worker_name)
        heartbeat = HEARTBEAT
        with self._redis.pipeline() as pipe:
            pipe.set_value(
                self.worker_user_key(worker_id),
                user_email.get(),
                expire_in=WORKER_GRACE)
            pipe.set_value(
                self.worker_heartbeat_key(worker_id),
                worker_status,
                expire_in=heartbeat)
        if worker_status == "offline":
            self.start_cleaner()
        return heartbeat * 0.5

    def get_worker_info(self, worker_id: WorkerId) -> WorkerInfo:
        with self._redis.pipeline() as pipe:
            pipe.get_value(self.worker_user_key(worker_id))
            pipe.get_value(self.worker_heartbeat_key(worker_id))
            user_str, raw_status = pipe.execute()
        if user_str is None:
            user_email: UName | None = None
        else:
            user_email = UName(user_str)
        if raw_status is None:
            worker_status: WorkerStatus = "offline"
        else:
            worker_status = to_worker_status(raw_status)
        if user_email is None:
            worker_status = "unknown"
        # NOTE: uncomment to clean up worker list
        # if worker_status == "offline":
        #     with self._redis.pipeline() as pipe:
        #         pipe.delete(self.worker_user_key(worker_id))
        #         pipe.delete(self.worker_heartbeat_key(worker_id))
        return {
            "email": user_email,
            "status": worker_status,
            "worker_id": worker_id,
        }

    def get_all_workers(self) -> Iterable[WorkerInfo]:
        prefix = self.worker_user_key(None)
        pat = f"{prefix}*"
        for key in self._redis.keys(match=pat, block=False):
            worker_id: WorkerId = key.removeprefix(prefix)
            yield self.get_worker_info(worker_id)

    def enqueue_task(
            self,
            ns: GNamespace,
            obj: dict[str, InputTypes],
            ) -> TaskId:
        task_id = TaskId.create()
        with self._redis.pipeline() as pipe:
            pipe.rpush(self.queue_key(ns), task_id.to_parseable())
            pipe.set_value(self.input_key(task_id), task_input_to_redis(obj))
            pipe.set_value(self.status_key(task_id), TASK_STATUS_WAIT)
        self._redis.publish(self.queue_channel(), "task")
        return task_id

    def _pop_task_script(self) -> ExecFunction:
        # NOTE: a bid in one step: take the first live task of the worker's
        # namespaces (in order of preference) off its queue, assign it to the
        # worker, and mark the task and the worker busy. Entries of cancelled
        # tasks (their input is gone) are dropped on the way. Since redis runs
        # a script atomically, a task is never off the queue without being
        # assigned (a crash or a concurrent `clear_task` cannot leave it lost
        # or half assigned) and no two bids can get the same task.
        # The keys of a task are derived from the popped task id inside the
        # script. The key prefixes (e.g., "input:") are passed as key
        # arguments so that redipy adds its own key prefix to them.
        ctx = FnContext()
        queue_base = ctx.add_key("queue_base")
        input_base = ctx.add_key("input_base")
        output_base = ctx.add_key("output_base")
        status_base = ctx.add_key("status_base")
        worker_base = ctx.add_key("worker_base")
        worker_user = RedisVar(ctx.add_key("worker_user"))
        worker_heartbeat = RedisVar(ctx.add_key("worker_heartbeat"))
        nss = ctx.add_arg("nss")
        task_workers = ctx.add_arg("task_workers")
        user_email = ctx.add_arg("user_email")
        grace_ms = ctx.add_arg("grace_ms")
        heartbeat_ms = ctx.add_arg("heartbeat_ms")
        res = ctx.add_local(None)
        task_id = ctx.add_local(None)
        input_str = ctx.add_local(None)

        loop, ix, ns = ctx.for_(nss)
        ns_then, _ = loop.if_(res.eq_(None))
        rqueue = RedisList(Strs(queue_base, ns))
        ns_then.add(task_id.assign(rqueue.lpop()))
        # NOTE: keep popping from the same namespace until a live task is
        # found or the queue is empty
        pop_loop = ns_then.while_(res.eq_(None).and_(task_id.ne_(None)))
        rinput = RedisVar(Strs(input_base, task_id))
        pop_loop.add(input_str.assign(rinput.get_value()))
        live, cancelled = pop_loop.if_(input_str.ne_(None))
        live.add(RedisVar(Strs(worker_base, task_id)).set_value(
            task_workers[ix]))
        live.add(RedisVar(Strs(status_base, task_id)).set_value(
            TASK_STATUS_BUSY))
        live.add(res.assign([]))
        live.add(res.set_at(0, ns))
        live.add(res.set_at(1, task_id))
        live.add(res.set_at(2, input_str))
        # NOTE: same as `clear_task`
        cancelled.add(rinput.delete())
        cancelled.add(RedisVar(Strs(output_base, task_id)).delete())
        cancelled.add(RedisVar(Strs(status_base, task_id)).delete())
        cancelled.add(RedisVar(Strs(worker_base, task_id)).delete())
        cancelled.add(task_id.assign(rqueue.lpop()))

        # NOTE: same as `heartbeat` with worker status "busy"
        busy, _ = ctx.if_(res.ne_(None))
        busy.add(worker_user.redis_fn("set", user_email, "PX", grace_ms))
        busy.add(worker_heartbeat.redis_fn(
            "set", "busy", "PX", heartbeat_ms))
        ctx.set_return_value(res)
        return self._redis.register_script(ctx)

    def pop_task(
            self,
            nss: list[GNamespace],
            *,
            user_email: UName,
            worker_name: str,
            timeout: float) -> tuple[GNamespace, TaskId, InputStr] | None:
        worker_id = get_worker_id(user_email, worker_name)
        keys = {
            "queue_base": self.queue_key(None),
            "input_base": self.input_key(None),
            "output_base": self.output_key(None),
            "status_base": self.status_key(None),
            "worker_base": self.task_worker_key(None),
            "worker_user": self.worker_user_key(worker_id),
            "worker_heartbeat": self.worker_heartbeat_key(worker_id),
        }
        args: dict[str, JSONType] = {
            "nss": [ns.get() for ns in nss],
            "task_workers": [
                task_worker_to_redis({
                    "ns": ns,
                    "worker_id": worker_id,
                })
                for ns in nss
            ],
            "user_email": user_email.get(),
            "grace_ms": to_millis(WORKER_GRACE),
            "heartbeat_ms": to_millis(HEARTBEAT),
        }

        def get_task() -> tuple[GNamespace, TaskId, InputStr] | None:
            res = self._pop_task(keys=keys, args=args)
            if res is None:
                return None
            ns_str, task_id_str, input_str = cast(list[str], res)
            return (GNamespace(ns_str), TaskId.parse(task_id_str), input_str)

        return self._redis.wait_for(
            self.queue_channel(), get_task, timeout=timeout)

    def _clean_task_script(self) -> ExecFunction:
        # NOTE: the cleaner's decision for one assignment of a vanished worker
        # in one step: requeue the task, or, if it is complete (or gone),
        # drop the stale assignment. Nothing happens if the assignment changed
        # since the cleaner read it (the task got finished, cancelled, or
        # requeued in between).
        # Dropping the assignment of a complete task is safe: the assignment
        # is only read by `set_result` (once, to check that the result comes
        # from the assigned worker) and by the cleaner. A bid sets the
        # assignment and the "busy" status together, so a complete status
        # means that there is no newer bid. A complete status is written by
        # `set_result` after its check (it deletes the assignment itself
        # afterwards, so deleting it earlier changes nothing), by `clear_task`
        # (which deletes the assignment in the same step), or directly via
        # `set_status`. The task's result is kept.
        ctx = FnContext()
        rworker = RedisVar(ctx.add_key("worker"))
        rstatus = RedisVar(ctx.add_key("status"))
        rqueue = RedisList(ctx.add_key("queue"))
        expected = ctx.add_arg("expected")
        task_id = ctx.add_arg("task_id")
        complete = ctx.add_local(sorted(TASK_COMPLETE))
        res = ctx.add_local(None)
        status = ctx.add_local(None)
        is_complete = ctx.add_local(False)

        same, _ = ctx.if_(rworker.get_value().eq_(expected))
        same.add(status.assign(rstatus.get_value()))
        # NOTE: a missing status is TASK_STATUS_UNKNOWN
        same.add(is_complete.assign(status.eq_(None)))
        loop, _, cur = same.for_(complete)
        is_cur, _ = loop.if_(status.eq_(cur))
        is_cur.add(is_complete.assign(True))
        done, requeue = same.if_(is_complete)
        done.add(rworker.delete())
        done.add(res.assign("cleaned"))
        # NOTE: a requeued task has waited longest so it goes first
        requeue.add(rqueue.lpush(task_id))
        requeue.add(rstatus.set_value(TASK_STATUS_WAIT))
        requeue.add(rworker.delete())
        requeue.add(res.assign("requeued"))
        ctx.set_return_value(res)
        return self._redis.register_script(ctx)

    def requeue_unavailable_worker_tasks(self) -> None:
        redis = self._redis
        prefix = self.task_worker_key(None)
        for worker_key in redis.keys(match=f"{prefix}*", block=False):
            task_worker_str = redis.get_value(worker_key)
            task_worker = redis_to_task_worker(task_worker_str)
            if task_worker_str is None or task_worker is None:
                continue
            info = self.get_worker_info(task_worker["worker_id"])
            if info["status"] not in WORKER_UNAVAILABLE:
                continue
            task_id = TaskId.parse(worker_key.removeprefix(prefix))
            res = cast(CleanResult | None, self._clean_task(
                keys={
                    "worker": worker_key,
                    "status": self.status_key(task_id),
                    "queue": self.queue_key(task_worker["ns"]),
                },
                args={
                    "expected": task_worker_str,
                    "task_id": task_id.to_parseable(),
                }))
            if res == "requeued":
                redis.publish(self.queue_channel(), "task")

    def get_status(self, task_id: TaskId | None) -> TaskStatus:
        if task_id is None:
            return TASK_STATUS_UNKNOWN
        res = self._redis.get_value(self.status_key(task_id))
        if res is None:
            return TASK_STATUS_UNKNOWN
        return to_status(res)

    def set_status(self, task_id: TaskId, status: TaskStatus) -> None:
        self._redis.set_value(self.status_key(task_id), status)

    def wait_for(
            self,
            task_id: TaskId,
            *,
            timeout: float | None = 10.0,
            ) -> ResponseObject | None:
        redis = self._redis
        output_key = self.output_key(task_id)

        def get_response() -> ResponseObject | None:
            return self.get_result(task_id)

        return redis.wait_for(output_key, get_response, timeout=timeout)

    def set_result(
            self,
            task_id: TaskId,
            *,
            user_email: UName,
            worker_name: str,
            response: ResponseObject) -> None:
        redis = self._redis
        task_worker_key = self.task_worker_key(task_id)
        task_worker = redis_to_task_worker(
            redis.get_value(task_worker_key))
        worker_id = get_worker_id(user_email, worker_name)
        if task_worker is None or task_worker["worker_id"] != worker_id:
            # NOTE: we are too late; someone else computed it; ignore results
            return
        output_key = self.output_key(task_id)
        self.set_status(task_id, response["status"])
        redis.set_value(output_key, response_to_redis(response))
        redis.delete(task_worker_key)
        redis.publish(output_key, "response")

    def get_result(self, task_id: TaskId) -> ResponseObject | None:
        res = self._redis.get_value(self.output_key(task_id))
        if res is None:
            return None
        return redis_to_response(res)

    def clear_task(self, task_id: TaskId) -> None:
        with self._redis.pipeline() as pipe:
            pipe.delete(self.input_key(task_id))
            pipe.delete(self.output_key(task_id))
            pipe.delete(self.status_key(task_id))
            pipe.delete(self.task_worker_key(task_id))
