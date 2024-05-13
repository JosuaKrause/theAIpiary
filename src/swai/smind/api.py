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
import os
import traceback
from typing import TypedDict

import redis as redis_lib
from scattermind.api.api import ScattermindAPI
from scattermind.api.loader import load_api
from scattermind.system.base import TaskId, UserId
from scattermind.system.io import open_readb
from scattermind.system.names import GNamespace
from scattermind.system.response import response_ok, TASK_COMPLETE
from scattermind.system.session.session import Session

from swai.config import Config
from swai.smind.llama_session import (
    ChunkPosition,
    get_active_task,
    get_model_output,
    get_visible_messages,
    load_system_prompt,
    save_messages,
    set_active_task,
    set_interrupted,
    VisibleMessage,
)


DEFAULT_TIMEOUT = 60.0  # 1min


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


def init_llama(
        user_id: UserId,
        *,
        graph_profile: GraphProfile) -> tuple[Session, list[VisibleMessage]]:
    smind = graph_profile.get_api()
    session = smind.new_session(user_id, copy_from=None)
    with session.get_local_folder() as cache_dir:
        msgs = load_system_prompt(cache_dir)
        save_messages(cache_dir, msgs)
    messages = get_visible_messages(session)
    return (session, messages)


def start_llama_response(
        prompt: str,
        session: Session,
        *,
        graph_profile: GraphProfile) -> TaskId:
    smind = graph_profile.get_api()
    prev_task_id = get_active_task(session)
    if prev_task_id is not None:
        set_interrupted(session, prev_task_id)
        for cur_task_id, result in smind.wait_for(
                [prev_task_id], timeout=DEFAULT_TIMEOUT):
            try:
                response_ok(result, no_warn=True)
            except ValueError as exc:
                raise ValueError("error computing previous response") from exc
            smind.clear_task(cur_task_id)
    return do_enqueue(prompt, session, graph_profile=graph_profile)


def do_enqueue(
        prompt: str,
        session: Session,
        *,
        graph_profile: GraphProfile) -> TaskId:
    smind = graph_profile.get_api()
    ns = graph_profile.get_ns()
    task_id = smind.enqueue_task(
        ns,
        {
            "prompt": prompt,
            "session": session,
        })
    set_active_task(session, task_id)
    return task_id


def retrieve_llama_response(
        session: Session,
        pos: ChunkPosition) -> tuple[str, ChunkPosition | None]:
    return get_model_output(
        session, pos, timeout=DEFAULT_TIMEOUT)


def recover_llama_chat(
        session: Session,
        *,
        graph_profile: GraphProfile,
        ) -> tuple[list[VisibleMessage], TaskId | None]:
    smind = graph_profile.get_api()
    messages = get_visible_messages(session)
    task_id = get_active_task(session)
    if task_id is not None:
        task_status = smind.get_status(task_id)
        if task_status in TASK_COMPLETE:
            set_active_task(session, None)
            smind.clear_task(task_id)
            task_id = None
    if task_id is None and messages:
        last_msg = messages[-1]
        if last_msg["role"] == "user":
            # NOTE: we got a task that got cleaned up before it finished
            task_id = do_enqueue("", session, graph_profile=graph_profile)
    return messages, task_id
