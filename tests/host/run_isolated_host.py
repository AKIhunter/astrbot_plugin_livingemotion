"""Bounded real-host probe with synthetic inputs and no external connections.

The parent creates a fresh root and re-executes in a scrubbed environment.
Only sanitized assertions and source/dependency identities leave the run root.
"""

import argparse
import asyncio
import hashlib
import importlib.metadata
import ipaddress
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import traceback


def guard_network(blocked):
    def audit(event, args):
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
            address = args[0] if event == "socket.getaddrinfo" else args[1]
            host = address[0] if isinstance(address, tuple) else address
            if host in {"localhost", b"localhost", None}:
                return
            try:
                allowed = ipaddress.ip_address(host).is_loopback
            except ValueError:
                allowed = False
            if not allowed:
                blocked.append(event)
                raise PermissionError("Host probe forbids non-loopback networking")
        if event in {"subprocess.Popen", "os.system", "os.posix_spawn"}:
            blocked.append(event)
            raise PermissionError("Host probe forbids runtime subprocesses")
    sys.addaudithook(audit)


def check(report, name, value, category="real_host", fatal=True):
    report["checks"].append({"name": name, "passed": bool(value), "category": category})
    if not value and fatal:
        raise AssertionError(name)


async def probe(args, report):
    import httpx
    import jwt
    import uvicorn
    from astrbot.core import LogBroker, astrbot_config, db_helper, sp
    from astrbot.core.core_lifecycle import AstrBotCoreLifecycle
    from astrbot.core.platform.astr_message_event import AstrMessageEvent
    from astrbot.core.platform.astrbot_message import AstrBotMessage, MessageMember
    from astrbot.core.platform.message_type import MessageType
    from astrbot.core.platform.platform_metadata import PlatformMetadata
    from astrbot.core.star.star_tools import StarTools
    from astrbot.dashboard.password_state import set_dashboard_password_hashes
    from astrbot.dashboard.server import AstrBotDashboard

    password = secrets.token_urlsafe(32)
    astrbot_config["platform"] = []
    astrbot_config["provider"] = []
    astrbot_config["dashboard"]["username"] = "isolated-contract-test"
    astrbot_config["dashboard"]["password_change_required"] = False
    astrbot_config["dashboard"]["password_storage_upgraded"] = True
    set_dashboard_password_hashes(astrbot_config, password)
    astrbot_config["dashboard"]["host"] = "127.0.0.1"
    astrbot_config["dashboard"]["enable"] = True
    astrbot_config["log_level"] = "WARNING"
    astrbot_config.save_config()
    core = AstrBotCoreLifecycle(LogBroker(), db_helper)
    server = None
    tasks = []
    try:
        await asyncio.wait_for(core.initialize(), timeout=80)
        check(report, "core_initialized", hasattr(core, "star_context"))
        check(report, "no_configured_providers", not core.provider_manager.provider_insts)
        # AstrBot may create its built-in WebChat adapter with no external account.
        report["platforms"] = [p.meta().name for p in core.platform_manager.get_insts()]
        check(report, "only_builtin_local_platforms", set(report["platforms"]) <= {"webchat"})
        root = Path(os.environ["ASTRBOT_ROOT"])
        check(report, "StarTools_data_root", StarTools.get_data_dir("livingemotion_host_probe")
              == root / "data/plugin_data/livingemotion_host_probe")
        context = core.star_context
        metadata = context.get_registered_star("livingemotion_host_probe")
        check(report, "fixture_loaded_by_real_plugin_manager", metadata is not None)
        check(report, "fixture_initialized", not metadata.star_cls.task.done())
        for iteration in range(3):
            old = metadata.star_cls
            ok, _ = await core.plugin_manager.reload("livingemotion_host_probe")
            metadata = context.get_registered_star("livingemotion_host_probe")
            check(report, f"reload_{iteration + 1}", ok and old.closed and old.task.done()
                  and old is not metadata.star_cls and not metadata.star_cls.task.done())
        check(report, "one_fixture_task_after_reload", sum(
            t.get_name() == "livingemotion-host-probe" and not t.done()
            for t in asyncio.all_tasks()) == 1)
        check(report, "web_routes_replaced_after_reload", sum(
            item[0].startswith("/livingemotion_host_probe/")
            for item in context.registered_web_apis) == 3)

        message = AstrBotMessage()
        message.type = MessageType.GROUP_MESSAGE
        message.self_id = "synthetic-bot-a"
        message.group_id = "synthetic-group"
        message.message_id = "synthetic-message-1"
        message.message_str = ""
        message.message = []
        message.sender = MessageMember(user_id="synthetic-human", nickname="fixture")
        event = AstrMessageEvent("", message, PlatformMetadata(
            name="synthetic_adapter", description="No real account", id="synthetic-instance-a"),
            session_id="synthetic-group")
        check(report, "event_bot_and_route", event.get_self_id() == "synthetic-bot-a"
              and event.unified_msg_origin ==
              "synthetic-instance-a:GroupMessage:synthetic-group", "real_class_synthetic_input")
        report["event_fields"] = {
            "bot": event.get_self_id(), "adapter": event.platform_meta.name,
            "instance": event.platform_meta.id, "umo": event.unified_msg_origin,
        }
        # Persona rows, UMO preferences and conversation are isolated real storage.
        for persona_id in ["probe-config", "probe-conversation", "probe-forced"]:
            await core.persona_mgr.create_persona(
                persona_id=persona_id, system_prompt="Synthetic test persona."
            )
        cfg = core.astrbot_config_mgr.get_conf(event.unified_msg_origin)
        cfg["agent_runner"]["config"]["persona"]["persona_id"] = "probe-config"
        resolve = core.persona_mgr.resolve_selected_persona
        result = await resolve(umo=event.unified_msg_origin,
                               conversation_persona_id=None, platform_name="synthetic_adapter")
        check(report, "persona_config", result[0] == "probe-config", "real_class_synthetic_input")
        result = await resolve(umo=event.unified_msg_origin,
                               conversation_persona_id="probe-conversation",
                               platform_name="synthetic_adapter")
        check(report, "persona_conversation", result[0] == "probe-conversation",
              "real_class_synthetic_input")
        await sp.put_async(scope="umo", scope_id=event.unified_msg_origin,
                           key="session_service_config", value={"persona_id": "probe-forced"})
        result = await resolve(umo=event.unified_msg_origin,
                               conversation_persona_id="probe-conversation",
                               platform_name="synthetic_adapter")
        check(report, "persona_forced", result[0] == result[2] == "probe-forced",
              "real_class_synthetic_input")
        await sp.put_async(scope="umo", scope_id=event.unified_msg_origin,
                           key="session_service_config", value={})
        result = await resolve(umo=event.unified_msg_origin,
                               conversation_persona_id="[%None]", platform_name="synthetic_adapter")
        check(report, "persona_explicit_none", result[0] == "[%None]" and result[1] is None,
              "real_class_synthetic_input")

        try:
            await context.llm_generate(chat_provider_id="missing-isolated-provider", prompt="test")
        except Exception as exc:
            check(report, "missing_provider_fail_closed", type(exc).__name__ == "ProviderNotFoundError")
        else:
            check(report, "missing_provider_fail_closed", False)
        tasks.append(asyncio.create_task(core.start(), name="probe-core"))
        dashboard = AstrBotDashboard(core, db_helper, core.dashboard_shutdown_event)
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(
            dashboard.asgi_app, log_level="error", access_log=False, lifespan="on"))
        tasks.append(asyncio.create_task(server.serve(sockets=[sock]), name="probe-http"))
        for _ in range(200):
            if server.started:
                break
            if tasks[-1].done():
                await tasks[-1]
            await asyncio.sleep(0.05)
        check(report, "real_loopback_http_started", server.started)
        report["http_port"] = port
        legacy = "/api/plug/livingemotion_host_probe/status"
        v1 = "/api/v1/plugins/extensions/livingemotion_host_probe/status"
        page = "/api/v1/plugins/livingemotion_host_probe/views/probe"
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}",
                                     trust_env=False, timeout=20) as client:
            for path in [legacy, v1, page, "/api/plugin/page/bridge-sdk.js"]:
                response = await client.get(path)
                check(report, f"anonymous_401:{path}", response.status_code == 401)
            response = await client.post("/api/plug/livingemotion_host_probe/check",
                                         json={"marker": "synthetic"})
            check(report, "anonymous_write_401", response.status_code == 401)
            response = await client.get(v1, headers={"Authorization": "Bearer invalid"})
            check(report, "invalid_token_401", response.status_code == 401)
            response = await client.post("/api/v1/auth/login", json={
                "username": "isolated-contract-test", "password": password})
            payload = response.json()
            token = payload.get("data", {}).get("token")
            check(report, "real_login_success", response.status_code == 200 and bool(token))
            client.headers["Authorization"] = f"Bearer {token}"
            for path in [legacy, v1]:
                response = await client.get(path)
                check(report, f"authenticated_200:{path}",
                      response.status_code == 200 and response.json()["data"]["authenticated"])
            guarded_paths = [
                "/api/plug/livingemotion_host_probe/guarded",
                "/api/v1/plugins/extensions/livingemotion_host_probe/guarded",
            ]
            for path in guarded_paths:
                for method in ["GET", "POST"]:
                    response = await client.request(method, path)
                    check(report, f"guard_dashboard_pass:{method}:{path}",
                          response.status_code == 200 and response.json()["data"]["guarded"])
            response = await client.post("/api/v1/plugins/extensions/livingemotion_host_probe/check",
                                         json={"marker": "synthetic"})
            check(report, "native_plugin_request_json", response.json()["data"]["marker"] == "synthetic")
            response = await client.get(page)
            page_data = response.json().get("data", {})
            # No content URLs/tokens are persisted in the report.
            content_path = page_data.get("content_path")
            check(report, "page_entry_200", response.status_code == 200 and bool(content_path))
            async with httpx.AsyncClient(base_url=str(client.base_url), trust_env=False) as anonymous:
                response = await anonymous.get(content_path)
                check(report, "scoped_page_asset_200", response.status_code == 200
                      and "Isolated Host Probe" in response.text)
                asset_token = content_path.split("/_t/", 1)[1].split("/", 1)[0].split("?", 1)[0]
                response = await anonymous.get("/api/plugin/page/bridge-sdk.js",
                                                params={"asset_token": asset_token})
                check(report, "scoped_bridge_sdk_200", response.status_code == 200
                      and "AstrBotPluginPage" in response.text)
                report["asset_token_management_status"] = {}
                for path in [legacy, v1]:
                    response = await anonymous.get(
                        path, headers={"Authorization": f"Bearer {asset_token}"})
                    report["asset_token_management_status"][path] = response.status_code
                    check(report, f"asset_token_rejected:{path}",
                          response.status_code in {401, 403}, fatal=False)
                path = "/api/v1/plugins/extensions/livingemotion_host_probe/check"
                response = await anonymous.post(
                    path, headers={"Authorization": f"Bearer {asset_token}"},
                    json={"marker": "asset-must-not-authorize-write"})
                report["asset_token_management_status"][path] = response.status_code
                check(report, "asset_token_rejected_for_write",
                      response.status_code in {401, 403}, fatal=False)
                for path in guarded_paths:
                    for method in ["GET", "POST"]:
                        response = await anonymous.request(
                            method, path, headers={"Authorization": f"Bearer {asset_token}"})
                        check(report, f"guard_asset_rejected:{method}:{path}",
                              response.status_code == 401)
                base_claims = {"username": "isolated-contract-test", "exp": int(time.time()) + 60}
                secret = astrbot_config["dashboard"]["jwt_secret"]
                synthetic_tokens = {
                    "oauth_typed": jwt.encode(
                        dict(base_claims, token_type="oauth_access", scope="plugins"), secret,
                        algorithm="HS256"),
                    "oauth_untyped_scope": jwt.encode(
                        dict(base_claims, scope="plugins", sub="synthetic-subject"), secret,
                        algorithm="HS256"),
                    "oauth_auth_source": jwt.encode(
                        dict(base_claims, auth_source="oauth"), secret, algorithm="HS256"),
                    "forged_signature": jwt.encode(base_claims, secrets.token_hex(32), algorithm="HS256"),
                    "expired": jwt.encode(dict(base_claims, exp=1), secret, algorithm="HS256"),
                }
                for label, synthetic_token in synthetic_tokens.items():
                    response = await anonymous.get(
                        guarded_paths[1], headers={"Authorization": f"Bearer {synthetic_token}"})
                    check(report, f"guard_rejected:{label}", response.status_code == 401,
                          "real_http_synthetic_token")
        report["model_network_calls"] = 0
        report["real_message_sends"] = 0
        report["browser_bridge_handshake"] = "not_executed"
        report["completed"] = True
    finally:
        if server is not None:
            server.should_exit = True
        if hasattr(core, "curr_tasks"):
            await asyncio.wait_for(core.stop(), timeout=20)
        for task in tasks:
            try:
                await asyncio.wait_for(task, timeout=10)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                task.cancel()
        if hasattr(core, "star_context"):
            metadata = core.star_context.get_registered_star("livingemotion_host_probe")
            if metadata:
                check(report, "terminate_stops_fixture_task", metadata.star_cls.task.done())


def child(args):
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(args.host_source))
    sys.path.insert(0, os.environ["ASTRBOT_ROOT"])
    blocked = []
    guard_network(blocked)
    report = {
        "checks": [], "host_head": args.host_head, "runtime": sys.version,
        "started_unix": time.time(),
        "packages": dict(sorted((d.metadata["Name"], d.version)
                                for d in importlib.metadata.distributions())),
        "host_source_sha256": {
            path: hashlib.sha256((args.host_source / path).read_bytes()).hexdigest()
            for path in [
                "pyproject.toml", "astrbot/core/star/base.py",
                "astrbot/core/star/star_manager.py", "astrbot/core/star/context.py",
                "astrbot/core/star/star_tools.py", "astrbot/core/persona_mgr.py",
                "astrbot/core/platform/astr_message_event.py",
                "astrbot/core/platform/message_session.py", "astrbot/api/web.py",
                "astrbot/dashboard/server.py", "astrbot/dashboard/api/auth.py",
                "astrbot/dashboard/api/plugins.py", "astrbot/dashboard/plugin_page_bridge.js",
                "astrbot/dashboard/services/plugin_page_service.py",
            ]
        },
    }
    failed = False
    try:
        asyncio.run(probe(args, report))
    except Exception as exc:
        failed = True
        report["failure"] = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
    report["blocked_runtime_operations"] = blocked
    report["success"] = not failed and all(item["passed"] for item in report["checks"])
    Path(os.environ["ASTRBOT_ROOT"], "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return 1 if failed else (0 if report["success"] else 2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host-source", type=Path, required=True)
    parser.add_argument("--sandbox-parent", type=Path, required=True)
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--host-head", default="")
    args = parser.parse_args()
    args.host_source = args.host_source.resolve()
    if args.child:
        return child(args)
    args.sandbox_parent.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="run-", dir=args.sandbox_parent.resolve()))
    for path in ["home", "tmp", "data/plugins"]:
        (root / path).mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path(__file__).parent / "fixture_plugin",
                    root / "data/plugins/livingemotion_host_probe",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    head = subprocess.check_output(
        ["git", "-C", str(args.host_source), "rev-parse", "HEAD"], text=True).strip()
    env = {
        "PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin",
        "HOME": str(root / "home"), "TMPDIR": str(root / "tmp"),
        "ASTRBOT_ROOT": str(root), "PYTHONDONTWRITEBYTECODE": "1",
        "LANG": "en_US.UTF-8", "TZ": "UTC", "PYTHONUNBUFFERED": "1",
        "NO_PROXY": "127.0.0.1,localhost,::1",
    }
    with (root / "runtime.log").open("w") as log:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--child",
             "--host-source", str(args.host_source), "--sandbox-parent", str(args.sandbox_parent),
             "--host-head", head], cwd=root, env=env, stdout=log, stderr=log,
            timeout=150)
    print(json.dumps({"root": str(root), "exit_code": result.returncode,
                      "report": str(root / "report.json")}, indent=2))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
