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
import pickle
from typing import Literal, TypeAlias, TypedDict

from llama_cpp import ChatCompletionRequestMessage, Llama, LlamaState
from scattermind.system.base import TaskId
from scattermind.system.io import (
    open_readb,
    open_reads,
    open_writeb,
    open_writes,
)
from scattermind.system.session.session import Session

from swai.smind.default_prompts import HELLO_PROMPT, SYSTEM_PROMPT


ChunkPosition: TypeAlias = tuple[TaskId, int]


VisibleMessage = TypedDict('VisibleMessage', {
    "role": Literal["assistant", "user"],
    "content": str,
})


STATE_FILE = "state.pkl"
MSGS_FILE = "msgs.json"
SYS_PROMPT_FILE = "system_prompt.txt"
HELLO_PROMPT_FILE = "hello_prompt.txt"


def load_state(model: Llama, cache_dir: str) -> bool:
    state_file = os.path.join(cache_dir, STATE_FILE)
    if not os.path.exists(state_file):
        return False
    with open_readb(state_file) as state_in:
        llama_state: LlamaState = pickle.load(state_in)
        model.load_state(llama_state)
    return True


def save_state(model: Llama, cache_dir: str) -> None:
    state_file = os.path.join(cache_dir, STATE_FILE)
    with open_writeb(state_file) as state_out:
        llama_state: LlamaState = model.save_state()
        pickle.dump(llama_state, state_out)


def get_visible_messages(session: Session) -> list[VisibleMessage]:
    with session.get_local_folder() as cache_dir:
        msgs = load_messages(cache_dir)
    if msgs is None:
        return []
    return [
        {
            "role": msg["role"],
            "content": f"{msg['content']}",
        }
        for msg in msgs
        if msg["role"] == "user" or msg["role"] == "assistant"
    ]


def load_messages(cache_dir: str) -> list[ChatCompletionRequestMessage] | None:
    msgs_file = os.path.join(cache_dir, MSGS_FILE)
    if not os.path.exists(msgs_file):
        return None
    with open_reads(msgs_file) as msgs_in:
        messages: list[ChatCompletionRequestMessage] = json.load(msgs_in)
    return messages


def save_messages(
        cache_dir: str, messages: list[ChatCompletionRequestMessage]) -> None:
    msgs_file = os.path.join(cache_dir, MSGS_FILE)
    with open_writes(msgs_file) as msgs_out:
        json.dump(messages, msgs_out, sort_keys=True, indent=2)


def load_system_prompt(cache_dir: str) -> list[ChatCompletionRequestMessage]:
    sys_prompt_file = os.path.join(cache_dir, SYS_PROMPT_FILE)
    hello_prompt_file = os.path.join(cache_dir, HELLO_PROMPT_FILE)
    if os.path.exists(sys_prompt_file):
        with open_reads(sys_prompt_file) as sys_in:
            system_prompt: str = sys_in.read().strip()
    else:
        system_prompt = SYSTEM_PROMPT
    if os.path.exists(hello_prompt_file):
        with open_reads(hello_prompt_file) as hello_in:
            hello_prompt: str = hello_in.read().strip()
    else:
        hello_prompt = HELLO_PROMPT
    messages: list[ChatCompletionRequestMessage] = [
        {
            "role": "system",
            "content": system_prompt,
        },
    ]
    if hello_prompt:
        messages.append(
            {
                "role": "assistant",
                "content": hello_prompt,
            })
    return messages


def get_active_key() -> str:
    return "active"


def get_response_key(task_id: TaskId) -> str:
    return f"response:{task_id.to_parseable()}"


def get_interrupt_key(task_id: TaskId) -> str:
    return f"interrupt:{task_id.to_parseable()}"


def set_active_task(session: Session, task_id: TaskId | None) -> None:
    # FIXME: detect active tasks that are aborted and switch over to them
    # needs task in response api
    active_key = get_active_key()
    if task_id is None:
        session.pop_value(active_key)
    else:
        session.set_value(active_key, 0, task_id.to_parseable())


def get_active_task(session: Session) -> TaskId | None:
    active_key = get_active_key()
    res = session.get_value(active_key, 0)
    if res is None:
        return None
    return TaskId.parse(res)


def handle_model_output(
        session: Session,
        task_id: TaskId,
        response: list[str],
        content: str | None) -> None:
    if not content:
        return
    response_key = get_response_key(task_id)
    response.append(content)
    session.push_value(response_key, content)
    session.notify_signal(response_key)


def handle_model_finish(session: Session, task_id: TaskId) -> None:
    response_key = get_response_key(task_id)
    session.push_value(response_key, "")
    session.notify_signal(response_key)


def get_model_output(
        session: Session,
        pos: ChunkPosition,
        timeout: float) -> tuple[str, ChunkPosition | None]:
    task_id, index = pos
    response_key = get_response_key(task_id)

    def has_content() -> Literal[True] | str | None:
        res = session.get_value(response_key, index)
        if res is None:
            return None
        if not res:
            return True
        return res

    cur = session.wait_for_signal(response_key, has_content, timeout)
    if cur is None:
        return ("", (task_id, index))
    if not isinstance(cur, str):
        return ("", None)
    response: list[str] = [cur]
    while True:
        index += 1
        cur = session.get_value(response_key, index)
        # NOTE: "" for end of response and None for missing chunk
        if not cur:
            break
        response.append(cur)
    return ("".join(response), (task_id, index) if cur is None else None)


def set_interrupted(session: Session, task_id: TaskId) -> None:
    interrupt_key = get_interrupt_key(task_id)
    session.set_value(interrupt_key, 0, "stop")


def check_is_interrupted(session: Session, task_id: TaskId) -> bool:
    interrupt_key = get_interrupt_key(task_id)
    return session.get_value(interrupt_key, 0) == "stop"
