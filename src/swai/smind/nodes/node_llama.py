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
import os
from typing import cast

from llama_cpp import (  # llama_supports_gpu_offload,
    CreateChatCompletionStreamResponse,
    Llama,
    LlamaDiskCache,
)
from scattermind.system.base import GraphId, NodeId
from scattermind.system.client.client import ComputeTask
from scattermind.system.graph.graph import Graph
from scattermind.system.graph.node import Node
from scattermind.system.info import DataFormatJSON, SESSION_INFO, STRING_INFO
from scattermind.system.payload.values import ComputeState
from scattermind.system.queue.queue import QueuePool
from scattermind.system.readonly.access import ReadonlyAccess
from scattermind.system.session.session import Session
from scattermind.system.torch_util import str_to_tensor, tensor_to_str

from swai.smind.llama_session import (
    append_new_message,
    check_is_interrupted,
    get_active_task,
    handle_model_finish,
    handle_model_output,
    load_messages,
    load_system_prompt,
    mark_cut_off,
    ROLE_ASSISTANT,
    ROLE_USER,
    save_messages,
    set_active_task,
)


LLAMA_SEED = 123
"""The sampling seed for every answer."""
DEFAULT_N_CTX = 16384
"""The context size if the graph does not set `n_ctx`."""


def execute_prompt(
        model: Llama,
        prompt: str,
        *,
        cache_dir: str,
        session: Session,
        task: ComputeTask) -> str:
    """
    Computes the answer to the prompt and streams it to the session. The answer
    is added to the chat history only if the task is still the active task of
    the session when it is done (see `set_active_task`).

    Args:
        model (Llama): The model.
        prompt (str): The new user message. Empty to answer the history as is.
        cache_dir (str): The local folder of the session.
        session (Session): The session.
        task (ComputeTask): The task.

    Returns:
        str: The answer.
    """
    if not task.is_valid():
        return ""
    task_id = task.get_task_id()
    if check_is_interrupted(session, task_id):
        # NOTE: the task was replaced before we started; the server already
        # took care of the history
        return ""
    # NOTE: a fixed seed makes the answer depend only on the history. there is
    # no per-session model state to restore: prompt processing of the shared
    # history prefix is reused through the `LlamaDiskCache` (see
    # `execute_tasks`)
    model.set_seed(LLAMA_SEED)
    messages = load_messages(cache_dir)
    if messages is None:
        messages = load_system_prompt(cache_dir)
    if prompt:
        append_new_message(messages, text=prompt, role=ROLE_USER)
    save_messages(cache_dir, messages)
    session.sync_out()
    response: list[str] = []
    cut_off = False

    try:
        for out in model.create_chat_completion(
                messages, max_tokens=None, stream=True):
            if not task.is_valid():
                cut_off = True
                break
            resp = cast(CreateChatCompletionStreamResponse, out)
            delta = resp["choices"][0]["delta"]
            content: str | None = cast(str, delta.get("content", ""))
            handle_model_output(session, task_id, response, content)
            if check_is_interrupted(session, task_id):
                cut_off = True
                break
    except EOFError:
        pass
    handle_model_finish(session, task_id)
    full_response = "".join(response)

    if get_active_task(session) == task_id:
        messages.append(
            {
                "role": ROLE_ASSISTANT,
                "content": (
                    mark_cut_off(full_response)
                    if cut_off
                    else full_response),
            })
        save_messages(cache_dir, messages)
        set_active_task(session, None)
    else:
        # NOTE: the task was replaced while we were busy. drop our copy of the
        # history so the sync at the end of the session block does not
        # overwrite the newer history
        session.sync_in()
    return full_response


class LlamaNode(Node):
    def __init__(self, kind: str, graph: Graph, node_id: NodeId) -> None:
        super().__init__(kind, graph, node_id)
        self._model: Llama | None = None

    def do_is_pure(
            self,
            graph: Graph,
            queue_pool: QueuePool,
            pure_cache: dict[GraphId, bool]) -> bool:
        return False

    def get_input_format(self) -> DataFormatJSON:
        return {
            "prompt": STRING_INFO,
            "session": SESSION_INFO,
        }

    def get_output_format(self) -> dict[str, DataFormatJSON]:
        return {
            "out": {
                "response": STRING_INFO,
            },
        }

    def get_weight(self) -> float:
        return 1.0

    def get_load_cost(self) -> float:
        # NOTE: scattermind only compares load costs of the nodes an executor
        # could load (it divides each queue's pressure by them). the worker
        # loads only the llama graph and this is its only node, so the value
        # does not influence scheduling; 1.0 is the cost of a typical node
        return 1.0

    def session_field(self) -> str | None:
        return "session"

    def do_load(self, roa: ReadonlyAccess) -> None:
        lib = os.getenv("LLAMA_CPP_LIB")
        lib_exists = False if lib is None else os.path.exists(lib)
        print(f"LLAMA_CPP_LIB is {lib} {lib_exists=}")
        # print(f"{llama_supports_gpu_offload()=}")
        self._model = Llama(
            model_path=self.get_arg("model_path").get("str"),
            n_ctx=self.get_arg("n_ctx").get("int", DEFAULT_N_CTX),
            n_gpu_layers=self.get_arg("n_gpu_layers").get("int", -1),  # 33
            # n_threads=6,
            # n_batch=521,
            seed=LLAMA_SEED,
            # flash_attn=True,
            verbose=True)

    def do_unload(self) -> None:
        self._model = None

    def expected_output_meta(
            self, state: ComputeState) -> dict[str, tuple[float, int]]:
        tasks = list(state.get_inputs_tasks())
        return {
            "out": (len(tasks), len(tasks) * 500),
        }

    def execute_tasks(self, state: ComputeState) -> None:
        assert self._model is not None
        model = self._model
        inputs = state.get_values()
        sessions = inputs.get_sessions()
        prompts = inputs.get_data("prompt")
        tasks = inputs.get_current_tasks()
        scratch_folder = inputs.get_session_scratch_folder()
        model.set_cache(LlamaDiskCache(
            os.path.join(scratch_folder, self.get_id().to_parseable())))
        with Session.get_local_folders(sessions) as cache_dirs:
            for cache_dir, session, prompt, task in zip(
                    cache_dirs, sessions, prompts.iter_values(), tasks):
                prompt_str = tensor_to_str(prompt)
                response_str = execute_prompt(
                    model,
                    prompt_str.strip(),
                    cache_dir=cache_dir,
                    session=session,
                    task=task)
                response = str_to_tensor(response_str)
                state.push_results(
                    "out",
                    [task],
                    {
                        "response": state.create_single(response),
                    })
