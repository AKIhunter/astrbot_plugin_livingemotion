"""承诺的识别 落库 执行与取消。

检测点固定在 after_message_sent：消息没发出去就绝不建任务，
避免“用户没看见那句话 任务却排上了”的幽灵任务。
"""

from __future__ import annotations

import re
import time

from ..contracts import Context
from ..storage.promise_store import (
    PromiseStore, bucket_label, fingerprint, parse_bucket,
)

# 模型在回复末尾附带的指令；装饰阶段剔除，用户永远看不到。
MARK = re.compile(r"<!--\s*promise\s*:\s*([^:：|]{1,12})\s*[:：|]\s*([^>\n]{1,300}?)\s*-->")
# 取消指令：可以带短编号，也可以只给关键词，由插件负责对上号。
CANCEL = re.compile(r"<!--\s*promise-cancel\s*:\s*([^>\n]{0,120}?)\s*-->")
MAX_ACTIVE = 3
MAX_DEPTH = 3
MAX_ADVANCE = 3


def strip_marks(text: str) -> tuple[str, list[tuple[str, str]], list[str]]:
    """把回复里的指令抠掉，返回干净正文与两类指令。"""
    body = str(text or "")
    created: list[tuple[str, str]] = []
    cancels: list[str] = []
    for match in MARK.finditer(body):
        created.append((match.group(1).strip(), match.group(2).strip()))
    for match in CANCEL.finditer(body):
        cancels.append(match.group(1).strip())
    cleaned = MARK.sub("", body)
    cleaned = CANCEL.sub("", cleaned)
    # 抠掉标记后常留下行尾空白与空行，收一下。
    lines = [line.rstrip() for line in cleaned.split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines).strip(), created, cancels


class PromiseService:
    """承诺的读写入口；页面与调度器都只通过它说话。"""

    def __init__(self, store, application) -> None:
        self.store = store
        self.app = application
        self.promises = PromiseStore(store)

    # ---------- 识别 ----------

    @staticmethod
    def extract(text: str):
        return strip_marks(text)

    async def remember(self, context: Context, items) -> list[dict]:
        """把回复里的承诺指令落库。只在消息确认发出后调用。"""
        results = []
        timezone = getattr(self.app.config, "timezone", "") or "Asia/Shanghai"
        for bucket, description in items:
            if not description:
                continue
            due_at = parse_bucket(bucket, self.store.clock(), timezone)
            note = description[:400]
            result = await self.promises.create(
                context, description=description, note=note, bucket=bucket, due_at=due_at)
            results.append(result)
        return results

    # ---------- 查询 ----------

    async def active(self, context: Context) -> list[dict]:
        rows = await self.promises.list(context)
        now = self.store.clock()
        for row in rows:
            row["eta_seconds"] = max(0.0, float(row["due_at"]) - now)
            row["bucket_label"] = bucket_label(row["bucket"])
        return rows

    async def view(self, context: Context) -> dict:
        rows = await self.active(context)
        return {
            "api_version": 1,
            "enabled": bool(getattr(self.app.config, "promise_enabled", True)),
            "max_active": MAX_ACTIVE,
            "items": [{
                "promise_id": row["promise_id"],
                "description": row["description"],
                "bucket": row["bucket"],
                "bucket_label": row["bucket_label"],
                "due_at": row["due_at"],
                "eta_seconds": row["eta_seconds"],
                "status": row["status"],
                "depth": row["depth"],
                "advance_count": row["advance_count"],
                "created_at": row["created_at"],
            } for row in rows],
        }

    # ---------- 取消 ----------

    async def cancel(self, context: Context, token: str = "") -> dict:
        """按编号或关键词定位待取消的承诺；定位不到时把候选交给调用方去问。"""
        rows = await self.active(context)
        if not rows:
            return {"status": "empty", "items": []}
        token = str(token or "").strip()
        if token:
            picked = []
            number = None
            if token.isdigit():
                number = int(token)
            for index, row in enumerate(rows, start=1):
                if number is not None and index == number:
                    picked.append(row)
                    continue
                if number is None and token and token in row["description"]:
                    picked.append(row)
            if len(picked) == 1:
                result = await self.promises.cancel(picked[0]["promise_id"])
                if result.get("status") == "ok":
                    return {"status": "cancelled", "description": picked[0]["description"]}
                return {"status": "conflict", "items": rows}
            if len(picked) > 1:
                return {"status": "ambiguous", "items": picked}
            return {"status": "unmatched", "items": rows}
        if len(rows) == 1:
            result = await self.promises.cancel(rows[0]["promise_id"])
            if result.get("status") == "ok":
                return {"status": "cancelled", "description": rows[0]["description"]}
        return {"status": "ambiguous", "items": rows}

    async def cancel_all(self, context: Context) -> int:
        rows = await self.active(context)
        done = 0
        for row in rows:
            if (await self.promises.cancel(row["promise_id"])).get("status") == "ok":
                done += 1
        return done

    # ---------- 提前 ----------

    async def advance(self, context: Context, token: str = "") -> dict:
        rows = await self.active(context)
        if not rows:
            return {"status": "empty"}
        target = rows[0]
        if token.isdigit():
            index = int(token)
            if 1 <= index <= len(rows):
                target = rows[index - 1]
        elif token:
            hit = [row for row in rows if token in row["description"]]
            if len(hit) != 1:
                return {"status": "ambiguous", "items": rows}
            target = hit[0]
        timezone = getattr(self.app.config, "timezone", "") or "Asia/Shanghai"
        due_at = parse_bucket("马上", self.store.clock(), timezone)
        if not await self.promises.advance_quota_block(context, due_at):
            return {"status": "quota_blocked", "description": target["description"]}
        result = await self.promises.reschedule(target["promise_id"], due_at=due_at, bucket="马上",
                                                max_advance=MAX_ADVANCE)
        if result.get("status") == "ok":
            return {"status": "advanced", "description": target["description"]}
        return {"status": result.get("status", "failed"), "description": target["description"]}

    # ---------- 到期执行 ----------

    async def run_due(self, now: float | None = None, *, limit: int = 4) -> int:
        """到点就跑。返回成功发出的条数。"""
        moment = self.store.clock() if now is None else float(now)
        rows = await self.promises.due(now=moment, limit=limit)
        sent = 0
        for row in rows:
            if await self._deliver(row):
                sent += 1
        if sent:
            await self.promises.purge(keep=200)
        return sent

    async def _deliver(self, row: dict) -> bool:
        promise_id = row["promise_id"]
        context = self._context_for(row)
        if context is None:
            context = await self.restore_context(row)
        if context is None:
            # 找不到会话就留着等下一轮，别把承诺判死。
            await self.promises.move(promise_id, status="failed", error="context_missing")
            return False
        moved = await self.promises.move(promise_id, status="running", expect=("scheduled",))
        if moved.get("status") != "ok":
            return False
        try:
            text = await self._compose(context, row)
        except Exception as exc:
            await self.promises.move(promise_id, status="failed", error=f"{type(exc).__name__}")
            return False
        if not text:
            await self.promises.move(promise_id, status="failed", error="empty")
            return False
        if not await self.promises.advance_quota_block(context, self.store.clock()):
            await self.promises.move(promise_id, status="failed", error="quota")
            return False
        result = await self.app.send_promise_notice(context, text, "promise:" + promise_id)
        if result in ("confirmed", "sent"):
            await self.promises.move(promise_id, status="sent", expect=("running",))
            return True
        await self.promises.move(promise_id, status="unknown", expect=("running",), error=str(result))
        return False

    def _context_for(self, row: dict) -> Context | None:
        """把落库的 scope 还原成可发送的会话上下文。

        重启后 _contexts 可能还没填满，这时不能直接判死；
        按落库的 scope 反查 store 里登记过的会话。
        """
        scope = str(row.get("scope_key") or "")
        if not scope:
            return None
        for context in list((getattr(self.app, "_contexts", {}) or {}).values()):
            if getattr(context, "scope_key", "") == scope:
                return context
        return None

    async def restore_context(self, row: dict):
        """兜底：从持久化的会话表里把上下文补回内存，再发给它。"""
        scope = str(row.get("scope_key") or "")
        contexts = getattr(self.app, "_contexts", None)
        if not scope or contexts is None:
            return None
        try:
            for context in await self.store.list_contexts():
                if getattr(context, "scope_key", "") == scope:
                    contexts[context.account_key] = context
                    return context
        except Exception:
            return None
        return None

    async def _compose(self, context: Context, row: dict) -> str:
        """兑现内容要真说话，这里才走模型。"""
        from .promise_notice import strip_stops

        description = row["description"]
        try:
            reply = await self.app.compose_promise(context, description, row["note"])
        except Exception:
            reply = ""
        if reply:
            return strip_stops(reply).strip()
        # 模型不可用时不留空，用固定句式保底，至少把话说出去。
        return strip_stops(f"之前说好的 {description} 现在给你").strip()


def register(store, application) -> PromiseService:
    service = PromiseService(store, application)
    application.promises = service
    return service


__all__ = ["CANCEL", "MARK", "MAX_ACTIVE", "MAX_DEPTH", "PromiseService",
           "register", "strip_marks"]
