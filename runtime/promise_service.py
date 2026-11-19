"""承诺的识别 落库 执行与取消。

检测点固定在 after_message_sent：消息没发出去就绝不建任务，
避免“用户没看见那句话 任务却排上了”的幽灵任务。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time

from dataclasses import replace

from ..contracts import Context, rebuild_route, stable_key
from ..storage.promise_store import (
    PromiseStore, bucket_label, fingerprint, parse_bucket,
)

logger = logging.getLogger("astrbot_plugin_livingemotion.promise")

# 模型在回复末尾附带的指令；装饰阶段剔除，用户永远看不到。
MARK = re.compile(r"<!--\s*promise\s*:\s*([^:：|]{1,12})\s*[:：|]\s*([^>\n]{1,300}?)\s*-->")
# 取消指令：可以带短编号，也可以只给关键词，由插件负责对上号。
CANCEL = re.compile(
    r"<\s*!?\s*--\s*promise-cancel(?=\s|[:：]|-->)\s*[:：]?\s*([^>\n]{0,120}?)\s*-->")
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
        from .promise_ownership import PromiseOwnership
        self.ownership = PromiseOwnership(self)
        self._run_lock = asyncio.Lock()

    # ---------- 识别 ----------

    @staticmethod
    def extract(text: str):
        return strip_marks(text)

    async def remember(self, context: Context, items, *, event=None,
                       summary: str = "", query: str = "") -> list[dict]:
        """把回复里的承诺指令落库。只在消息确认发出后调用。

        `summary` 是承诺建立时的上下文概要，`query` 是给向量检索用的锚点。
        两者都在有真实 event 的这一刻产生；等到期再想补，event 早没了。
        """
        results = []
        timezone = getattr(self.app.config, "timezone", "") or "Asia/Shanghai"
        from .promise_ownership import RECURRING
        source_id = str(getattr(getattr(event, "message_obj", None), "message_id", "") or "")
        for bucket, description in items:
            if not description:
                continue
            from .promise_actions import needs_image
            policy = getattr(self.app, "image_action_policy", None)
            if needs_image(description) and callable(policy):
                permission = await policy(context, event=event)
                if permission.get("allowed") is not True:
                    results.append({"status": "relationship_refused"})
                    continue
            if RECURRING.search(str(bucket)) or RECURRING.search(description):
                results.append({"status": "recurring_requires_future_task"})
                continue
            tool_tasks = (event.get_extra("livingemotion:future_tasks") or []) if event else []
            if len(tool_tasks) > 1:
                # 一轮已经建立多个宿主任务时，标记没有唯一归属；不能凭空双建。
                results.append({"status": "host_owned_turn"})
                continue
            due_at = parse_bucket(bucket, self.store.clock(), timezone)
            note = description[:400]
            async with self.ownership.lock:
                job_id = await self.ownership.host_match(
                    context, description, due_at, event=event)
                result = await self.promises.create(
                    context, description=description, note=note, bucket=bucket,
                    due_at=due_at, context_summary=summary, source_event_id=source_id,
                    max_active=self.max_active)
                if job_id and result.get("status") in ("created", "advanced", "duplicate"):
                    if await self.promises.delegate(result["promise_id"], job_id):
                        result = {**result, "status": "delegated", "host_job_id": job_id}
            results.append(result)
            if result.get("status") in ("created", "advanced"):
                # 召回前置：此刻还有真实事件可用，外部记忆后端只认这个。
                # 失败不该影响承诺本身，所以由应用层吞掉异常只留痕。
                hook = getattr(self.app, "prefetch_promise_memory", None)
                if callable(hook):
                    try:
                        # 这是"消息已发出"之后的收尾，不能因为记忆后端慢
                        # 把提交钩子拖住；拿不到就退化成只有概要。
                        await asyncio.wait_for(
                            hook(context, event, description=description,
                                 summary=summary, query=query,
                                 promise_id=result["promise_id"]),
                            timeout=5.0)
                    except Exception as exc:
                        logger.warning("[LE-promise] 召回前置失败 %s: %r",
                                       str(result.get("promise_id"))[:8], exc)
        return results

    # ---------- 查询 ----------

    @property
    def max_active(self) -> int:
        value = getattr(self.app.config, "promise_max_active", MAX_ACTIVE)
        return max(1, min(10, value)) if type(value) is int else MAX_ACTIVE

    async def active(self, context: Context) -> list[dict]:
        rows = await self.promises.list(context, limit=None)
        now = self.store.clock()
        for row in rows:
            row["eta_seconds"] = max(0.0, float(row["due_at"]) - now)
            row["bucket_label"] = bucket_label(row["bucket"])
            if row["status"] == "waiting":
                row["eta_seconds"] = None
                row["bucket_label"] = row["bucket"]
        return rows

    async def view(self, context: Context) -> dict:
        rows = await self.active(context)
        return {
            "api_version": 1,
            "enabled": bool(getattr(self.app.config, "promise_enabled", True)),
            "max_active": self.max_active,
            "active_count": await self.promises.count_active(context),
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
                "reason": row.get("last_error", ""),
            } for row in rows],
        }

    # ---------- 取消 ----------

    async def cancel(self, context: Context, token: str = "") -> dict:
        return await self.cancel_tokens(context, [token])

    async def cancel_tokens(self, context: Context, tokens) -> dict:
        """先定位本轮全部目标，再原子取消；歧义或状态冲突绝不部分成功。"""
        rows = await self.active(context)
        if not rows:
            return {"status": "empty", "items": []}
        selected = {}
        for value in tokens:
            parts = re.split(r"[|、,，]", str(value or "").strip())
            for part in parts:
                token = part.strip()
                if not token:
                    picked = rows if len(parts) == 1 else []
                elif token.isdigit():
                    number = int(token)
                    picked = rows[number - 1:number] if number > 0 else []
                else:
                    picked = [row for row in rows if token in row["description"]
                              or (len(token) >= 8 and row["promise_id"].startswith(token))]
                if not picked:
                    return {"status": "unmatched", "items": rows}
                if len(picked) > 1:
                    return {"status": "ambiguous", "items": picked}
                selected[picked[0]["promise_id"]] = picked[0]
        if not selected:
            return {"status": "unmatched", "items": rows}
        result = await self.promises.cancel_many(list(selected), context=context)
        if result.get("status") == "ok":
            return {"status": "cancelled", "count": len(selected),
                    "description": "、".join(row["description"] for row in selected.values())}
        return {"status": "conflict", "items": rows}

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
        # 用户要求提前就是"现在就办"：二三十秒后触发，不再走档位随机，
        # 也不查行为额度——承诺兑现本来就不占额度。
        due_at = self.store.clock() + 20
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
        # 旧版本把到点项挂成 awaiting 等下一轮回复；现在到点就发，
        # 那些遗留行没人再取，启动和每轮 tick 顺手放回队列。
        try:
            released = await self.promises.release_awaiting(self.store.clock())
            if released:
                logger.warning("[LE-promise] 放回待交付 %d 条", released)
        except Exception:
            pass

        def read(db):
            return [dict(row) for row in db.execute(
                "SELECT promise_id, status, action_state, action_result_json FROM promises "
                "WHERE status IN ('running','unknown')")]

        try:
            stuck = await self.store._run(read)
        except Exception:
            return 0
        healed = 0
        for row in stuck:
            promise_id = row["promise_id"]
            try:
                external = json.loads(row["action_result_json"] or "{}").get("external_image") is True
            except (ValueError, TypeError):
                external = False
            if external:
                # 普通图片由 LH 保存真实结果；tick 不能抢回执行或触发重复收费。
                continue
            if row["action_state"] in ("generating", "sending", "unknown"):
                if row["status"] == "running":
                    await self.promises.move(
                        promise_id, status="unknown", expect=("running",),
                        error="action_interrupted")
                    logger.warning("[LE-promise] 动作中断 需核对 %s phase=%s",
                                   promise_id[:8], row["action_state"])
                continue
            outcome = await self.promises.reclaim(promise_id)
            if outcome.get("status") == "ok":
                healed += 1
        if healed:
            logger.warning("[LE-promise] 自愈 %d 条卡死承诺", healed)
        return healed

    async def run_due(self, now: float | None = None, *, limit: int = 4) -> int:
        """到点就跑。返回成功发出的条数。"""
        if self._run_lock.locked():
            return 0
        async with self._run_lock:
            return await self._run_due(now, limit=limit)

    async def _run_due(self, now: float | None, *, limit: int) -> int:
        await self.heal()
        moment = self.store.clock() if now is None else float(now)
        if not self.app.promise_actions_active():
            # 并轨被关掉：先前挂起等回复的承诺不会有人来取，放回队列单独发。
            released = await self.promises.release_awaiting(moment)
            if released:
                logger.warning("[LE-promise] 并轨已关闭 放回队列 %d 条", released)
        rows = await self.promises.due(now=moment, limit=limit)
        sent = 0
        for row in rows:
            if await self._deliver(row):
                sent += 1
        # waiting 不执行生图；只补一次调整追问，包含升级前已有的暂停任务。
        for row in await self.promises.pending_adjustment_notices(now=moment, limit=limit):
            await self._ask_adjustment(row)
        if sent:
            await self.promises.purge(keep=200)
        # 片段缓存到期即释放：追问回到正常向量检索，不长期占着语境。
        try:
            await self.promises.purge_traces(moment)
        except Exception:
            pass
        return sent

    async def take_awaiting(self, context: Context) -> list[dict]:
        """本轮需要顺带交付的承诺（耦合生效时才会有）。"""
        if not self.app.promise_actions_active():
            return []
        return await self.promises.take_awaiting(scope_key=context.scope_key)

    async def mark_delivered(self, promise_id: str) -> None:
        """并入回复后落 sent：这条不再由调度器处理。"""
        await self.promises.move(promise_id, status="sent", expect=("awaiting",))

    async def mark_delivered_many(self, promise_ids) -> list:
        """批量落 sent，返回真正写成功的 id。

        逐条处理而不是一条 SQL 全改：单条被取消/已是终态时不该连累其它条目。
        """
        done = []
        for promise_id in promise_ids or ():
            try:
                outcome = await self.promises.move(
                    str(promise_id), status="sent", expect=("awaiting",))
            except Exception as exc:
                logger.warning("[LE-promise] 交付落库失败 %s: %r",
                               str(promise_id)[:8], exc)
                continue
            if str(outcome.get("status")) == "ok":
                done.append(str(promise_id))
            else:
                logger.warning("[LE-promise] 交付落库被拒 %s -> %s",
                               str(promise_id)[:8], outcome)
        return done

    async def _deliver(self, row: dict) -> bool:
        promise_id = row["promise_id"]
        # 到点就是到点了：这里必须自己把消息发出去。
        # 曾经为了躲开「和被动回复内容重合」改成 awaiting + 并进下一轮，
        # 结果是用户不开口就永远不提醒（实测 2 分钟的浇水提醒卡了一晚上）。
        # 并轨只适用于"正好在生成回复"的场景，而到点触发时没有正在进行的回复。
        context = await self._live_context(row)
        if context is None:
            # 分两种“找不到”：会话只是暂时不在内存（重启后还没收到消息、
            # 或超出 128 条被挤出）——推后重试即可；会话在库里都不存在了
            # ——那这条承诺永远发不出去，再等也没用，直接判死。
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
        # 和 future_task 写入共用锁；宿主先接管就不抢执行，LE 先运行就不再双建。
        async with self.ownership.lock:
            try:
                job_id = await self.ownership.host_match(
                    context, row["description"], float(row["original_due_at"]))
            except Exception:
                await self.promises.defer(
                    promise_id, retry_at=self.store.clock() + CONTEXT_WAIT,
                    error="host_task_lookup_failed", no_penalty=True)
                return False
            if job_id and not row.get("action_state"):
                await self.promises.delegate(promise_id, job_id)
                return False
            moved = await self.promises.move(
                promise_id, status="running", expect=("scheduled",))
        if moved.get("status") != "ok":
            return False
        from .promise_actions import DEADLINE_SECONDS, ImagePromiseAction, needs_image
        if needs_image(row["description"]):
            try:
                outcome = await asyncio.wait_for(
                    ImagePromiseAction(self).run(context, row), DEADLINE_SECONDS)
            except Exception as exc:
                current = await self.promises.get(promise_id) or {}
                phase = current.get("action_state")
                outcome = {"status": "unknown" if phase in (
                    "generating", "sending", "unknown") else "unavailable"}
                if phase == "sent":
                    outcome = {"status": "sent", "text": current.get("delivered_text") or "图片已发送"}
                logger.warning("[LE-promise] 图片执行异常 %s phase=%s type=%s",
                               promise_id[:8], phase, type(exc).__name__)
            status = outcome.get("status")
            if status == "sent":
                text = str(outcome.get("text") or "图片已发送")
                await self.promises.move(promise_id, status="sent", expect=("running",))
                await self.promises.set_delivery(promise_id, text)
                await self.promises.put_trace(
                    scope_key=context.scope_key, promise_id=promise_id, kind="delivery",
                    summary=str(row.get("context_summary") or ""),
                    reply_text=text, ttl_seconds=self._trace_ttl())
                logger.warning("[LE-promise] 图片已提交 %s", promise_id[:8])
                return True
            if status == "unknown":
                current = await self.promises.get(promise_id) or {}
                try:
                    artifact = json.loads(current.get("action_result_json") or "{}")
                except (ValueError, TypeError):
                    artifact = {}
                await self.promises.checkpoint_action(promise_id, "unknown", artifact)
                await self.promises.move(promise_id, status="unknown", expect=("running",),
                                         error="image_action_unknown")
                return False
            if status == "waiting":
                await self.promises.move(
                    promise_id, status="waiting", expect=("running",),
                    error=str(outcome.get("reason") or "image_result_unknown"))
                if outcome.get("reason") in {"content_rejected", "prompt_too_long", "prompt_adjustment_required"}:
                    current = await self.promises.get(promise_id)
                    if current and current["status"] == "waiting":
                        await self._ask_adjustment(current)
                return False
            await self.promises.defer(
                promise_id, retry_at=self.store.clock() + RETRY_BACKOFF,
                error="image_" + str(status), max_retry=MAX_RETRY)
            return False
        try:
            composed = await self._compose(context, row)
        except Exception as exc:
            await self.promises.defer(promise_id, retry_at=self.store.clock() + RETRY_BACKOFF,
                                      error=f"compose:{type(exc).__name__}", max_retry=MAX_RETRY)
            return False
        text = str((composed or {}).get("text") or "").strip()
        if not text:
            await self.promises.defer(promise_id, retry_at=self.store.clock() + RETRY_BACKOFF,
                                      error="empty", max_retry=MAX_RETRY)
            return False
        # 承诺兑现不占主动行为额度：这是用户点名要的东西，不是机器人想说话。
        # 占额度会导致"聊得多的日子，答应的事直接发不出来"。
        # intent_id 是 intents 表主键，create_intent 走 INSERT OR IGNORE。
        # 同一条承诺第二次尝试若还沿用 "promise:<id>"，就会撞上第一次失败
        # 留下的行 → duplicate → _control 只在旧行是 succeeded 时才认，
        # 于是永远 unknown。一条有失败前科的承诺就再也发不出去。
        attempt = int(row.get("retry_count") or 0)
        result = await self.app.send_promise_notice(
            context, text, "promise:" + promise_id + ("#%d" % attempt if attempt else ""),
            keep_stops=True)
        if result in ("confirmed", "sent"):
            await self.promises.move(promise_id, status="sent", expect=("running",))
            # 兑现文本与当时召回到的材料一起留一天：用户接下来追问「你刚发的那张」
            # 「前几天说的那个」时直接命中，不必再跑一次向量检索。
            await self.promises.set_delivery(promise_id, text)
            await self.promises.put_trace(
                scope_key=str(row.get("scope_key") or ""), promise_id=promise_id,
                kind="delivery",
                summary=str((composed or {}).get("summary") or row.get("context_summary") or ""),
                materials=(composed or {}).get("materials") or (),
                reply_text=text, ttl_seconds=self._trace_ttl())
            logger.warning("[LE-promise] 承诺已发出 %s 气泡=%d",
                           promise_id[:8], len([p for p in text.split("\n") if p.strip()]))
            return True
        if result in ("rejected", "unknown"):
            # 这两类是“现在发不出去但还有救”：可能撞冷却、可能上下文变了。
            # 绝不能留 running/unknown 这种没人再扫的状态。
            retry_at, penalty = self.store.clock() + RETRY_BACKOFF, True
            # 夜里被静默拦下不算失败：推到醒来再看，别把重试次数烧光，
            # 否则一个跨夜的承诺第二天只会剩一条 failed。
            try:
                night = await self.app.night_snapshot(context)
                if (night.display_state or night.phase).value == "deep_sleep":
                    retry_at = max(night.wake_window_deadline or 0,
                                   self.store.clock() + 3600)
                    penalty = False
            except Exception:
                pass
            await self.promises.defer(promise_id, retry_at=retry_at,
                                      error=str(result), max_retry=MAX_RETRY,
                                      no_penalty=penalty)
            logger.warning("[LE-promise] 承诺发送被拒 %s -> defer(%s)",
                           promise_id[:8], result)
            return False
        await self.promises.defer(promise_id, retry_at=self.store.clock() + RETRY_BACKOFF,
                                  error=str(result), max_retry=MAX_RETRY)
        return False

    async def _scope_known(self, scope) -> bool:
        """这个 scope 在会话库里登记过吗。

        登记过 = 会话还在，只是当前没有实时事件（重启/睡眠/被挤出内存），
        等用户说话即可。查不到 = 会话被删或换了实例，承诺无处投递。
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

    async def _ask_adjustment(self, row: dict) -> None:
        context = await self._live_context(row)
        if context is None or not await self.app._preparation_guard(
                context, int(row.get("generation") or 0), self.app.revision, delivery=True):
            await self.promises.defer_adjustment_notice(
                row["promise_id"], self.store.clock() + CONTEXT_WAIT)
            return
        claimed = await self.promises.claim_adjustment_notice(context, row["promise_id"])
        if claimed is None:
            await self.promises.defer_adjustment_notice(
                row["promise_id"], self.store.clock() + CONTEXT_WAIT)
            return
        attempt = claimed["adjustment_notice_attempt"]
        pid = claimed["promise_id"]
        payload = claimed.get("action_result_json") or "{}"
        artifact = json.loads(payload)
        key = stable_key("promise-adjustment", pid, artifact.get("request_id"), artifact.get("prompt"))

        async def still_waiting():
            current = await self.promises.get(pid) or {}
            return (current.get("status") == "waiting"
                    and current.get("adjustment_notice_state") == "sending"
                    and current.get("adjustment_notice_attempt") == attempt
                    and current.get("action_result_json") == payload)

        # 只说用户听得懂的情况；编号、执行状态和上游正文留在内部。
        if artifact.get("notice"):
            text = str(artifact["notice"])[:200] + "你想调整一下，还是这次就算了？"
        elif int(artifact.get("adjustment_round") or 0) > 0:
            text = ("按你刚才改的想法又试了一下，还是没能弄好，有些内容我暂时做不了。"
                    "我先停在这里。你想再调整一下，还是这次就算了？")
        else:
            text = ("这张没能弄好，有些内容我暂时做不了。"
                    "你想换个人物、场景或风格再试试，还是这次就算了？")
        if context.scene_kind.value == "group":
            text = f"@{context.account_id} " + text
        try:
            result = await self.app.send_promise_notice(
                context, text, key + f":{attempt}", keep_stops=True, authorize=still_waiting)
        except asyncio.CancelledError:
            await asyncio.shield(self.promises.finish_adjustment_notice(
                pid, attempt, payload=payload, state="unknown"))
            raise
        except Exception:
            result = "unknown"
        # failed 可能是回执落库异常；只有明确 rejected 才能换尝试 ID 重发。
        state = "sent" if result in ("confirmed", "sent") else (
            "rejected" if result == "rejected" else "unknown")
        await self.promises.finish_adjustment_notice(
            pid, attempt, payload=payload, state=state,
            retry_at=self.store.clock() + RETRY_BACKOFF)
        logger.warning("[LE-promise] 调整追问 %s result=%s", pid[:8], state)

    async def _live_context(self, row: dict) -> Context | None:
        """按 scope_key 从内存里找**带发送路由**的上下文。

        落库的 context_json 一律 route=None（见 storage/sqlite.py:1120），
        所以重启后靠它永远发不出去；route 只存在于 bridge.sources 的实时
        source 上。承诺的到期距离用户上一条消息可能隔了几十分钟，
        这段时间里 source 还在（保留最近 128 个），这才是可用的那一个。
        """
        scope = str(row.get("scope_key") or "")
        account = str(row.get("handoff_account_key") or "")
        if not scope:
            return None
        # 先看 bridge.sources：这里存的是真实事件解析出的 source，
        # context.route 一定非空，且和向宿主发消息用的是同一条路由。
        sources = getattr(getattr(self.app, "bridge", None), "sources", None) or {}
        for source in reversed(list(sources.values())):
            real = getattr(source, "context", None)
            if (real is not None and getattr(real, "scope_key", "") == scope and real.route
                    and (not account or real.account_key == account)):
                return real
        # 再看 _contexts：同一进程内收到过消息的话，这里也是带 route 的。
        for context in reversed(list((getattr(self.app, "_contexts", {}) or {}).values())):
            if (getattr(context, "scope_key", "") == scope and getattr(context, "route", None)
                    and (not account or context.account_key == account)):
                return context
        # 最后从会话表还原，并把 route 按宿主规则重建。
        # 重启后 sources 与 _contexts 都空，但 source_contexts 里
        # adapter_id / scene_kind / scene_id 三样都在，route 是它们的纯函数：
        #   f"{adapter_id}:{FriendMessage|GroupMessage}:{scene_id}"
        # 这是“用户没先说话也能把承诺送出去”的那把钥匙。
        try:
            for stored in await self.store.list_contexts():
                if getattr(stored, "scope_key", "") != scope:
                    continue
                if account and stored.account_key != account:
                    continue
                route = self._rebuild_route(stored)
                if route:
                    return replace(stored, route=route)
        except Exception as exc:
            logger.warning("[LE-promise] 会话表还原失败 %r", exc)
        return None

    @staticmethod
    def _rebuild_route(context) -> str:
        return rebuild_route(context)

    async def _compose(self, context: Context, row: dict) -> dict:
        """兑现内容要真说话，这里才走模型。

        返回值带 `materials`：到点生成时用到的召回材料，兑现后原样写进
        片段缓存，追问时就不必重新检索。
        """
        from .promise_notice import clean_delivery, strip_stops

        description = row["description"]
        summary = str(row.get("context_summary") or "")
        materials: list = []
        try:
            reply, materials = await self.app.compose_promise(context, row)
        except Exception as exc:
            logger.warning("[LE-promise] 兑现文案模型失败 %s: %r",
                           str(row.get("promise_id") or "")[:8], exc)
            reply = ""
        if reply:
            body = clean_delivery(reply)
            if body:
                return {"text": body, "materials": materials, "summary": summary}
        # 模型不可用时不留空。提醒类不能套「现在给你」——那是交付东西的说法，
        # 用在「提醒给花浇水」上就成了病句。
        import re as _re
        body = _re.sub(r"^\s*\d+\s*(?:分钟|分|小时|秒)\s*(?:后|之后|以后)?\s*[，,]?\s*",
                       "", str(description or "")).strip() or str(description or "").strip()
        if body.startswith(("提醒", "记得", "别忘了")):
            text = strip_stops(f"到点了 {body}").strip()
        else:
            text = strip_stops(f"之前说好的 {body} 现在给你").strip()
        return {"text": text, "materials": [], "summary": summary}

    def _trace_ttl(self) -> float:
        hours = getattr(self.app.config, "promise_trace_ttl_hours", 24)
        try:
            return max(1.0, min(168.0, float(hours))) * 3600.0
        except (TypeError, ValueError):
            return 86400.0


def register(store, application) -> PromiseService:
    service = PromiseService(store, application)
    application.promises = service
    return service


__all__ = ["CANCEL", "MARK", "MAX_ACTIVE", "MAX_DEPTH", "PromiseService",
           "register", "strip_marks"]
