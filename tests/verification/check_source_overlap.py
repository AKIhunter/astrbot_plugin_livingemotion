"""Read selected reference sources only; retain hashes/locations, never source text."""

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
REFERENCE_FILES = (
    "main.py", "__init__.py", "api.py", "contracts.py", "config.py",
    "page_api/__init__.py",
)
REVIEWED_EVIDENCE = frozenset({
    "tests/host/evidence-v4.29.4.json",
    "tests/console/evidence-v4.29.4.json",
    "tests/ui/evidence/browser-results.json",
    *("tests/ui/evidence/" + name for name in (
        "1280-light-overview.png", "1280-dark-overview.png",
        "390-light-overview.png", "390-dark-overview.png",
        "390-light-emotion.png", "390-dark-emotion.png",
        "390-light-private-reading.png", "390-dark-private-reading.png",
    )),
})
EXCLUDED_DIRECTORIES = frozenset({
    ".git", ".venv", ".venv-ci", "venv", ".ci-work", ".ci-results",
    "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    "htmlcov", "test-results", "playwright-report", "runs", "artifacts", "logs",
})


def digest(data):
    return hashlib.sha256(data).hexdigest()


def signatures(path, root):
    data = path.read_bytes()
    functions, literals = [], []
    if path.suffix == ".py":
        tree = ast.parse(data, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.end_lineno - node.lineno + 1 >= 10:
                    # Compare bodies independently of function names and source locations.
                    body = ast.Module(body=node.body, type_ignores=[])
                    functions.append((digest(ast.dump(body).encode()), node.lineno))
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if len(node.value.strip()) >= 120:
                    literals.append((digest(node.value.strip().encode()), node.lineno))
    return {"path": str(path.relative_to(root)), "sha256": digest(data),
            "functions": functions, "long_literals": literals}


def delivery_files(manifest):
    content = json.loads(manifest.read_text(encoding="utf-8"))
    names = content["files"]
    if (not isinstance(names, list) or not names
            or any(not isinstance(name, str) for name in names)
            or len(names) != len(set(names))):
        raise ValueError("invalid_delivery_manifest")
    paths = []
    for name in names:
        relative = Path(name)
        path = ROOT / relative
        if (relative.is_absolute() or ".." in relative.parts or not path.is_file()
                or not path.resolve().is_relative_to(ROOT.resolve())):
            raise ValueError("invalid_delivery_path")
        paths.append(path)
    return sorted(paths)


def candidate_files():
    files = []
    for directory, names, filenames in os.walk(ROOT):
        relative = Path(directory).relative_to(ROOT)
        names[:] = [
            name for name in names
            if name not in EXCLUDED_DIRECTORIES and not name.startswith(".venv")
            and ("evidence" not in name or any(
                reviewed.startswith((relative / name).as_posix() + "/")
                for reviewed in REVIEWED_EVIDENCE
            ))
        ]
        for name in filenames:
            item = relative / name
            is_evidence = ("evidence" in item.parts[:-1]
                           or name.startswith("evidence") or "final_evidence" in item.parts)
            if (name == ".DS_Store" or item.suffix in {".pyc", ".pyo", ".log", ".xml"}
                    or is_evidence and item.as_posix() not in REVIEWED_EVIDENCE):
                continue
            files.append(item.as_posix())
    missing = REVIEWED_EVIDENCE.difference(files)
    if missing:
        raise ValueError("reviewed_evidence_missing")
    return sorted(files)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--label", required=True)
    inventory = parser.add_mutually_exclusive_group()
    inventory.add_argument("--manifest", type=Path, help='JSON object with a "files" path list')
    inventory.add_argument("--candidate", action="store_true", help="Inventory the delivery candidate")
    args = parser.parse_args()
    if not args.label.replace("-", "").replace("_", "").isalnum():
        parser.error("label must be a simple filename")
    target = Path(__file__).parent / "evidence" / (args.label + ".json")
    if target.exists():
        parser.error("evidence label already exists; choose a new label")
    target.parent.mkdir(exist_ok=True)
    if args.candidate:
        args.manifest = target.with_suffix(".manifest.json")
        if args.manifest.exists():
            parser.error("manifest label already exists; choose a new label")
        manifest = {
            "files": candidate_files(),
            "reviewed_evidence": sorted(REVIEWED_EVIDENCE),
            "excluded_directories": sorted(EXCLUDED_DIRECTORIES),
            "scope": "User-specified delivery candidate, not a Git/staged inventory",
        }
        with args.manifest.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(manifest, ensure_ascii=True, indent=2) + "\n")
    if args.manifest:
        files = delivery_files(args.manifest)
    else:
        files = [ROOT / name for name in (
            "__init__.py", "main.py", "api.py", "contracts.py", "config.py",
        )]
        for directory in (
            "adapters", "domain", "ports", "runtime", "services", "storage", "tools", "page_api",
        ):
            files.extend((ROOT / directory).rglob("*.py"))
        files.extend(path for path in (ROOT / "pages").rglob("*") if path.is_file())
    new = [signatures(path, ROOT) for path in sorted(files)]
    old = [signatures(args.reference / name, args.reference) for name in REFERENCE_FILES]
    changed = [
        record["path"] for record in new
        if not (ROOT / record["path"]).is_file()
        or digest((ROOT / record["path"]).read_bytes()) != record["sha256"]
    ]
    overlaps = []
    for category in ("functions", "long_literals"):
        lookup = {}
        for record in old:
            for value, line in record[category]:
                lookup.setdefault(value, []).append({"file": record["path"], "line": line})
        for record in new:
            for value, line in record[category]:
                if value in lookup:
                    overlaps.append({"kind": category, "sha256": value,
                                     "new": {"file": record["path"], "line": line},
                                     "reference": lookup[value]})
    for record in new:
        for reference in old:
            if record["sha256"] == reference["sha256"]:
                overlaps.append({"kind": "whole_file", "new": record["path"],
                                 "reference": reference["path"]})
    output = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "command": [sys.executable, *sys.argv], "reference_root": str(args.reference),
        "manifest_sha256": digest(args.manifest.read_bytes()) if args.manifest else None,
        "inventory_scope": ("delivery_candidate" if args.candidate else
                            "explicit_delivery_manifest" if args.manifest else "product_sources_only"),
        "changed_during_scan": changed,
        "inventory_changed_during_scan": args.candidate and candidate_files() != manifest["files"],
        "checked_new_files": new, "checked_reference_files": old,
        "matches": overlaps,
        "limits": "Python AST function bodies >=10 lines and literals >=120 chars; "
                  "all candidate file types get byte-exact whole-file comparison only. "
                  "13 selected reference files, not all upstream history or other dependencies. "
                  "No fuzzy/renamed-code/legal provenance proof; no Git/network/runtime data read.",
        "notices": {name: digest((ROOT / name).read_bytes())
                    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md")},
    }
    with target.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(output, ensure_ascii=True, indent=2) + "\n")
    print(json.dumps({"new_files": len(new), "reference_files": len(old),
                      "python_functions": sum(len(item["functions"]) for item in new),
                      "python_long_literals": sum(len(item["long_literals"]) for item in new),
                      "matches": len(overlaps), "changed_during_scan": changed,
                      "inventory_changed_during_scan": output["inventory_changed_during_scan"],
                      "evidence": str(target)}))
    return int(bool(overlaps or changed or output["inventory_changed_during_scan"]))


if __name__ == "__main__":
    raise SystemExit(main())
