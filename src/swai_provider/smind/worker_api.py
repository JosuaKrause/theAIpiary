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
import os
import traceback
from typing import TypedDict

import redis as redis_lib
from scattermind.api.api import InputTypes, ScattermindAPI
from scattermind.api.loader import load_api
from scattermind.system.base import TaskId
from scattermind.system.info import DataFormat
from scattermind.system.io import open_readb
from scattermind.system.names import GNamespace
from scattermind.system.response import ResponseObject, TASK_COMPLETE

from swai_provider.config import Config


LONG_TIMEOUT = 10.0 * 60.0  # 10min


QueueStat = TypedDict('QueueStat', {
    "id": str,
    "name": str,
    "queue_length": int,
    "listeners": int,
})


def load_smind(config_fname: str) -> ScattermindAPI:
    with open_readb(config_fname) as fin:
        config_obj = json.load(fin)
    return load_api(config_obj)


class GraphProfile:
    def __init__(self, smind: ScattermindAPI, ns: GNamespace) -> None:
        self._smind = smind
        self._ns = ns
        self._input_format = smind.main_input_format(ns)
        inputs = list(smind.main_inputs(ns))
        outputs = list(smind.main_outputs(ns))
        self._inputs = inputs
        self._outputs = outputs

        self._output_field: str | None = None
        self._output_size: int | None = None

    def get_api(self) -> ScattermindAPI:
        return self._smind

    def get_ns(self) -> GNamespace:
        return self._ns

    def get_input_format(self) -> DataFormat:
        return self._input_format

    def get_input_fields(self) -> list[str]:
        return self._inputs

    def get_outputs(self) -> list[str]:
        return self._outputs

    def get_output_field(self) -> str:
        output_field = self._output_field
        if output_field is None:
            outputs = self._outputs
            if len(outputs) != 1:
                raise ValueError(f"invalid graph outputs: {outputs}")
            output_field = outputs[0]
            self._output_field = output_field
        return output_field

    def get_output_size(self) -> int:
        output_size = self._output_size
        if output_size is None:
            _, output_shape = self._smind.output_format(
                self._ns, self.get_output_field())
            if len(output_shape) != 1:
                raise ValueError(f"invalid graph output shape: {output_shape}")
            output_size = output_shape[0]
            if output_size is None:
                raise ValueError(f"graph {self._ns} has variable shape")
            self._output_size = output_size
        return output_size


def load_graph(
        config: Config,
        smind: ScattermindAPI,
        graph_fname: str) -> GraphProfile:
    with open(os.path.join(config["graphs"], graph_fname), "rb") as fin:
        graph_def_obj = json.load(fin)
    ns: GNamespace = smind.load_graph(graph_def_obj)
    return GraphProfile(smind, ns)


def get_queue_stats(smind: ScattermindAPI) -> list[QueueStat]:
    try:
        return [
            {
                "id": stat["id"].to_parseable(),
                "name": stat["name"].get(),
                "queue_length": stat["queue_length"],
                "listeners": stat["listeners"],
            }
            for stat in smind.get_queue_stats()
        ]
    except redis_lib.ConnectionError:
        print(traceback.format_exc())
        return []


def execute_task(
        task_id: TaskId,
        input_data: dict[str, InputTypes],
        *,
        graph_profile: GraphProfile) -> ResponseObject:
    # pylint: disable=unsubscriptable-object
    smind = graph_profile.get_api()
    ns = graph_profile.get_ns()
    task_id = smind.enqueue_task(ns, input_data, task_id=task_id)
    response: ResponseObject | None = None
    while response is None or response["status"] not in TASK_COMPLETE:
        for (_, resp) in smind.wait_for([task_id], timeout=LONG_TIMEOUT):
            response = resp
    return response
