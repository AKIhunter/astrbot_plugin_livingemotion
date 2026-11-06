"""Record source identities only; never copy source bodies or runtime data."""

import argparse
import hashlib
import json
import os
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


FILES = {
    "astrbot_plugin_congling": [
        "metadata.yaml", "main.py", "core/paths.py", "core/store.py",
        "humanize/persona.py", "humanize/proactive.py", "memory/emotion.py",
        "memory/affinity.py", "memory/diary.py", "night/state.py",
        "night/energy.py", "night/stages.py", "night/wake_flow.py", "night/dream.py",
        "page_api/__init__.py", "pages/fromling/index.html",
    ],
    "BiliBot": ["metadata.yaml", "main.py", "core/emotion_bridge.py"],
    "astrbot_plugin_at_guard": [
        "metadata.yaml", "main.py", "guard_expression.py", "guard_webui.py",
        "guard_native_settings.py", "tests/test_congling_expression_handoff.py",
    ],
    "LivingMemory": [
        "metadata.yaml", "main.py", "core/astrbot_compat.py",
        "core/identity.py", "docs/oneid-core.md",
    ],
}


def git(root, *args):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    return subprocess.check_output(
        ["git", "-C", str(root), *args], env=env
    )


def capture(workspace):
    result = {"captured_at_utc": datetime.now(timezone.utc).isoformat(), "repos": []}
    for name, paths in FILES.items():
        root = workspace / "插件" / name
        before = git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
        head = git(root, "rev-parse", "HEAD").decode().strip()
        entries = before.split(b"\0")
        codes = Counter()
        i = 0
        while i < len(entries):
            entry = entries[i]
            i += 1
            if not entry:
                continue
            code = entry[:2].decode("ascii")
            codes[code] += 1
            if "R" in code or "C" in code:
                i += 1
        selected = {}
        for path in paths:
            file = root / path
            if not file.is_file() or file.is_symlink():
                selected[path] = {"sha256": None, "status": "missing_or_symlink"}
                continue
            selected[path] = {
                "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                "status": git(root, "status", "--porcelain=v1", "--", path)
                .decode().strip()[:2] or "clean",
            }
        after = git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
        result["repos"].append({
            "path": f"插件/{name}", "head": head, "dirty": bool(before),
            "status_counts": dict(sorted(codes.items())),
            "status_manifest_sha256": hashlib.sha256(before).hexdigest(),
            "status_stable_during_capture": before == after,
            "selected": selected,
        })
    return result


def markdown(result):
    lines = [
        "# 源码基线快照", "",
        f"采集时间（UTC）：`{result['captured_at_utc']}`。", "",
        "本文件由 `tests/host/capture_baseline.py` 生成，只记录源码身份。",
        "不包含上游函数体、提示词、素材、聊天、数据库、密钥或运行配置。",
        "HEAD 不是 dirty 工作区的完整身份；以各选用文件 SHA-256 为准。",
        "dirty 全量状态只保存数量及原始 NUL 清单的摘要，不泄露未选用文件名。",
        "这是采集时点的基线，其他代理后续配套修改不属于此快照。",
        "status_stable 只说明采集前后路径状态相同，不保证跨仓库原子快照。",
        "从绫许可未确认，仅作接口/行为参考，不据此授权复制或重新许可。", "",
    ]
    for repo in result["repos"]:
        lines.extend([
            f"## {repo['path']}", "",
            f"- HEAD：`{repo['head']}`",
            f"- dirty：`{repo['dirty']}`；status_stable：`{repo['status_stable_during_capture']}`",
            f"- dirty 状态计数：`{json.dumps(repo['status_counts'])}`",
            f"- dirty 清单 SHA-256：`{repo['status_manifest_sha256']}`", "",
            "| 选用文件 | 状态 | SHA-256 |", "| --- | --- | --- |",
        ])
        for path, value in repo["selected"].items():
            lines.append(f"| `{path}` | `{value['status']}` | `{value['sha256']}` |")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = capture(args.workspace.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        output.write(markdown(result))
    print(json.dumps({
        "output": str(args.output),
        "repos": [{k: v for k, v in repo.items() if k != "selected"} for repo in result["repos"]],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
