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
from typing import get_args, Literal, TypeAlias


WorkerToken: TypeAlias = str


CapabilityName = Literal[
    "change_capabilities",
    "logout_other_user",
    "create_user",
    "list_users",
    "write_other_chat",
    "read_other_chat",
    "register_own_worker",
    "register_other_worker",
]
CAPABILITIES: tuple[CapabilityName] = get_args(CapabilityName)
CAP_CHANGE_CAPABILITIES: CapabilityName = "change_capabilities"
CAP_LOGOUT_OTHER_USER: CapabilityName = "logout_other_user"
CAP_CREATE_USER: CapabilityName = "create_user"
CAP_LIST_USERS: CapabilityName = "list_users"
CAP_WRITE_OTHER_CHAT: CapabilityName = "write_other_chat"
CAP_READ_OTHER_CHAT: CapabilityName = "read_other_chat"
CAP_REGISTER_OWN_WORKER: CapabilityName = "register_own_worker"
CAP_REGISTER_OTHER_WORKER: CapabilityName = "register_other_worker"
