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
    ROLE_ASSISTANT,
    ROLE_USER,
    save_messages,
    set_active_task,
)


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
        return 1.0  # TODO

    def session_field(self) -> str | None:
        return "session"

    def do_load(self, roa: ReadonlyAccess) -> None:
        lib = os.getenv("LLAMA_CPP_LIB")
        lib_exists = False if lib is None else os.path.exists(lib)
        print(f"LLAMA_CPP_LIB is {lib} {lib_exists=}")
        # print(f"{llama_supports_gpu_offload()=}")
        self._model = Llama(
            model_path=self.get_arg("model_path").get("str"),
            n_ctx=self.get_arg("n_ctx").get("int", 30000),
            n_gpu_layers=self.get_arg("n_gpu_layers").get("int", -1),  # 33
            # n_threads=6,
            # n_batch=521,
            seed=123,
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

    def _execute_prompt(
            self,
            model: Llama,
            prompt: str,
            *,
            cache_dir: str,
            session: Session,
            task: ComputeTask) -> str:
        if not task.is_valid():
            return ""
        task_id = task.get_task_id()
        # FIXME: use state
        # if not load_state(model, cache_dir):
        if True:  # pylint: disable=using-constant-test
            model.set_seed(123)
        set_active_task(session, task_id)
        messages = load_messages(cache_dir)
        if messages is None:
            messages = load_system_prompt(cache_dir)
        if prompt:
            append_new_message(messages, text=prompt, role=ROLE_USER)
        save_messages(cache_dir, messages)
        session.sync_out()
        response: list[str] = []

        try:
            for out in model.create_chat_completion(
                    messages, max_tokens=None, stream=True):
                if not task.is_valid():
                    break
                resp = cast(CreateChatCompletionStreamResponse, out)
                delta = resp["choices"][0]["delta"]
                content: str | None = cast(str, delta.get("content", ""))
                handle_model_output(session, task_id, response, content)
                if check_is_interrupted(session, task_id):
                    break
        except EOFError:
            pass
        handle_model_finish(session, task_id)
        full_response = "".join(response)
        messages.append(
            {
                "role": ROLE_ASSISTANT,
                "content": full_response,
            })

        # NOTE: if the task is not the same anymore our response is ignored!
        if get_active_task(session) == task_id:
            save_messages(cache_dir, messages)
            # FIXME: use state
            # save_state(model, cache_dir)
            set_active_task(session, None)
        return full_response

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
                response_str = self._execute_prompt(
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
