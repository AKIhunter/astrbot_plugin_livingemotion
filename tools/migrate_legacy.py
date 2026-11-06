"""Run from any working directory; requires Python 3.10+ and no host installation."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from astrbot_plugin_livingemotion.contracts import canonical_json
from astrbot_plugin_livingemotion.storage.legacy_import import (
    MigrationError,
    import_manifest,
    preview,
    read_json,
    rollback_plan,
    verify,
    write_json,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="livingEmotion 离线快照迁移；必须停止目标插件")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("preview", "import", "verify", "rollback-plan"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--target", required=True, help="现有独立目标库的绝对路径")
        sub.add_argument("--target-stopped", action="store_true", help="确认目标插件及写者已停止")
        sub.add_argument("--output", help="新建 0600 JSON 报告；绝不覆盖已有文件")
        if name == "rollback-plan":
            sub.add_argument("--consumers", required=True, help="明确的消费者恢复选择 JSON")
        else:
            sub.add_argument("--snapshot", required=True, help="已完成的一致快照绝对路径")
            sub.add_argument("--snapshot-confirmed", action="store_true",
                             help="确认不是生产活动库，且快照已通过一致备份生成")
            sub.add_argument("--selection" if name == "preview" else "--manifest", required=True)
    args = parser.parse_args(argv)
    try:
        # Preflight output before a transaction, including same-file protection.
        if args.output:
            output = Path(args.output)
            if output.exists() or not output.parent.is_dir():
                raise MigrationError("output_must_be_new_file")
            protected = [args.target]
            if args.command != "rollback-plan":
                protected.extend([args.snapshot, getattr(args, "selection", None),
                                  getattr(args, "manifest", None)])
            if any(output.resolve() == Path(path).resolve() for path in protected if path):
                raise MigrationError("output_overlaps_input")
        if args.command == "rollback-plan":
            result = rollback_plan(args.target, read_json(args.consumers),
                                   target_stopped=args.target_stopped)
        else:
            options = {
                "snapshot_confirmed": args.snapshot_confirmed,
                "target_stopped": args.target_stopped,
            }
            data = read_json(args.selection if args.command == "preview" else args.manifest)
            operation = {"preview": preview, "import": import_manifest, "verify": verify}[args.command]
            result = operation(args.snapshot, args.target, data, **options)
        if args.output:
            write_json(args.output, result)
        print(canonical_json(result))
        return 3 if result.get("status") == "mismatch" else 0
    except MigrationError as exc:
        print(canonical_json({"status": "rejected", "reason_code": str(exc)}), file=sys.stderr)
    except (sqlite3.Error, OSError, ValueError, TypeError, KeyError, OverflowError):
        print(canonical_json({"status": "rejected", "reason_code": "invalid_input_or_io"}),
              file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
