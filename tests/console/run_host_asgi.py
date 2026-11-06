"""Run bounded ASGI/handler tests in the pinned host interpreter, without sockets."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import secrets
import subprocess
import sys
import tempfile
import traceback
import unittest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host-source", type=Path, required=True)
    parser.add_argument("--host-version", choices=("4.29.1", "4.29.2", "4.29.3", "4.29.4"),
                        default="4.29.4")
    parser.add_argument("--sandbox-parent", type=Path, required=True)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    host = args.host_source.resolve()
    plugin = Path(__file__).resolve().parents[2]
    args.output = args.output or Path(__file__).with_name(f"evidence-v{args.host_version}.json")
    if not args.worker:
        host_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=host, text=True,
        ).strip()
        if args.host_version == "4.29.4":
            expected = "61335414433db721b3f7ecc93f90deafe0a59d78"
        else:
            try:
                expected = subprocess.check_output(
                    ["git", "rev-parse", f"v{args.host_version}^{{commit}}"], cwd=host, text=True,
                ).strip()
            except subprocess.CalledProcessError:
                parser.error("The requested host version must have its exact local release tag")
        if host_head != expected:
            parser.error("Host HEAD does not match the requested pinned release")
        args.sandbox_parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="console-asgi-", dir=args.sandbox_parent) as root:
            env = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": root, "TMPDIR": root, "LANG": "en_US.UTF-8",
                "ASTRBOT_ROOT": root, "ASTRBOT_TEST_MODE": "true",
                "ASTRBOT_DASHBOARD_INITIAL_PASSWORD": secrets.token_urlsafe(36),
                "LIVINGEMOTION_CONSOLE_TEST_ROOT": root,
                "LIVINGEMOTION_CONSOLE_HOST_HEAD": host_head,
                "PYTHONPATH": os.pathsep.join((str(host), str(plugin.parent))),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--worker",
                 "--host-source", str(host), "--sandbox-parent", root,
                 "--host-version", args.host_version,
                 "--output", str(args.output.resolve())],
                env=env, cwd=root, timeout=120,
            )
            return result.returncode

    blocked = []

    def deny_network(event, _args):
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo",
                     "subprocess.Popen", "os.system", "os.posix_spawn"}:
            blocked.append({
                "event": event,
                "callers": [f"{Path(frame.filename).name}:{frame.name}"
                            for frame in traceback.extract_stack(limit=6)[:-1]],
            })
            raise PermissionError("Console ASGI tests forbid networking and subprocesses")

    sys.addaudithook(deny_network)
    checks = []

    class EvidenceResult(unittest.TextTestResult):
        def addSuccess(self, test):
            super().addSuccess(test)
            checks.append({"name": test.id(), "passed": True})

        def addFailure(self, test, err):
            super().addFailure(test, err)
            checks.append({"name": test.id(), "passed": False})

        def addError(self, test, err):
            super().addError(test, err)
            checks.append({"name": test.id(), "passed": False})

        def addSubTest(self, test, subtest, err):
            super().addSubTest(test, subtest, err)
            checks.append({"name": subtest.id(), "passed": err is None, "subtest": True})

    suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern="test_console.py")
    result = unittest.TextTestRunner(verbosity=2, resultclass=EvidenceResult).run(suite)
    host_files = [
        "astrbot/api/web.py", "astrbot/core/star/context.py",
        "astrbot/dashboard/api/auth.py", "astrbot/dashboard/api/plugins.py",
        "astrbot/dashboard/server.py", "astrbot/dashboard/services/auth_service.py",
        "astrbot/dashboard/services/plugin_page_service.py",
    ]
    hashes = {
        "host/" + name: hashlib.sha256((host / name).read_bytes()).hexdigest()
        for name in host_files
    }
    for folder in ("page_api", "tests/console"):
        for path in sorted((plugin / folder).glob("*.py")):
            hashes[str(path.relative_to(plugin))] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ("runtime/console.py", "storage/console_data.py", "domain/emotion.py"):
        hashes[name] = hashlib.sha256((plugin / name).read_bytes()).hexdigest()
    report = {
        "suite": "real_host_ASGI_and_request_binding_with_synthetic_application",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "platform": f"{os.uname().sysname} {os.uname().release}/{os.uname().machine}",
        "host_version": args.host_version,
        "host_head": os.environ["LIVINGEMOTION_CONSOLE_HOST_HEAD"],
        "dependencies": {name: importlib.metadata.version(name)
                         for name in ("PyJWT", "fastapi", "httpx", "starlette")},
        "tests_run": result.testsRun, "failures": len(result.failures),
        "errors": len(result.errors), "skipped": len(result.skipped),
        "network_attempts_blocked": blocked, "checks": checks, "sha256": hashes,
        "limitations": [
            "No final plugin Application/lifecycle integration or browser iframe.",
            "No actual platform traffic, providers, model calls or sends.",
            "Native authentication functions and routes; synthetic business application.",
        ],
    }
    args.output.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n")
    return 0 if result.wasSuccessful() and not result.skipped and not blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
