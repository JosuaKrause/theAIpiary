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
