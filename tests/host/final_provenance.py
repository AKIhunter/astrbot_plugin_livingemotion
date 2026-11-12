"""Record immutable inputs around the original final runner; never rewrite runs."""

import argparse
import fnmatch
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timezone

from final_run import hashes


PLUGINS = (
    "astrbot_plugin_livingemotion",
    "astrbot_plugin_at_guard",
    "LivingMemory",
    "BiliBot",
)
COPY_IGNORES = (
    ".git", ".venv", ".trae", "__pycache__", "*.pyc", "node_modules", "tests",
    "data", "*.db", "*.sqlite*", ".env*", ".pytest_cache", "docs",
)


def files(root, ignores=()):
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file() and not any(
            fnmatch.fnmatch(part, pattern)
            for part in p.relative_to(root).parts for pattern in ignores
        )
    }


def digest(manifest):
    return hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-dir", type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--run", type=Path)
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[4]
    isolated = workspace / ".livingemotion-host-t1"
    audit = args.audit_dir or Path(tempfile.mkdtemp(
        prefix="final-frozen-provenance-", dir=isolated / "runs"
    ))
    output = audit / f"{args.label}.json"
    if output.exists():
        raise FileExistsError("Provenance labels must be unique")
    manifests = {
        name: files(workspace / "插件" / name, COPY_IGNORES) for name in PLUGINS
    }
    manifests["tests_host"] = hashes(Path(__file__).parent)
    manifests["host_source"] = hashes(isolated / "AstrBot")
    manifests["dashboard_dist"] = files(isolated / "final-dashboard/dist")
    record = {
        "label": args.label,
        "utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "host_head": (isolated / "AstrBot/.git/HEAD").read_text().strip(),
        "manifests": manifests,
        "digests": {name: digest(items) for name, items in manifests.items()},
        "file_counts": {name: len(items) for name, items in manifests.items()},
    }
    baseline = audit / "baseline.json"
    if baseline.exists():
        original = json.loads(baseline.read_text())
        record["changed_inputs"] = [
            name for name, value in record["digests"].items()
            if value != original["digests"].get(name)
        ]
    if args.run:
        run = args.run.resolve()
        report = json.loads((run / "report.json").read_text())
        copied = run / "data/plugins"
        record["run_id"] = run.name
        record["run_tests_match"] = report["test_hashes"] == manifests["tests_host"]
        record["run_products_match"] = {
            name: files(copied / name) == manifests[name]
            for name in PLUGINS if (copied / name).exists()
        }
        record["run_source_before_matches_after"] = (
            report["source_before"] == hashes(copied)
        )
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "audit_dir": audit.relative_to(workspace).as_posix(),
        **{key: value for key, value in record.items() if key != "manifests"},
    }, ensure_ascii=False))
    return 2 if (
        record.get("changed_inputs")
        or record.get("run_tests_match") is False
        or not all(record.get("run_products_match", {}).values())
        or record.get("run_source_before_matches_after") is False
    ) else 0


if __name__ == "__main__":
    raise SystemExit(main())
