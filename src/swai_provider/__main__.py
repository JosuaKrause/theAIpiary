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
