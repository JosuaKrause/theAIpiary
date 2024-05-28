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
from typing import cast, get_args, Literal, TypeAlias

from scattermind.system.names import UName
from scattermind.system.util import get_short_hash


WorkerId: TypeAlias = str


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
