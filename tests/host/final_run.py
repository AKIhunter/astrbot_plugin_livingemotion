"""Independent product acceptance, real host and loopback HTTP only.

The parent copies source into a new root, clears inherited credentials and
executes the child. Raw logs and ephemeral credentials never enter evidence.
"""

import argparse
import asyncio
from collections import Counter
import hashlib
import importlib.metadata
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

from run_isolated_host import guard_network

NAME = "astrbot_plugin_livingemotion"
HEAD = "61335414433db721b3f7ecc93f90deafe0a59d78"


def hashes(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.suffix in {".py", ".yaml", ".json", ".js", ".mjs", ".html", ".css"}
        and not any(x in p.parts for x in ("__pycache__", "node_modules", ".git", "final_evidence"))
    }


class Evidence:
    def __init__(self, report):
        self.report = report

    def check(self, name, value, *, layer="real_host_product", detail=None, fatal=False):
        item = {"name": name, "passed": bool(value), "layer": layer}
        if detail is not None:
            item["detail"] = detail
        self.report["checks"].append(item)
        if not value and fatal:
            raise AssertionError(name)

    async def case(self, name, operation):
        try:
            return await operation()
        except Exception as exc:
            traceback.print_exc()
            self.check(name, False, detail={"exception_type": type(exc).__name__})


async def run(args, report):
    import httpx
    import uvicorn
    from astrbot.core import LogBroker, astrbot_config, db_helper
    from astrbot.core.core_lifecycle import AstrBotCoreLifecycle
    from astrbot.dashboard.password_state import set_dashboard_password_hashes
    from astrbot.dashboard.server import AstrBotDashboard
    from final_checks import basic, http_matrix, stopped, seed
    from final_combination import pipelines, behavior_persona, consumers
    from final_boundaries import reply_receipts, bili_fault, rollback
    from final_c30_product import native_after_sent

    e = Evidence(report)
    root = Path(os.environ["ASTRBOT_ROOT"])
    password = secrets.token_urlsafe(30)
    astrbot_config["platform"] = []
    astrbot_config["provider"] = []
    astrbot_config["dashboard"].update({
        "username": "synthetic-final-admin", "password_change_required": False,
        "password_storage_upgraded": True, "host": "127.0.0.1", "enable": True,
    })
    set_dashboard_password_hashes(astrbot_config, password)
    astrbot_config["log_level"] = "WARNING"
    astrbot_config.save_config()
    core = AstrBotCoreLifecycle(LogBroker(), db_helper)
    server, tasks, plugin = None, [], None
    try:
        await asyncio.wait_for(core.initialize(), 90)
        e.check("C01.core_initialized", hasattr(core, "star_context"), fatal=True)
        context = core.star_context
        meta = context.get_registered_star(NAME)
        e.check("C01.product_loaded", meta is not None and meta.activated, fatal=True)
        plugin = meta.star_cls
        e.check("C01.product_initialized", plugin.api is not None and plugin.page_api is not None,
                fatal=True)
        e.check("C52.no_provider_configured", not core.provider_manager.provider_insts)
        report["platforms"] = [p.meta().name for p in core.platform_manager.get_insts()]
        e.check("no_external_platform", set(report["platforms"]) <= {"webchat"})
        report["loaded_plugins"] = [
            p.name for p in context.get_all_stars() if p.activated
        ]
        report["plugin_instances"] = [
            {"name": p.name, "module": type(p.star_cls).__module__,
             "class": type(p.star_cls).__qualname__}
            for p in context.get_all_stars() if p.activated
        ]
        report["source_before"] = hashes(root / "data/plugins")
        core._final_synthetic_events = []
        if args.focus != "c30":
            await e.case("basic_suite_completed",
                         lambda: basic(core, e, root, focus=args.focus != "full"))
            await e.case("native_pipeline_suite_completed", lambda: pipelines(core, e))
        if args.focus != "full":
            await e.case("native_after_sent_suite_completed", lambda: native_after_sent(core, e))
            await e.case("reply_receipt_suite_completed", lambda: reply_receipts(core, e))
            await e.case("stop_suite_completed", lambda: stopped(core, e, root))
            e.check("C03.source_unchanged", hashes(root / "data/plugins") == report["source_before"])
            return
        await e.case("native_persona_behavior_suite_completed", lambda: behavior_persona(core, e))
        await e.case("native_after_sent_suite_completed", lambda: native_after_sent(core, e))
        await e.case("reply_receipt_suite_completed", lambda: reply_receipts(core, e))
        if args.scenario != "single":
            await e.case("bili_fault_suite_completed", lambda: bili_fault(core, e))
            await e.case("consumer_suite_completed", lambda: consumers(core, e))
        core._final_synthetic_events.append(await seed(core))
        plugin = context.get_registered_star(NAME).star_cls
        tasks.append(asyncio.create_task(core.start(), name="final-core"))
        dashboard = AstrBotDashboard(core, db_helper, core.dashboard_shutdown_event,
                                    webui_dir=str(args.dashboard_dist))
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(
            dashboard.asgi_app, log_level="error", access_log=False, lifespan="on"))
        tasks.append(asyncio.create_task(server.serve(sockets=[sock]), name="final-http"))
        async with asyncio.timeout(15):
            while not server.started:
                if tasks[-1].done():
                    await tasks[-1]
                await asyncio.sleep(0.02)
        e.check("real_http_started", server.started)
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", trust_env=False,
                                     timeout=20) as client:
            login = await client.post("/api/v1/auth/login", json={
                "username": "synthetic-final-admin", "password": password})
            token = login.json().get("data", {}).get("token")
            e.check("F1.real_password_login", login.status_code == 200 and bool(token), fatal=True)
            await e.case("http_suite_completed",
                         lambda: http_matrix(core, client, token, e, root))
        if args.browser:
            # Parent reads this file; it is deliberately not copied to evidence.
            ready = {"base_url": f"http://127.0.0.1:{port}",
                     "username": "synthetic-final-admin", "password": password}
            (root / "browser-ready.json").write_text(json.dumps(ready))
            async with asyncio.timeout(360):
                while not (root / "browser-done").exists():
                    await asyncio.sleep(0.1)
            e.check("browser_process_completed", (root / "browser-done").read_text() == "0",
                    layer="real_dashboard_browser")
        if args.scenario == "four":
            await e.case("rollback_suite_completed", lambda: rollback(core, e, root))
        await e.case("stop_suite_completed", lambda: stopped(core, e, root))
        e.check("C03.source_unchanged", hashes(root / "data/plugins") == report["source_before"])
    finally:
        if server:
            server.should_exit = True
        if hasattr(core, "curr_tasks"):
            try:
                await asyncio.wait_for(core.stop(), 30)
            except Exception as exc:
                e.check("core_stop", False, detail=type(exc).__name__)
        elif plugin:
            await plugin.terminate()
        for task in tasks:
            try:
                await asyncio.wait_for(task, 15)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        report["livingemotion_tasks_after_stop"] = [
            t.get_name() for t in asyncio.all_tasks()
            if t.get_name().startswith("livingemotion-") and not t.done()
        ]
        e.check("C03.no_tasks_after_core_stop", not report["livingemotion_tasks_after_stop"])


def child(args):
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(args.host_source), os.environ["ASTRBOT_ROOT"]]
    blocked = []
    guard_network(blocked)
    report = {"checks": [], "host_head": HEAD, "started_unix": time.time(),
              "python": sys.version, "platform": list(os.uname()),
              "scenario": args.scenario,
              "focus": args.focus, "final_frozen_acceptance": False,
              "packages": dict(sorted((d.metadata["Name"], d.version)
                                     for d in importlib.metadata.distributions())),
              "test_hashes": hashes(Path(__file__).parent),
              "real_model_calls": 0, "real_platform_deliveries": "not_executed",
              "sender_bool_delivery_semantics": "unknown"}
    try:
        asyncio.run(run(args, report))
    except Exception as exc:
        traceback.print_exc()
        report["fatal_type"] = type(exc).__name__
    report["elapsed_seconds"] = round(time.time() - report["started_unix"], 3)
    report["blocked_runtime_operations"] = dict(Counter(blocked))
    report["counts"] = dict(Counter("passed" if c["passed"] else "failed"
                                   for c in report["checks"]))
    report["success"] = "fatal_type" not in report and not report["counts"].get("failed")
    Path(os.environ["ASTRBOT_ROOT"], "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["success"] else 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host-source", type=Path, required=True)
    parser.add_argument("--sandbox-parent", type=Path, required=True)
    parser.add_argument("--dashboard-dist", type=Path, required=True)
    parser.add_argument("--scenario", choices=["single", "four"], default="single")
    parser.add_argument("--focus", choices=["full", "h01-h03-c30", "c30"], default="full")
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--child", action="store_true")
    args = parser.parse_args()
    for name in ("host_source", "sandbox_parent", "dashboard_dist"):
        setattr(args, name, getattr(args, name).resolve())
    if args.child:
        return child(args)
    head = (args.host_source / ".git/HEAD").read_text().strip()
    if head != HEAD:
        raise ValueError("Expected fixed detached host HEAD")
    if args.focus != "full" and args.browser:
        parser.error("Focused regressions do not run the browser")
    prefix = "final-" + (args.focus + "-" if args.focus != "full" else "")
    root = Path(tempfile.mkdtemp(prefix=prefix + args.scenario + "-", dir=args.sandbox_parent))
    for part in ("home", "tmp", "data/plugins", "data/config"):
        (root / part).mkdir(parents=True, exist_ok=True)
    plugin_root = Path(__file__).resolve().parents[2]
    sources = [plugin_root]
    if args.scenario != "single":
        sources += [plugin_root.parent / n for n in
                    ("astrbot_plugin_at_guard", "LivingMemory", "BiliBot")]
    for source in sources:
        shutil.copytree(source, root / "data/plugins" / source.name, ignore=shutil.ignore_patterns(
            ".git", ".venv", ".trae", "__pycache__", "*.pyc", "node_modules", "tests",
            "data", "*.db", "*.sqlite*", ".env*", ".pytest_cache", "docs"))
    env = {"PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin",
           "HOME": str(root / "home"), "TMPDIR": str(root / "tmp"),
           "ASTRBOT_ROOT": str(root), "PYTHONDONTWRITEBYTECODE": "1",
           "ASTRBOT_DISABLE_METRICS": "1",
           "LANG": "en_US.UTF-8", "TZ": "UTC", "PYTHONUNBUFFERED": "1",
           "NO_PROXY": "127.0.0.1,localhost,::1"}
    argv = [sys.executable, str(Path(__file__).resolve()), "--child",
            "--host-source", str(args.host_source), "--sandbox-parent", str(args.sandbox_parent),
            "--dashboard-dist", str(args.dashboard_dist), "--scenario", args.scenario,
            "--focus", args.focus]
    if args.browser:
        argv.append("--browser")
    print(json.dumps({"root": str(root)}, ensure_ascii=False), flush=True)
    with (root / "runtime.log").open("w") as log:
        process = subprocess.Popen(argv, cwd=root, env=env, stdout=log, stderr=log)
        try:
            if args.browser:
                deadline = time.monotonic() + 150
                while not (root / "browser-ready.json").exists():
                    if process.poll() is not None or time.monotonic() > deadline:
                        break
                    time.sleep(0.1)
                if (root / "browser-ready.json").exists():
                    browser = subprocess.run(
                        ["node", str(Path(__file__).with_name("final_browser.mjs")), str(root)],
                        timeout=330, check=False)
                    (root / "browser-done").write_text(str(browser.returncode))
            process.wait(timeout=180)
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise
    if (root / "report.json").exists():
        report = json.loads((root / "report.json").read_text())
        print(json.dumps({"report": str(root / "report.json"), "counts": report["counts"],
                          "fatal_type": report.get("fatal_type"),
                          "exit_code": process.returncode}, ensure_ascii=False))
    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
