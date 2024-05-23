
def setup(
        server: QuickServer,
        *,
        deploy: bool,
        versions: VersionDict) -> tuple[QuickServer, str]:



    def verify_model_session_read(
            _req: QSRH, rargs: ReqArgs, okay: ReqNext) -> Response | ReqNext:
        args = rargs["post"]
        session = smind.get_session(SessionId.parse(args["model_session"]))
        user_id = smind.get_session_user(session.get_session_id())
        user_session = rargs["meta"]["user_session"]
        sec_ctx.ensure_can_read_chat(user_session, user_id)
        rargs["meta"]["model_session"] = session
        return okay

    def verify_model_session_write(
            _req: QSRH, rargs: ReqArgs, okay: ReqNext) -> Response | ReqNext:
        args = rargs["post"]
        session = smind.get_session(SessionId.parse(args["model_session"]))
        user_id = smind.get_session_user(session.get_session_id())
        user_session: SessionToken = rargs["meta"]["user_session"]
        sec_ctx.ensure_can_write_chat(user_session, user_id)
        rargs["meta"]["model_session"] = session
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

    @server.json_get(f"{prefix}/info")
    def _get_info(_req: QSRH, _rargs: ReqArgs) -> StatsResponse:
        return {
            "queues": get_queue_stats(smind),
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
        user_name = args["name"]
        password = args["password"]
        user_session = sec_ctx.login(UName(user_name), password)
        if user_session is None:
            return {
                "user_name": None,
                "logged": False,
                "capabilities": [],
            }
        login_name = sec_ctx.get_name(user_session)
        if login_name is None:
            return {
                "user_name": None,
                "logged": False,
                "capabilities": [],
            }
        cookie = SimpleCookie()
        cookie["user_session"] = user_session
        cookie["user_session"]["expires"] = 90*24*60*60
        req.send_cookie(cookie)
        return {
            "user_name": login_name.get(),
            "logged": True,
            "capabilities": sorted(sec_ctx.list_capabilities(
                user_session, login_name)),
        }

    @server.json_post(f"{prefix}/reset_password_token")
    @server.middleware(verify_user_session)
    def _get_reset_password_token(
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
    def _post_reset_password(_req: QSRH, rargs: ReqArgs) -> LoginResponse:
        args = rargs["post"]
        password = args["password"]
        reset_token = args["reset_token"]
        user_name = sec_ctx.set_password(password, reset_token)
        if user_name is not None:
            sec_ctx.force_logout_user(user_name)
        return {
            "user_name": None if user_name is None else user_name.get(),
            "logged": False,
            "capabilities": [],
        }

    @server.json_post(f"{prefix}/logout")
    @server.middleware(verify_user_session)
    def _post_logout(_req: QSRH, rargs: ReqArgs) -> LoginResponse:
        user_session: SessionToken = rargs["meta"]["user_session"]
        args = rargs["post"]
        user_name = args.get("name")

        if user_name is not None:
            sec_ctx.logout_user(user_session, UName(user_name))
        else:
            sec_ctx.logout(user_session)
            # FIXME: clear cookie
        return {
            "user_name": None,
            "logged": False,
            "capabilities": [],
        }

    # TODO:
    # - auto create first user
    # - create user
    # - list users (+reset +logout +email)
    # - list capabilities
    # - edit capabilities

    # # # SECURE # # #
    server.add_middleware(verify_user_session)

    # *** chat ***

    @server.json_post(f"{prefix}/new")
    def _post_new(_req: QSRH, rargs: ReqArgs) -> ChatInitResponse:
        user_session: SessionToken = rargs["meta"]["user_session"]
        name: UName = rargs["meta"]["user_name"]
        user_id = sec_ctx.get_user_id(user_session, name)
        session, messages = init_llama(user_id, graph_profile=graph_llama)
        return {
            "model_session": session.get_session_id().to_parseable(),
            "messages": messages,
        }

    @server.json_post(f"{prefix}/recover")
    @server.middleware(verify_model_session_read)
    def _post_recover(_req: QSRH, rargs: ReqArgs) -> ChatRecoverResponse:
        meta = rargs["meta"]
        session: Session = meta["model_session"]
        messages, task_id = recover_llama_chat(
            session, graph_profile=graph_llama)
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
        task_id = start_llama_response(
            prompt, session, graph_profile=graph_llama)
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

    return server
