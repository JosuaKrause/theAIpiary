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
from typing import TypedDict

import requests
from quick_server import add_shutdown_hook
from scattermind.system.util import get_time_str

from swai_provider.config import get_config
from swai_provider.env import envload_str
from swai_provider.smind.worker_api import load_graph, load_smind
from swai_provider.version import get_version


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


def task_loop() -> None:
    config = get_config()
    api_url = envload_str("SWAI_API_URL")

    smind_config = config["smind"]
    smind = load_smind(smind_config)
    graphs = [load_graph(config, smind, "graph_llama.json")]
    nss = [graph.get_ns().get() for graph in graphs]
    done = False

    def hook() -> None:
        nonlocal done

        done = True

    add_shutdown_hook(hook)

    api = requests.Session()
    while not done:
        pass
