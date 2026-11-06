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


CONNECT_TIMEOUT = 10.0  # 10s
"""Time to establish a connection to the server."""
READ_TIMEOUT = 60.0  # 1min
"""Time the server may stay silent while answering a regular request."""
REQUEST_TIMEOUT: tuple[float, float] = (CONNECT_TIMEOUT, READ_TIMEOUT)
"""The (connect, read) timeout of regular requests to the server."""
LONG_POLL_GRACE = 30.0  # 30s
"""Extra read time on top of the wait of a long poll request (the server
holds those requests open for up to the requested wait)."""


def long_poll_timeout(wait: float) -> tuple[float, float]:
    """
    The (connect, read) timeout of a request that the server holds open for
    up to `wait` seconds.

    Args:
        wait (float): The time the server waits before answering.

    Returns:
        tuple[float, float]: The timeout.
    """
    return (CONNECT_TIMEOUT, max(wait, 0.0) + LONG_POLL_GRACE)


def retry_on_disconnect(
        cb: Callable[[], requests.Response],
        *,
        retries: int | None = None,
        wait_before_retry: float = DEFAULT_WAIT,
        unify: type[BaseException] | None = None,
        include_general_http_errors: bool = False,
        on_retry: Callable[[], None] | None = None) -> requests.Response:
    """
    Calls `cb` and retries if the server could not be reached. Connection
    errors, timeouts, and responses with a status in `CONNECTION_CODES` are
    retried. Other HTTP errors are only retried if
    `include_general_http_errors` is set.

    Args:
        cb (Callable[[], requests.Response]): Performs the request.
        retries (int | None, optional): The number of retries after the first
            attempt. If None, the request is retried until it succeeds.
            Defaults to None.
        wait_before_retry (float, optional): The time in seconds to wait
            before each retry. Defaults to DEFAULT_WAIT.
        unify (type[BaseException] | None, optional): If set, a failure that
            would have been retried, if there were retries left, raises this
            exception instead (the original error is the cause). Defaults to
            None.
        include_general_http_errors (bool, optional): Whether to retry all
            HTTP errors. Defaults to False.
        on_retry (Callable[[], None] | None, optional): Called before each
            retry. If None, a message is printed. Defaults to None.

    Returns:
        requests.Response: The successful response.
    """
    cur_retries = 1 if retries is None else retries

    def log_retry() -> None:
        print(f"{get_time_str()} could not connect to server! retrying...")

    retry_cb = log_retry if on_retry is None else on_retry

    def handle(exc: BaseException) -> None:
        if cur_retries > 0:
            retry_cb()
            return
        if unify is None:
            raise exc
        raise unify() from exc

    while True:
        resp: requests.Response | None = None
        try:
            resp = cb()
            resp.raise_for_status()
            return resp
        except ConnectionRefusedError as exc:
            handle(exc)
        except requests.exceptions.HTTPError as exc:
            if resp is not None and resp.status_code in CONNECTION_CODES:
                handle(exc)
            elif include_general_http_errors:
                handle(exc)
            else:
                raise exc
        except (requests.ConnectionError, requests.Timeout) as exc:
            # NOTE: ConnectTimeout is both a ConnectionError and a Timeout
            handle(exc)
        if wait_before_retry > 0.0:
            time.sleep(wait_before_retry)
        cur_retries -= 1
        if retries is None:
            cur_retries = 1
