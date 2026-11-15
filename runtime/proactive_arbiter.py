"""主动聊天的单一入口：先看宿主有没有在自己找人聊。

AstrBot 自带一条「主动找主人聊话题」的 cron（默认 10:30 / 15:30 / 20:30）。
LivingEmotion 也有一套按随机间隔发起的主动行为。两套同时开着，同一时段
就会各说一次——用户看到的是"今天怎么连着来两条"。

处理原则：**不替用户改宿主数据**。宿主的任务在它自己的面板里可见、可管理，
插件越过它去删 job，既不透明也不可靠（APScheduler 在内存里已经排好，
改库要重启才生效）。所以这里只做三件事：

1. 只读探测 `data_v4.db` 的 `cron_jobs`，认出主动聊天类任务；
2. 认出来的时候，LivingEmotion 侧**让行**（跳过本轮随机主动行为）；
3. 结果进「功能耦合」面板，让用户知道是让给谁、去哪里关。

关掉宿主那条之后，探测结果自然变空，这边立刻恢复，不需要改任何配置。
"""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger("astrbot_plugin_livingemotion.promise")

# 只认明确指向"主动找人说话"的措辞。不要把「晚安」「日记」这类
# 也算了进来——它们各有自己的通道，算进来会让主动行为被永久让行。
HOST_CHAT_WORDS = ("主动找", "主动聊", "主动问候", "聊话题", "找主人", "主动搭话", "主动说话")
PROBE_TTL = 300.0

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
                  ("id", "name", "job_type", "cron_expression", "run_at", "enabled", "note")
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
        "jobs": [{"id": str(job.get("id") or ""), "name": str(job.get("name") or ""),
                  "schedule": _schedule_of(job)} for job in hits[:5]],
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


__all__ = ["cached", "probe_once", "refresh"]
