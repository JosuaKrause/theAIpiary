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
from typing import NotRequired, TypedDict

from swai.smind.llama_session import VisibleMessage
from swai.system.user.manager import CapabilityName, WorkerToken


LoginResponse = TypedDict('LoginResponse', {
    "user_name": str | None,
    "logged": bool,
    "capabilities": list[CapabilityName],
    "message": str | None,
})
TaskBidResponse = TypedDict('TaskBidResponse', {
    "ns": str | None,
    "task_id": str | None,
    "input_data": str | None,
})
TaskFinishResponse = TypedDict('TaskFinishResponse', {
    "well_done": bool,
})
WorkerTokenResponse = TypedDict('WorkerTokenResponse', {
    "worker_token": WorkerToken,
})
WorkerUserResponse = TypedDict('WorkerUserResponse', {
    "user_id": str | None,
})
WorkerSessionResponse = TypedDict('WorkerSessionResponse', {
    "ok": bool,
})
WorkerSessionListResponse = TypedDict('WorkerSessionListResponse', {
    "sessions": list[str],
})
WorkerValueResponse = TypedDict('WorkerValueResponse', {
    "value": NotRequired[str | None],
    "length": NotRequired[int],
    "success": bool,
})
WorkerUploadResponse = TypedDict('WorkerUploadResponse', {
    "done": bool,
})
WorkerBlobListResponse = TypedDict('WorkerBlobListResponse', {
    "blobs": list[str],
})
WorkerBlobHashResponse = TypedDict('WorkerBlobHashResponse', {
    "blob_hashes": dict[str, str],
})
WorkerKeysResponse = TypedDict('WorkerKeysResponse', {
    "keys": list[str],
})
WorkerSignalResponse = TypedDict('WorkerSignalResponse', {
    "signal": bool,
})
ResetTokenResponse = TypedDict('ResetTokenResponse', {
    "user_name": str,
    "reset_token": str,
})
VersionResponse = TypedDict('VersionResponse', {
    "app_name": str,
    "app_commit": str,
    "python": str,
    "deploy_date": str,
    "start_date": str,
    "error": list[str] | None,
})
ChatInitResponse = TypedDict('ChatInitResponse', {
    "model_session": str,
    "messages": list[VisibleMessage],
})
ChatRecoverResponse = TypedDict('ChatRecoverResponse', {
    "messages": list[VisibleMessage],
    "task": str | None,
})
ChatPromptResponse = TypedDict('ChatPromptResponse', {
    "task": str,
})
ChatTextResponse = TypedDict('ChatTextResponse', {
    "diff": str,
    "task": str | None,
    "next_index": int | None,
})
