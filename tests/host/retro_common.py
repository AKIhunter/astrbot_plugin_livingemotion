"""Independent P8 identities and child isolation, not legacy acceptance helpers."""

from __future__ import annotations

from collections import Counter
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time


NAME = "astrbot_plugin_livingemotion"
HOST_COMMITS = {
    "v4.29.1": "dffe922773725e9c178392c423676ad65044748c",
    "v4.29.2": "38fc189d58758cc9ceda8585fbdee84eabf8a13a",
    "v4.29.3": "f61a7f42696da6df25dc7a249ec9b8d54ed9da18",
    "v4.29.4": "61335414433db721b3f7ecc93f90deafe0a59d78",
}
ROUTES = {
    "state": "GET", "records": "GET", "config": "POST",
    "preview": "POST", "action": "POST", "scopes": "GET",
    "relationships": "GET", "relationship": "POST",
    "energy": "GET", "settings-options": "GET",
}
PRODUCT_DIRS = {
    "adapters", "domain", "page_api", "pages", "ports", "runtime",
    "services", "storage", "tools",
}
PRODUCT_SUFFIXES = {".py", ".yaml", ".yml", ".json", ".js", ".mjs", ".html", ".css", ".svg"}
EXCLUDED = {".git", "__pycache__", "node_modules", ".venv", ".pytest_cache"}


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args], text=True, stderr=subprocess.DEVNULL,
    ).strip()


def digest(files):
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def product_files(root):
    files = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in EXCLUDED for part in rel.parts):
            continue
        if not path.is_file() or path.suffix not in PRODUCT_SUFFIXES:
            continue
        if len(rel.parts) > 1 and rel.parts[0] not in PRODUCT_DIRS:
            continue
        if path.is_symlink():
            raise ValueError("Product source symlinks are not accepted")
        files[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def source_identity(root):
    files = product_files(root)
    # An isolated source candidate carries its origin separately; hash the
    # actual tested tree, never pretend it is the origin repository worktree.
    origin = Path(os.environ.get("LIVINGEMOTION_SOURCE_ORIGIN", str(root)))
    return {
        "git_head": git(origin, "rev-parse", "HEAD"),
        "git_status": git(origin, "status", "--porcelain").splitlines(),
        "source_origin": str(origin), "tested_source": str(root),
        "files_sha256": files, "source_sha256": digest(files),
    }


def host_identity(root, tag):
    head = git(root, "rev-parse", "HEAD")
    resolved_tag = git(root, "rev-parse", tag + "^{commit}")
    status = git(root, "status", "--porcelain", "--untracked-files=no")
    if head != HOST_COMMITS[tag] or resolved_tag != head or status:
        raise ValueError(f"Host identity mismatch: {tag}")
    paths = subprocess.check_output(
        ["git", "-C", str(root), "ls-files", "-z"],
    ).decode().split("\0")
    files = {}
    for rel in sorted(filter(None, paths)):
        path = root / rel
        if path.is_file():
            files[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "tag": tag, "commit": head, "tag_commit": resolved_tag,
        "tracked_worktree_clean": True,
        "tracked_files_sha256": files, "source_sha256": digest(files),
    }


def scrubbed_env(root, python):
    return {
        "PATH": f"{python.parent}:/usr/bin:/bin",
        "HOME": str(root / "home"), "TMPDIR": str(root / "tmp"),
        "ASTRBOT_ROOT": str(root), "ASTRBOT_DISABLE_METRICS": "1",
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1",
        "LANG": "en_US.UTF-8", "TZ": "UTC",
        "NO_PROXY": "127.0.0.1,localhost,::1",
    }


def network_guard(blocked):
    def allowed(host):
        if host in ("localhost", b"localhost"):
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except (TypeError, ValueError):
            return False

    def audit(event, args):
        if event == "socket.getaddrinfo":
            host = args[0]
        elif event in {"socket.connect", "socket.bind", "socket.sendto"}:
            address = args[2] if event == "socket.sendto" else args[1]
            host = address[0] if isinstance(address, tuple) else address
        else:
            host = None
        if event in {
            "socket.connect", "socket.bind", "socket.getaddrinfo", "socket.sendto",
        } and not allowed(host):
            blocked.append(event)
            raise PermissionError("P8 runtime forbids non-loopback sockets")
        if event in {"subprocess.Popen", "os.system", "os.posix_spawn", "os.exec"}:
            blocked.append(event)
            raise PermissionError("P8 runtime forbids subprocesses")

    sys.addaudithook(audit)


def guard_selftest(e):
    for label, operation in {
        "external_dns": lambda: socket.getaddrinfo("example.invalid", 443),
        "external_connect": lambda: socket.create_connection(("192.0.2.1", 443)),
        "wildcard_bind": lambda: bind_address("0.0.0.0"),
        "runtime_subprocess": lambda: subprocess.run(["/usr/bin/true"], check=True),
    }.items():
        try:
            operation()
        except PermissionError:
            e.check("isolation." + label, True, layer="harness")
        else:
            e.check("isolation." + label, False, layer="harness", fatal=True)
    e.check("isolation.loopback_bind", bind_address("127.0.0.1"), layer="harness")
    e.check(
        "isolation.no_inherited_credentials",
        not any(
            marker in key.upper()
            for key in os.environ
            for marker in ("API_KEY", "TOKEN", "PASSWORD", "HTTP_PROXY", "HTTPS_PROXY")
        ),
        layer="harness", fatal=True,
    )


def bind_address(host):
    with socket.socket() as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1] > 0


class Evidence:
    def __init__(self, report):
        self.report = report

    def check(self, name, passed, *, detail=None, layer="real_host", fatal=False):
        entry = {"name": name, "passed": bool(passed), "layer": layer}
        if detail is not None:
            entry["detail"] = detail
        self.report["checks"].append(entry)
        if not passed and fatal:
            raise AssertionError(name)

    async def case(self, name, operation):
        start = time.monotonic()
        try:
            await operation()
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self.check(name, False, detail={"exception_type": type(exc).__name__})
        self.report.setdefault("case_seconds", {})[name] = round(
            time.monotonic() - start, 3,
        )

    def finish(self):
        counts = Counter("passed" if c["passed"] else "failed" for c in self.report["checks"])
        self.report["counts"] = dict(counts)
        self.report["success"] = not counts.get("failed") and not self.report.get("fatal_type")
        self.report["final_frozen_acceptance"] = (
            self.report["phase"] == "final" and self.report["success"]
        )


def product(module):
    import importlib
    return importlib.import_module(f"data.plugins.{NAME}.{module}")


def plugin(core):
    return core.star_context.get_registered_star(NAME).star_cls


def owned_tasks():
    import asyncio
    return [
        task for task in asyncio.all_tasks()
        if task.get_name().startswith("livingemotion-") and not task.done()
    ]
