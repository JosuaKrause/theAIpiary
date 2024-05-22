import requests
from scattermind.api.api import InputTypes, redis_to_task_input
from scattermind.system.base import TaskId
from scattermind.system.names import GNamespace, UName
from scattermind.system.response import response_to_redis, ResponseObject

from swai.server_response_types import TaskBidResponse, TaskFinishResponse
from swai.system.user.manager import WorkerToken
from swai_provider.env import envload_str
from swai_provider.smind.worker_api import GraphProfile


class TaskHandler:
    def __init__(self) -> None:
        self._name = UName(envload_str("SWAI_USER"))
        self._worker_token: WorkerToken = envload_str("SWAI_WORKER_TOKEN")
        self._api_url = envload_str("SWAI_API_URL")
        self._api = requests.Session()

    def _url(self, path: str) -> str:
        return f"{self._api_url}/task{path}"

    def _json(self) -> dict[str, str | int | float | list[str] | None]:
        return {
            "name": self._name.get(),
            "worker_token": self._worker_token,
        }

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
        obj["nss"] = [ns.get() for ns in graph_ns.keys()]
        obj["timeout"] = timeout
        resp = self._api.post(self._url("/bid"), json=obj)
        resp.raise_for_status()
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

    def task_finish(self, task_id: TaskId, response: ResponseObject) -> None:
        obj = self._json()
        obj["task_id"] = task_id.to_parseable()
        obj["response"] = response_to_redis(response)
        resp = self._api.post(self._url("/finish"), json=obj)
        resp.raise_for_status()
        res: TaskFinishResponse = resp.json()
        assert res["well_done"]
