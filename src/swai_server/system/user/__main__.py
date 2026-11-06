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
import getpass
import sys

from redipy.util import python_module

from swai_server.system.user.manager import hash_password, RawPassword


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=f"python -m {python_module()}",
        description="Create a password hash")
    return parser.parse_args()


def run() -> None:
    parse_args()
    try:
        password: RawPassword = getpass.getpass("Password: ", sys.stderr)
        repeat_pw: RawPassword = getpass.getpass(
            "Repeat Password: ", sys.stderr)
        if password != repeat_pw:
            print("passwords did not match!", file=sys.stderr)
            sys.exit(1)
        hashpw = hash_password(password)
        print("ADMIN_EMAIL='admin'")
        print(f"ADMIN_PW='{hashpw}'")
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    run()
