"""承诺任务的持久化：建表、去重、状态流转。

独立于 intents 表，因为承诺的时间跨度是分钟到天，
而行为意图的 TTL 只有三百秒，两者语义完全不同。
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from ..contracts import Context, stable_key, to_dict

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
    # 兑现那一刻的短时记忆片段。有真实 event 的时刻只有「承诺刚落库」和
    # 「本轮回复刚提交」两处，而承诺到期往往隔了几十分钟、甚至跨重启——
    # 那时既没有 event，也没有当时的上下文。所以召回要前置或就近快照：
    # 落库时存一份 prefetch，兑现时存一份 delivery，追问时直接命中这里，
    # 不必再走一次向量检索（TTL 默认一天，过期即释放）。
    """CREATE TABLE IF NOT EXISTS promise_traces (
        trace_id TEXT PRIMARY KEY,
        scope_key TEXT NOT NULL,
        promise_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        summary TEXT NOT NULL DEFAULT '',
        materials_json TEXT NOT NULL DEFAULT '[]',
        reply_text TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL,
        expires_at REAL NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS promise_traces_scope ON promise_traces(scope_key, expires_at)",
)

# 老库升级：字段不存在时补上，已存在就跳过。
MIGRATIONS = (
    "ALTER TABLE promises ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0",
    # 承诺建立时的上下文概要：给到期生成做检索锚点，也给模型交代「当时在聊什么」。
    "ALTER TABLE promises ADD COLUMN context_summary TEXT NOT NULL DEFAULT ''",
    # 兑现时真正发出去的文本（多气泡以换行连接），供追问命中与排错。
    "ALTER TABLE promises ADD COLUMN delivered_text TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE promises ADD COLUMN source_event_id TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE promises ADD COLUMN host_job_id TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE promises ADD COLUMN action_state TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE promises ADD COLUMN action_result_json TEXT NOT NULL DEFAULT '{}'",
    "ALTER TABLE promises ADD COLUMN handoff_key TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE promises ADD COLUMN handoff_account_key TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE promises ADD COLUMN adjustment_notice_state TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE promises ADD COLUMN adjustment_notice_attempt INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE promises ADD COLUMN adjustment_notice_retry_at REAL NOT NULL DEFAULT 0",
    "ALTER TABLE promises ADD COLUMN waiting_since REAL NOT NULL DEFAULT 0",
)

# 允许的状态转换；越界的写入一律拒绝，避免状态机被绕过。
TRANSITIONS = {
    # awaiting：已经到点，但处在耦合状态——不单独发消息，
    # 等对话里下一轮回复一并交付（见 application._inject_pending_promises）。
    "scheduled": {"running", "awaiting", "cancelled", "failed", "delegated"},
    "running": {"sent", "failed", "unknown", "delegated", "waiting"},
    "awaiting": {"sent", "cancelled", "failed"},
    "sent": set(),
    "failed": set(),
    "cancelled": set(),
    # 只结束后续处理；未知副作用不能自动恢复执行。
    "unknown": {"cancelled", "failed"},
    "delegated": set(),
    # waiting 与旧 awaiting 不同：等待需求调整或结果核对，tick/heal 绝不能自动释放。
    "waiting": {"scheduled", "cancelled", "failed"},
}

ACTIVE = ("scheduled", "running", "waiting", "awaiting", "unknown")
NOTICE_KINDS = (
    "content_rejected", "prompt_too_long", "prompt_adjustment_required",
    "provider_error", "result_unknown", "delivery_unknown", "quota_exhausted",
    "rate_limited", "image_action_unknown", "action_interrupted",
    "image_rejected", "image_unavailable",
)

# 「刚发过就别再建」的判定窗口（秒）。
# 这条规则只用来挡住**同一条回复被重复提交**造成的双份任务，
# 不能当「今天说过就永不再记」：提醒类措辞（「十分钟后提醒我出门」）
# 一天里本来就会反复出现，24 小时窗口会把第二次请求静默吞掉。
ALREADY_SENT_WINDOW = 600


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


def is_adjustment(text: str) -> bool:
    """只挡住纯确认/重试口令；不能把“嗯”当成用户已改变画面。"""
    value = normalize(text).replace(" ", "")
    return bool(value) and not re.fullmatch(
        r"(?:(?:嗯+|哦+|好+|好的|行|可以|知道了|收到|ok|yes|继续|"
        r"再试(?:一次|试)?|重试(?:一次)?|再来(?:一次)?|试试|retry|tryagain|"
        r"算了(?:吧)?|不用(?:拍|画)?了|别(?:拍|画)了|"
        r"取消(?:这张(?:照片|图片|图)?|这次)?(?:吧)?|"
        r"(?:这张(?:照片|图片|图)?|这次)?(?:就)?(?:先)?(?:不(?:拍|画)了|不要了)))+",
        value,
    )


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
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS promises_handoff "
                       "ON promises(scope_key,handoff_key) WHERE handoff_key!=''")
            # 旧暂停项沿用原时间，不因升级重新获得等待期限。
            db.execute("UPDATE promises SET waiting_since=updated_at "
                       "WHERE status IN ('waiting','unknown') AND waiting_since=0")

        await self.store._run(create)
        self._ready = True

    async def create(self, context: Context, *, description: str, note: str,
                     bucket: str, due_at: float, depth: int = 0,
                     ttl_days: int = 7, context_summary: str = "",
                     source_event_id: str = "", max_active: int | None = None) -> dict[str, Any]:
        if max_active is not None and (type(max_active) is not int or not 1 <= max_active <= 10):
            raise ValueError("promise_max_active: expected 1-10")
        await self.ensure()
        from ..runtime.promise_actions import needs_image
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
                if source_event_id:
                    # 消息提交钩子可能晚于 LH 失败回执，不能再次建立同源图片任务。
                    if needs_image(description):
                        handed = db.execute(
                            """SELECT promise_id FROM promises
                               WHERE scope_key=? AND source_event_id=? AND handoff_key!=''
                                 AND (handoff_account_key='' OR handoff_account_key=?) LIMIT 1""",
                            (scope, str(source_event_id), context.account_key)).fetchone()
                        if handed:
                            return {"status": "duplicate", "promise_id": handed["promise_id"]}
                    owned = db.execute(
                        """SELECT promise_id,host_job_id FROM promises
                           WHERE scope_key=? AND source_event_id=? AND fingerprint=?
                             AND status='delegated' LIMIT 1""",
                        (scope, str(source_event_id), fp)).fetchone()
                    if owned:
                        return {"status": "delegated", **dict(owned)}
                # 同内容已在队列里就不新建，只把时间提前（更早的到期更急）。
                row = db.execute(
                    """SELECT promise_id, due_at, status FROM promises
                       WHERE scope_key=? AND fingerprint=?
                         AND status IN ('scheduled','running','waiting','awaiting','unknown')""",
                    (scope, fp)).fetchone()
                if row:
                    if row["status"] in ("waiting", "awaiting", "unknown"):
                        # 暂停或等待合并交付的同一项只复用，不通过重复标记释放暂停。
                        return {"status": "duplicate", "promise_id": row["promise_id"]}
                    if due_at < row["due_at"]:
                        db.execute(
                            "UPDATE promises SET due_at=?, bucket=?, updated_at=? "
                            "WHERE promise_id=? AND status='scheduled'",
                            (due_at, bucket, now, row["promise_id"]))
                        return {"status": "advanced", "promise_id": row["promise_id"]}
                    return {"status": "duplicate", "promise_id": row["promise_id"]}
                # 刚发过同样的事就不再建，窗口见 ALREADY_SENT_WINDOW 的说明。
                recent = db.execute(
                    """SELECT promise_id, sent_at FROM promises
                       WHERE scope_key=? AND fingerprint=? AND status='sent'
                         AND sent_at IS NOT NULL AND sent_at>?""",
                    (scope, fp, now - ALREADY_SENT_WINDOW)).fetchone()
                if recent:
                    return {"status": "already_sent", "promise_id": recent["promise_id"],
                            "age": int(now - float(recent["sent_at"] or now))}
                active = db.execute(
                    "SELECT COUNT(*) FROM promises WHERE scope_key=? "
                    "AND status IN ('scheduled','running','waiting','awaiting','unknown')",
                    (scope,)).fetchone()[0]
                # 去重/同源复用优先；名额检查和 INSERT 同事务，最后一个名额不会被并发抢穿。
                if max_active is not None and active >= max_active:
                    return {"status": "limit_reached", "active": active, "max_active": max_active}
                promise_id = stable_key("promise-id", scope, fp, now, description)
                db.execute(
                    """INSERT INTO promises(promise_id,scope_key,generation,status,bucket,
                       fingerprint,description,note,due_at,original_due_at,original_bucket,
                       advance_count,depth,created_at,updated_at,sent_at,last_error,
                       context_summary,source_event_id,handoff_account_key)
                       VALUES(?,?,?,'scheduled',?,?,?,?,?,?,?,0,?,?,?,NULL,'',?,?,?)""",
                    (promise_id, scope, generation,
                     bucket, fp, normalize(description)[:500], str(note or "")[:2000],
                     due_at, due_at, bucket, max(0, int(depth)), now, now,
                     str(context_summary or "")[:1200], str(source_event_id or "")[:200],
                     context.account_key if self._needs_image(description) else ""))
                return {"status": "created", "promise_id": promise_id, "active": active + 1}

            return self.store._transaction(db, mutate)

        return await self.store._run(create)

    async def accept_image_handoff(self, context: Context, *, request_id: str,
                                   source_event_id: str, failure: dict,
                                   max_active: int | None = None, retry_limit: int = 3) -> dict:
        """同一请求只交接一次；创建与动作状态在同一事务中落盘。"""
        if max_active is not None and (type(max_active) is not int or not 1 <= max_active <= 10):
            raise ValueError("promise_max_active: expected 1-10")
        await self.ensure()
        now = self.store.clock()
        generation = await self.store.get_generation(context)
        pid = stable_key("image-followup", context.scope_key, request_id)
        payload = json.dumps({**failure, "source_context": to_dict(context)}, ensure_ascii=False)
        notice = "sent" if failure.get("adjustment_asked") is True else ""
        ready = retry_limit > 0 and not failure.get("use_reference") and (
            failure["kind"] == "rate_limited" or failure.get("auto_prompt_retry") is True
            and failure["kind"] in {"content_rejected", "prompt_too_long"})
        status, action = ("scheduled", "retry_ready") if ready else ("waiting", "held")
        bucket = "等待重试" if ready else "等待调整" if failure["kind"] in {
            "content_rejected", "prompt_too_long", "prompt_adjustment_required"} else "等待核对"
        description = "生图：" + failure["prompt"][:490]

        def write(db):
            def mutate():
                if self.store._generation(db, context) != generation:
                    return {"status": "rejected", "reason": "generation_changed"}
                row = db.execute(
                    "SELECT promise_id,status FROM promises WHERE scope_key=? AND handoff_key=?",
                    (context.scope_key, request_id)).fetchone()
                if row:
                    if notice == "sent":
                        db.execute(
                            """UPDATE promises SET adjustment_notice_state='sent'
                               WHERE promise_id=? AND status='waiting'
                               AND last_error IN ('content_rejected','prompt_too_long',
                                                  'prompt_adjustment_required')""", (row["promise_id"],))
                    return {"status": "duplicate", "promise_id": row["promise_id"],
                            "task_status": row["status"]}
                # 原回复已经登记过图片承诺时，复用唯一尚未执行的那条；不抢宿主/执行中任务。
                from ..runtime.promise_actions import needs_image
                originals = db.execute(
                    """SELECT * FROM promises WHERE scope_key=? AND source_event_id=?
                       AND handoff_key='' AND status NOT IN ('cancelled','failed')""",
                    (context.scope_key, source_event_id)).fetchall() if source_event_id else []
                originals = [r for r in originals if needs_image(r["description"])]
                if originals:
                    if (len(originals) != 1 or originals[0]["status"] != "scheduled"
                            or originals[0]["generation"] != generation
                            or originals[0]["host_job_id"]
                            or originals[0]["action_state"] not in ("", "retry_ready")):
                        return {"status": "rejected", "reason": "source_image_already_owned"}
                    original = originals[0]
                    db.execute(
                        """UPDATE promises SET status=?,bucket=?,fingerprint=?,description=?,note=?,
                           due_at=?,original_due_at=?,original_bucket=?,updated_at=?,context_summary=?,
                           action_state=?,action_result_json=?,handoff_key=?,last_error=?,
                           handoff_account_key=?,adjustment_notice_state=?,
                           adjustment_notice_attempt=0,adjustment_notice_retry_at=0,
                           waiting_since=?
                           WHERE promise_id=? AND status='scheduled'""",
                        (status, bucket, fingerprint(context.scope_key, description), description,
                         failure["prompt"], now + 300, now + 300, bucket, now, failure["reason"],
                         action, payload, request_id, failure["kind"], context.account_key,
                         notice, now if status == "waiting" else 0, original["promise_id"]))
                    return {"status": "accepted", "promise_id": original["promise_id"],
                            "task_status": status}
                active = db.execute(
                    "SELECT COUNT(*) FROM promises WHERE scope_key=? "
                    "AND status IN ('scheduled','running','waiting','awaiting','unknown')",
                    (context.scope_key,)).fetchone()[0]
                if max_active is not None and active >= max_active:
                    return {"status": "limit_reached", "active": active, "max_active": max_active}
                db.execute(
                    """INSERT INTO promises
                       (promise_id,scope_key,generation,status,bucket,fingerprint,description,note,
                        due_at,original_due_at,original_bucket,depth,created_at,updated_at,
                        context_summary,source_event_id,action_state,action_result_json,handoff_key,
                        last_error,handoff_account_key,adjustment_notice_state,waiting_since)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,0,?,?,?,?,?,?,?,?,?,?,?)""",
                    (pid, context.scope_key, generation, status, bucket,
                     fingerprint(context.scope_key, description), description, failure["prompt"],
                     now + 300, now + 300, bucket, now, now,
                     failure["reason"], source_event_id, action, payload, request_id, failure["kind"],
                     context.account_key, notice, now if status == "waiting" else 0))
                return {"status": "accepted", "promise_id": pid, "task_status": status}
            return self.store._transaction(db, mutate)
        return await self.store._run(write)

    async def resume_image_handoff(self, context: Context, promise_id: str, *,
                                   prompt: str, source_event_id: str) -> dict:
        """仅用户新一轮明确调整可释放内容拒绝；结果未知不能由模型释放。"""
        await self.ensure()
        now = self.store.clock()
        generation = await self.store.get_generation(context)

        def write(db):
            def mutate():
                if self.store._generation(db, context) != generation:
                    return {"status": "rejected", "reason": "generation_changed"}
                row = db.execute(
                    "SELECT * FROM promises WHERE promise_id=? AND scope_key=? "
                    "AND handoff_account_key=? AND handoff_key!=''",
                    (promise_id, context.scope_key, context.account_key)).fetchone()
                if not row:
                    return {"status": "missing"}
                if row["status"] != "waiting":
                    return {"status": "conflict"}
                failure = json.loads(row["action_result_json"])
                if (failure.get("kind") not in {
                        "content_rejected", "prompt_too_long", "prompt_adjustment_required"} or failure.get("use_reference")
                        or not source_event_id or not is_adjustment(prompt)
                        or source_event_id == row["source_event_id"]
                        or normalize(prompt) == normalize(failure["prompt"])):
                    return {"status": "rejected", "reason": "adjustment_required"}
                failure.update(prompt=prompt, kind="adjusted_request", reason="用户已调整画面需求",
                               adjustment_round=int(failure.get("adjustment_round") or 0) + 1,
                               original_prompt=prompt, attempted_prompt=prompt, prompt_retry_count=0)
                failure.pop("prompt_repair", None)
                failure.pop("notice", None)
                description = "生图：" + prompt[:490]
                db.execute(
                    """UPDATE promises SET status='scheduled',action_state='retry_ready',
                       action_result_json=?,description=?,note=?,fingerprint=?,due_at=?,
                       bucket='马上',updated_at=?,generation=?,last_error='',source_event_id=?,
                       adjustment_notice_state='',adjustment_notice_attempt=0,
                       adjustment_notice_retry_at=0,waiting_since=0
                       WHERE promise_id=? AND status='waiting'""",
                    (json.dumps(failure, ensure_ascii=False), description, prompt,
                     fingerprint(context.scope_key, description), now + 20, now, generation,
                     source_event_id, promise_id))
                return {"status": "resumed", "promise_id": promise_id}
            return self.store._transaction(db, mutate)
        return await self.store._run(write)

    @staticmethod
    def _needs_image(description):
        from ..runtime.promise_actions import needs_image
        return needs_image(description)

    async def bind_image_request(self, context: Context, binding: dict) -> dict:
        """收费前原子领取原事项，与后台调度争用同一条状态。"""
        await self.ensure()
        generation, now = await self.store.get_generation(context), self.store.clock()

        def write(db):
            def mutate():
                row = db.execute(
                    "SELECT * FROM promises WHERE promise_id=? AND scope_key=?",
                    (binding["promise_id"], context.scope_key)).fetchone()
                if (not row or row["handoff_account_key"] not in ("", context.account_key)
                        or row["generation"] != generation
                        or self.store._generation(db, context) != generation):
                    return {"status": "rejected", "reason": "source_changed"}
                if not row["handoff_account_key"] and context.scene_kind.value == "group":
                    return {"status": "rejected", "reason": "legacy_source_unverified"}
                if (row["status"] != "scheduled" or row["host_job_id"]
                        or row["action_state"] not in ("", "retry_ready")
                        or not self._needs_image(row["description"])):
                    return {"status": "rejected", "reason": "image_already_owned_or_paused"}
                prior = json.loads(row["action_result_json"] or "{}")
                source = prior.get("source_context")
                if source and any(source.get(k) != to_dict(context).get(k) for k in (
                        "persona_revision", "identity_revision", "account_id")):
                    return {"status": "rejected", "reason": "source_changed"}
                artifact = {**prior, **binding, "external_image": True,
                            "source_context": to_dict(context)}
                db.execute(
                    "UPDATE promises SET status='running',action_state='generating',"
                    "action_result_json=?,handoff_account_key=?,updated_at=? "
                    "WHERE promise_id=? AND status='scheduled'",
                    (json.dumps(artifact, ensure_ascii=False), context.account_key, now,
                     binding["promise_id"]))
                return {"status": "bound", "promise_id": binding["promise_id"]}
            return self.store._transaction(db, mutate)
        return await self.store._run(write)

    async def settle_image_request(self, context: Context, receipt: dict, *,
                                   ttl_seconds: float = 86400, retry_limit: int = 3) -> dict:
        """请求、代次与来源一致才结算；成功事实和 trace 在同一事务提交。"""
        await self.ensure()
        generation, now = await self.store.get_generation(context), self.store.clock()
        pid = receipt["promise_id"]

        def write(db):
            def mutate():
                row = db.execute(
                    "SELECT * FROM promises WHERE promise_id=? AND scope_key=?",
                    (pid, context.scope_key)).fetchone()
                if (not row or row["handoff_account_key"] != context.account_key
                        or row["generation"] != generation
                        or self.store._generation(db, context) != generation):
                    return {"status": "rejected", "reason": "source_changed"}
                prior = json.loads(row["action_result_json"] or "{}")
                source = prior.get("source_context") or {}
                if (prior.get("external_image") is not True
                        or prior.get("request_id") != receipt["request_id"]
                        or any(source.get(k) != to_dict(context).get(k) for k in (
                            "instance_id", "persona_revision", "identity_revision", "account_id", "route"))):
                    return {"status": "rejected", "reason": "request_mismatch"}
                if row["status"] == "sent":
                    return {"status": "duplicate", "promise_id": pid}
                if row["status"] not in ("running", "waiting", "unknown"):
                    return {"status": "rejected", "reason": "task_changed"}
                artifact = {**prior, **receipt}
                sent = receipt["status"] == "sent"
                kind = str(receipt.get("kind") or "result_unknown")
                # 新映射可重试的确定失败仍走原调度链路；未知结果始终暂停。
                ready = retry_limit > 0 and not sent and receipt["status"] == "failed" and (
                    kind == "rate_limited" or receipt.get("auto_prompt_retry") is True
                    and kind in {"content_rejected", "prompt_too_long"})
                status = "sent" if sent else "scheduled" if ready else "waiting"
                action = "sent" if sent else "retry_ready" if ready else "held"
                if ready:
                    artifact.pop("external_image", None)
                text = ("图片已发送；原需求：" + str(receipt.get("prompt") or "")
                        + ("；上游画法：" + str(receipt["revised"]) if receipt.get("revised") else ""))[:4000]
                db.execute(
                    """UPDATE promises SET status=?,action_state=?,action_result_json=?,
                       delivered_text=?,sent_at=?,last_error=?,bucket=?,handoff_key=?,
                       adjustment_notice_state=?,updated_at=?,due_at=?,waiting_since=?
                       WHERE promise_id=?""",
                    (status, action, json.dumps(artifact, ensure_ascii=False),
                     text if sent else "", now if sent else None, "" if sent else kind,
                     row["bucket"] if sent else "等待重试" if ready else (
                         "等待调整" if kind in {"content_rejected", "prompt_too_long",
                                               "prompt_adjustment_required"} else "等待核对"),
                     row["handoff_key"] or receipt["request_id"],
                     "sent" if receipt.get("adjustment_asked") is True else row["adjustment_notice_state"],
                     now, now + 300 if ready else row["due_at"],
                     (row["waiting_since"] or now) if status == "waiting" else 0, pid))
                if sent:
                    db.execute(
                        """INSERT INTO promise_traces(trace_id,scope_key,promise_id,kind,summary,
                           materials_json,reply_text,created_at,expires_at)
                           VALUES(?,?,?,'delivery',?,'[]',?,?,?)
                           ON CONFLICT(trace_id) DO UPDATE SET reply_text=excluded.reply_text,
                             created_at=excluded.created_at,expires_at=excluded.expires_at""",
                        (pid + ":delivery", context.scope_key, pid,
                         str(row["context_summary"] or "")[:1200], text, now,
                         now + max(3600, min(168 * 3600, float(ttl_seconds)))))
                return {"status": "sent" if sent else "settled", "promise_id": pid}
            return self.store._transaction(db, mutate)
        return await self.store._run(write)

    async def delivered_images(self, context: Context) -> list[dict]:
        await self.ensure()

        def read(db):
            rows = db.execute(
                "SELECT description,delivered_text,sent_at FROM promises "
                "WHERE scope_key=? AND status='sent' AND sent_at>? "
                "AND (handoff_account_key=? OR (handoff_account_key='' AND ?)) "
                "ORDER BY sent_at DESC LIMIT 20",
                # 旧群聊空归属无法确认收件人，不作为当前账号的图片事实。
                (context.scope_key, self.store.clock() - 7 * 86400, context.account_key,
                 context.scene_kind.value != "group")).fetchall()
            return [dict(row) for row in rows if self._needs_image(row["description"])][:5]
        return await self.store._run(read)

    async def list(self, context: Context, *, statuses=ACTIVE,
                   limit: int | None = 20) -> list[dict[str, Any]]:
        await self.ensure()
        scope = context.scope_key
        marks = ",".join("?" for _ in statuses)

        def read(db):
            rows = db.execute(
                f"""SELECT * FROM promises WHERE scope_key=? AND status IN ({marks})
                    AND (handoff_account_key='' OR handoff_account_key=?)
                    ORDER BY due_at ASC,created_at ASC,promise_id ASC LIMIT ?""",
                (scope, *statuses, context.account_key,
                 -1 if limit is None else max(1, min(200, int(limit))))).fetchall()
            return [dict(row) for row in rows]

        return await self.store._run(read)

    async def count_active(self, context: Context) -> int:
        await self.ensure()
        return await self.store._run(lambda db: db.execute(
            "SELECT COUNT(*) FROM promises WHERE scope_key=? "
            "AND status IN ('scheduled','running','waiting','awaiting','unknown')",
            (context.scope_key,)).fetchone()[0])

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

    async def active(self, *, scope_key: str = "", limit: int | None = 3) -> list[dict[str, Any]]:
        """待兑现的承诺：按到期时间排，limit=None 时完整展示。

        只给页面只读展示用；真正调度走 due()。
        """
        await self.ensure()

        def read(db):
            sql = ("SELECT promise_id,scope_key,description,status,bucket,due_at,original_due_at,"
                   "created_at,handoff_account_key,advance_count,last_error "
                   "FROM promises WHERE status IN ('scheduled','running','waiting','awaiting','unknown')")
            args: list[Any] = []
            if scope_key:
                sql += " AND scope_key=?"
                args.append(scope_key)
            sql += " ORDER BY due_at ASC,promise_id ASC"
            if limit is not None:
                sql += " LIMIT ?"
                args.append(max(1, min(50, int(limit))))
            return [dict(row) for row in db.execute(sql, args)]

        return await self.store._run(read)

    async def take_awaiting(self, *, scope_key: str,
                            limit: int = 3) -> list[dict[str, Any]]:
        """到点待并入回复的承诺。

        耦合生效时刻意不发独立消息：多一条气泡就会和被动回复撞车。
        这里只取出来交给本轮请求，由回复本身完成交付。
        """
        await self.ensure()
        if not scope_key:
            return []

        def read(db):
            rows = db.execute(
                """SELECT promise_id,description,status,bucket,due_at FROM promises
                   WHERE scope_key=? AND status='awaiting'
                   ORDER BY due_at ASC LIMIT ?""",
                (scope_key, max(1, min(20, int(limit))))).fetchall()
            return [dict(row) for row in rows]

        return await self.store._run(read)

    async def release_awaiting(self, now: float) -> int:
        """把等待并入回复的承诺放回队列。

        用户中途把「承诺代办」切回 off 时，之前攒下的 awaiting 不会有任何
        人再来取，会永远卡在那里。off 的语义就是「照旧单独发一条」，
        所以这里把它们重新排到当前时刻。
        """
        await self.ensure()

        def write(db):
            def mutate():
                cur = db.execute(
                    """UPDATE promises SET status='scheduled', due_at=?, updated_at=?
                       WHERE status='awaiting'""", (now, now))
                return {"status": "ok", "released": cur.rowcount}

            return self.store._transaction(db, mutate)

        result = await self.store._run(write)
        return int(result.get("released") or 0)

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
                       last_error=?,waiting_since=CASE
                         WHEN ? IN ('waiting','unknown') THEN
                           CASE WHEN waiting_since>0 THEN waiting_since ELSE ? END
                         ELSE 0 END
                       WHERE promise_id=? AND status=?""",
                    (status, now, sent_at, str(error or "")[:300], status, now, promise_id, current))
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
                if row["status"] not in ("scheduled", "running"):
                    return {"status": "conflict", "current": row["status"]}
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
                       WHERE promise_id=? AND status='running'
                         AND action_state NOT IN ('generating','sending','unknown')""",
                    (now, promise_id))
                return {"status": "ok" if changed.rowcount else "noop"}

            return self.store._transaction(db, mutate)

        return await self.store._run(write)

    async def checkpoint_action(self, promise_id: str, state: str, result=None) -> bool:
        """副作用前先落阶段，重启后不盲目重复收费或发送。"""
        await self.ensure()
        payload = json.dumps(result or {}, ensure_ascii=False)

        def write(db):
            changed = db.execute(
                """UPDATE promises SET action_state=?, action_result_json=?, updated_at=?
                   WHERE promise_id=? AND status='running'""",
                (state, payload, self.store.clock(), promise_id))
            return changed.rowcount == 1

        return await self.store._run(write)

    async def get(self, promise_id: str) -> dict | None:
        await self.ensure()

        def read(db):
            row = db.execute("SELECT * FROM promises WHERE promise_id=?", (promise_id,)).fetchone()
            return dict(row) if row else None

        return await self.store._run(read)

    async def hold_image_request(self, context: Context, promise_id: str, failure: dict) -> bool:
        """到期生图的内容拒绝也建立原任务恢复入口，不另建一条待办。"""
        await self.ensure()
        request_id = str(failure.get("request_id") or stable_key(
            "image-rejection", promise_id, failure.get("prompt")))
        payload = json.dumps({**failure, "request_id": request_id,
                              "source_context": to_dict(context)}, ensure_ascii=False)

        def write(db):
            changed = db.execute(
                """UPDATE promises SET status='waiting',bucket='等待调整',
                   last_error=?,action_state='held',action_result_json=?,
                   handoff_key=?,handoff_account_key=?,adjustment_notice_state=?,
                   adjustment_notice_attempt=0,adjustment_notice_retry_at=0,updated_at=?,
                   waiting_since=?
                   WHERE promise_id=? AND scope_key=? AND status='running'""",
                (str(failure.get("kind") or "content_rejected"), payload, request_id, context.account_key,
                 "sent" if failure.get("adjustment_asked") is True else "",
                 self.store.clock(), self.store.clock(), promise_id, context.scope_key))
            return changed.rowcount == 1
        return await self.store._run(write)

    async def pending_adjustment_notices(self, *, now: float, limit: int = 12) -> list[dict]:
        await self.ensure()

        def read(db):
            rows = db.execute(
                """SELECT * FROM promises WHERE status IN ('waiting','unknown')
                   AND last_error IN ('content_rejected','prompt_too_long','prompt_adjustment_required',
                                      'provider_error','result_unknown','delivery_unknown',
                                      'quota_exhausted','rate_limited','image_action_unknown',
                                      'action_interrupted','image_rejected','image_unavailable')
                   AND adjustment_notice_state IN ('','rejected')
                   AND adjustment_notice_attempt<3 AND adjustment_notice_retry_at<=?
                   ORDER BY updated_at,promise_id LIMIT ?""",
                (now, max(1, min(100, limit)))).fetchall()
            return [dict(row) for row in rows]
        return await self.store._run(read)

    async def hold_image_failure(self, context: Context, promise_id: str, failure: dict,
                                 *, state="held", expect=("running",)) -> bool:
        """统一失败收尾；身份/代次/状态在一个事务核验，失败请求内容仍留存。"""
        await self.ensure()
        now = self.store.clock()
        def write(db):
            def mutate():
                row = db.execute("SELECT * FROM promises WHERE promise_id=?", (promise_id,)).fetchone()
                if (not row or row["status"] not in expect or row["scope_key"] != context.scope_key
                        or row["generation"] != self.store._generation(db, context)
                        or row["handoff_account_key"] not in ("", context.account_key)):
                    return False
                request_id = str(failure.get("request_id") or row["handoff_key"] or stable_key(
                    "image-failure", promise_id, failure.get("prompt")))
                artifact = {**failure, "request_id": request_id, "source_context": to_dict(context)}
                db.execute(
                    """UPDATE promises SET status=?,bucket='等待核对',action_state=?,
                       action_result_json=?,last_error=?,handoff_key=?,handoff_account_key=?,
                       waiting_since=CASE WHEN waiting_since>0 THEN waiting_since ELSE ? END,
                       updated_at=? WHERE promise_id=?""",
                    ("unknown" if state == "unknown" else "waiting", state,
                     json.dumps(artifact, ensure_ascii=False),
                     str(failure.get("kind") or "provider_error"), request_id, context.account_key,
                     now, now, promise_id))
                return True
            return self.store._transaction(db, mutate)
        return await self.store._run(write)

    async def expire_waiting(self, *, now: float, timeout_seconds: float) -> int:
        """结束等待并释放名额；保留 action_state/请求/失败内容，不伪装已完成。"""
        await self.ensure()
        def write(db):
            changed = db.execute(
                """UPDATE promises SET status='failed',bucket='等待超时',updated_at=?,
                   last_error='waiting_timeout'
                   WHERE status IN ('waiting','unknown')
                   AND CASE WHEN waiting_since>0 THEN waiting_since ELSE updated_at END<=?""",
                (now, now - timeout_seconds))
            return changed.rowcount
        return await self.store._run(write)

    async def claim_adjustment_notice(self, context: Context, promise_id: str) -> dict | None:
        """发送前原子占位；崩溃留下 sending，重启不盲目重复追问。"""
        await self.ensure()
        now = self.store.clock()

        def write(db):
            def mutate():
                row = db.execute("SELECT * FROM promises WHERE promise_id=?", (promise_id,)).fetchone()
                if (not row or row["scope_key"] != context.scope_key
                        or row["handoff_account_key"] not in ("", context.account_key)
                        or row["generation"] != self.store._generation(db, context)
                        or row["status"] not in ("waiting", "unknown")
                        or row["last_error"] not in NOTICE_KINDS
                        or row["adjustment_notice_state"] not in ("", "rejected")
                        or row["adjustment_notice_attempt"] >= 3
                        or row["adjustment_notice_retry_at"] > now):
                    return None
                db.execute(
                    """UPDATE promises SET adjustment_notice_state='sending',
                       adjustment_notice_attempt=adjustment_notice_attempt+1
                       WHERE promise_id=?""", (promise_id,))
                return {**dict(row), "adjustment_notice_attempt": row["adjustment_notice_attempt"] + 1}
            return self.store._transaction(db, mutate)
        return await self.store._run(write)

    async def defer_adjustment_notice(self, promise_id: str, retry_at: float) -> None:
        """暂时不能通知时让出扫描位置，不消耗发送次数，也不阻塞其它会话。"""
        await self.ensure()
        await self.store._run(lambda db: db.execute(
            """UPDATE promises SET adjustment_notice_retry_at=?
               WHERE promise_id=? AND status IN ('waiting','unknown')
               AND adjustment_notice_state IN ('','rejected')""", (retry_at, promise_id)))

    async def finish_adjustment_notice(self, promise_id: str, attempt: int, *,
                                       payload: str, state: str, retry_at: float = 0) -> bool:
        await self.ensure()
        if state not in ("sent", "rejected", "unknown"):
            raise ValueError("invalid_adjustment_notice_state")

        def write(db):
            changed = db.execute(
                """UPDATE promises SET adjustment_notice_state=?,adjustment_notice_retry_at=?
                   WHERE promise_id=? AND status IN ('waiting','unknown')
                   AND adjustment_notice_state='sending' AND adjustment_notice_attempt=?
                   AND action_result_json=?""",
                (state, retry_at, promise_id, attempt, payload))
            return changed.rowcount == 1
        return await self.store._run(write)

    async def delegate(self, promise_id: str, job_id: str) -> bool:
        """宿主接管是独立终态，不能冒充本插件已发送。"""
        await self.ensure()

        def write(db):
            changed = db.execute(
                """UPDATE promises SET status='delegated', host_job_id=?, updated_at=?
                   WHERE promise_id=? AND status IN ('scheduled','running')
                     AND action_state=''""",
                (str(job_id), self.store.clock(), promise_id))
            return changed.rowcount == 1

        return await self.store._run(write)

    async def cancel(self, promise_id: str) -> dict[str, Any]:
        return await self.cancel_many([promise_id])

    async def cancel_many(self, promise_ids, *, context: Context | None = None) -> dict[str, Any]:
        """取消后续履行，保留请求与副作用记录；执行中的任务仍不可取消。"""
        await self.ensure()
        ids = list(dict.fromkeys(promise_ids))
        now = self.store.clock()

        def write(db):
            def mutate():
                if not ids:
                    return {"status": "missing"}
                for pid in ids:
                    row = db.execute("SELECT * FROM promises WHERE promise_id=?", (pid,)).fetchone()
                    if not row:
                        return {"status": "missing"}
                    if context and (row["scope_key"] != context.scope_key
                                    or row["handoff_account_key"] not in ("", context.account_key)
                                    or row["generation"] != self.store._generation(db, context)):
                        return {"status": "conflict"}
                    if row["status"] not in ("scheduled", "awaiting", "waiting", "unknown"):
                        return {"status": "conflict"}
                for pid in ids:
                    db.execute("UPDATE promises SET status='cancelled',updated_at=? "
                               "WHERE promise_id=?", (now, pid))
                return {"status": "ok", "count": len(ids)}
            return self.store._transaction(db, mutate)
        return await self.store._run(write)

    async def recent_exchanges(self, scope_key: str, *,
                               limit: int = 8) -> list[dict[str, Any]]:
        """最近几轮对话（双方），给承诺概要提供素材。

        `body_window` 里存的就是双方已确认的正文，按 seq 倒序取再翻正，
        保证摘要是「先说后说」的自然顺序。跨重启也在库里，不依赖内存。
        """
        await self.ensure()
        key = str(scope_key or "")
        if not key:
            return []

        def read(db):
            rows = db.execute(
                """SELECT e.actor_role,e.event_type,w.body,w.occurred_at
                   FROM body_window w JOIN events e ON e.seq=w.seq
                   WHERE w.scope_key=? ORDER BY w.seq DESC LIMIT ?""",
                (key, max(1, min(20, int(limit))))).fetchall()
            return [dict(row) for row in reversed(rows)]

        try:
            return await self.store._run(read)
        except Exception:
            # 摘要是增强项，读不到就退化成只用本轮两句话。
            return []

    async def set_delivery(self, promise_id: str, text: str) -> None:
        """记下真正发出去的文本；失败不影响发送结果。"""
        await self.ensure()
        now = self.store.clock()

        def write(db):
            db.execute(
                "UPDATE promises SET delivered_text=?, updated_at=? WHERE promise_id=?",
                (str(text or "")[:4000], now, promise_id))

        try:
            await self.store._run(write)
        except Exception:
            pass

    async def put_trace(self, *, scope_key: str, promise_id: str, kind: str,
                        summary: str = "", materials=(), reply_text: str = "",
                        ttl_seconds: float = 86400.0) -> None:
        """写一条短时记忆片段；同 (承诺, 类型) 覆盖，不堆积。"""
        await self.ensure()
        now = self.store.clock()
        trace_id = f"{promise_id}:{kind}"
        payload = json.dumps(list(materials or ()), ensure_ascii=False)[:16000]

        def write(db):
            db.execute(
                """INSERT INTO promise_traces(trace_id,scope_key,promise_id,kind,summary,
                   materials_json,reply_text,created_at,expires_at)
                   VALUES(?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(trace_id) DO UPDATE SET
                     summary=excluded.summary, materials_json=excluded.materials_json,
                     reply_text=excluded.reply_text, created_at=excluded.created_at,
                     expires_at=excluded.expires_at""",
                (trace_id, scope_key, promise_id, kind, str(summary or "")[:1200],
                 payload, str(reply_text or "")[:4000], now,
                 now + max(60.0, float(ttl_seconds))))

        try:
            await self.store._run(write)
        except Exception:
            pass

    async def latest_trace(self, scope_key: str, now: float, *,
                           promise_id: str = "") -> dict[str, Any] | None:
        """取当前仍有效、最近的一条片段；过期的当不存在。"""
        await self.ensure()
        key = str(scope_key or "")
        if not key:
            return None

        def read(db):
            sql = ("SELECT trace_id,scope_key,promise_id,kind,summary,materials_json,"
                   "reply_text,created_at,expires_at FROM promise_traces "
                   "WHERE scope_key=? AND expires_at>?")
            args: list[Any] = [key, float(now)]
            if promise_id:
                sql += " AND promise_id=?"
                args.append(str(promise_id))
            sql += " ORDER BY created_at DESC LIMIT 1"
            row = db.execute(sql, args).fetchone()
            if not row:
                return None
            value = dict(row)
            try:
                value["materials"] = json.loads(value.pop("materials_json") or "[]")
            except Exception:
                value["materials"] = []
                value.pop("materials_json", None)
            return value

        try:
            return await self.store._run(read)
        except Exception:
            return None

    async def purge_traces(self, now: float) -> int:
        """释放过期片段；TTL 到期后追问回到正常向量检索。"""
        await self.ensure()

        def write(db):
            return db.execute(
                "DELETE FROM promise_traces WHERE expires_at<=?", (float(now),)).rowcount

        try:
            return int(await self.store._run(write))
        except Exception:
            return 0

    async def purge(self, *, keep: int = 200) -> int:
        """只留最近的若干条，其余直接删掉；不保留历史也不分页。"""
        await self.ensure()

        def write(db):
            def mutate():
                stale = db.execute(
                    """SELECT promise_id FROM promises WHERE handoff_key='' AND status IN ('sent','failed','cancelled','delegated')
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


# 确切延后：「2分钟」「10分钟后」「90秒」「1小时」。
# 用户既然给了数字，落点就必须是这个数字；语义档的随机区间只在没给数字时兜底。
EXACT_DELAY = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*(秒钟|秒|分钟|分|小时|钟头|sec|min|hr|s|m|h)"
    r"(?:后|之后|以后|内)?\s*$", re.IGNORECASE)
# 「半小时」不带数字，单独认一下；否则会被当成语义档随机到二十几分钟。
EXACT_HALF = re.compile(r"^\s*半\s*个?\s*(?:小时|钟头|h|hr)\s*(?:后|之后|以后)?\s*$",
                        re.IGNORECASE)
EXACT_UNIT = {
    "秒钟": 1, "秒": 1, "s": 1, "sec": 1,
    "分钟": 60, "分": 60, "m": 60, "min": 60,
    "小时": 3600, "钟头": 3600, "h": 3600, "hr": 3600,
}


def parse_bucket(bucket: str, now: float, timezone: str = "Asia/Shanghai") -> float:
    """把语义档换算成时间点。档位由模型给，落点由本地时钟算。"""
    import random
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(timezone or "Asia/Shanghai")
    current = datetime.fromtimestamp(now, tz)
    name = str(bucket or "一会儿").strip()

    if EXACT_HALF.match(name):
        return now + 1800
    exact = EXACT_DELAY.match(name)
    if exact:
        return now + float(exact.group(1)) * EXACT_UNIT[exact.group(2).lower()]

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
    name = str(bucket or "").strip()
    if EXACT_HALF.match(name):
        return "30 分钟后"
    exact = EXACT_DELAY.match(name)
    if exact:
        total = int(round(float(exact.group(1)) * EXACT_UNIT[exact.group(2).lower()]))
        if total < 60:
            return "%d 秒后" % total
        if total < 3600:
            return ("%d 分钟后" % (total // 60) if total % 60 == 0
                    else "%d 分 %d 秒后" % (total // 60, total % 60))
        return ("%d 小时后" % (total // 3600) if total % 3600 == 0
                else "%d 小时 %d 分后" % (total // 3600, total % 3600 // 60))
    return {"马上": "几分钟内", "now": "几分钟内", "一会儿": "过一会儿", "soon": "过一会儿",
            "待会": "等会儿", "later": "等会儿", "今晚": "今晚", "tonight": "今晚",
            "明天": "明天", "tomorrow": "明天", "过几天": "过几天",
            "later_days": "过几天"}.get(str(bucket or ""), "过一会儿")


__all__ = [
    "ACTIVE", "PromiseStore", "SCHEMA", "TRANSITIONS",
    "bucket_label", "fingerprint", "normalize", "parse_bucket",
]
