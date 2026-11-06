"""Repeatable offline component evidence; never loads production configuration."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).resolve().parent / "evidence"
SUITES = {
    "components": [
        "tests/domain", "tests/identity", "tests/memory", "tests/night",
        "tests/behavior", "tests/experience", "tests/storage", "tests/contracts",
        "tests/runtime", "tests/integration",
    ],
    "probes": ["tests/verification/test_cross_module.py"],
    "migration": ["tests/migration", "tests/verification/test_migration_cli.py"],
    "migration-base": [
        "tests/migration/test_legacy_import.py",
        "tests/verification/test_migration_cli.py::"
        "test_cli_rollback_preserves_new_event_and_requires_stopped_target",
    ],
    "full": ["tests"],
    "ci-environment": [
        "tests/budgets/test_model_payload.py::test_real_provider_request_local_wire_payload",
    ],
    "verification-tools": ["tests/verification/test_evidence_tools.py"],
}


def hashes():
    paths = []
    for directory in (
        "domain", "storage", "adapters", "services", "runtime", "ports", "tools", "page_api",
    ):
        paths.extend((ROOT / directory).rglob("*.py"))
    paths.extend(path for path in (ROOT / "pages").rglob("*") if path.is_file())
    paths.extend(path for path in (ROOT / ".github").rglob("*") if path.is_file())
    paths.extend(ROOT / name for name in (
        "api.py", "contracts.py", "config.py", "main.py", "_conf_schema.json", "pyproject.toml",
        "__init__.py", "requirements-dev.txt", "metadata.yaml", "README.md",
        "LICENSE", "THIRD_PARTY_NOTICES.md", ".gitignore",
    ))
    paths.extend(path for path in (ROOT / "tests").rglob("*.py")
                 if not any(part in {"node_modules", "__pycache__"} for part in path.parts))
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(set(paths))
    }


def environment():
    return {
        "executable": sys.executable, "prefix": sys.prefix, "base_prefix": sys.base_prefix,
        "sys_path": sys.path,
        "distributions": {
            item.metadata["Name"]: item.version
            for item in importlib.metadata.distributions() if item.metadata.get("Name")
        },
        "optional_imports_before_pytest": {
            name: bool(importlib.util.find_spec(name)) for name in ("astrbot", "httpx", "openai")
        },
        "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
        "PYTHONHOME": os.environ.get("PYTHONHOME", ""),
        "PYTHONNOUSERSITE": os.environ.get("PYTHONNOUSERSITE", ""),
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def junit_summary(path):
    if not path.is_file():
        return {"available": False}
    try:
        suites = ET.parse(path).getroot()
    except ET.ParseError:
        return {"available": False, "error": "invalid_junit_xml"}
    return {
        "available": True,
        "suites": [dict(suite.attrib) for suite in suites.iter("testsuite")],
        "cases": [
            {
                "classname": case.get("classname"), "name": case.get("name"),
                "outcome": next(
                    (kind for kind in ("failure", "error", "skipped")
                     if case.find(kind) is not None), "passed",
                ),
            }
            for case in suites.iter("testcase")
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("suite", choices=SUITES)
    parser.add_argument("--label", default="")
    parser.add_argument("--match", default="", help="Optional pytest -k expression for focused checks")
    parser.add_argument("--collect-only", action="store_true")
    args = parser.parse_args()
    if args.suite == "migration" and not (ROOT / "docs" / "migration.md").is_file():
        parser.error("migration owner handoff docs/migration.md is not present")
    OUTPUT.mkdir(exist_ok=True)
    label = args.label or args.suite
    if not label.replace("-", "").replace("_", "").isalnum():
        parser.error("label must be a simple filename")
    if any((OUTPUT / (label + suffix)).exists() for suffix in (".json", ".log", ".xml")):
        parser.error("evidence label already exists; choose a new label")
    command = [
        sys.executable, "-m", "pytest", *SUITES[args.suite], "-vv",
        "-p", "no:cacheprovider", "--tb=short",
        f"--junitxml={OUTPUT / (label + '.xml')}",
    ]
    if args.match:
        command.extend(["-k", args.match])
    if args.collect_only:
        command.append("--collect-only")
    before = hashes()
    test_environment = environment()
    started = datetime.now(timezone.utc).isoformat()
    clock = time.monotonic()
    timed_out = False
    try:
        result = subprocess.run(
            command, cwd=ROOT, text=True, capture_output=True, timeout=240,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        exit_code, output = result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired as error:
        timed_out, exit_code = True, 124
        output = "".join(
            value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""
            for value in (error.stdout, error.stderr)
        )
        output += "\nverification_runner_timeout_seconds=240\n"
    duration = time.monotonic() - clock
    after = hashes()
    (OUTPUT / (label + ".log")).write_text(output, encoding="utf-8")
    junit = junit_summary(OUTPUT / (label + ".xml"))
    if not junit["available"] and exit_code == 0:
        exit_code = 125
    record = {
        "started_at_utc": started, "duration_seconds": duration,
        "python": sys.version, "platform": platform.platform(),
        "cwd": str(ROOT), "command": command, "exit_code": exit_code,
        "collect_only": args.collect_only, "timed_out": timed_out,
        "test_environment": test_environment,
        "junit": junit,
        "source_sha256": before,
        "changed_during_run": [
            key for key in before.keys() | after.keys() if before.get(key) != after.get(key)
        ],
        "boundaries": "Synthetic fixtures, temporary SQLite, model/sender stubs. No host claim.",
    }
    (OUTPUT / (label + ".json")).write_text(
        json.dumps(record, ensure_ascii=True, indent=2) + "\n", encoding="utf-8",
    )
    print(output)
    print(json.dumps({"exit_code": exit_code, "changed_during_run":
                      record["changed_during_run"], "record": f"evidence/{label}.json"}))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
