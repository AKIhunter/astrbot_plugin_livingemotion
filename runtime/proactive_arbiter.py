"""只在同一会话的宿主定时问候前后让行；宿主任务始终只读。"""

from __future__ import annotations

import logging
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from ..contracts import rebuild_route

logger = logging.getLogger("astrbot_plugin_livingemotion.promise")

# 只认明确指向"主动找人说话"的措辞。不要把「提醒」「日记」这类
# 也算了进来——它们各有自己的通道，算进来会让主动行为被永久让行。
# 「早安 / 晚安 / 撒娇 / 自拍」也算：这类定时问候同样会与随机主动行为撞车，
# 用户看到的是"八点半刚说完早安，九点又来一条"。
HOST_CHAT_WORDS = (
    "主动找", "主动聊", "主动问候", "主动搭话", "主动说话", "聊话题", "找主人",
    "早安", "晚安", "撒娇", "问候", "想念", "想你", "自拍", "分享心情",
)
PROBE_TTL = 300.0
YIELD_WINDOW_SECONDS = 15 * 60

_CACHE: dict[str, tuple[float, dict]] = {}


def _data_root(data_dir) -> Path | None:
    """从插件数据目录反推宿主 `data/`。"""
    try:
        path = Path(data_dir)
    except Exception:
        return None
    # 典型值：<AstrBot>/data/plugin_data/astrbot_plugin_livingemotion
    for candidate in (path.parent.parent, path.parent, path):
        if (candidate / "data_v4.db").exists():
            return candidate
    return None


def _read_jobs(db_path: Path) -> list[dict]:
    """只读打开，绝不加锁；列名按实际表结构取，不假设版本。"""
    uri = f"file:{db_path.as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=1.0)
    connection.row_factory = sqlite3.Row
    try:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(cron_jobs)")}
        if not columns:
            return []
        wanted = [name for name in
                  ("id", "name", "job_type", "cron_expression", "run_at", "enabled", "note",
                   "payload", "last_run_at", "next_run_time")
                  if name in columns]
        if not wanted:
            return []
        rows = connection.execute(
            f"SELECT {','.join(wanted)} FROM cron_jobs").fetchall()
        return [{name: row[name] for name in wanted} for row in rows]
    finally:
        connection.close()


def _schedule_of(job: dict) -> str:
    cron = str(job.get("cron_expression") or "").strip()
    if cron:
        return cron
    run_at = str(job.get("run_at") or "").strip()
    if run_at:
        return f"一次性 {run_at}"
    return ""


def _is_host_chat(job: dict) -> bool:
    if str(job.get("enabled", 1) or 0) in ("0", "False", "false"):
        return False
    haystack = f"{job.get('name') or ''} {job.get('note') or ''}"
    return any(word in haystack for word in HOST_CHAT_WORDS)


def _host_timestamp(value) -> float | None:
    """宿主数据库的无时区日期是 UTC，不能按插件/机器本地时区解释。"""
    try:
        moment = datetime.fromisoformat(str(value or ""))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.timestamp()
    except (ValueError, TypeError, OverflowError):
        return None


def _job_view(job: dict) -> dict:
    try:
        payload = json.loads(job.get("payload") or "{}")
    except (ValueError, TypeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return {
        "id": str(job.get("id") or ""), "name": str(job.get("name") or ""),
        "schedule": _schedule_of(job),
        "target_route": str(payload.get("session") or ""),
        "next_run_at": _host_timestamp(job.get("next_run_time")),
        "last_run_at": _host_timestamp(job.get("last_run_at")),
    }


def yielding_jobs(state: dict, context, now: float) -> list[dict]:
    """按宿主已排定/最近执行时间判断，不凭任务存在或过期缓存全天让行。"""
    route = rebuild_route(context)
    if not route or not state.get("present"):
        return []
    hits = []
    for job in state.get("jobs") or []:
        if job.get("target_route") != route:
            continue
        # next_run_at 在触发后短暂滞后，仍覆盖这次任务的后窗口。
        # last_run_at 覆盖刷新后以及晚到的实际执行；不重新推算 cron/时区。
        if any(isinstance(at, (int, float)) and abs(now - at) <= YIELD_WINDOW_SECONDS
               for at in (job.get("next_run_at"), job.get("last_run_at"))):
            hits.append(job)
    return hits


def probe_once(data_dir) -> dict:
    """同步探测一次；失败一律按"没检测到"处理，绝不让面板或主动行为崩。"""
    root = _data_root(data_dir)
    if root is None:
        return {"present": False, "count": 0, "jobs": [], "reason": "host_data_not_found"}
    try:
        jobs = _read_jobs(root / "data_v4.db")
    except Exception as exc:
        logger.warning("[LE-coupling] 宿主 cron 探测失败 %r", exc)
        return {"present": False, "count": 0, "jobs": [], "reason": "host_data_unreadable"}
    hits = [job for job in jobs if _is_host_chat(job)]
    return {
        "present": bool(hits),
        "count": len(hits),
        "jobs": [_job_view(job) for job in hits],
        "reason": "" if hits else "no_host_proactive_chat",
        "checked_at": time.time(),
    }


def cached(data_dir) -> dict:
    """不触发 IO 的只读视图，给同步构造的 DTO 用。"""
    key = str(data_dir or "")
    entry = _CACHE.get(key)
    if not entry:
        return {"present": False, "count": 0, "jobs": [], "reason": "not_probed_yet"}
    return entry[1]


def refresh(data_dir, *, ttl: float = PROBE_TTL) -> dict:
    key = str(data_dir or "")
    now = time.time()
    entry = _CACHE.get(key)
    if entry and now - entry[0] < ttl:
        return entry[1]
    value = probe_once(data_dir)
    _CACHE[key] = (now, value)
    return value


__all__ = ["cached", "probe_once", "refresh", "yielding_jobs"]
