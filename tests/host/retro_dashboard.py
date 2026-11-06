"""Prepare exact native Dashboard bundles without changing host repositories."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

from retro_common import digest, host_identity, scrubbed_env


RELEASE_SHA = {
    "v4.29.1": "55a52c359d16574ccef04e760006b3b0d7a5253c3c4912099ae3ebc53e4f3603",
    "v4.29.3": "a09f560c4140b930180f63a4929c885da80e24fb9bbda56619727bd25e985a11",
    "v4.29.4": "12f394569e5b7971a53218e261917032f8c499a504584de3af8dacfd7557af74",
}


def tree_files(root):
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*")) if p.is_file()
        and not any(part in {"node_modules", "dist", ".git"} for part in p.relative_to(root).parts)
    }


def dashboard_identity(root, tag):
    data = json.loads((root / "identity.json").read_text())
    files = tree_files(root / "dist")
    if data["tag"] != tag or files != data["files_sha256"]:
        raise ValueError("Native Dashboard bundle identity changed")
    if tag in RELEASE_SHA:
        archive = root / f"AstrBot-{tag}-dashboard.zip"
        if hashlib.sha256(archive.read_bytes()).hexdigest() != RELEASE_SHA[tag]:
            raise ValueError("Native Dashboard release archive identity changed")
    return data


def prepare(base, host4, python):
    for tag in (*RELEASE_SHA, "v4.29.2"):
        root = base / "dashboard" / tag
        host = host4 if tag == "v4.29.4" else base / "hosts" / tag
        identity = host_identity(host, tag)
        root.mkdir(parents=True, exist_ok=True)
        if (root / "identity.json").exists():
            dashboard_identity(root, tag)
            continue
        provenance = {"tag": tag, "host_commit": identity["commit"]}
        if tag in RELEASE_SHA:
            archive = root / f"AstrBot-{tag}-dashboard.zip"
            actual = hashlib.sha256(archive.read_bytes()).hexdigest()
            if actual != RELEASE_SHA[tag]:
                raise ValueError("Official Dashboard archive digest mismatch")
            with zipfile.ZipFile(archive) as bundle:
                for item in bundle.infolist():
                    if not item.filename.startswith("dist/") or ".." in Path(item.filename).parts:
                        raise ValueError("Unexpected native archive entry")
                bundle.extractall(root)
            provenance.update(origin="github_release", archive_sha256=actual)
        else:
            build = root / "build"
            if build.exists():
                raise ValueError("Previous unfinished native build exists; inspect it first")
            source_files = tree_files(host / "dashboard")
            shutil.copytree(host / "dashboard", build / "dashboard")
            asset = "astrbot/core/utils/t2i/template/shiki_runtime.iife.js"
            destination = build / asset
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(host / asset, destination)
            (build / "home").mkdir()
            (build / "tmp").mkdir()
            env = scrubbed_env(build, python)
            env["PATH"] = "/opt/homebrew/bin:/usr/bin:/bin"
            env["CI"] = "true"
            commands = [
                ["npx", "--yes", "pnpm@10.28.2", "install", "--frozen-lockfile"],
                ["npx", "--yes", "pnpm@10.28.2", "run", "build"],
            ]
            with (root / "build.log").open("w") as log:
                for command in commands:
                    subprocess.run(command, cwd=build / "dashboard", env=env,
                                   stdout=log, stderr=log, check=True, timeout=600)
            shutil.copytree(build / "dashboard/dist", root / "dist")
            provenance.update(
                origin="exact_tag_local_build_no_release", commands=commands,
                source_files_sha256=source_files, source_sha256=digest(source_files),
                pnpm_lock_sha256=source_files["pnpm-lock.yaml"],
            )
        files = tree_files(root / "dist")
        if "index.html" not in files or not any(
            p.startswith("assets/PluginViewPage-") and p.endswith(".js") for p in files
        ):
            raise ValueError("Bundle lacks native Dashboard plugin view")
        provenance.update(files_sha256=files, source_sha256_bundle=digest(files))
        (root / "identity.json").write_text(json.dumps(provenance, indent=2))
        if host_identity(host, tag) != identity:
            raise ValueError("Host changed during Dashboard preparation")
        print(json.dumps({"tag": tag, "origin": provenance["origin"],
                          "bundle_sha256": digest(files)}), flush=True)


if __name__ == "__main__":
    workspace = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=workspace / ".livingemotion-retro-host")
    parser.add_argument("--host4", type=Path, default=workspace / ".livingemotion-host-t1/AstrBot")
    parser.add_argument("--python", type=Path,
                        default=workspace / ".livingemotion-host-t1/venv/bin/python3.12")
    args = parser.parse_args()
    prepare(args.base, args.host4, args.python)
