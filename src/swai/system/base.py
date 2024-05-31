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
import time
from collections.abc import Callable
from typing import cast, get_args, Literal, TypeAlias, TypedDict

import requests
from scattermind.system.names import UName
from scattermind.system.util import get_short_hash


WorkerId: TypeAlias = str


DEFAULT_WAIT = 1.0  # 1s


def get_worker_id(user_email: UName, worker_name: str) -> WorkerId:
    if not worker_name:
        raise ValueError(f"{worker_name=} cannot be empty")
    return f"{get_short_hash(user_email.get())}-{worker_name}"


WorkerStatus = Literal[
    "unknown",
    "idle",
    "busy",
    "backedup",
    "offline",
]
WORKER_STATUS: set[WorkerStatus] = set(get_args(WorkerStatus))
WORKER_UNAVAILABLE: set[WorkerStatus] = {"offline", "unknown"}


STATUS_MAPPING: dict[WorkerStatus, int] = {
    "idle": 0,
    "busy": 1,
    "backedup": 2,
    "offline": 3,
    "unknown": 4,
}


def to_worker_status(text: str) -> WorkerStatus:
    if text not in WORKER_STATUS:
        raise ValueError(f"{text=} is not in {WORKER_STATUS}")
    return cast(WorkerStatus, text)


SessionInfoJSON = TypedDict('SessionInfoJSON', {
    "model_session": str,
    "time": str | None,
    "summary": str | None,
})


def retry_on_disconnect(
        cb: Callable[[], requests.Response],
        *,
        retries: int | None = None,
        wait_before_retry: float = DEFAULT_WAIT) -> requests.Response:
    cur_retries = 1 if retries is None else retries
    while True:
        try:
            resp = cb()
            resp.raise_for_status()
            return resp
        except ConnectionRefusedError:
            if cur_retries <= 0:
                raise
        except requests.exceptions.HTTPError as err:
            if err.errno != 61:
                raise
            if cur_retries <= 0:
                raise
        except requests.ConnectionError:
            if cur_retries <= 0:
                raise
        if wait_before_retry > 0.0:
            time.sleep(wait_before_retry)
        cur_retries -= 1
        if retries is None:
            cur_retries = 1
