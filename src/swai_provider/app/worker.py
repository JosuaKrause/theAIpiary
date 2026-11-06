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
import sys
import threading
import traceback
import uuid
from collections.abc import Callable
from typing import TypedDict

from quick_server import add_shutdown_hook
from scattermind.api.api import InputTypes
from scattermind.system.base import TaskId
from scattermind.system.torch_util import get_arch
from scattermind.system.util import get_short_hash, get_time_str

from swai.system.base import DEFAULT_WAIT, WorkerStatus
from swai_provider.app.task_hnd import TaskHandler
from swai_provider.config import get_config
from swai_provider.env import envload_str
from swai_provider.smind.worker_api import (
    execute_task,
    get_queue_stats,
    GraphProfile,
    load_graph,
    load_smind,
)
from swai_provider.version import get_version


DEFAULT_TIMEOUT = 60.0  # 1min
"""How long the server holds a bid open while waiting for a task."""
HEARTBEAT_RETRY_WAIT = DEFAULT_WAIT
"""Wait before the next heartbeat if a heartbeat failed."""


VersionDict = TypedDict('VersionDict', {
    "python_version": str,
    "app_version": str,
    "commit": str,
    "deploy_time": str,
    "start_time": str,
})


def get_version_strs() -> VersionDict:
    py_version = f"{sys.version}"
    version_name = get_version("name")
    version_hash = get_version("hash")
    version_date = get_version("date")
    server_start = get_time_str()
    return {
        "python_version": py_version,
        "app_version": version_name,
        "commit": version_hash,
        "deploy_time": version_date,
        "start_time": server_start,
    }


def get_worker_name(env_file: str) -> str:
    device_id = envload_str("DEVICE_ID", default="")
    if not device_id:
        device_id = get_short_hash(uuid.uuid4().hex)
        with open(env_file, "a", encoding="utf-8") as fout:
            print(f"DEVICE_ID='{device_id}'", file=fout)
    arch = get_arch()
    return f"{device_id}-{arch}"


def send_heartbeat(
        task_hnd: TaskHandler,
        get_status: Callable[[], WorkerStatus],
        *,
        retries: int | None,
        wait_before_retry: float) -> float | None:
    """
    Sends a heartbeat to the server. Failures are logged, not raised.

    Args:
        task_hnd (TaskHandler): The task handler.
        get_status (Callable[[], WorkerStatus]): The status to report.
        retries (int | None): Retries if the server cannot be reached. None
            retries until the server can be reached.
        wait_before_retry (float): The wait between retries.

    Returns:
        float | None: The time until the next heartbeat is due or None if the
            heartbeat failed with an unexpected error.
    """
    try:
        return task_hnd.task_heartbeat(
            worker_status=get_status(),
            retries=retries,
            wait_before_retry=wait_before_retry)
    except Exception:  # pylint: disable=broad-exception-caught
        print(f"{get_time_str()} heartbeat failed:\n{traceback.format_exc()}")
        return None


def heartbeat_loop(
        task_hnd: TaskHandler,
        *,
        get_status: Callable[[], WorkerStatus],
        is_done: Callable[[], bool],
        cond: threading.Condition,
        retry_wait: float = HEARTBEAT_RETRY_WAIT) -> None:
    """
    Sends heartbeats until `is_done` returns True. A failed heartbeat is
    logged and sent again after `retry_wait` seconds. When done, a final
    heartbeat is sent. Notifying `cond` wakes the loop up early.

    Args:
        task_hnd (TaskHandler): The task handler.
        get_status (Callable[[], WorkerStatus]): The status to report.
        is_done (Callable[[], bool]): Whether the provider is shutting down.
        cond (threading.Condition): Notified on shutdown.
        retry_wait (float, optional): The wait after a failed heartbeat.
            Defaults to HEARTBEAT_RETRY_WAIT.
    """
    # NOTE: the local scattermind worker's health is not part of the
    # heartbeat. scattermind's only cheap check is its healthcheck endpoint
    # (`perform_healthcheck` / `ScattermindAPI.get_healthcheck`), but the
    # configured `address_in` is `localhost` (deploy/smind-config.json) which,
    # from the provider (`api`) container of
    # src/swai_client/public/scripts/docker-compose.yml, is not the `worker`
    # container, and local/smind-config.json (`make run-provider`) configures
    # no healthcheck at all. the executor heartbeats in redis are only
    # reachable through an ExecutorManager, which the provider does not load
    # (`load_api` skips it). the server's heartbeat endpoint also has no field
    # for it; only the WorkerStatus is sent
    while not is_done():
        # NOTE: no retries inside the request: a failed heartbeat is sent
        # again on the next interval so the loop can still see a shutdown
        hb_sleep = send_heartbeat(
            task_hnd,
            get_status,
            retries=0,
            wait_before_retry=retry_wait)
        if hb_sleep is None:
            hb_sleep = retry_wait
        if hb_sleep > 0.0:
            with cond:
                if not is_done():
                    cond.wait(hb_sleep)
    send_heartbeat(
        task_hnd,
        get_status,
        retries=3,
        wait_before_retry=0.1)


def task_loop(env_file: str) -> None:
    config = get_config()

    smind_config = config["smind"]
    smind = load_smind(smind_config)
    graphs = [load_graph(config, smind, "graph_llama.json")]
    worker_name = get_worker_name(env_file)
    print(f"{get_time_str()} device name: {worker_name}")
    task_hnd = TaskHandler(worker_name)
    cond = threading.Condition()
    done = False
    is_busy = False

    def get_status() -> WorkerStatus:
        if done:
            return "offline"
        if is_busy:
            return "busy"
        total_queues = 0
        for stats in get_queue_stats(smind):
            total_queues += stats["queue_length"]
        if total_queues > 0:
            return "backedup"
        return "idle"

    def compute_task(
            task: tuple[GraphProfile, TaskId, dict[str, InputTypes]]) -> None:
        nonlocal is_busy

        is_busy = True
        graph, task_id, input_data = task
        print(f"{get_time_str()} picked up {graph.get_ns()=} {task_id=}")
        response = execute_task(task_id, input_data, graph_profile=graph)
        task_hnd.task_finish(task_id, response)
        print(f"{get_time_str()} done")
        is_busy = False
        send_heartbeat(
            task_hnd,
            get_status,
            retries=None,
            wait_before_retry=DEFAULT_WAIT)

    def hook() -> None:
        nonlocal done

        done = True
        with cond:
            cond.notify_all()

    add_shutdown_hook(hook)

    def is_done() -> bool:
        return done

    def heartbeat() -> None:
        heartbeat_loop(
            task_hnd, get_status=get_status, is_done=is_done, cond=cond)

    th = threading.Thread(target=heartbeat, daemon=True)
    th.start()

    try:
        while not done:
            maybe_task = task_hnd.task_bid(graphs, timeout=DEFAULT_TIMEOUT)
            if maybe_task is None:
                continue  # NOTE: no sleep!
            compute_task(maybe_task)
    finally:
        if sys.exc_info()[1] is not None:
            print(traceback.format_exc())
        done = True
        with cond:
            cond.notify_all()
        send_heartbeat(
            task_hnd,
            get_status,
            retries=3,
            wait_before_retry=0.1)
