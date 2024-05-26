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

from quick_server import create_server, QuickServer
from quick_server import QuickServerRequestHandler as QSRH
from quick_server import ReqArgs, ReqNext, Response
from scattermind.system.base import SessionId, TaskId, UserId
from scattermind.system.names import GNamespace, UName
from scattermind.system.response import redis_to_response
from scattermind.system.session.session import Session
from scattermind.system.util import get_time_str

from swai.clean import sanity_check
from swai.server_response_types import (
    ChatInitResponse,
    ChatPromptResponse,
    ChatRecoverResponse,
    ChatTextResponse,
    LoginResponse,
    ResetTokenResponse,
    TaskBidResponse,
    TaskFinishResponse,
    VersionResponse,
    WorkerBlobHashResponse,
    WorkerBlobListResponse,
    WorkerKeysResponse,
    WorkerSessionListResponse,
    WorkerSessionResponse,
    WorkerSignalResponse,
    WorkerTokenResponse,
    WorkerUploadResponse,
    WorkerUserResponse,
    WorkerValueResponse,
)
from swai.system.user.loader import load_user_manager
from swai.system.user.manager import (
    HashPassword,
    RawPassword,
    ResetToken,
    SessionToken,
    WorkerToken,
)
from swai.system.user.secure import SecureContext
from swai_server.auction.queue import TaskQueue
from swai_server.config import get_config
from swai_server.env import envload_int, envload_path, envload_str
from swai_server.smind.server_api import (
    create_session_store,
    init_llama,
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
        "server_version": f"SWAIserver/{version_name[1:]}",
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

    # server.suppress_noise = True

    server.register_shutdown()

    def report_slow_requests(
            method_str: str, path: str, duration: float) -> None:
        print(f"slow request {method_str} {path} ({duration}s)")

    max_upload = 120 * 1024 * 1024  # 120MiB
    server_timeout = 10 * 60
    server.report_slow_requests = report_slow_requests
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

    session_store = create_session_store(config)
    task_queue = TaskQueue(session_store, config["task_queue"])
    sec_ctx = SecureContext(load_user_manager(
        config["user_mng"], admin_email=admin_email, admin_pw=admin_pw))
    model_ns = GNamespace("llama")

    public_path = envload_path("UI_PATH", default="build/")
    server.bind_path("/", public_path)

    def file_fallback(_: str) -> str:
        print(f"path {_}")
        return os.path.join(public_path, "index.html")

    server.set_file_fallback_hook(file_fallback)

    def maybe_user_session(
            _req: QSRH, rargs: ReqArgs, okay: ReqNext) -> Response | ReqNext:
        cookie = rargs["cookie"]
        if cookie is None:
            return okay
        session_cookie = cookie.get("user_session")
        if session_cookie is None:
            return okay
        user_session = session_cookie.value
        user_name = sec_ctx.get_email(user_session)
        if user_name is None:
            return okay
        rargs["meta"]["user_session"] = user_session
        rargs["meta"]["user_name"] = user_name
        return okay

    def verify_user_session(
            req: QSRH, rargs: ReqArgs, okay: ReqNext) -> Response | ReqNext:
        maybe_user_session(req, rargs, okay)
        user_session = rargs["meta"].get("user_session")
        if user_session is None:
            return Response("must be logged in", 401)
        user_name: UName | None = rargs["meta"].get("user_name")
        if user_name is None:
            # FIXME: clear cookie
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
            _req: QSRH, rargs: ReqArgs, okay: ReqNext) -> Response | ReqNext:
        args = rargs["post"]
        worker_token: WorkerToken = args["worker_token"]
        name = UName(args["name"])
        sec_ctx.ensure_worker_token(name, worker_token)
        rargs["meta"]["user_name"] = name
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

    @server.json_post(f"{prefix}/user")
    @server.middleware(maybe_user_session)
    def _post_user(_req: QSRH, rargs: ReqArgs) -> LoginResponse:
        user_session: SessionToken | None = rargs["meta"].get("user_session")
        if user_session is None:
            return {
                "user_name": None,
                "logged": False,
                "capabilities": [],
            }
        login_name: UName | None = rargs["meta"].get("user_name")
        if login_name is None:
            return {
                "user_name": None,
                "logged": False,
                "capabilities": [],
            }
        return {
            "user_name": login_name.get(),
            "logged": True,
            "capabilities": sorted(sec_ctx.list_capabilities(
                user_session, login_name)),
        }

    @server.json_post(f"{prefix}/login")
    def _post_login(req: QSRH, rargs: ReqArgs) -> LoginResponse:
        args = rargs["post"]
        user_name: str = args["name"]
        password: RawPassword = args["password"]
        user_session = sec_ctx.login(UName(user_name), password)
        if user_session is None:
            return {
                "user_name": None,
                "logged": False,
                "capabilities": [],
            }
        login_name = sec_ctx.get_email(user_session)
        if login_name is None:
            return {
                "user_name": None,
                "logged": False,
                "capabilities": [],
            }
        cookie = SimpleCookie()
        cookie["user_session"] = user_session
        cookie["user_session"]["max-age"] = 90*24*60*60
        req.send_cookie(cookie)
        return {
            "user_name": login_name.get(),
            "logged": True,
            "capabilities": sorted(sec_ctx.list_capabilities(
                user_session, login_name)),
        }

    @server.json_post(f"{prefix}/create_worker_token")
    @server.middleware(verify_user_session)
    def _post_create_worker_token(
            _req: QSRH, rargs: ReqArgs) -> WorkerTokenResponse:
        user_session: SessionToken = rargs["meta"]["user_session"]
        name: UName = rargs["meta"]["user_name"]
        args = rargs["post"]
        user_name: str | None = args.get("name")
        if user_name is not None:
            name = UName(user_name)
        worker_token = sec_ctx.create_worker_token(user_session, name)
        return {
            "worker_token": worker_token,
        }

    @server.json_post(f"{prefix}/reset_password_token")
    @server.middleware(verify_user_session)
    def _post_reset_password_token(
            _req: QSRH, rargs: ReqArgs) -> ResetTokenResponse:
        user_session: SessionToken = rargs["meta"]["user_session"]
        args = rargs["post"]
        user_name: str = args["name"]
        reset_token = sec_ctx.generate_reset_token(
            user_session, UName(user_name))
        return {
            "user_name": user_name,
            "reset_token": reset_token,
        }

    @server.json_post(f"{prefix}/reset_password")
    def _post_reset_password(req: QSRH, rargs: ReqArgs) -> LoginResponse:
        args = rargs["post"]
        password: RawPassword = args["password"]
        reset_token: ResetToken = args["reset_token"]
        user_name = sec_ctx.set_password(password, reset_token)
        if user_name is not None:
            sec_ctx.force_logout_user(user_name)
            cookie = SimpleCookie()
            cookie["user_session"] = ""
            cookie["user_session"]["max-age"] = 0
            req.send_cookie(cookie)
        return {
            "user_name": None if user_name is None else user_name.get(),
            "logged": False,
            "capabilities": [],
        }

    @server.json_post(f"{prefix}/logout")
    @server.middleware(verify_user_session)
    def _post_logout(req: QSRH, rargs: ReqArgs) -> LoginResponse:
        user_session: SessionToken = rargs["meta"]["user_session"]
        args = rargs["post"]
        user_name: str | None = args.get("name")

        if user_name is not None:
            sec_ctx.logout_user(user_session, UName(user_name))
        else:
            sec_ctx.logout(user_session)
            cookie = SimpleCookie()
            cookie["user_session"] = ""
            cookie["user_session"]["max-age"] = 0
            req.send_cookie(cookie)
        return {
            "user_name": None,
            "logged": False,
            "capabilities": [],
        }

    # FIXME: use authorization headers
    # TODO:
    # - create user
    # - list users (+reset +logout +email)
    # - edit capabilities

    # *** worker API ***

    # * tasks *

    @server.json_post(f"{prefix}/task/bid")
    @server.middleware(verify_worker_token)
    def _post_task_bid(_req: QSRH, rargs: ReqArgs) -> TaskBidResponse:
        args = rargs["post"]
        nss = [GNamespace(ns) for ns in args["nss"]]
        timeout = float(args["timeout"])
        assert timeout > 0.0
        task = task_queue.pop_task(nss, timeout=timeout)
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
        args = rargs["post"]
        task_id = TaskId.parse(args["task_id"])
        response = redis_to_response(args["response"])
        task_queue.set_result(task_id, response)
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
    def _put_smind_upload(_req: QSRH, rargs: ReqArgs) -> WorkerUploadResponse:
        args = rargs["post"]
        session_id = SessionId.parse(args["session"])
        blob: str = args["blob"]
        files = rargs["files"]
        with session_store.open_blob_write(session_id, blob) as fout:
            shutil.copyfileobj(files["blob"], fout)  # type: ignore
        return {
            "done": True,
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

    @server.json_post(f"{prefix}/new")
    def _post_new(_req: QSRH, rargs: ReqArgs) -> ChatInitResponse:
        user_session: SessionToken = rargs["meta"]["user_session"]
        name: UName = rargs["meta"]["user_name"]
        user_id = sec_ctx.get_user_id(user_session, name)
        session, messages = init_llama(session_store, user_id)
        return {
            "model_session": session.get_session_id().to_parseable(),
            "messages": messages,
        }

    @server.json_post(f"{prefix}/recover")
    @server.middleware(verify_model_session_read)
    def _post_recover(_req: QSRH, rargs: ReqArgs) -> ChatRecoverResponse:
        meta = rargs["meta"]
        session: Session = meta["model_session"]
        messages, task_id = recover_llama_chat(task_queue, model_ns, session)
        return {
            "messages": messages,
            "task": None if task_id is None else task_id.to_parseable(),
        }

    @server.json_post(f"{prefix}/prompt")
    @server.middleware(verify_model_session_write)
    @server.middleware(verify_prompt)
    def _post_prompt(_req: QSRH, rargs: ReqArgs) -> ChatPromptResponse:
        meta = rargs["meta"]
        session: Session = meta["model_session"]
        prompt: str = meta["prompt"]
        task_id = start_llama_response(task_queue, model_ns, prompt, session)
        return {
            "task": task_id.to_parseable(),
        }

    @server.json_post(f"{prefix}/response")
    @server.middleware(verify_model_session_read)
    def _post_response(_req: QSRH, rargs: ReqArgs) -> ChatTextResponse:
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
