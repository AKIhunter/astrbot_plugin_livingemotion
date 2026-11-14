"""承诺任务的持久化：建表、去重、状态流转。

独立于 intents 表，因为承诺的时间跨度是分钟到天，
而行为意图的 TTL 只有三百秒，两者语义完全不同。
"""

from __future__ import annotations

import json
import time
from typing import Any

from ..contracts import Context, stable_key

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS promises (
        promise_id TEXT PRIMARY KEY,
        scope_key TEXT NOT NULL,
        generation INTEGER NOT NULL,
        status TEXT NOT NULL,
        bucket TEXT NOT NULL,
        fingerprint TEXT NOT NULL,
        description TEXT NOT NULL,
        note TEXT NOT NULL,
        due_at REAL NOT NULL,
        original_due_at REAL NOT NULL,
        original_bucket TEXT NOT NULL,
        advance_count INTEGER NOT NULL DEFAULT 0,
        depth INTEGER NOT NULL DEFAULT 0,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL,
        sent_at REAL,
        retry_count INTEGER NOT NULL DEFAULT 0,
        last_error TEXT NOT NULL DEFAULT '')""",
    "CREATE INDEX IF NOT EXISTS promises_scope ON promises(scope_key, status)",
    "CREATE INDEX IF NOT EXISTS promises_due ON promises(status, due_at)",
    "CREATE INDEX IF NOT EXISTS promises_fp ON promises(scope_key, fingerprint, status)",
)

# 老库升级：字段不存在时补上，已存在就跳过。
MIGRATIONS = (
    "ALTER TABLE promises ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0",
)

# 允许的状态转换；越界的写入一律拒绝，避免状态机被绕过。
TRANSITIONS = {
    "scheduled": {"running", "cancelled", "failed"},
    "running": {"sent", "failed", "unknown"},
    "sent": set(),
    "failed": set(),
    "cancelled": set(),
    "unknown": set(),
}

ACTIVE = ("scheduled", "running")


def normalize(description: str) -> str:
    """去重指纹只关心“说的是不是同一件事”，标点与空白不参与。"""
    stops = "，。、；：,.;:!！?？…\u2026"
    body = []
    for char in str(description or ""):
        body.append(" " if char in stops else char)
    text = "".join(body)
    return " ".join(text.split()).lower()


def fingerprint(scope_key: str, description: str) -> str:
    return stable_key("promise", scope_key, normalize(description))


class PromiseStore:
    """挂在 SQLiteStore 上的一组方法，复用它的串行事务与线程池。"""

    def __init__(self, store) -> None:
        self.store = store
        self._ready = False

    async def ensure(self) -> None:
        if self._ready:
            return

        def create(db):
            for statement in SCHEMA:
                db.execute(statement)
            for statement in MIGRATIONS:
                try:
                    db.execute(statement)
                except Exception:
                    pass  # 字段已存在

        await self.store._run(create)
        self._ready = True

    async def create(self, context: Context, *, description: str, note: str,
                     bucket: str, due_at: float, depth: int = 0,
                     ttl_days: int = 7) -> dict[str, Any]:
        await self.ensure()
        scope = context.scope_key
        fp = fingerprint(scope, description)
        now = self.store.clock()
        # generation 不在 Context 上，必须实时取；写错的代次会让任务无法发送。
        try:
            generation = await self.store.get_generation(context)
        except Exception:
            generation = 0

        def create(db):
            def mutate():
                # 同内容已在队列里就不新建，只把时间提前（更早的到期更急）。
                row = db.execute(
                    """SELECT promise_id, due_at, status FROM promises
                       WHERE scope_key=? AND fingerprint=? AND status IN ('scheduled','running')""",
                    (scope, fp)).fetchone()
                if row:
                    if due_at < row["due_at"]:
                        db.execute(
                            "UPDATE promises SET due_at=?, bucket=?, updated_at=? "
                            "WHERE promise_id=? AND status='scheduled'",
                            (due_at, bucket, now, row["promise_id"]))
                        return {"status": "advanced", "promise_id": row["promise_id"]}
                    return {"status": "duplicate", "promise_id": row["promise_id"]}
                # 二十四小时内已经发过同样的事，不再重复骚扰。
                recent = db.execute(
                    """SELECT promise_id FROM promises
                       WHERE scope_key=? AND fingerprint=? AND status='sent'
                         AND sent_at IS NOT NULL AND sent_at>?""",
                    (scope, fp, now - 86400)).fetchone()
                if recent:
                    return {"status": "already_sent", "promise_id": recent["promise_id"]}
                active = db.execute(
                    "SELECT COUNT(*) FROM promises WHERE scope_key=? AND status IN ('scheduled','running')",
                    (scope,)).fetchone()[0]
                promise_id = stable_key("promise-id", scope, fp, now, description)
                db.execute(
                    """INSERT INTO promises(promise_id,scope_key,generation,status,bucket,
                       fingerprint,description,note,due_at,original_due_at,original_bucket,
                       advance_count,depth,created_at,updated_at,sent_at,last_error)
                       VALUES(?,?,?,'scheduled',?,?,?,?,?,?,?,0,?,?,?,NULL,'')""",
                    (promise_id, scope, generation,
                     bucket, fp, normalize(description)[:500], str(note or "")[:2000],
                     due_at, due_at, bucket, max(0, int(depth)), now, now))
                return {"status": "created", "promise_id": promise_id, "active": active + 1}

            return self.store._transaction(db, mutate)

        return await self.store._run(create)

    async def list(self, context: Context, *, statuses=ACTIVE, limit: int = 20) -> list[dict[str, Any]]:
        await self.ensure()
        scope = context.scope_key
        marks = ",".join("?" for _ in statuses)

        def read(db):
            rows = db.execute(
                f"""SELECT * FROM promises WHERE scope_key=? AND status IN ({marks})
                    ORDER BY due_at ASC LIMIT ?""",
                (scope, *statuses, max(1, min(200, int(limit))))).fetchall()
            return [dict(row) for row in rows]

        return await self.store._run(read)

    async def count_active(self, context: Context) -> int:
        rows = await self.list(context, limit=200)
        return len(rows)

    async def due(self, *, now: float, limit: int = 12) -> list[dict[str, Any]]:
        """所有会话里已经到点的承诺，交给调度器逐个处理。"""
        await self.ensure()

        def read(db):
            rows = db.execute(
                """SELECT * FROM promises WHERE status='scheduled' AND due_at<=?
                   ORDER BY due_at ASC LIMIT ?""",
                (now, max(1, min(100, int(limit))))).fetchall()
            return [dict(row) for row in rows]

        return await self.store._run(read)

    async def move(self, promise_id: str, *, status: str, expect=ACTIVE,
                   error: str = "") -> dict[str, Any]:
        await self.ensure()
        now = self.store.clock()

        def write(db):
            def mutate():
                row = db.execute("SELECT status FROM promises WHERE promise_id=?",
                                 (promise_id,)).fetchone()
                if not row:
                    return {"status": "missing"}
                current = row["status"]
                if current not in expect:
                    return {"status": "conflict", "current": current}
                if status not in TRANSITIONS.get(current, set()):
                    return {"status": "illegal", "current": current}
                sent_at = now if status == "sent" else None
                db.execute(
                    """UPDATE promises SET status=?, updated_at=?, sent_at=COALESCE(?,sent_at),
                       last_error=? WHERE promise_id=? AND status=?""",
                    (status, now, sent_at, str(error or "")[:300], promise_id, current))
                return {"status": "ok", "from": current, "to": status}

            return self.store._transaction(db, mutate)

        return await self.store._run(write)

    async def reschedule(self, promise_id: str, *, due_at: float, bucket: str,
                         max_advance: int = 3) -> dict[str, Any]:
        """提前执行时间。原值不动，用来回答“本来打算什么时候发”。"""
        await self.ensure()
        now = self.store.clock()

        def write(db):
            def mutate():
                row = db.execute(
                    """SELECT status, advance_count, updated_at FROM promises
                       WHERE promise_id=?""", (promise_id,)).fetchone()
                if not row:
                    return {"status": "missing"}
                if row["status"] != "scheduled":
                    return {"status": "conflict", "current": row["status"]}
                if row["advance_count"] >= max_advance:
                    return {"status": "too_many", "count": row["advance_count"]}
                # 乐观锁：更新时刻被别人改过就放弃这次调整。
                changed = db.execute(
                    """UPDATE promises SET due_at=?, bucket=?, advance_count=advance_count+1,
                       updated_at=? WHERE promise_id=? AND status='scheduled' AND updated_at=?""",
                    (due_at, bucket, now, promise_id, row["updated_at"]))
                if changed.rowcount == 0:
                    return {"status": "raced"}
                return {"status": "ok", "advance_count": row["advance_count"] + 1}

            return self.store._transaction(db, mutate)

        return await self.store._run(write)

    async def defer(self, promise_id: str, *, retry_at: float, error: str = "",
                    max_retry: int = 3, no_penalty: bool = False) -> dict[str, Any]:
        """发送没成但还值得再试：回到 scheduled，并把 due_at 推后。

        与 failed 的区别：failed 是终态，不再尝试；defer 是“这一轮不行，
        过一会儿再来”。上下文没恢复、上游抖动、瞬时被拒都该走这里。
        """
        await self.ensure()
        now = self.store.clock()

        def write(db):
            def mutate():
                row = db.execute(
                    "SELECT status, retry_count, created_at FROM promises WHERE promise_id=?",
                    (promise_id,)).fetchone()
                if not row:
                    return {"status": "missing"}
                # 会话不在内存不是发送失败，只是“还不到时候”。
                # 这种等待不消耗重试预算，否则用户睡一觉承诺就全死了。
                if no_penalty:
                    db.execute(
                        """UPDATE promises SET status='scheduled', due_at=?, updated_at=?,
                           last_error=? WHERE promise_id=?""",
                        (retry_at, now, str(error or "")[:300], promise_id))
                    return {"status": "deferred", "retry_count": int(row["retry_count"] or 0)}
                tries = int(row["retry_count"] or 0)
                if tries >= max_retry:
                    db.execute(
                        """UPDATE promises SET status='failed', updated_at=?, last_error=?
                           WHERE promise_id=?""",
                        (now, str(error or "retry_exhausted")[:300], promise_id))
                    return {"status": "exhausted", "retry_count": tries}
                db.execute(
                    """UPDATE promises SET status='scheduled', due_at=?, updated_at=?,
                       retry_count=retry_count+1, last_error=? WHERE promise_id=?""",
                    (retry_at, now, str(error or "")[:300], promise_id))
                return {"status": "deferred", "retry_count": tries + 1}

            return self.store._transaction(db, mutate)

        return await self.store._run(write)

    async def reclaim(self, promise_id: str) -> dict[str, Any]:
        """把卡在 running/unknown 的行拉回 scheduled，供重启后自愈。"""
        await self.ensure()
        now = self.store.clock()

        def write(db):
            def mutate():
                changed = db.execute(
                    """UPDATE promises SET status='scheduled', updated_at=?
                       WHERE promise_id=? AND status IN ('running','unknown')""",
                    (now, promise_id))
                return {"status": "ok" if changed.rowcount else "noop"}

            return self.store._transaction(db, mutate)

        return await self.store._run(write)

    async def cancel(self, promise_id: str) -> dict[str, Any]:
        return await self.move(promise_id, status="cancelled", expect=("scheduled",))

    async def purge(self, *, keep: int = 200) -> int:
        """只留最近的若干条，其余直接删掉；不保留历史也不分页。"""
        await self.ensure()

        def write(db):
            def mutate():
                stale = db.execute(
                    """SELECT promise_id FROM promises WHERE status IN ('sent','failed','cancelled','unknown')
                       ORDER BY updated_at DESC LIMIT -1 OFFSET ?""", (keep,)).fetchall()
                if not stale:
                    return 0
                db.executemany("DELETE FROM promises WHERE promise_id=?",
                               [(row["promise_id"],) for row in stale])
                return len(stale)

            return self.store._transaction(db, mutate)

        return await self.store._run(write)

    async def advance_quota_block(self, context: Context, due_at: float) -> bool:
        """提前前先看目标日期配额还够不够；跨天就是换桶。"""
        period = time.strftime("%Y-%m-%d", time.localtime(due_at))
        limit = getattr(self.store.config, "behavior_daily_limit", 6)

        def read(db):
            used = db.execute(
                "SELECT COALESCE(SUM(units),0) FROM quota_reservations "
                "WHERE period=? AND pool='send'", (period,)).fetchone()[0]
            return used

        try:
            used = await self.store._run(read)
        except Exception:
            return True
        return used < limit


def parse_bucket(bucket: str, now: float, timezone: str = "Asia/Shanghai") -> float:
    """把语义档换算成时间点。档位由模型给，落点由本地时钟算。"""
    import random
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(timezone or "Asia/Shanghai")
    current = datetime.fromtimestamp(now, tz)
    name = str(bucket or "一会儿").strip()

    if name in ("马上", "now"):
        return now + random.uniform(120, 300)
    if name in ("一会儿", "soon"):
        return now + random.uniform(900, 1800)
    if name in ("待会", "later"):
        return now + random.uniform(2400, 4200)
    if name in ("今晚", "tonight"):
        target = current.replace(hour=random.randint(20, 22), minute=random.randint(0, 59),
                                 second=0, microsecond=0)
        if target <= current:
            target += timedelta(days=1)
        return target.timestamp()
    if name in ("明天", "tomorrow"):
        target = (current + timedelta(days=1)).replace(
            hour=random.randint(9, 11), minute=random.randint(0, 59), second=0, microsecond=0)
        return target.timestamp()
    if name in ("过几天", "later_days"):
        return now + random.uniform(2, 4) * 86400
    return now + random.uniform(900, 1800)


def bucket_label(bucket: str) -> str:
    return {"马上": "几分钟内", "now": "几分钟内", "一会儿": "过一会儿", "soon": "过一会儿",
            "待会": "等会儿", "later": "等会儿", "今晚": "今晚", "tonight": "今晚",
            "明天": "明天", "tomorrow": "明天", "过几天": "过几天",
            "later_days": "过几天"}.get(str(bucket or ""), "过一会儿")


__all__ = [
    "ACTIVE", "PromiseStore", "SCHEMA", "TRANSITIONS",
    "bucket_label", "fingerprint", "normalize", "parse_bucket",
]
