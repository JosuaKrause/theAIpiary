# Copyright (c) 2024 Josua Krause - All Rights Reserved
#
# THE CONTENTS OF THIS PROJECT ARE PROPRIETARY AND CONFIDENTIAL.
# UNAUTHORIZED COPYING, TRANSFERRING OR REPRODUCTION OF THE CONTENTS OF
# THIS PROJECT, VIA ANY MEDIUM IS STRICTLY PROHIBITED.
#
# The receipt or possession of the source code and/or any parts thereof does
# not convey or imply any right to use them for any purpose other than the
# purpose for which they were provided to you.
#
# The software is provided "AS IS", without warranty of any kind, express or
# implied, including but not limited to the warranties of merchantability,
# fitness for a particular purpose and non infringement. In no event shall the
# authors or copyright holders be liable for any claim, damages or other
# liability, whether in an action of contract, tort or otherwise, arising from,
# out of or in connection with the software or the use or other dealings in the
# software.
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the software.
import json
import threading
from collections.abc import Iterable
from typing import TypeAlias, TypedDict

from redipy import Redis, RedisConfig
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
        self._cleaner_cond = threading.Condition()
        self.start_cleaner()

    def start_cleaner(self) -> None:
        cleaner_cond = self._cleaner_cond
        with cleaner_cond:
            if self._cleaner_th is not None:
                cleaner_cond.notify_all()
                return

            def run() -> None:
                cleaner_freq = HEARTBEAT * 0.5
                while th is self._cleaner_th:
                    with cleaner_cond:
                        cleaner_cond.wait(cleaner_freq)
                    self.requeue_unavailable_worker_tasks()

            th = threading.Thread(target=run, daemon=True)
            self._cleaner_th = th
            th.start()

    @staticmethod
    def queue_channel() -> str:
        return "queue"

    @staticmethod
    def queue_key(ns: GNamespace) -> str:
        return f"queue:{ns.get()}"

    @staticmethod
    def input_key(task_id: TaskId) -> str:
        return f"input:{task_id.to_parseable()}"

    @staticmethod
    def output_key(task_id: TaskId) -> str:
        return f"output:{task_id.to_parseable()}"

    @staticmethod
    def status_key(task_id: TaskId) -> str:
        return f"status:{task_id.to_parseable()}"

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

    def pop_task(
            self,
            nss: list[GNamespace],
            *,
            user_email: UName,
            worker_name: str,
            timeout: float) -> tuple[GNamespace, TaskId, InputStr] | None:
        # FIXME: make big redis function
        worker_id = get_worker_id(user_email, worker_name)
        redis = self._redis
        queue_channel = self.queue_channel()

        def get_task() -> tuple[GNamespace, TaskId, InputStr] | None:
            for ns in nss:
                task = redis.lpop(self.queue_key(ns))
                if task is None:
                    continue
                task_id = TaskId.parse(task)
                input_str = redis.get_value(self.input_key(task_id))
                if input_str is not None:
                    redis.set_value(
                        self.task_worker_key(task_id),
                        task_worker_to_redis({
                            "ns": ns,
                            "worker_id": worker_id,
                        }))
                    self.set_status(task_id, TASK_STATUS_BUSY)
                    self.heartbeat(
                        user_email=user_email,
                        worker_name=worker_name,
                        worker_status="busy")
                    return (ns, task_id, input_str)
                self.clear_task(task_id)
            return None

        return redis.wait_for(queue_channel, get_task, timeout=timeout)

    def requeue_unavailable_worker_tasks(self) -> None:
        redis = self._redis
        prefix = self.task_worker_key(None)
        for worker_key in redis.keys(match=f"{prefix}*", block=False):
            task_worker = redis_to_task_worker(redis.get_value(worker_key))
            if task_worker is None:
                continue
            info = self.get_worker_info(task_worker["worker_id"])
            if info["status"] not in WORKER_UNAVAILABLE:
                continue
            task_id = TaskId.parse(worker_key.removeprefix(prefix))
            task_status = self.get_status(task_id)
            if task_status in TASK_COMPLETE:
                # FIXME: maybe clean up task / worker here?
                # might be a race-condition; so let's not do that for now
                continue
            with redis.pipeline() as pipe:
                pipe.lpush(
                    self.queue_key(task_worker["ns"]),
                    task_id.to_parseable())
                pipe.set_value(self.status_key(task_id), TASK_STATUS_WAIT)
                pipe.delete(worker_key)
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
