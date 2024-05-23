from typing import TypeAlias

from redipy import Redis, RedisConfig
from scattermind.api.api import InputTypes, task_input_to_redis
from scattermind.system.base import TaskId
from scattermind.system.names import GNamespace
from scattermind.system.response import (
    redis_to_response,
    response_to_redis,
    ResponseObject,
    TASK_STATUS_BUSY,
    TASK_STATUS_UNKNOWN,
    TASK_STATUS_WAIT,
    TaskStatus,
    to_status,
)
from scattermind.system.session.session import SessionStore


ResponseStr: TypeAlias = str


class TaskQueue:
    def __init__(self, session_store: SessionStore, cfg: RedisConfig) -> None:
        self._session_store = session_store
        self._redis = Redis(cfg=cfg, redis_module="task")

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
            timeout: float) -> tuple[TaskId, ResponseStr] | None:
        redis = self._redis
        queue_channel = self.queue_channel()

        def get_task() -> tuple[TaskId, ResponseStr] | None:
            for ns in nss:
                task = redis.lpop(self.queue_key(ns))
                if task is None:
                    continue
                task_id = TaskId.parse(task)
                input_str = redis.get_value(self.input_key(task_id))
                if input_str is not None:
                    self.set_status(task_id, TASK_STATUS_BUSY)
                    return task_id, input_str
                self.clear_task(task_id)
            return None

        return redis.wait_for(queue_channel, get_task, timeout=timeout)

    def get_status(self, task_id: TaskId) -> TaskStatus:
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

    def set_result(self, task_id: TaskId, response: ResponseObject) -> None:
        redis = self._redis
        output_key = self.output_key(task_id)
        self.set_status(task_id, response["status"])
        redis.set_value(output_key, response_to_redis(response))
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
