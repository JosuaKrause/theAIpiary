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
import requests
from scattermind.api.api import InputTypes, redis_to_task_input
from scattermind.system.base import TaskId
from scattermind.system.names import GNamespace, UName
from scattermind.system.response import response_to_redis, ResponseObject
from scattermind.system.util import get_time_str

from swai.auth import get_authorization
from swai.server_response_types import (
    HeartbeatResponse,
    TaskBidResponse,
    TaskFinishResponse,
)
from swai.system.base import (
    long_poll_timeout,
    REQUEST_TIMEOUT,
    retry_on_disconnect,
    WorkerStatus,
)
from swai.system.user import WorkerToken
from swai_provider.env import envload_str
from swai_provider.smind.worker_api import GraphProfile


class TaskHandler:
    def __init__(self, worker_name: str) -> None:
        self._worker_name = worker_name
        self._name = UName(envload_str("AIPIARY_USER"))
        self._worker_token: WorkerToken = envload_str("AIPIARY_WORKER_TOKEN")
        self._api_url = envload_str("AIPIARY_API_URL").removesuffix("/")
        self._api = requests.Session()

    def _url(self, path: str) -> str:
        return f"{self._api_url}/api/task{path}"

    def _json(self) -> dict[str, str | int | float | list[str] | None]:
        return {}

    def _headers(self) -> dict[str, str]:
        return {
            "authorization": get_authorization(self._name, self._worker_token),
        }

    def task_heartbeat(
            self,
            *,
            worker_status: WorkerStatus,
            retries: int | None,
            wait_before_retry: float) -> float:
        obj = self._json()
        obj["worker_name"] = self._worker_name
        obj["status"] = worker_status
        try:
            resp = retry_on_disconnect(
                lambda: self._api.post(
                    self._url("/heartbeat"),
                    json=obj,
                    headers=self._headers(),
                    timeout=REQUEST_TIMEOUT),
                idempotent=True,
                retries=retries,
                wait_before_retry=wait_before_retry,
                include_general_http_errors=True,
                unify=ValueError)
        except ValueError as exc:
            print(
                f"{get_time_str()} heartbeat failed ({exc.__cause__!r}). "
                f"next attempt in {wait_before_retry}s")
            return wait_before_retry
        res: HeartbeatResponse = resp.json()
        return res["timeout"]

    def task_bid(
            self,
            graphs: list[GraphProfile],
            *,
            timeout: float,
            ) -> tuple[GraphProfile, TaskId, dict[str, InputTypes]] | None:
        graph_ns: dict[GNamespace, GraphProfile] = {
            graph.get_ns(): graph
            for graph in graphs
        }
        obj = self._json()
        obj["worker_name"] = self._worker_name
        obj["nss"] = [ns.get() for ns in graph_ns.keys()]
        obj["timeout"] = timeout
        # NOTE: the server holds the bid open for up to `timeout` seconds.
        # the bid is not idempotent: a bid that reached the server may have
        # assigned a task to this worker; if the response is lost (read
        # timeout, broken connection) that task stays assigned to this worker,
        # which never received it, and is not requeued while the worker keeps
        # sending heartbeats. a repeated bid would pop yet another task.
        # making the bid idempotent on the server (a re-bid returns the task
        # already assigned to the worker) would allow retrying it
        resp = retry_on_disconnect(
            lambda: self._api.post(
                self._url("/bid"),
                json=obj,
                headers=self._headers(),
                timeout=long_poll_timeout(timeout)),
            idempotent=False)
        res: TaskBidResponse = resp.json()
        out_ns = res["ns"]
        out_task_id = res["task_id"]
        out_input_data = res["input_data"]
        if out_ns is None or out_task_id is None or out_input_data is None:
            return None
        ns = GNamespace(out_ns)
        graph = graph_ns[ns]
        task_id = TaskId.parse(out_task_id)
        input_data = redis_to_task_input(
            out_input_data, graph.get_input_format())
        return (graph, task_id, input_data)

    def task_finish(
            self,
            task_id: TaskId,
            response: ResponseObject) -> None:
        obj = self._json()
        obj["worker_name"] = self._worker_name
        obj["task_id"] = task_id.to_parseable()
        obj["response"] = response_to_redis(response)
        # NOTE: the server ignores results of a task that is no longer
        # assigned to this worker, which includes a repeated finish
        resp = retry_on_disconnect(
            lambda: self._api.post(
                self._url("/finish"),
                json=obj,
                headers=self._headers(),
                timeout=REQUEST_TIMEOUT),
            idempotent=True)
        resp.raise_for_status()
        res: TaskFinishResponse = resp.json()
        assert res["well_done"]
