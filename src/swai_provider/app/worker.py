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
import sys
import threading
import traceback
import uuid
from typing import TypedDict

from quick_server import add_shutdown_hook
from scattermind.api.api import InputTypes
from scattermind.system.base import TaskId
from scattermind.system.torch_util import get_arch
from scattermind.system.util import get_time_str

from swai.system.base import WorkerStatus
from swai_provider.app.task_hnd import TaskHandler
from swai_provider.config import get_config
from swai_provider.smind.worker_api import (
    execute_task,
    get_queue_stats,
    GraphProfile,
    load_graph,
    load_smind,
)
from swai_provider.version import get_version


DEFAULT_TIMEOUT = 60.0  # 1min


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


def get_worker_name() -> str:
    device_id = f"{uuid.getnode():0>12x}"
    arch = get_arch()
    return f"{device_id}-{arch}"


def task_loop() -> None:
    config = get_config()

    smind_config = config["smind"]
    smind = load_smind(smind_config)
    graphs = [load_graph(config, smind, "graph_llama.json")]
    worker_name = get_worker_name()
    print(f"device name: {get_worker_name()}")
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
        print(f"picked up {graph.get_ns()=} {task_id=}")
        response = execute_task(task_id, input_data, graph_profile=graph)
        task_hnd.task_finish(task_id, response)
        print("done")
        is_busy = False
        task_hnd.task_heartbeat(
            worker_status=get_status(),
            retries=None,
            wait_before_retry=1.0)

    def hook() -> None:
        nonlocal done

        done = True
        with cond:
            cond.notify_all()

    add_shutdown_hook(hook)

    def heartbeat() -> None:
        while not done:
            hb_sleep = task_hnd.task_heartbeat(
                worker_status=get_status(),
                retries=None,
                wait_before_retry=1.0)
            if hb_sleep > 0.0:
                with cond:
                    cond.wait(hb_sleep)
        task_hnd.task_heartbeat(
            worker_status=get_status(),
            retries=3,
            wait_before_retry=0.1)
        # FIXME: what to do if the heartbeat fails / errors out?

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
        task_hnd.task_heartbeat(
            worker_status=get_status(),
            retries=3,
            wait_before_retry=0.1)
