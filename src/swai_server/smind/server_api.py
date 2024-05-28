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
from scattermind.system.base import TaskId, UserId
from scattermind.system.names import GNamespace
from scattermind.system.response import response_ok, TASK_COMPLETE
from scattermind.system.session.loader import load_session_store
from scattermind.system.session.session import Session, SessionStore

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
from swai_server.auction.queue import TaskQueue
from swai_server.config import Config


DEFAULT_TIMEOUT = 60.0  # 1min


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
        session: Session) -> TaskId:
    prev_task_id = get_active_task(session)
    if prev_task_id is not None:
        set_interrupted(session, prev_task_id)
        result = queue.wait_for(prev_task_id, timeout=DEFAULT_TIMEOUT)
        if result is None:
            raise ValueError(
                f"could not terminate previous task {prev_task_id}")
        try:
            response_ok(result, no_warn=True)
        except ValueError as exc:
            raise ValueError("error computing previous response") from exc
        queue.clear_task(prev_task_id)
    return do_enqueue(queue, ns, prompt, session)


def do_enqueue(
        queue: TaskQueue,
        ns: GNamespace,
        prompt: str,
        session: Session) -> TaskId:
    task_id = queue.enqueue_task(
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
