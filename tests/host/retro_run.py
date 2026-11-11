"""P8 four-version preparation and frozen product acceptance.

Prepare runs host-only probes. Final requires an explicit source manifest.
All runtime evidence stays outside the product repository.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
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

from retro_common import (
    Evidence, HOST_COMMITS, NAME, digest, guard_selftest, host_identity,
    network_guard, owned_tasks, product_files, scrubbed_env, source_identity,
)


WORKSPACE = Path(os.environ.get("LIVINGEMOTION_WORKSPACE", Path(__file__).resolve().parents[4]))
BASE = WORKSPACE / ".livingemotion-retro-host"
PYTHON = WORKSPACE / ".livingemotion-host-t1/venv/bin/python3.12"
HOST4 = WORKSPACE / ".livingemotion-host-t1/AstrBot"
CANDIDATE_SPEC = ">=4.29.1,<=4.29.4"
CANDIDATE_VERSION = "0.2.0"


async def browser_cases(args, e, root, base_url, password, native_config):
    ready = {
        "tag": args.tag, "base_url": base_url,
        "username": "retro-isolated-admin", "password": password,
        "dashboard": e.report["dashboard"], "product": e.report["product"],
    }
    path = root / "browser-ready.json"
    path.write_text(json.dumps(ready))
    path.chmod(0o600)
    revoked = False
    async with asyncio.timeout(300):
        while not (root / "browser-done.json").exists():
            if not revoked and (root / "browser-revoke-request.json").exists():
                native_config["dashboard"]["username"] = "retro-revoked-admin"
                native_config.save_config()
                (root / "browser-revoked.json").write_text("{}")
                revoked = True
            await asyncio.sleep(0.05)
    path.unlink(missing_ok=True)
    browser_path = root / "browser-report.json"
    report = json.loads(browser_path.read_text()) if browser_path.exists() else {}
    done = json.loads((root / "browser-done.json").read_text())
    e.check("browser.actual_native_iframe_complete", report.get("success") is True,
            detail={"failure_check": report.get("failure_check"),
                    "frames": len(report.get("frames", [])),
                    "fatal_type": report.get("fatal_type")})
    e.check("browser.process_exit", done.get("exit_code") == 0,
            detail=done.get("exit_code"))
    e.report["browser"] = report
    e.check("browser.same_host_product_and_bundle",
            report.get("tag") == args.tag
            and report.get("product_source_sha256") == e.report["product"]["source_sha256"]
            and report.get("native_dashboard_bundle_sha256") ==
            e.report["dashboard"]["source_sha256_bundle"])
    e.check("browser.real_iframe_views", len(report.get("frames", [])) ==
            (4 if args.experience_only else 36))


async def runtime(args, e):
    import httpx
    import uvicorn
    from astrbot.core import LogBroker, astrbot_config, db_helper
    from astrbot.core.config.default import VERSION
    from astrbot.core.core_lifecycle import AstrBotCoreLifecycle
    from astrbot.dashboard.password_state import set_dashboard_password_hashes
    from astrbot.dashboard.server import AstrBotDashboard
    from retro_http import login, product_http
    from retro_native import lifecycle_cases, persona_cases, pipeline_cases
    from retro_transport import native_transports
    import astrbot

    e.check("host.version_constant", VERSION == args.tag.removeprefix("v"),
            detail=VERSION, fatal=True)
    e.check("host.actual_import_source", Path(astrbot.__file__).resolve().is_relative_to(
        args.host_source), detail=str(Path(astrbot.__file__).resolve()), fatal=True)
    root = Path(os.environ["ASTRBOT_ROOT"])
    password = secrets.token_urlsafe(32)
    astrbot_config["platform"] = []
    astrbot_config["provider"] = []
    astrbot_config["dashboard"].update({
        "username": "retro-isolated-admin", "host": "127.0.0.1", "enable": True,
        "password_change_required": False, "password_storage_upgraded": True,
    })
    set_dashboard_password_hashes(astrbot_config, password)
    astrbot_config["provider_settings"].update(
        enable=True, streaming_response=True, default_provider_id="",
    )
    astrbot_config["provider_tts_settings"]["enable"] = False
    astrbot_config["t2i"] = False
    astrbot_config["content_safety"]["enable"] = False
    astrbot_config["content_safety"]["also_use_in_response"] = False
    astrbot_config["log_level"] = "WARNING"
    astrbot_config.save_config()
    core = AstrBotCoreLifecycle(LogBroker(), db_helper)
    final = args.phase == "final"
    tasks, server = [], None
    try:
        await asyncio.wait_for(core.initialize(), 90)
        e.check("host.core_initialized", hasattr(core, "star_context"), fatal=True)
        platforms = [p.meta().name for p in core.platform_manager.get_insts()]
        e.report["platforms"] = platforms
        e.check("isolation.no_external_platform", set(platforms) <= {"webchat"}, fatal=True)
        e.check("isolation.no_configured_provider", not core.provider_manager.provider_insts,
                fatal=True)
        loaded = [p.name for p in core.star_context.get_all_stars() if p.activated]
        e.report["loaded_plugins"] = loaded
        gate = args.phase == "gate"
        load_product = final or gate
        expected = {"livingemotion_retro_probe"} | ({NAME} if load_product else set())
        # Host built-ins are separate from user-installed plugin identities.
        actual = {
            p.name for p in core.star_context.get_all_stars()
            if p.activated and p.module_path.startswith("data.plugins.")
        }
        e.check("host.exact_isolated_plugins", actual == expected,
                detail=sorted(actual), fatal=True)
        if load_product:
            import yaml
            installed = root / "data/plugins" / NAME
            meta = yaml.safe_load((installed / "metadata.yaml").read_text())
            e.check("identity.explicit_candidate_metadata",
                    meta["astrbot_version"] == args.candidate_spec
                    and str(meta["version"]) == args.candidate_version,
                    detail={"spec": meta["astrbot_version"], "version": meta["version"]},
                    fatal=True)
            failed = core.plugin_manager.failed_plugin_dict.get(NAME, {})
            reason = failed.get("error", "") if isinstance(failed, dict) else str(failed)
            e.check("gate.actual_manager_result", NAME in actual and not failed,
                    detail={"tag": args.tag, "activated": NAME in actual, "reason": reason,
                            "expected": "candidate_loaded"},
                    fatal=True)
        if load_product:
            metadata = core.star_context.get_registered_star(NAME)
            e.check("identity.actual_source_registered_version",
                    str(metadata.version) == args.candidate_version,
                    detail=str(metadata.version), fatal=True)
            e.check("product.real_manager_initialized",
                    metadata.star_cls.api is not None and metadata.star_cls.page_api is not None,
                    fatal=True)
            origin = Path(sys.modules[type(metadata.star_cls).__module__].__file__).resolve()
            e.check("product.actual_loaded_origin", origin == root / "data/plugins" / NAME / "main.py",
                    detail=str(origin), fatal=True)
        if gate:
            e.report["product_behavior_acceptance"] = False
            return
        if not args.experience_only:
            await e.case("persona_cases", lambda: persona_cases(core, e))
            await e.case("pipeline_cases", lambda: pipeline_cases(core, e, final=final))
        if final and not args.experience_only:
            from retro_reply import final_reply_cases
            from retro_sleep import final_sleep_cases
            await e.case("ticket_window_cases", lambda: final_reply_cases(core, e))
            await e.case("native_sleep_cases", lambda: final_sleep_cases(core, e))
        if not args.experience_only:
            await e.case("transport_cases", lambda: native_transports(core, e, final=final))
        tasks.append(asyncio.create_task(core.start(), name="retro-core"))
        dashboard = AstrBotDashboard(
            core, db_helper, core.dashboard_shutdown_event, webui_dir=str(root / "dashboard"),
        )
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(
            dashboard.asgi_app, log_level="error", access_log=False, lifespan="on",
        ))
        tasks.append(asyncio.create_task(server.serve(sockets=[sock]), name="retro-http"))
        async with asyncio.timeout(20):
            while not server.started:
                if tasks[-1].done():
                    await tasks[-1]
                await asyncio.sleep(0.02)
        e.check("http.real_loopback_server", server.started)
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=15,
        ) as client:
            token = await login(client, password, e)
            if final:
                if args.experience_only:
                    from retro_daily import daily_http
                    await e.case("daily_http_cases", lambda: daily_http(core, client, token, e))
                else:
                    await e.case("product_http_cases", lambda: product_http(core, client, token, e))
        if final:
            await e.case("native_browser_cases", lambda: browser_cases(
                args, e, root, f"http://127.0.0.1:{port}", password, astrbot_config,
            ))
        if not args.experience_only:
            await e.case("lifecycle_cases", lambda: lifecycle_cases(core, e, final=final))
    finally:
        if server:
            server.should_exit = True
        if hasattr(core, "curr_tasks"):
            try:
                await asyncio.wait_for(core.stop(), 30)
            except Exception as exc:
                e.check("lifecycle.core_stop", False, detail=type(exc).__name__)
        else:
            for meta in core.star_context.get_all_stars() if hasattr(core, "star_context") else []:
                if meta.name == NAME and meta.star_cls:
                    await meta.star_cls.terminate()
        for task in tasks:
            try:
                await asyncio.wait_for(task, 15)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        e.check("lifecycle.no_product_tasks_after_stop", not owned_tasks(),
                detail=[task.get_name() for task in owned_tasks()])


def child(args):
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(args.host_source), os.environ["ASTRBOT_ROOT"]]
    root = Path(os.environ["ASTRBOT_ROOT"])
    report = json.loads((root / "input.json").read_text())
    report.update({
        "checks": [], "phase": args.phase, "final_frozen_acceptance": False,
        "python": sys.version,
        "dependencies": dict(sorted(
            (dist.metadata["Name"], dist.version) for dist in importlib.metadata.distributions()
        )),
        "real_model_calls": 0, "real_platform_deliveries": "not_executed",
        "sender_return_delivery_semantics": "not_delivery_evidence",
    })
    e = Evidence(report)
    blocked = []
    network_guard(blocked)
    start = time.monotonic()
    try:
        guard_selftest(e)
        asyncio.run(runtime(args, e))
    except Exception as exc:
        traceback.print_exc()
        report["fatal_type"] = type(exc).__name__
    if args.phase in ("gate", "final"):
        installed = product_files(root / "data/plugins" / NAME)
        e.check("identity.product_copy_after", installed == report["product"]["files_sha256"],
                layer="identity")
    # No raw credentials, request URLs containing tokens, or SDK keys leave the root.
    report["blocked_runtime_operations"] = dict(Counter(blocked))
    report["elapsed_seconds"] = round(time.monotonic() - start, 3)
    e.finish()
    (root / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["success"] else 2


def script_hashes():
    import hashlib
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(Path(__file__).parent.glob("retro_*"))
        if path.suffix in {".py", ".mjs"}
    }


def execute_child(command, root, env, args):
    deadline = time.monotonic() + 600
    browser_ran = False
    with (root / "runtime.log").open("w") as log:
        process = subprocess.Popen(command, cwd=root, env=env, stdout=log, stderr=log)
        try:
            while process.poll() is None:
                if not browser_ran and (root / "browser-ready.json").exists():
                    browser_ran = True
                    browser_command = [
                        str(args.node), str(Path(__file__).with_name(
                            "retro_daily_browser.mjs" if args.experience_only else "retro_browser.mjs")),
                        str(root / "browser-ready.json"), str(args.playwright), str(args.chrome),
                    ]
                    browser_env = {**env, "PATH": f"{args.node.parent}:/usr/bin:/bin"}
                    with (root / "browser.log").open("w") as browser_log:
                        try:
                            browser = subprocess.run(
                                browser_command, cwd=root, env=browser_env,
                                stdout=browser_log, stderr=browser_log,
                                timeout=min(270, max(1, deadline - time.monotonic())),
                            )
                            code = browser.returncode
                        except subprocess.TimeoutExpired:
                            code = 124
                    (root / "browser-done.json").write_text(json.dumps({"exit_code": code}))
                if time.monotonic() >= deadline:
                    process.terminate()
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    return 124
                time.sleep(0.05)
            return process.returncode
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            (root / "browser-ready.json").unlink(missing_ok=True)


def parent(args):
    args.base.mkdir(parents=True, exist_ok=True)
    if not args.python.is_file():
        raise ValueError("Missing verified Python environment")
    source = Path(__file__).resolve().parents[2]
    if args.phase == "freeze":
        if args.freeze_manifest is None:
            raise ValueError("Freeze needs --freeze-manifest")
        identity = source_identity(source)
        from retro_dashboard import dashboard_identity
        identity["harness_sha256"] = script_hashes()
        identity["dashboard"] = {
            tag: dashboard_identity(args.base / "dashboard" / tag, tag)
            for tag in HOST_COMMITS
        }
        if product_files(source) != identity["files_sha256"]:
            raise ValueError("Source changed during freeze; wait for all writers")
        args.freeze_manifest.parent.mkdir(parents=True, exist_ok=True)
        with args.freeze_manifest.open("x") as stream:
            json.dump(identity, stream, indent=2, ensure_ascii=False)
        print(json.dumps({"phase": "freeze", "source_sha256": identity["source_sha256"],
                          "final_frozen_acceptance": False}))
        return 0
    identity = source_identity(source)
    if args.phase == "final":
        if args.freeze_manifest is None:
            raise ValueError("Final requires --freeze-manifest after freeze notification")
        frozen = json.loads(args.freeze_manifest.read_text())
        if identity["git_head"] != frozen["git_head"] or identity["files_sha256"] != frozen["files_sha256"]:
            raise ValueError("Current product differs from frozen identity")
        identity = frozen
        if script_hashes() != frozen["harness_sha256"]:
            raise ValueError("Harness differs from frozen identity")
        if not args.node.is_file() or not args.chrome.is_file() or not args.playwright.exists():
            raise ValueError("Final needs native browser tools; it cannot skip iframe acceptance")
    reports = []
    tags = [args.tag] if args.tag else list(HOST_COMMITS)
    for tag in tags:
        if args.phase == "final" and (
            product_files(source) != identity["files_sha256"]
            or script_hashes() != identity["harness_sha256"]
        ):
            raise ValueError("Frozen source or harness changed before next host; do not retry")
        host = args.host4 if tag == "v4.29.4" else args.base / "hosts" / tag
        host = host.resolve()
        host_data = host_identity(host, tag)
        root = Path(tempfile.mkdtemp(prefix=f"{args.phase}-{tag}-", dir=args.base))
        for part in ("home", "tmp", "data/plugins", "data/config", "dashboard"):
            (root / part).mkdir(parents=True, exist_ok=True)
        dashboard_data = None
        if args.phase == "final":
            from retro_dashboard import dashboard_identity, tree_files
            dashboard_root = args.base / "dashboard" / tag
            dashboard_data = dashboard_identity(dashboard_root, tag)
            if dashboard_data != identity["dashboard"][tag]:
                raise ValueError("Dashboard differs from frozen identity")
            if dashboard_data["host_commit"] != host_data["commit"]:
                raise ValueError("Dashboard belongs to a different native host")
            shutil.copytree(dashboard_root / "dist", root / "dashboard", dirs_exist_ok=True)
            if tree_files(root / "dashboard") != dashboard_data["files_sha256"]:
                raise ValueError("Dashboard runtime copy identity mismatch")
        else:
            (root / "dashboard/index.html").write_text(
                "<!doctype html><title>P8 isolated API probe</title>")
        fixture = root / "data/plugins/livingemotion_retro_probe"
        fixture.mkdir()
        shutil.copyfile(Path(__file__).with_name("retro_fixture.py"), fixture / "main.py")
        if args.phase in ("gate", "final"):
            target = root / "data/plugins" / NAME
            for rel in identity["files_sha256"]:
                destination = target / rel
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / rel, destination)
            if product_files(target) != identity["files_sha256"]:
                raise ValueError("Copied product differs from frozen source")
            if product_files(source) != identity["files_sha256"]:
                raise ValueError("Source changed while copying")
            # P8 life rules require a configured timezone. Keep this native
            # fixture configured across cases; restoring an empty timezone
            # would unintentionally switch persisted v2 states to v1 rules.
            config_path = root / "data/config" / f"{NAME}_config.json"
            config_path.write_text(json.dumps({"timezone": "UTC", "night_policy_version": 2}))
        inputs = {
            "host": host_data, "product": identity, "harness_sha256": script_hashes(),
            "phase": args.phase, "final_frozen_acceptance": False,
            "product_executed": args.phase in ("gate", "final"),
            "evidence_root": str(root),
            "dashboard": dashboard_data,
            "candidate": {"version": args.candidate_version, "spec": args.candidate_spec},
            "synthetic_native_config": {"timezone": "UTC", "night_policy_version": 2}
            if args.phase in ("gate", "final") else None,
        }
        (root / "input.json").write_text(json.dumps(inputs, ensure_ascii=False))
        command = [
            str(args.python), str(Path(__file__).resolve()), "--child",
            "--phase", args.phase, "--host-source", str(host), "--tag", tag,
            "--candidate-spec", args.candidate_spec, "--candidate-version", args.candidate_version,
        ]
        if args.experience_only:
            command.append("--experience-only")
        exit_code = execute_child(command, root, scrubbed_env(root, args.python), args)
        path = root / "report.json"
        report = json.loads(path.read_text()) if path.is_file() else {
            **inputs, "success": False, "fatal_type": "ChildTimeoutOrBootstrapFailure",
        }
        report["child_exit_code"] = exit_code
        report["success"] = report["success"] and exit_code == 0
        report["host_unchanged_after"] = host_identity(host, tag) == host_data
        report["harness_unchanged_after"] = script_hashes() == inputs["harness_sha256"]
        if args.phase in ("gate", "final"):
            report["product_source_unchanged_after"] = (
                source_identity(source)["git_head"] == identity["git_head"]
                and product_files(source) == identity["files_sha256"]
            )
        if args.phase == "final":
            report["dashboard_unchanged_after"] = (
                dashboard_identity(dashboard_root, tag) == dashboard_data
                and tree_files(root / "dashboard") == dashboard_data["files_sha256"]
            )
        report["success"] = report["success"] and all(
            report[key] for key in (
                "host_unchanged_after", "harness_unchanged_after",
                *(["product_source_unchanged_after"] if args.phase in ("gate", "final") else []),
                *(["dashboard_unchanged_after"] if args.phase == "final" else []),
            )
        )
        report["final_frozen_acceptance"] = args.phase == "final" and report["success"]
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        reports.append(report)
        print(json.dumps({
            "tag": tag, "phase": args.phase, "success": report["success"],
            "final_frozen_acceptance": report["final_frozen_acceptance"],
            "report": str(path), "counts": report.get("counts", {}),
            "fatal_type": report.get("fatal_type"),
        }), flush=True)
        if args.phase in ("gate", "final") and not report["product_source_unchanged_after"]:
            print(json.dumps({"stopped": "product_source_drift", "no_automatic_refreeze": True}),
                  flush=True)
            break
    summary = {
        "phase": args.phase, "reports": [r["evidence_root"] + "/report.json" for r in reports],
        "all_requested_hosts_ready": all(r["success"] for r in reports),
        "four_version_final_acceptance": args.phase == "final" and len(reports) == 4
        and all(r["final_frozen_acceptance"] for r in reports),
        "product_source_sha256": identity["source_sha256"],
    }
    summary_path = args.base / f"{args.phase}-summary-{time.time_ns()}.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps({"summary": str(summary_path), **summary}), flush=True)
    return 0 if summary["all_requested_hosts_ready"] else 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("prepare", "gate", "freeze", "final"), default="prepare")
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--python", type=Path, default=PYTHON)
    parser.add_argument("--host4", type=Path, default=HOST4)
    parser.add_argument("--freeze-manifest", type=Path)
    parser.add_argument("--tag", choices=list(HOST_COMMITS))
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--experience-only", action="store_true",
                        help="Focused daily archive acceptance, not full legacy regression")
    parser.add_argument("--host-source", type=Path)
    parser.add_argument("--candidate-spec", default=CANDIDATE_SPEC)
    parser.add_argument("--candidate-version", default=CANDIDATE_VERSION)
    parser.add_argument("--node", type=Path, default=Path("/opt/homebrew/bin/node"))
    parser.add_argument("--chrome", type=Path,
                        default=Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"))
    parser.add_argument("--playwright", type=Path,
                        default=Path("/tmp/at-guard-ui-tools/node_modules/playwright"))
    args = parser.parse_args()
    for name in ("base", "python", "host4", "freeze_manifest", "host_source"):
        value = getattr(args, name)
        if value is not None:
            # Do not resolve the venv Python symlink: that loses its environment.
            setattr(args, name, value.absolute() if name == "python" else value.resolve())
    return child(args) if args.child else parent(args)


if __name__ == "__main__":
    raise SystemExit(main())
