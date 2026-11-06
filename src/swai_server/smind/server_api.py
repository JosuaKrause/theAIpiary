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
import traceback

from scattermind.system.base import TaskId, UserId
from scattermind.system.names import GNamespace
from scattermind.system.response import response_ok, TASK_COMPLETE
from scattermind.system.session.loader import load_session_store
from scattermind.system.session.session import Session, SessionStore
from scattermind.system.util import get_time_str

from swai.clean import shorten
from swai.smind.llama_session import (
    append_new_message,
    ChunkPosition,
    get_active_task,
    get_model_output,
    get_visible_messages,
    load_messages,
    load_system_prompt,
    mark_cut_off,
    ROLE_ASSISTANT,
    ROLE_USER,
    save_messages,
    set_active_task,
    set_interrupted,
    VisibleMessage,
)
from swai.system.base import SessionInfoJSON
from swai_server.auction.queue import TaskQueue
from swai_server.config import Config


DEFAULT_TIMEOUT = 60.0  # 1min
INTERRUPT_TIMEOUT = 5.0
"""How long a new prompt waits for the previous answer of the chat to stop.
"""


def create_session_store(config: Config) -> SessionStore:
    return load_session_store(config["session_store"])


def list_sessions(
        session_store: SessionStore, user_id: UserId) -> list[Session]:
    return list(session_store.get_sessions(user_id))


def init_llama(
        session_store: SessionStore,
        user_id: UserId) -> tuple[Session, list[VisibleMessage]]:
    session = session_store.create_new_session(user_id, copy_from=None)
    with session.get_local_folder() as cache_dir:
        msgs = load_system_prompt(cache_dir)
        save_messages(cache_dir, msgs)
    messages = get_visible_messages(session)
    return (session, messages)


def start_llama_response(
        queue: TaskQueue,
        ns: GNamespace,
        prompt: str,
        session: Session) -> TaskId | None:
    prev_task_id = get_active_task(session)
    if prev_task_id is not None:
        interrupt_task(queue, session, prev_task_id)
    if not prompt:
        return None
    return do_enqueue(queue, ns, prompt, session)


def interrupt_task(
        queue: TaskQueue, session: Session, task_id: TaskId) -> None:
    """
    Stops the active task of the session so that a new prompt can take its
    place. The worker is asked to stop and given `INTERRUPT_TIMEOUT` seconds
    to store its answer so far. If it does not, the answer streamed so far
    is stored instead. Either way the answer is marked as cut off and the task
    is removed from the queue. A worker that comes back later can neither
    change the history nor deliver a result (see `set_active_task`).

    Args:
        queue (TaskQueue): The task queue.
        session (Session): The chat session.
        task_id (TaskId): The active task of the session.
    """
    set_interrupted(session, task_id)
    result = queue.wait_for(task_id, timeout=INTERRUPT_TIMEOUT)
    if result is None:
        print(
            f"previous task {task_id} did not stop within "
            f"{INTERRUPT_TIMEOUT}s; replacing it")
    else:
        try:
            response_ok(result, no_warn=True)
        except ValueError:
            print(traceback.format_exc())
            print(f"error computing previous response {task_id}")
    # NOTE: a worker that stored its answer is not active anymore. if the task
    # is still active, it failed, it did not stop in time, or no worker took it
    store_partial = get_active_task(session) == task_id
    set_active_task(session, None)
    queue.clear_task(task_id)
    if not store_partial:
        return
    partial_response, _ = get_model_output(session, (task_id, 0), 0.1)
    with session.get_local_folder() as cache_dir:
        msgs = load_messages(cache_dir)
        if msgs is not None:
            append_new_message(
                msgs,
                text=mark_cut_off(partial_response),
                role=ROLE_ASSISTANT)
            save_messages(cache_dir, msgs)


SESSION_TIME_KEY = "session_time"
SESSION_SUMMARY_KEY = "session_summary"


def do_enqueue(
        queue: TaskQueue,
        ns: GNamespace,
        prompt: str,
        session: Session) -> TaskId:
    with session.get_local_folder() as cache_dir:
        msgs = load_messages(cache_dir)
        if msgs is not None:
            append_new_message(msgs, text=prompt, role=ROLE_USER)
            save_messages(cache_dir, msgs)
    task_id = queue.enqueue_task(
        ns,
        {
            "prompt": prompt,
            "session": session,
        })
    # NOTE: set the active task right away: a worker only stores its answer
    # if its task is the active one
    set_active_task(session, task_id)
    session.set_value(SESSION_TIME_KEY, 0, get_time_str())
    if not session.get_length(SESSION_SUMMARY_KEY):
        session.set_value(SESSION_SUMMARY_KEY, 0, shorten(prompt))
    return task_id


def get_session_info(session: Session) -> SessionInfoJSON:
    return {
        "model_session": session.get_session_id().to_parseable(),
        "time": session.get_value(SESSION_TIME_KEY, 0),
        "summary": session.get_value(SESSION_SUMMARY_KEY, 0),
    }


def retrieve_llama_response(
        session: Session,
        pos: ChunkPosition) -> tuple[str, ChunkPosition | None]:
    return get_model_output(
        session, pos, timeout=DEFAULT_TIMEOUT)


def recover_llama_chat(
        queue: TaskQueue,
        ns: GNamespace,
        session: Session) -> tuple[list[VisibleMessage], TaskId | None]:
    messages = get_visible_messages(session)
    task_id = get_active_task(session)
    if task_id is not None:
        task_status = queue.get_status(task_id)
        if task_status in TASK_COMPLETE:
            set_active_task(session, None)
            queue.clear_task(task_id)
            task_id = None
    if task_id is None and messages:
        last_msg = messages[-1]
        if last_msg["role"] == "user":
            # NOTE: we got a task that got cleaned up before it finished
            task_id = do_enqueue(queue, ns, "", session)
    return messages, task_id
