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
import io
import os
import shutil
import sys
import threading
from http.cookies import SimpleCookie
from typing import TypedDict

from quick_server import create_server, PreventDefaultResponse, QuickServer
from quick_server import QuickServerRequestHandler as QSRH
from quick_server import ReqArgs, ReqNext, Response
from scattermind.system.base import SessionId, TaskId, UserId
from scattermind.system.io import open_readb, open_writeb, remove_file
from scattermind.system.names import GNamespace, UName
from scattermind.system.response import redis_to_response
from scattermind.system.session.session import Session
from scattermind.system.util import get_time_str, parse_time_str, to_bool

from swai.auth import parse_authorization
from swai.clean import sanity_check
from swai.server_response_types import (
    ChangeCapabilityResponse,
    ChatInitResponse,
    ChatListResponse,
    ChatPromptResponse,
    ChatRecoverResponse,
    ChatTextResponse,
    HeartbeatResponse,
    LoginResponse,
    ResetTokenResponse,
    TaskBidResponse,
    TaskFinishResponse,
    UserInfoResponse,
    UserListResponse,
    VersionResponse,
    WorkerBlobHashResponse,
    WorkerBlobListResponse,
    WorkerInfoJSON,
    WorkerInfoResponse,
    WorkerKeysResponse,
    WorkerSessionListResponse,
    WorkerSessionResponse,
    WorkerSignalResponse,
    WorkerTokenResponse,
    WorkerUploadResponse,
    WorkerUserResponse,
    WorkerValueResponse,
)
from swai.system.base import SessionInfoJSON, STATUS_MAPPING, to_worker_status
from swai.system.user.loader import load_user_manager
from swai.system.user.manager import (
    as_capability,
    DEFAULT_CAPABILITIES,
    HashPassword,
    RawPassword,
    ResetToken,
    SessionToken,
)
from swai.system.user.secure import SecureContext
from swai_server.app.email import (
    EmailConfig,
    is_valid_email_config,
    send_create_user,
    send_password_reset,
)
from swai_server.auction.queue import TaskQueue, WorkerInfo
from swai_server.config import get_config
from swai_server.env import envload_int, envload_path, envload_str
from swai_server.smind.server_api import (
    create_session_store,
    get_session_info,
    init_llama,
    list_sessions,
    recover_llama_chat,
    retrieve_llama_response,
    start_llama_response,
)
from swai_server.version import get_version


MAX_INPUT_LENGTH = 10 * 1024  # 10KiB


VersionDict = TypedDict('VersionDict', {
    "python_version_detail": str,
    "python_version": str,
    "server_version": str,
    "app_version": str,
    "commit": str,
    "deploy_time": str,
    "start_time": str,
})


def get_version_strs() -> VersionDict:
    py_version_detail = f"{sys.version}"
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    version_name = get_version("name")
    version_hash = get_version("hash")
    version_date = get_version("date")
    server_start = get_time_str()
    return {
        "python_version_detail": py_version_detail,
        "python_version": py_version,
        "server_version": f"AIpiaryServer/{version_name[1:]}",
        "app_version": version_name,
        "commit": version_hash,
        "deploy_time": version_date,
        "start_time": server_start,
    }


def setup(
        server: QuickServer,
        *,
        deploy: bool,
        versions: VersionDict) -> tuple[QuickServer, str]:
    prefix = "/api"

    server.suppress_noise = True

    server.register_shutdown()

    def report_slow_requests(
            method_str: str,
            path: str,
            duration: float,
            complete: bool) -> None:
        duration_str = f"({duration}s)" if complete else "pending"
        print(f"slow request {method_str} {path} {duration_str}")

    max_upload = 120 * 1024 * 1024  # 120MiB
    server_timeout = 10 * 60
    server.report_slow_requests = (64.0, report_slow_requests)
    server.max_file_size = max_upload
    server.max_chunk_size = max_upload
    server.timeout = server_timeout
    server.socket.settimeout(server_timeout)

    server.link_empty_favicon_fallback()

    server.cross_origin = True  # FIXME: for now...

    if deploy:
        server.no_command_loop = True

    server.update_version_string(versions["server_version"])

    server.set_common_invalid_paths(["/", "//"])

    server.set_default_token_expiration(48 * 60 * 60)  # 2 days

    config = get_config()

    admin_email_str = envload_str("ADMIN_EMAIL", default="")
    admin_pw: HashPassword | None = envload_str("ADMIN_PW", default="")
    if not admin_email_str or not admin_pw:
        admin_email = None
        admin_pw = None
    else:
        admin_email = UName(admin_email_str)
        print(f"admin is {admin_email.get()}")

    discord: str | None = envload_str("DISCORD_URL", default="")
    if not discord:
        discord = None
    email_config: EmailConfig = {
        "own_url": envload_str("OWN_URL", default="").removesuffix("/"),
        "own_email": envload_str("OWN_EMAIL", default=""),
        "smtp_host": envload_str("SMTP_HOST", default=""),
        "smtp_port": envload_int("SMTP_PORT", default=587),
        "smtp_user": envload_str("SMTP_USER", default=""),
        "smtp_pw": envload_str("SMTP_PW", default=""),
    }
    if not is_valid_email_config(email_config):
        if email_config["smtp_pw"]:
            email_config["smtp_pw"] = "***"
        print(f"EMAIL CONFIG IS NOT VALID! {email_config}")

    session_store = create_session_store(config)
    task_queue = TaskQueue(session_store, config["task_queue"])
    sec_ctx = SecureContext(load_user_manager(
        config["user_mng"], admin_email=admin_email, admin_pw=admin_pw))
    model_ns = GNamespace("llama")

    # NOTE: not needed
    # server.add_default_white_list()
    # server.add_file_patterns(["*.sh", "*.bat"], blacklist=False)

    public_path = envload_path("UI_PATH", default="build/")
    server.bind_path("/", public_path)

    def file_fallback(_: str) -> str:
        return os.path.join(public_path, "index.html")

    server.set_file_fallback_hook(file_fallback)

    def send_login_cookie(req: QSRH, user_session: SessionToken) -> None:
        cookie = SimpleCookie()
        cookie["user_session"] = user_session
        cookie["user_session"]["path"] = "/"
        cookie["user_session"]["max-age"] = 90*24*60*60
        req.send_cookie(cookie)

    def send_logout_cookie(req: QSRH) -> None:
        cookie = SimpleCookie()
        cookie["user_session"] = ""
        cookie["user_session"]["path"] = "/"
        cookie["user_session"]["expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
        req.send_cookie(cookie)

    def redirect_to_www(
            req: QSRH, path: str, _cookie: SimpleCookie | None) -> None:
        _proto, orig_host = req.get_original_host()
        orig_host = orig_host.removesuffix("/")
        if not orig_host.endswith("theaipiary.com"):
            return
        if orig_host == "theaipiary.com":
            orig_host = f"www.{orig_host}"
        else:
            return
        req.send_response(301, "Use www subdomain.")
        req.send_header("Location", f"https://{orig_host}{path}")
        req.end_headers()
        raise PreventDefaultResponse()

    server.add_pre_middleware(redirect_to_www)

    def maybe_user_session(
            _req: QSRH, rargs: ReqArgs, okay: ReqNext) -> Response | ReqNext:
        cookie = rargs["cookie"]
        if cookie is None:
            return okay
        session_cookie = cookie.get("user_session")
        if session_cookie is None:
            return okay
        user_session = session_cookie.value
        user_email = sec_ctx.get_email(user_session)
        if user_email is None:
            return okay
        rargs["meta"]["user_session"] = user_session
        rargs["meta"]["user_email"] = user_email
        return okay

    def verify_user_session(
            req: QSRH, rargs: ReqArgs, okay: ReqNext) -> Response | ReqNext:
        maybe_user_session(req, rargs, okay)
        user_session = rargs["meta"].get("user_session")
        if user_session is None:
            return Response("must be logged in", 401)
        user_email: UName | None = rargs["meta"].get("user_email")
        if user_email is None:
            send_logout_cookie(req)
            return Response("must be logged in", 401)
        return okay

    def verify_prompt(
            _req: QSRH, rargs: ReqArgs, okay: ReqNext) -> Response | ReqNext:
        args = rargs.get("post", {})
        text = args.get("prompt")
        if text is None:
            text = rargs.get("query", {}).get("p")
        if text is None:
            raise KeyError("POST 'prompt' or GET 'p' not set")
        text = f"{text}"
        if len(text) > MAX_INPUT_LENGTH:
            return Response(
                f"prompt length exceeds {MAX_INPUT_LENGTH} bytes", 413)
        rargs["meta"]["prompt"] = sanity_check(text)
        return okay

    def verify_model_session_read(
            _req: QSRH, rargs: ReqArgs, okay: ReqNext) -> Response | ReqNext:
        args = rargs["post"]
        session = session_store.get_session(
            SessionId.parse(args["model_session"]))
        user_id = session_store.get_user(session.get_session_id())
        user_session = rargs["meta"]["user_session"]
        sec_ctx.ensure_can_read_chat(user_session, user_id)
        rargs["meta"]["model_session"] = session
        return okay

    def verify_model_session_write(
            _req: QSRH, rargs: ReqArgs, okay: ReqNext) -> Response | ReqNext:
        args = rargs["post"]
        session = session_store.get_session(
            SessionId.parse(args["model_session"]))
        user_id = session_store.get_user(session.get_session_id())
        user_session: SessionToken = rargs["meta"]["user_session"]
        sec_ctx.ensure_can_write_chat(user_session, user_id)
        rargs["meta"]["model_session"] = session
        return okay

    def verify_worker_token(
            req: QSRH, rargs: ReqArgs, okay: ReqNext) -> Response | ReqNext:
        auth = req.headers.get("authorization")
        if auth is None:
            return Response("must include authorization header", 401)
        email, worker_token = parse_authorization(auth)
        sec_ctx.ensure_worker_token(email, worker_token)
        rargs["meta"]["user_email"] = email
        return okay

    # *** misc ***

    @server.json_get(f"{prefix}/version")
    def _get_version(_req: QSRH, _rargs: ReqArgs) -> VersionResponse:
        return {
            "app_name": versions["app_version"],
            "app_commit": versions["commit"],
            "python": versions["python_version"],
            "deploy_date": versions["deploy_time"],
            "start_date": versions["start_time"],
            "error": None,
        }

    # *** user management ***

    @server.json_post(f"{prefix}/user/current")
    @server.middleware(maybe_user_session)
    def _post_user_current(_req: QSRH, rargs: ReqArgs) -> LoginResponse:
        user_session: SessionToken | None = rargs["meta"].get("user_session")
        if user_session is None:
            return {
                "logged": False,
                "message": "not logged in",
            }
        user_email: UName | None = rargs["meta"].get("user_email")
        if user_email is None:
            return {
                "logged": False,
                "message": f"no user in {user_session=}",
            }
        user_info = sec_ctx.get_user_info(user_session, user_email)
        return {
            "logged": True,
            "email": user_info["email"].get(),
            "display_name": user_info["display_name"],
            "capabilities": sorted(user_info["capabilities"]),
            "discord": discord,
        }

    @server.json_post(f"{prefix}/user/login")
    def _post_user_login(req: QSRH, rargs: ReqArgs) -> LoginResponse:
        args = rargs["post"]
        user_name: str = args["name"]
        password: RawPassword = args["password"]
        user_session = sec_ctx.login(UName(user_name), password)
        if user_session is None:
            return {
                "logged": False,
                "message": "username or password is incorrect",
            }
        user_email = sec_ctx.get_email(user_session)
        if user_email is None:
            return {
                "logged": False,
                "message": f"invalid {user_session=}",
            }
        send_login_cookie(req, user_session)
        user_info = sec_ctx.get_user_info(user_session, user_email)
        return {
            "logged": True,
            "email": user_info["email"].get(),
            "display_name": user_info["display_name"],
            "capabilities": sorted(user_info["capabilities"]),
            "discord": discord,
        }

    @server.json_post(f"{prefix}/user/create")
    @server.middleware(verify_user_session)
    def _post_user_create(
            _req: QSRH, rargs: ReqArgs) -> ResetTokenResponse:
        user_session: SessionToken = rargs["meta"]["user_session"]
        user_email: UName = rargs["meta"]["user_email"]
        args = rargs["post"]
        new_email_str: str = args["new_email"]
        new_display: str = args["new_display"]
        new_email = UName(new_email_str)
        if not sec_ctx.create_user(user_session, new_email, new_display):
            return {
                "email": None,
            }
        for cap in DEFAULT_CAPABILITIES:
            sec_ctx.force_capability(new_email, cap, has=True)
        reset_token = sec_ctx.generate_reset_token(new_email)
        user_info = sec_ctx.force_user_info(user_email)
        send_create_user(
            email_config,
            new_email=new_email,
            new_display=new_display,
            creator=user_info,
            reset_token=reset_token,
            discord=discord)
        return {
            "email": new_email.get(),
        }

    @server.json_post(f"{prefix}/user/list")
    @server.middleware(verify_user_session)
    def _post_user_list(_req: QSRH, rargs: ReqArgs) -> UserListResponse:
        user_session: SessionToken = rargs["meta"]["user_session"]
        user_list = sec_ctx.list_users(user_session)

        def get_user_info(user: UName) -> UserInfoResponse:
            info = sec_ctx.get_user_info(user_session, user)
            capabilities = sec_ctx.maybe_list_capabilities(
                user_session, user)
            return {
                "email": info["email"].get(),
                "display_name": info["display_name"],
                "capabilities": sorted(capabilities),
            }

        return {
            "users": [
                get_user_info(user) for user in user_list
            ],
        }

    @server.json_post(f"{prefix}/user/create_worker_token")
    @server.middleware(verify_user_session)
    def _post_user_create_worker_token(
            _req: QSRH, rargs: ReqArgs) -> WorkerTokenResponse:
        user_session: SessionToken = rargs["meta"]["user_session"]
        user_email: UName = rargs["meta"]["user_email"]
        args = rargs["post"]
        user_name: str | None = args.get("name")
        if user_name is not None:
            user_email = UName(user_name)
        worker_token = sec_ctx.create_worker_token(user_session, user_email)
        return {
            "worker_token": worker_token,
        }

    @server.json_post(f"{prefix}/user/reset_password_token")
    def _post_user_reset_password_token(
            _req: QSRH, rargs: ReqArgs) -> ResetTokenResponse:
        args = rargs["post"]
        user_name: str = args["name"]
        user_email = UName(user_name)
        reset_token = sec_ctx.generate_reset_token(user_email)
        if reset_token is None:
            return {
                "email": None,
            }
        user_info = sec_ctx.force_user_info(user_email)
        send_password_reset(
            email_config,
            user=user_info,
            reset_token=reset_token)
        return {
            "email": user_email.get(),
        }

    @server.json_post(f"{prefix}/user/reset_password")
    def _post_user_reset_password(req: QSRH, rargs: ReqArgs) -> LoginResponse:
        args = rargs["post"]
        password: RawPassword = args["password"]
        reset_token: ResetToken = args["reset_token"]
        user_email = sec_ctx.set_password(password, reset_token)
        if user_email is not None:
            sec_ctx.force_logout_user(user_email)
            send_logout_cookie(req)
            user_info = sec_ctx.force_user_info(user_email)
            return {
                # NOTE: we are not logged in but we need this to redirect!
                "logged": True,
                "email": user_info["email"].get(),
                "display_name": user_info["display_name"],
                "capabilities": sorted(user_info["capabilities"]),
                "discord": discord,
            }
        return {
            "logged": False,
            "message": "password set",
        }

    @server.json_put(f"{prefix}/user/capability")
    @server.middleware(verify_user_session)
    def _put_user_capability(
            _req: QSRH, rargs: ReqArgs) -> ChangeCapabilityResponse:
        user_session: SessionToken = rargs["meta"]["user_session"]
        args = rargs["post"]
        user_name: str = args["name"]
        user_email = UName(user_name)
        capability = as_capability(args["capability"])
        set_has = to_bool(args["set_has"])
        sec_ctx.set_capability(
            user_session, user_email, capability, has=set_has)
        return {
            "okay": True,
        }

    @server.json_post(f"{prefix}/user/logout")
    @server.middleware(verify_user_session)
    def _post_user_logout(req: QSRH, rargs: ReqArgs) -> LoginResponse:
        user_session: SessionToken = rargs["meta"]["user_session"]
        args = rargs["post"]
        user_name: str | None = args.get("name")

        if user_name is not None:
            sec_ctx.logout_user(user_session, UName(user_name))
        else:
            sec_ctx.logout(user_session)
            send_logout_cookie(req)
        return {
            "logged": False,
            "message": "successfully logged out",
        }

    # TODO:
    # - add user mod (+reset +logout +email +delete)
    # - edit capabilities

    # *** worker API ***

    # * tasks *

    @server.json_post(f"{prefix}/task/workers")
    @server.middleware(verify_user_session)
    def _post_task_workers(_req: QSRH, rargs: ReqArgs) -> WorkerInfoResponse:
        user_session: SessionToken = rargs["meta"]["user_session"]
        user_email: UName = rargs["meta"]["user_email"]
        status_mapping = STATUS_MAPPING

        def convert(info: WorkerInfo) -> WorkerInfoJSON:
            email = sec_ctx.secure_email(user_session, info["email"])
            if email is None:
                email_str = None
            else:
                email_str = email.get()
            return {
                "worker_id": info["worker_id"],
                "email": email_str,
                "status": info["status"],
                "own": info["email"] == user_email,
            }

        def sort_key(info: WorkerInfoJSON) -> tuple[int, int, str, str]:
            email_str = "" if info["email"] is None else info["email"]
            return (
                0 if info["own"] else 1,
                status_mapping.get(info["status"], 5),
                email_str,
                info["worker_id"],
            )

        return {
            "workers": sorted((
                convert(worker)
                for worker in task_queue.get_all_workers()
            ), key=sort_key),
        }

    @server.json_post(f"{prefix}/task/heartbeat")
    @server.middleware(verify_worker_token)
    def _post_task_heartbeat(_req: QSRH, rargs: ReqArgs) -> HeartbeatResponse:
        user_email: UName = rargs["meta"]["user_email"]
        args = rargs["post"]
        worker_name: str = args["worker_name"]
        worker_status = to_worker_status(args["status"])
        timeout = task_queue.heartbeat(
            user_email=user_email,
            worker_name=worker_name,
            worker_status=worker_status)
        return {
            "timeout": timeout,
        }

    @server.json_post(f"{prefix}/task/bid")
    @server.middleware(verify_worker_token)
    def _post_task_bid(_req: QSRH, rargs: ReqArgs) -> TaskBidResponse:
        user_email: UName = rargs["meta"]["user_email"]
        args = rargs["post"]
        worker_name: str = args["worker_name"]
        nss = [GNamespace(ns) for ns in args["nss"]]
        timeout = float(args["timeout"])
        assert timeout > 0.0
        task = task_queue.pop_task(
            nss,
            user_email=user_email,
            worker_name=worker_name,
            timeout=timeout)
        if task is None:
            return {
                "ns": None,
                "task_id": None,
                "input_data": None,
            }
        ns, task_id, input_data = task
        return {
            "ns": ns.get(),
            "task_id": task_id.to_parseable(),
            "input_data": input_data,
        }

    @server.json_post(f"{prefix}/task/finish")
    @server.middleware(verify_worker_token)
    def _post_task_finish(_req: QSRH, rargs: ReqArgs) -> TaskFinishResponse:
        user_email: UName = rargs["meta"]["user_email"]
        args = rargs["post"]
        worker_name: str = args["worker_name"]
        task_id = TaskId.parse(args["task_id"])
        response = redis_to_response(args["response"])
        task_queue.set_result(
            task_id,
            user_email=user_email,
            worker_name=worker_name,
            response=response)
        return {
            "well_done": True,
        }

    # * smind sessions *

    @server.json_post(f"{prefix}/smind/user")
    @server.middleware(verify_worker_token)
    def _post_smind_user(_req: QSRH, rargs: ReqArgs) -> WorkerUserResponse:
        args = rargs["post"]
        session_id = SessionId.parse(args["session"])
        user_id = session_store.get_user(session_id)
        return {
            "user_id": None if user_id is None else user_id.to_parseable(),
        }

    @server.json_put(f"{prefix}/smind/session")
    @server.middleware(verify_worker_token)
    def _put_smind_session(
            _req: QSRH, rargs: ReqArgs) -> WorkerSessionResponse:
        args = rargs["post"]
        user_id = UserId.parse(args["user_id"])
        session_id = SessionId.parse(args["session"])
        session_store.register_session(user_id, session_id)
        return {
            "ok": True,
        }

    @server.json_post(f"{prefix}/smind/session")
    @server.middleware(verify_worker_token)
    def _post_smind_session(
            _req: QSRH, rargs: ReqArgs) -> WorkerSessionListResponse:
        args = rargs["post"]
        user_id = UserId.parse(args["user_id"])
        return {
            "sessions": [
                session.get_session_id().to_parseable()
                for session in session_store.get_sessions(user_id)
            ],
        }

    @server.json_delete(f"{prefix}/smind/session")
    @server.middleware(verify_worker_token)
    def _delete_smind_session(
            _req: QSRH, rargs: ReqArgs) -> WorkerSessionResponse:
        args = rargs["post"]
        session_id = SessionId.parse(args["session"])
        session_store.remove(session_id)
        return {
            "ok": True,
        }

    @server.json_post(f"{prefix}/smind/value")
    @server.middleware(verify_worker_token)
    def _post_smind_value(
            _req: QSRH, rargs: ReqArgs) -> WorkerValueResponse:
        args = rargs["post"]
        session_id = SessionId.parse(args["session"])
        key: str = args["key"]
        index = int(args.get("index", 0))
        value: str | None = args.get("value")
        op = args["op"]
        if op == "get":
            value = session_store.get_value(session_id, key, index)
            return {
                "value": value,
                "success": True,
            }
        if op == "pop":
            value = session_store.pop_value(session_id, key)
            return {
                "value": value,
                "success": True,
            }
        if op == "set":
            if value is None:
                raise ValueError(f"need value for {op=}")
            session_store.set_value(session_id, key, index, value)
            return {
                "success": True,
            }
        if op == "push":
            if value is None:
                raise ValueError(f"need value for {op=}")
            session_store.push_value(session_id, key, value)
            return {
                "success": True,
            }
        if op == "length":
            length = session_store.get_length(session_id, key)
            return {
                "length": length,
                "success": True,
            }
        raise ValueError(f"unknown {op=}")

    @server.json_post(f"{prefix}/smind/keys")
    @server.middleware(verify_worker_token)
    def _post_smind_keys(
            _req: QSRH, rargs: ReqArgs) -> WorkerKeysResponse:
        args = rargs["post"]
        session_id = SessionId.parse(args["session"])
        return {
            "keys": session_store.get_keys(session_id),
        }

    @server.json_post(f"{prefix}/smind/signal")
    @server.middleware(verify_worker_token)
    def _post_smind_signal(
            _req: QSRH, rargs: ReqArgs) -> WorkerSignalResponse:
        args = rargs["post"]
        session_id = SessionId.parse(args["session"])
        key: str = args["key"]
        session_store.notify_signal(session_id, key)
        return {
            "signal": True,
        }

    @server.json_post(f"{prefix}/smind/wait")
    @server.middleware(verify_worker_token)
    def _post_smind_wait(
            _req: QSRH, rargs: ReqArgs) -> WorkerSignalResponse:
        args = rargs["post"]
        session_id = SessionId.parse(args["session"])
        key: str = args["key"]
        timeout = float(args["timeout"])
        assert timeout > 0.0

        def any_signal() -> bool:
            return True

        res = session_store.wait_for_signal(
            session_id, key, any_signal, timeout=timeout)
        return {
            "signal": bool(res),
        }

    @server.json_put(f"{prefix}/smind/blob")
    @server.middleware(verify_worker_token)
    def _put_smind_blob(_req: QSRH, rargs: ReqArgs) -> WorkerUploadResponse:
        # NOTE: file uploads convert all values to strings!
        args = rargs["post"]
        session_id = SessionId.parse(args["session"])
        blob: str = args["blob"]
        upload_id: str = args["upload_id"]
        fragment = int(args["fragment"])
        complete = to_bool(args["complete"])
        files = rargs["files"]
        scratch = session_store.scratch_folder()

        def get_fragment_fname(pos: int) -> str:
            return os.path.join(scratch, f"{upload_id}.{pos}.chunk")

        with open_writeb(get_fragment_fname(fragment)) as fout:
            shutil.copyfileobj(files["blob"], fout)  # type: ignore

        if complete:
            fnames: list[str] = [
                get_fragment_fname(pos)
                for pos in range(fragment + 1)
            ]
            missing: list[int] = []
            for (pos, cur) in enumerate(fnames):
                if not os.path.exists(cur):
                    missing.append(pos)
            if missing:
                return {
                    "done": False,
                    "missing": missing,
                }
            with session_store.open_blob_write(session_id, blob) as fout:
                for cur in fnames:
                    with open_readb(cur) as fin:
                        shutil.copyfileobj(fin, fout)  # type: ignore
            for cur in fnames:
                remove_file(cur)

        return {
            "done": True,
            "missing": [],
        }

    @server.text_post(f"{prefix}/smind/blob")
    @server.middleware(verify_worker_token)
    def _post_smind_blob(req: QSRH, rargs: ReqArgs) -> Response:
        args = rargs["post"]
        session_id = SessionId.parse(args["session"])
        blob: str = args["blob"]
        bout = io.BytesIO()
        with session_store.open_blob_read(session_id, blob) as fin:
            shutil.copyfileobj(fin, bout)
        bout.seek(0, io.SEEK_SET)
        req.send_header(
            "content-disposition", f"attachment; filename=\"{blob}\"")
        return Response(bout, ctype="application/octet-stream")

    @server.json_delete(f"{prefix}/smind/blob")
    @server.middleware(verify_worker_token)
    def _delete_smind_blob(
            _req: QSRH, rargs: ReqArgs) -> WorkerUploadResponse:
        args = rargs["post"]
        session_id = SessionId.parse(args["session"])
        blobs: list[str] = args["blobs"]
        session_store.blob_remove(session_id, blobs)
        return {
            "done": True,
            "missing": [],
        }

    @server.json_post(f"{prefix}/smind/list")
    @server.middleware(verify_worker_token)
    def _post_smind_list(
            _req: QSRH, rargs: ReqArgs) -> WorkerBlobListResponse:
        args = rargs["post"]
        session_id = SessionId.parse(args["session"])
        return {
            "blobs": session_store.blob_list(session_id),
        }

    @server.json_post(f"{prefix}/smind/hash")
    @server.middleware(verify_worker_token)
    def _post_smind_hash(
            _req: QSRH, rargs: ReqArgs) -> WorkerBlobHashResponse:
        args = rargs["post"]
        session_id = SessionId.parse(args["session"])
        blobs: list[str] = args["blobs"]
        return {
            "blob_hashes": session_store.blob_hash(session_id, blobs),
        }

    # # # SECURE # # #
    server.add_middleware(verify_user_session)

    # *** chat ***

    @server.json_post(f"{prefix}/chat/list")
    def _post_chat_list(_req: QSRH, rargs: ReqArgs) -> ChatListResponse:
        user_session: SessionToken = rargs["meta"]["user_session"]
        user_email: UName = rargs["meta"]["user_email"]
        user_id = sec_ctx.get_user_id(user_session, user_email)
        sessions = list_sessions(session_store, user_id)

        def sort_key(info: SessionInfoJSON) -> float:
            timestamp = (
                0
                if info["time"] is None
                else parse_time_str(info["time"]).timestamp())
            return timestamp

        return {
            "model_sessions": sorted(
                (
                    get_session_info(session)
                    for session in sessions
                ),
                key=sort_key,
                reverse=True),
        }

    @server.json_post(f"{prefix}/chat/new")
    def _post_chat_new(_req: QSRH, rargs: ReqArgs) -> ChatInitResponse:
        user_session: SessionToken = rargs["meta"]["user_session"]
        user_email: UName = rargs["meta"]["user_email"]
        user_id = sec_ctx.get_user_id(user_session, user_email)
        session, messages = init_llama(session_store, user_id)
        return {
            "model_session": session.get_session_id().to_parseable(),
            "messages": messages,
        }

    @server.json_post(f"{prefix}/chat/recover")
    @server.middleware(verify_model_session_read)
    def _post_chat_recover(_req: QSRH, rargs: ReqArgs) -> ChatRecoverResponse:
        meta = rargs["meta"]
        session: Session = meta["model_session"]
        try:
            messages, task_id = recover_llama_chat(
                task_queue, model_ns, session)
        except FileNotFoundError as exc:
            raise PreventDefaultResponse(404, "session not available") from exc
        return {
            "messages": messages,
            "task": None if task_id is None else task_id.to_parseable(),
            "status": task_queue.get_status(task_id),
        }

    @server.json_post(f"{prefix}/chat/prompt")
    @server.middleware(verify_model_session_write)
    @server.middleware(verify_prompt)
    def _post_chat_prompt(_req: QSRH, rargs: ReqArgs) -> ChatPromptResponse:
        meta = rargs["meta"]
        session: Session = meta["model_session"]
        prompt: str = meta["prompt"]
        task_id = start_llama_response(task_queue, model_ns, prompt, session)
        return {
            "task": None if task_id is None else task_id.to_parseable(),
            "status": task_queue.get_status(task_id),
        }

    @server.json_post(f"{prefix}/chat/response")
    @server.middleware(verify_model_session_read)
    def _post_chat_response(_req: QSRH, rargs: ReqArgs) -> ChatTextResponse:
        args = rargs["post"]
        meta = rargs["meta"]
        session: Session = meta["model_session"]
        task_id = TaskId.parse(args["task"])
        index = int(args["index"])
        diff, next_pos = retrieve_llama_response(session, (task_id, index))
        if next_pos is not None:
            task_out, next_index = next_pos
        else:
            task_out = None
            next_index = None
        return {
            "diff": diff,
            "task": None if task_out is None else task_out.to_parseable(),
            "next_index": next_index,
            "status": task_queue.get_status(task_out),
        }

    return server, prefix


def setup_server(
        *,
        deploy: bool,
        addr: str | None,
        port: int | None,
        versions: VersionDict) -> tuple[QuickServer, str]:
    if addr is None:
        addr = envload_str("HOST", default="127.0.0.1")
    if port is None:
        port = envload_int("PORT", default=8080)
    history_file = envload_path("HISTORY_PATH")

    server: QuickServer = create_server(
        (addr, port),
        parallel=True,
        thread_factory=threading.Thread,
        token_handler=None,
        worker_constructor=None,
        soft_worker_death=True)
    if history_file is not None:
        server.history_file = history_file
    success = False
    try:
        res = setup(server, deploy=deploy, versions=versions)
        success = True
        return res
    finally:
        if not success:
            server.socket.close()
            server.done = True
            server.server_close()


def fallback_server(
        *,
        deploy: bool,
        addr: str | None,
        port: int | None,
        versions: VersionDict,
        exc_strs: list[str]) -> tuple[QuickServer, str]:
    if addr is None:
        addr = envload_str("HOST", default="127.0.0.1")
    if port is None:
        port = envload_int("PORT", default=8080)
    history_file = envload_path("HISTORY_PATH")

    server: QuickServer = create_server(
        (addr, port),
        parallel=True,
        thread_factory=threading.Thread,
        token_handler=None,
        worker_constructor=None,
        soft_worker_death=True)
    if history_file is not None:
        server.history_file = history_file

    prefix = "/api"

    server_timeout = 10 * 60
    server.timeout = server_timeout
    server.socket.settimeout(server_timeout)

    if deploy:
        server.no_command_loop = True

    server.update_version_string(versions["server_version"])

    server.set_common_invalid_paths(["/", "//"])

    # *** misc ***

    @server.json_get(f"{prefix}/version")
    def _get_version(_req: QSRH, _rargs: ReqArgs) -> VersionResponse:
        return {
            "app_name": versions["app_version"],
            "app_commit": versions["commit"],
            "python": versions["python_version_detail"],
            "deploy_date": versions["deploy_time"],
            "start_date": versions["start_time"],
            "error": exc_strs,
        }

    return server, prefix


def start(server: QuickServer, prefix: str) -> None:
    addr, port = server.server_address
    if not isinstance(addr, str):
        addr = addr.decode("utf-8")
    print(
        f"starting API at http://{addr}:{port}{prefix}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        print("shutting down..")
        server.server_close()
