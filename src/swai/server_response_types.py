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
from typing import Literal, NotRequired, TypedDict

from scattermind.system.response import TaskStatus

from swai.smind.llama_session import VisibleMessage
from swai.system.base import SessionInfoJSON, WorkerId, WorkerStatus
from swai.system.user import CapabilityName, WorkerToken


UserLogged = TypedDict('UserLogged', {
    "logged": Literal[True],
    "email": str,
    "display_name": str,
    "capabilities": list[CapabilityName],
    "discord": str | None,
})
UserNotLogged = TypedDict('UserNotLogged', {
    "logged": Literal[False],
    "message": str,
})
LoginResponse = UserLogged | UserNotLogged
ChangeCapabilityResponse = TypedDict('ChangeCapabilityResponse', {
    "okay": bool,
    "capabilities": list[CapabilityName],
})
UserInfoResponse = TypedDict('UserInfoResponse', {
    "email": str,
    "display_name": str,
    "capabilities": list[CapabilityName],
    "admin": bool,
})
SendResetResponse = TypedDict('SendResetResponse', {
    "email": str,
    "sent": bool,
})
ChangeEmailResponse = TypedDict('ChangeEmailResponse', {
    "email": str,
    "new_email": str,
    "sent": bool,
})
ConfirmEmailChangeResponse = TypedDict('ConfirmEmailChangeResponse', {
    "confirmed": bool,
    "email": str | None,
    "message": str,
})
DeleteUserResponse = TypedDict('DeleteUserResponse', {
    "email": str,
    "deleted": bool,
    "chats": int,
})
UserListResponse = TypedDict('UserListResponse', {
    "users": list[UserInfoResponse],
})
WorkerInfoJSON = TypedDict('WorkerInfoJSON', {
    "worker_id": WorkerId,
    "email": str | None,
    "status": WorkerStatus,
    "own": bool,
})
WorkerInfoResponse = TypedDict('WorkerInfoResponse', {
    "workers": list[WorkerInfoJSON],
})
HeartbeatResponse = TypedDict('HeartbeatResponse', {
    "timeout": float,
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
    "missing": list[int],
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
    "email": str | None,
})
VersionResponse = TypedDict('VersionResponse', {
    "app_name": str,
    "app_commit": str,
    "python": str,
    "deploy_date": str,
    "start_date": str,
    "error": list[str] | None,
})
ChatListResponse = TypedDict('ChatListResponse', {
    "model_sessions": list[SessionInfoJSON],
})
ChatInitResponse = TypedDict('ChatInitResponse', {
    "model_session": str,
    "messages": list[VisibleMessage],
})
ChatRecoverResponse = TypedDict('ChatRecoverResponse', {
    "messages": list[VisibleMessage],
    "task": str | None,
    "status": TaskStatus,
})
ChatPromptResponse = TypedDict('ChatPromptResponse', {
    "task": str | None,
    "status": TaskStatus,
})
ChatTextResponse = TypedDict('ChatTextResponse', {
    "diff": str,
    "task": str | None,
    "next_index": int | None,
    "status": TaskStatus,
})
