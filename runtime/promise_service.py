"""承诺的识别 落库 执行与取消。

检测点固定在 after_message_sent：消息没发出去就绝不建任务，
避免“用户没看见那句话 任务却排上了”的幽灵任务。
"""

from __future__ import annotations

import logging
import re
import time

from ..contracts import Context
from ..storage.promise_store import (
    PromiseStore, bucket_label, fingerprint, parse_bucket,
)

logger = logging.getLogger("astrbot_plugin_livingemotion.promise")

# 模型在回复末尾附带的指令；装饰阶段剔除，用户永远看不到。
MARK = re.compile(r"<!--\s*promise\s*:\s*([^:：|]{1,12})\s*[:：|]\s*([^>\n]{1,300}?)\s*-->")
# 取消指令：可以带短编号，也可以只给关键词，由插件负责对上号。
CANCEL = re.compile(r"<!--\s*promise-cancel\s*:\s*([^>\n]{0,120}?)\s*-->")
MAX_ACTIVE = 3
MAX_DEPTH = 3
MAX_ADVANCE = 3
# 发不出去时的重试：每次推后 5 分钟，最多 3 次，之后才落 failed。
RETRY_BACKOFF = 300.0
MAX_RETRY = 3
# 会话不在内存时多久再试。用户一说话 source 就回来，所以不必等太久。
CONTEXT_WAIT = 60.0


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

    async def heal(self) -> int:
        """把卡在 running/unknown 的行拉回队列。

        这两种状态没人再扫：move 的目标集里没有它们往回走的路。
        进程被 kill、上游超时、宿主导回 unknown 都会留在这里。
        启动时跑一次，之后每轮 tick 也顺手跑，成本是一次 UPDATE。
        """
        await self.promises.ensure()

        def read(db):
            return [row["promise_id"] for row in db.execute(
                "SELECT promise_id FROM promises WHERE status IN ('running','unknown')")]

        try:
            stuck = await self.store._run(read)
        except Exception:
            return 0
        healed = 0
        for promise_id in stuck:
            outcome = await self.promises.reclaim(promise_id)
            if outcome.get("status") == "ok":
                healed += 1
        if healed:
            logger.warning("[LE-promise] 自愈 %d 条卡死承诺", healed)
        return healed

    async def run_due(self, now: float | None = None, *, limit: int = 4) -> int:
        """到点就跑。返回成功发出的条数。"""
        await self.heal()
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
        context = self._live_context(row)
        if context is None:
            # 分两种“找不到”：会话只是暂时不在内存（重启后还没收到消息、
            # 或超出 128 条被挤出）——推后重试即可；会话在库里都不存在了
            # ——那这条承诺永远发不出去，再等也没用，直接判死。
            # 不区分的话，孤儿承诺会每 60 秒 defer 一次，日志永远刷。
            if not await self._scope_known(row.get("scope_key")):
                await self.promises.cancel(promise_id)
                logger.warning("[LE-promise] 会话已不存在 放弃承诺 %s scope=%s",
                               promise_id[:8], str(row.get("scope_key") or "")[:12])
                return False
            # 这不是“永久失败”——用户一说话 source 就回来了。推后重试，
            # 而不是把承诺判死。耗尽重试次数才落 failed。
            outcome = await self.promises.defer(
                promise_id, retry_at=self.store.clock() + CONTEXT_WAIT,
                error="context_unavailable", no_penalty=True)
            logger.warning("[LE-promise] 会话不在内存 推迟承诺 %s -> %s",
                           promise_id[:8], outcome.get("status"))
            return False
        moved = await self.promises.move(promise_id, status="running", expect=("scheduled",))
        if moved.get("status") != "ok":
            return False
        try:
            text = await self._compose(context, row)
        except Exception as exc:
            await self.promises.defer(promise_id, retry_at=self.store.clock() + RETRY_BACKOFF,
                                      error=f"compose:{type(exc).__name__}", max_retry=MAX_RETRY)
            return False
        if not text:
            await self.promises.defer(promise_id, retry_at=self.store.clock() + RETRY_BACKOFF,
                                      error="empty", max_retry=MAX_RETRY)
            return False
        if not await self.promises.advance_quota_block(context, self.store.clock()):
            # 配额不足要等到明天，直接推后一天。
            await self.promises.defer(promise_id, retry_at=self.store.clock() + 86400,
                                      error="quota", max_retry=MAX_RETRY)
            return False
        result = await self.app.send_promise_notice(context, text, "promise:" + promise_id)
        if result in ("confirmed", "sent"):
            await self.promises.move(promise_id, status="sent", expect=("running",))
            logger.warning("[LE-promise] 承诺已发出 %s", promise_id[:8])
            return True
        if result in ("rejected", "unknown"):
            # 这两类是“现在发不出去但还有救”：可能撞冷却、可能上下文变了。
            # 绝不能留 running/unknown 这种没人再扫的状态。
            await self.promises.defer(promise_id, retry_at=self.store.clock() + RETRY_BACKOFF,
                                      error=str(result), max_retry=MAX_RETRY)
            logger.warning("[LE-promise] 承诺发送被拒 %s -> defer(%s)",
                           promise_id[:8], result)
            return False
        await self.promises.defer(promise_id, retry_at=self.store.clock() + RETRY_BACKOFF,
                                  error=str(result), max_retry=MAX_RETRY)
        return False

    async def _scope_known(self, scope) -> bool:
        """这个 scope 在会话库里登记过吗。

        登记过 = 会话还在，只是当前没有实时事件（重启 睡眠 被挤出内存），
        等用户说话即可。查不到 = 会话被删了或换了实例，承诺无处投递。
        """
        key = str(scope or "")
        if not key:
            return False

        def read(db):
            return db.execute(
                "SELECT 1 FROM source_contexts WHERE scope_key=? LIMIT 1", (key,)).fetchone()

        try:
            return await self.store._run(read) is not None
        except Exception:
            # 查不动就别误杀，按“还在”处理。
            return True

    def _live_context(self, row: dict) -> Context | None:
        """按 scope_key 从内存里找**带发送路由**的上下文。

        落库的 context_json 一律 route=None（见 storage/sqlite.py:1120），
        所以重启后靠它永远发不出去；route 只存在于 bridge.sources 的实时
        source 上。承诺的到期距离用户上一条消息可能隔了几十分钟，
        这段时间里 source 还在（保留最近 128 个），这才是可用的那一个。
        """
        scope = str(row.get("scope_key") or "")
        if not scope:
            return None
        # 先看 bridge.sources：这里存的是真实事件解析出的 source，
        # context.route 一定非空，且和向宿主发消息用的是同一条路由。
        sources = getattr(getattr(self.app, "bridge", None), "sources", None) or {}
        for source in reversed(list(sources.values())):
            real = getattr(source, "context", None)
            if real is not None and getattr(real, "scope_key", "") == scope and real.route:
                return real
        # 再看 _contexts：同一进程内收到过消息的话，这里也是带 route 的。
        for context in reversed(list((getattr(self.app, "_contexts", {}) or {}).values())):
            if getattr(context, "scope_key", "") == scope and getattr(context, "route", None):
                return context
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
