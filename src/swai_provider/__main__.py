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
import argparse
import os

from dotenv import load_dotenv
from quick_server import setup_shutdown
from redipy.util import python_module

from swai_provider.app.worker import get_version_strs, task_loop


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=f"python -m {python_module()}",
        description="Run the provider worker")
    parser.add_argument(
        "--env",
        help="loads the given env file at startup")
    return parser.parse_args()


def run() -> None:
    args = parse_args()
    env_file: str = args.env
    if not os.path.exists(env_file):
        raise ValueError(f"could not load env! {env_file} does not exist!")
    print(f"loading env {env_file}")
    load_dotenv(env_file)
    versions = get_version_strs()
    print(f"python version: {versions['python_version']}")
    print(f"app version: {versions['app_version']}")
    print(f"app commit: {versions['commit']}")
    print(f"deploy time: {versions['deploy_time']}")
    print(f"start time: {versions['start_time']}")
    setup_shutdown()
    task_loop(env_file)


if __name__ == "__main__":
    run()
