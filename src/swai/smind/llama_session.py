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
from typing import Literal, TypeAlias, TypedDict

from llama_cpp import ChatCompletionRequestMessage
from scattermind.system.base import TaskId
from scattermind.system.io import open_reads, open_writes
from scattermind.system.session.session import Session

from swai.smind.default_prompts import HELLO_PROMPT, SYSTEM_PROMPT


ChunkPosition: TypeAlias = tuple[TaskId, int]


Role = Literal["assistant", "user"]
FullRole = Literal["system"] | Role


ROLE_ASSISTANT: Literal["assistant"] = "assistant"
ROLE_USER: Literal["user"] = "user"
ROLE_SYSTEM: Literal["system"] = "system"


VisibleMessage = TypedDict('VisibleMessage', {
    "role": Role,
    "content": str,
})


MSGS_FILE = "msgs.json"
SYS_PROMPT_FILE = "system_prompt.txt"
HELLO_PROMPT_FILE = "hello_prompt.txt"


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
        if msg["role"] == ROLE_USER or msg["role"] == ROLE_ASSISTANT
    ]


def load_messages(cache_dir: str) -> list[ChatCompletionRequestMessage] | None:
    msgs_file = os.path.join(cache_dir, MSGS_FILE)
    if not os.path.exists(msgs_file):
        return None
    with open_reads(msgs_file) as msgs_in:
        messages: list[ChatCompletionRequestMessage] = json.load(msgs_in)
    return messages


def append_new_message(
        messages: list[ChatCompletionRequestMessage],
        *,
        text: str,
        role: Role) -> None:
    if messages:
        last_msg = messages[-1]
        if last_msg["role"] == role and last_msg["content"] == text:
            return
    msg: ChatCompletionRequestMessage
    if role == ROLE_USER:
        msg = {
            "role": ROLE_USER,
            "content": text,
        }
    elif role == ROLE_ASSISTANT:
        msg = {
            "role": ROLE_ASSISTANT,
            "content": text,
        }
    elif role == ROLE_SYSTEM:
        msg = {
            "role": ROLE_SYSTEM,
            "content": text,
        }
    else:
        raise ValueError(f"invalid {role=}")
    messages.append(msg)


CUT_OFF_MARKER = "\u2026"
"""Ends an answer that was interrupted before the model finished it. The
marker is part of the stored message, so the client shows it after a reload
and the model sees in later turns that its answer did not end there."""


def mark_cut_off(text: str) -> str:
    """
    Marks an answer as cut off.

    Args:
        text (str): The answer so far. Can be empty if the model had not
            produced anything yet.

    Returns:
        str: The answer followed by `CUT_OFF_MARKER`.
    """
    text = text.rstrip()
    if not text:
        return CUT_OFF_MARKER
    return f"{text} {CUT_OFF_MARKER}"


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
            "role": ROLE_SYSTEM,
            "content": system_prompt,
        },
    ]
    if hello_prompt:
        messages.append(
            {
                "role": ROLE_ASSISTANT,
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
    # NOTE: only the server sets the active task: when it enqueues a task and
    # when it takes over from a task it interrupted or found complete
    # (`swai_server.smind.server_api`). A worker only clears the active task
    # after storing its answer and only if its task is still the active one.
    # A task that is not active anymore (it was replaced by a new prompt) never
    # changes the chat history; its result is ignored by the queue as well
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

    cur = session.wait_for_signal(response_key, has_content, timeout=timeout)
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
