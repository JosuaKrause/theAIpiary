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
import time
from collections.abc import Callable
from typing import cast, get_args, Literal, TypeAlias, TypedDict

import requests
from scattermind.system.names import UName
from scattermind.system.util import get_short_hash, get_time_str


WorkerId: TypeAlias = str


DEFAULT_WAIT = 17.0  # 17s


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


CONNECTION_CODES: set[int] = {504}


def retry_on_disconnect(
        cb: Callable[[], requests.Response],
        *,
        retries: int | None = None,
        wait_before_retry: float = DEFAULT_WAIT,
        unify: type[BaseException] | None = None,
        include_general_http_errors: bool = False,
        on_retry: Callable[[], None] | None = None) -> requests.Response:
    cur_retries = 1 if retries is None else retries

    def log_retry() -> None:
        print(f"{get_time_str()} could not connect to server! retrying...")

    if on_retry is None:
        on_retry = log_retry

    def handle(exc: BaseException) -> None:
        if cur_retries > 0:
            log_retry()
            return
        if unify is None:
            raise exc
        raise unify() from exc

    while True:
        try:
            resp = cb()
            if resp.status_code in CONNECTION_CODES:
                if cur_retries > 0:
                    log_retry()
                    continue
            resp.raise_for_status()
            return resp
        except ConnectionRefusedError as exc:
            handle(exc)
        except requests.exceptions.HTTPError as exc:
            if include_general_http_errors:
                handle(exc)
            else:
                raise exc
        except requests.ConnectionError as exc:
            handle(exc)
        if wait_before_retry > 0.0:
            time.sleep(wait_before_retry)
        cur_retries -= 1
        if retries is None:
            cur_retries = 1
