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
from typing import get_args, Literal, TypeAlias


WorkerToken: TypeAlias = str


CapabilityName = Literal[
    "change_capabilities",
    "logout_other_user",
    "create_user",
    "list_users",
    "register_own_worker",
    "register_other_worker",
]
CAPABILITIES: tuple[CapabilityName] = get_args(CapabilityName)
CAP_CHANGE_CAPABILITIES: CapabilityName = "change_capabilities"
CAP_LOGOUT_OTHER_USER: CapabilityName = "logout_other_user"
CAP_CREATE_USER: CapabilityName = "create_user"
CAP_LIST_USERS: CapabilityName = "list_users"
CAP_REGISTER_OWN_WORKER: CapabilityName = "register_own_worker"
CAP_REGISTER_OTHER_WORKER: CapabilityName = "register_other_worker"
