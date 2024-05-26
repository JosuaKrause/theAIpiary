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
from typing import Literal, TypedDict

from redipy import RedisConfig
from scattermind.system.names import UName

from swai.system.user.manager import RawPassword, UserManager


RedisUserManagerModule = TypedDict('RedisUserManagerModule', {
    "name": Literal["redis"],
    "cfg": RedisConfig,
})


UserManagerModule = RedisUserManagerModule


def load_user_manager(
        module: UserManagerModule,
        *,
        admin_email: UName,
        admin_pw: RawPassword | None) -> UserManager:
    # pylint: disable=import-outside-toplevel
    if module["name"] == "redis":
        from swai.system.user.redis import RedisUserManager
        return RedisUserManager(
            cfg=module["cfg"], admin_email=admin_email, admin_pw=admin_pw)
    raise ValueError(f"unknown session store: {module['name']}")
