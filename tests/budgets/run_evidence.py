"""Explicit offline lanes with collection, execution and source-integrity gates."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sqlite3
import sys
import tempfile
import time

from host_environment import configure_host, packages

PLUGIN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN.parent))
RUNTIME = "tests/budgets/test_runtime_budgets.py"
PROVIDER = "tests/budgets/test_model_payload.py"
WINDOW = "tests/budgets/test_window_budgets.py"
MEASUREMENT = "tests/performance/test_measurement.py"
TRANSPORT = "tests/budgets/provider_cancel_probe.py"
RUNNER = "tests/budgets/test_runner_integrity.py"
LANES = {
    "all": (RUNTIME, PROVIDER, WINDOW, MEASUREMENT),
    "portable": (RUNTIME, WINDOW, MEASUREMENT),
    "provider": (PROVIDER,),
    "window": (WINDOW,),
    "f8": ("tests/runtime", RUNTIME, PROVIDER),
    "transport": (TRANSPORT, PROVIDER),
    "runner": (RUNNER,),
}
EXPECTED = {RUNTIME: 15, PROVIDER: 16, WINDOW: 11, MEASUREMENT: 2, "tests/runtime": 22,
            TRANSPORT: 1, RUNNER: 13}


def hashes(host=None):
    paths = list(PLUGIN.glob("*.py"))
    for directory in ("adapters", "domain", "ports", "runtime", "services", "storage"):
        paths.extend((PLUGIN / directory).rglob("*.py"))
    paths.extend((PLUGIN / "tests/budgets").glob("*.py"))
    paths.extend((PLUGIN / "tests/runtime").glob("*.py"))
    paths.extend(PLUGIN / name for name in ("pyproject.toml", "tests/conftest.py", MEASUREMENT))
    result = {str(path.relative_to(PLUGIN)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sorted(set(paths))}
    if host:
        for name in ("pyproject.toml", "astrbot/__init__.py",
                     "astrbot/core/provider/sources/openai_source.py"):
            result["host/" + name] = hashlib.sha256((host / name).read_bytes()).hexdigest()
    return result


def offline(event, args):
    if event in {"socket.connect", "socket.bind", "socket.sendto", "socket.getaddrinfo"}:
        raise RuntimeError("offline_verification_network_forbidden")


def relative_node(nodeid):
    return nodeid[nodeid.index("tests/"):]


class Evidence:
    def __init__(self):
        self.cases = {}
        self.selected = []
        self.deselected = []
        self.collection_errors = []

    def pytest_collection_finish(self, session):
        self.selected = [relative_node(item.nodeid) for item in session.items]

    def pytest_deselected(self, items):
        self.deselected.extend(relative_node(item.nodeid) for item in items)

    def pytest_collectreport(self, report):
        if report.failed or report.skipped:
            self.collection_errors.append({"status": report.outcome})

    def pytest_runtest_logreport(self, report):
        name = relative_node(report.nodeid)
        row = self.cases.setdefault(name, {"status": "passed", "phases": {}, "measurements": {}})
        row["phases"][report.when] = report.outcome
        if report.when == "call":
            row["call_duration_seconds"] = report.duration
        if report.failed:
            row["status"] = "failed"
        elif report.skipped and row["status"] != "failed":
            row["status"] = "skipped"
        for key, value in report.user_properties:
            if key == "measurements":
                row["measurements"].update(value)
        # Never serialize tracebacks, logs, request bodies, keys or local paths.

    def integrity_failures(self, paths):
        failures = []
        collected = self.selected + self.deselected
        if self.collection_errors:
            failures.append("collection_failed_or_skipped")
        for path in paths:
            count = sum(node.split("::")[0] == path or node.startswith(path + "/")
                        for node in collected)
            if count != EXPECTED[path]:
                failures.append("collection_count_mismatch:" + path)
        if not self.selected:
            failures.append("no_tests_selected")
        if set(self.cases) != set(self.selected):
            failures.append("selected_tests_not_all_executed")
        for node, row in self.cases.items():
            if row["phases"] != {"setup": "passed", "call": "passed", "teardown": "passed"}:
                failures.append("not_all_phases_passed:" + node)
        # Keep original assertions untouched; also require the actual physical result.
        for node, row in self.cases.items():
            if node.endswith("::test_lower_scope_limit_cleanup_prunes_inactive_scopes"):
                if sorted(row["measurements"].get("persisted_per_scope_counts", [])) != [2, 2, 2]:
                    failures.append("inactive_scope_physical_counts_not_2_2_2")
        return failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lane", choices=LANES, default="all")
    parser.add_argument("--host-source", help="AstrBot source root; or ASTRBOT_HOST_SOURCE")
    parser.add_argument("-k", default="")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(PLUGIN / "tests/budgets"):
        parser.error("output must be under tests/budgets")
    if output.exists():
        parser.error("output already exists; use a new evidence label")
    host = host_version = None
    environment_error = None
    dependency_versions = packages(("pytest", "pytest-asyncio", "pytest-timeout",
                                    "openai", "httpx"))
    if sys.version_info < (3, 12):
        environment_error = "python_3_12_required"
    elif any(dependency_versions[name] is None
             for name in ("pytest", "pytest-asyncio", "pytest-timeout")):
        environment_error = "pytest_dependencies_missing"
    elif PROVIDER in LANES[args.lane]:
        try:
            host, host_version = configure_host(args.host_source)
        except RuntimeError as exc:
            environment_error = str(exc)
    before = hashes(host)
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    sys.addaudithook(offline)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True
    # The native-host lane must not inherit CI ignores, -x or third-party plugins.
    os.environ.pop("PYTEST_ADDOPTS", None)
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    evidence = Evidence()
    result = 2
    failures = [environment_error] if environment_error else []
    if environment_error is None:
        import pytest

        with tempfile.TemporaryDirectory(prefix="le-budget-offline-") as temporary:
            original = Path.cwd()
            os.chdir(temporary)
            try:
                options = [
                    *(str(PLUGIN / path) for path in LANES[args.lane]),
                    "-c", str(PLUGIN / "pyproject.toml"),
                    "-o", "addopts=-ra --strict-markers",
                    "-p", "no:cacheprovider", "-p", "pytest_asyncio.plugin",
                    "-p", "pytest_timeout", "--rootdir", str(PLUGIN),
                    "-q", "--tb=short", "-k", args.k,
                    "--basetemp", str(Path(temporary) / "pytest"),
                ]
                if host:
                    options.extend(("--budget-host-source", str(host)))
                result = int(pytest.main(options, plugins=[evidence]))
            finally:
                os.chdir(original)
        failures.extend(evidence.integrity_failures(LANES[args.lane]))
    after = hashes(host)
    provider_module = sys.modules.get("astrbot.core.provider.sources.openai_source")
    provider_matches = bool(host and provider_module and
                            Path(provider_module.__file__).resolve() ==
                            host / "astrbot/core/provider/sources/openai_source.py")
    host_modules_loaded = any(name == "astrbot" or name.startswith("astrbot.")
                              for name in sys.modules)
    if any(node.startswith((PROVIDER + "::", TRANSPORT + "::"))
           for node in evidence.selected) and not provider_matches:
        failures.append("provider_not_loaded_from_selected_host")
    if args.lane in ("portable", "window", "runner") and host_modules_loaded:
        failures.append("portable_lane_imported_host")
    changed = [name for name in before.keys() | after.keys() if before.get(name) != after.get(name)]
    if changed:
        failures.append("source_changed_during_run")
    exit_code = result or (1 if failures else 0)
    report = {
        "schema": "livingemotion-budget-verification-2",
        "started_at_utc": started_at,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.monotonic() - started,
        "environment": {"python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
                        "macos": platform.mac_ver()[0], "architecture": platform.machine(),
                        "packages": dependency_versions, "host_version": host_version,
                        "host_source_explicit": host is not None,
                        "host_modules_loaded": host_modules_loaded,
                        "provider_loaded_from_selected_host": provider_matches},
        "lane": args.lane, "test_paths": list(LANES[args.lane]), "selection": args.k,
        "addopts_overridden": True, "plugin_autoload": False, "pytest_cache": False,
        "offline": True, "synthetic_only": True, "real_network_requests": 0,
        "real_model_requests": 0, "send_calls": 0,
        "source_sha256_before": before, "source_sha256_after": after,
        "source_changed_during_run": bool(changed), "changed_sources": sorted(changed),
        "pytest_exit_code": result, "exit_code": exit_code,
        "gate_failures": failures,
        "complete_lane_passed": exit_code == 0 and not args.k,
        "collection": {
            "expected_before_selection": sum(EXPECTED[path] for path in LANES[args.lane]),
            "collected": len(evidence.selected) + len(evidence.deselected),
            "selected": len(evidence.selected), "deselected": len(evidence.deselected),
            "executed": len(evidence.cases),
            "call_executed": sum("call" in row["phases"] for row in evidence.cases.values()),
            "by_file": dict(Counter(node.split("::")[0] for node in evidence.selected)),
            "selected_nodeids": evidence.selected, "deselected_nodeids": evidence.deselected,
            "errors": evidence.collection_errors,
        },
        "counts": {status: sum(row["status"] == status for row in evidence.cases.values())
                   for status in ("passed", "failed", "skipped")},
        "cases": evidence.cases,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        stream.write(json.dumps(report, indent=2, ensure_ascii=True) + "\n")
    print(json.dumps({"lane": args.lane, "counts": report["counts"],
                      "gate_failures": failures, "exit_code": exit_code}))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
