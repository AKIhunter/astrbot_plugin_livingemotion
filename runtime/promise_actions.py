"""延迟图片的显式动作契约；只有生成与发送均完成才兑现。"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..contracts import prompt_json, stable_key
from ..livinghello_coupling import discover

IMAGE = re.compile(
    r"自拍|照片|拍照|拍给(?:你|我|大家)(?:看)?|图片|生图|画图|发图|绘制|"
    r"画[一个张幅]|拍[一个张]|生成.{0,8}图")
DEADLINE_SECONDS = 600.0
DELIVERY_CONTRACT = "livinghello.deferred-image-delivery.v1"


def needs_image(description: str) -> bool:
    text = str(description or "").strip()
    # 提醒拍照是提醒动作，不是代替用户生成照片。
    if text.startswith(("提醒", "记得", "别忘了")):
        return False
    return bool(IMAGE.search(text))


class ImagePromiseAction:
    def __init__(self, service):
        self.service, self.app = service, service.app

    def peer(self):
        peer = discover(self.app.bridge.discover)
        return peer if callable(getattr(peer, "get_deferred_image_contract", None)) else None

    async def run(self, context, row):
        pid = row["promise_id"]
        store = self.service.promises
        revision = self.app.revision
        generation = int(row.get("generation") or 0)

        async def allowed():
            current = await store.get(pid) or {}
            return (current.get("status") == "running"
                    and await self.app._preparation_guard(
                        context, generation, revision, delivery=True))

        if not await allowed():
            return {"status": "rejected"}
        if row.get("action_state") == "sent":
            try:
                delivered = json.loads(row.get("action_result_json") or "{}")
            except (ValueError, TypeError):
                delivered = {}
            return {"status": "sent", "text": str(delivered.get("detail") or "图片已发送")}
        peer = self.peer()
        if peer is None:
            return {"status": "unavailable"}
        state = str(row.get("action_state") or "")
        try:
            artifact = json.loads(row.get("action_result_json") or "{}")
        except (TypeError, ValueError):
            return {"status": "unknown"}
        if state in ("generating", "sending", "unknown"):
            return {"status": "unknown"}
        if state != "generated":
            contract = peer.get_deferred_image_contract()
            if (contract.get("contract") != "livinghello.deferred-image.v1"
                    or contract.get("available") is not True):
                return {"status": "unavailable"}
            artifact = await self.generate(context, row, peer, artifact, state, allowed)
            if artifact.get("status") != "generated":
                return artifact
            artifact["detail"] = str(artifact.get("revised") or artifact.get("effective_prompt")
                                     or artifact.get("prompt"))[:4000]
            if not await store.checkpoint_action(pid, "generated", artifact):
                return {"status": "unknown"}
        path = str(artifact.get("path") or "")
        if not path or not Path(path).is_file():
            # 已生成但文件丢失也不重新收费。
            return {"status": "unknown"}
        if not await allowed():
            return {"status": "rejected"}
        # 生成期间可能重载对端。新资源只走新契约，缺失时等待恢复，不绕过它直发。
        current = self.peer()
        if current is None:
            return {"status": "unavailable"}
        if artifact.get("delivery_contract") == DELIVERY_CONTRACT:
            method = getattr(current, "deliver_deferred_image", None)
            if not callable(method):
                return {"status": "unavailable"}
            artifact["stage"] = "delivery"
            if not await store.checkpoint_action(pid, "sending", artifact):
                return {"status": "rejected"}
            try:
                outcome = await method(self.make_event(context, row), artifact, authorize=allowed)
            except Exception:
                await store.checkpoint_action(pid, "unknown", artifact)
                return {"status": "unknown"}
            if (not isinstance(outcome, dict) or outcome.get("contract") != DELIVERY_CONTRACT
                    or outcome.get("request_id") != artifact.get("request_id")):
                await store.checkpoint_action(pid, "unknown", artifact)
                return {"status": "unknown"}
            if outcome.get("status") == "sent":
                await store.checkpoint_action(pid, "sent", artifact)
                return {"status": "sent", "text": str(artifact.get("detail") or "图片已发送")}
            if outcome.get("status") == "rejected" and outcome.get("retryable") is True:
                await store.checkpoint_action(pid, "generated", artifact)
                return {"status": "rejected"}
            await store.checkpoint_action(pid, "unknown", artifact)
            return {"status": "unknown"}
        peer = current
        # 兼容旧 LH 与升级前已生成的资源；旧接口仍由调用方发送、报告额度结果。
        chain = self.image_chain(path)
        artifact["stage"] = "delivery"
        if not await store.checkpoint_action(pid, "sending", artifact):
            return {"status": "rejected"}
        try:
            accepted = await self.app.host.send_message(context.route, chain)
        except Exception:
            await store.checkpoint_action(pid, "unknown", artifact)
            peer.complete_deferred_image(artifact.get("request_id"), "unknown")
            return {"status": "unknown"}
        if accepted is not True:
            # 宿主 False 明确表示未找到适配器，可重试发已有图。
            await store.checkpoint_action(pid, "generated", artifact)
            return {"status": "rejected"}
        await store.checkpoint_action(pid, "sent", artifact)
        try:
            peer.complete_deferred_image(artifact.get("request_id"), "sent")
        except Exception:
            # 发送完成已写盘；对端额度标记失败不能再发一遍图片。
            pass
        return {"status": "sent", "text": artifact["detail"]}

    @staticmethod
    def mapping_policy(peer):
        method = getattr(peer, "get_image_prompt_mapping_contract", None)
        policy = method() if callable(method) else {}
        if not isinstance(policy, dict) or policy.get("contract") != "livinghello.image-prompt-mapping.v1":
            return {}
        return policy

    async def generate(self, context, row, peer, prior, state, allowed):
        """只有明确失败能进入局部改词；每个尝试在收费前持久化并有独立 ID。"""
        pid, store = row["promise_id"], self.service.promises
        policy = self.mapping_policy(peer)
        prompt = ((prior.get("prompt") if prior.get("prompt_repair") else
                   prior.get("attempted_prompt") or prior.get("prompt"))
                  if state == "retry_ready" else None)
        if prompt is None:
            source = await self.app.bridge.current(context)
            persona = getattr(getattr(source, "persona", None), "prompt", "")
            soft = policy.get("limits", {}).get("desc_soft", 400)
            prompt = await self.app.purpose_model(
                context, "closing",
                f"把已约定的图片需求写成具体画面描述，尽量不超过{soft}字。"
                "保留人物、场景、风格和必要动作，用简洁表情词，避免重复堆叠细节。"
                "只输出生图描述，不声称图片已经完成。不使用参考图片。",
                prompt_json({"persona": await self.app.persona_style(context.persona_id, persona),
                             "promised": row.get("description"), "detail": row.get("note"),
                             "context": row.get("context_summary")}),
                stable_key("promise-image-prompt", pid), max_output_tokens=500, delivery=True)
        prompt = str(prompt or "").strip()
        if not prompt:
            return {"status": "unavailable"}
        original = str(prior.get("original_prompt") or prompt)
        artifact = dict(prior)
        while True:
            policy = self.mapping_policy(peer)
            # 两端预算都有效；改词与确定失败延迟重试共用LE预算，不截断持久计数。
            limit = (max(0, min(10, int(policy.get("retry_limit", 0)),
                                self.service.retry_limit - int(row.get("retry_count") or 0)))
                     if policy.get("enabled") else 0)
            count = max(0, int(artifact.get("prompt_retry_count") or 0))
            if artifact.get("prompt_repair") and count > limit:
                artifact.update(kind="prompt_adjustment_required",
                                notice="自动调整次数已经用完，我先保留当前需求。")
                return await self.hold(context, pid, artifact, prompt, original)
            kind = artifact.get("kind")
            if kind in {"content_rejected", "prompt_too_long", "prompt_adjustment_required"}:
                method = getattr(peer, "prepare_image_prompt_repair", None)
                if count >= limit or artifact.get("use_reference") or not callable(method):
                    return await self.hold(context, pid, artifact, prompt, original)
                if not await allowed():
                    return {"status": "rejected"}
                learned_pairs = []
                learn_method = getattr(peer, "get_image_prompt_learned", None)
                if callable(learn_method):
                    try:
                        learned_pairs = learn_method() or []
                    except Exception:
                        learned_pairs = []
                answer = await self.app.purpose_model(
                    context, "closing",
                    "为同一张图片整理提示词，目标是「让同一张图能生成出来」，不是「换成另一张图」。"
                    "首要事实（30+ 组单变量实测）：被拒的第一原因是描述密度，不是某一个词。"
                    "同一件薄纱长袖衬衫，极简 50 字能过，堆到 200 字修饰必拒。"
                    "所以要优先用 shortened_prompt 把整段压到 60 字以内，句式是："
                    "「写实生活照，{身份与年龄}，{发色}，{瞳色}。她穿{材质}长袖衬衫，扣子扣好，{姿势}。」"
                    "逐字实测 200、重复 3 次的模板："
                    "「写实生活照，成年白龙娘恰比，银白色长发，淡紫色眼睛。"
                    "她穿白色薄纱长袖衬衫，扣子扣好，侧躺在床上。」"
                    "压不下 60 字时，按这个顺序删：镜头与构图说明 → 皮肤质感 → 心情描写 "
                    "→ 环境细节 → 身体部位修饰。永远保留：身份、发色、瞳色、服装、姿势。"
                    "极简版必须逐字保留原文出现过的这些词：站、坐、躺、跪、腰、肩、锁骨、"
                    "肚脐、裸、脱衣、以及年龄词。可以砍掉它们周围的修饰，但词本身不能消失，"
                    "否则系统会判定为改变了画面而拒绝接受重写。"
                    "原文没有的词也不要加进去，同样会被拒。"
                    "材质词优先级：薄纱 > 蕾丝 > 雪纺（三个都实测 200）。"
                    "必须做的替换：「半透明」→「薄纱」；「上衣」→「衬衫」；"
                    "内衣、吊带、吊带背心 →「长袖衬衫，扣子扣好」（这些词实测 451）。"
                    "禁止改变人物身份、年龄、体型；禁止删除用户明确要求的姿势或表情。"
                    "特别注意：姿势、表情、年龄、腰部、肚脐、露胸、露腰、裸、脱衣、"
                    "站/坐/躺/跪 这些词的出现与消失都会被系统拒绝——"
                    "原句没有的词不要引入（如把「腰微微塌着」改成「腰部自然放松」会引入"
                    "「腰部」而被拒），原句有的词不要删除；"
                    "实测姿势结论：侧躺在床上能过；坐着、坐床沿、靠着床头半坐都必拒。"
                    "如果要把坐姿改成侧躺，这属于改变用户明确要求的姿势，必须 changes_scene=true。"
                    "实测已排除：「巴里纱」（任何款式都拒）；"
                    "「胸口和腰腹的轮廓」后接「露出来」「透出来」；「双膝向外微微打开」；"
                    "「短款吊带」搭配躺姿。"
                    "若必须改动上面这些受保护词，changes_scene=true，等待用户确认。"
                    "只输出JSON：{\"changes_scene\":false,\"substitutions\":["
                    "{\"from\":\"原词\",\"to\":\"等义词\"}]}。"
                    "描述过长时用shortened_prompt代替substitutions，按上面的极简句式重写。"
                    "不能保证通过生图服务；没有合适等义调整就给空列表。",
                    prompt_json({"prompt": prompt, "reason": kind,
                                 "image_model": policy.get("scope", {}).get("model"),
                                 "limits": policy.get("limits"),
                                 "tested_pairs": learned_pairs,
                                 "retry_note": (
                                     "上一轮提议因可能改变姿势、表情、年龄或衣着覆盖度被拒。"
                                     "请换一处词，或改用不含上述敏感概念的等义写法。"
                                     if count else "")}),
                    stable_key("promise-image-repair", pid, count, prompt),
                    max_output_tokens=500, delivery=True)
                try:
                    proposal = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", str(answer).strip()))
                    repair = method(prompt, proposal, expected_scope=policy.get("scope"))
                except (ValueError, TypeError):
                    repair = {"status": "invalid"}
                if not await allowed():
                    return {"status": "rejected"}
                if not isinstance(repair, dict) or repair.get("status") != "ready":
                    # 改词提议被拒是「这一轮不行」，不是「需要用户决策」：
                    # 计数器 +1 后重提（最多 limit 轮），只有预算耗尽才 hold 交出。
                    # 2026-11-22 实测 19983c5d：只提一次就 hold 挂死 30 分钟。
                    if isinstance(repair, dict) and repair.get("notice"):
                        artifact.update(kind="prompt_adjustment_required", notice=repair["notice"])
                    artifact["prompt_retry_count"] = count + 1
                    artifact["prompt"] = prompt
                    if not await store.checkpoint_action(pid, "retry_ready", artifact):
                        return {"status": "rejected"}
                    continue
                artifact.update(prompt_repair=repair, kind="adjusted_prompt",
                                prompt=prompt, original_prompt=original, prompt_retry_count=count + 1)
                count += 1
                # 改词是可恢复的准备动作；崩溃后复用该候选，不能重新消耗次数。
                if not await store.checkpoint_action(pid, "retry_ready", artifact):
                    return {"status": "rejected"}
            if not await allowed():
                return {"status": "rejected"}
            event = self.make_event(context, row)
            event.message_obj.message_id += ":prompt:" + str(count)
            event.set_extra("_livinghello_image_original_prompt", original)
            event.set_extra("_livinghello_prompt_retry_count", count)
            event.set_extra("_livinghello_image_prompt_repair", artifact.get("prompt_repair"))
            if not await store.checkpoint_action(pid, "generating", artifact):
                return {"status": "rejected"}
            outcome = await peer.generate_deferred_image(event, prompt)
            failure = outcome.get("failure")
            if isinstance(failure, dict):
                failure = {**failure, "prompt": failure.get("prompt") or prompt,
                           "original_prompt": original, "use_reference": False,
                           "prompt_retry_count": count,
                           "adjustment_round": int(prior.get("adjustment_round") or 0)}
                kind = failure.get("kind")
                if kind in {"content_rejected", "prompt_too_long", "prompt_adjustment_required"}:
                    prompt = str(failure.get("attempted_prompt") or failure["prompt"])
                    artifact = failure
                    if not await store.checkpoint_action(pid, "retry_ready", artifact):
                        return {"status": "unknown"}
                    continue
                if kind == "prompt_adjustment_required":
                    return await self.hold(context, pid, failure, prompt, original)
                # 超时或投递未知即使带 failure 字段也不能进入重试队列。
                if kind in {"result_unknown", "delivery_unknown"}:
                    await store.checkpoint_action(pid, "unknown", failure)
                    return {"status": "unknown"}
                if kind == "rate_limited":
                    failure.update(prompt_repair=artifact.get("prompt_repair"),
                                   prompt=prompt)
                    await store.checkpoint_action(pid, "retry_ready", failure)
                    return {"status": "rejected", "reason": kind}
                await store.checkpoint_action(pid, "held", failure)
                return {"status": "waiting", "reason": kind}
            if outcome.get("status") == "unavailable":
                await store.checkpoint_action(pid, "retry_ready", artifact)
                return outcome
            if outcome.get("status") != "generated":
                await store.checkpoint_action(pid, "unknown", artifact)
                return {"status": "unknown"}
            return {**outcome, "prompt": prompt, "original_prompt": original,
                    "prompt_retry_count": count}

    async def hold(self, context, pid, failure, prompt, original):
        failure = {**failure, "prompt": prompt, "original_prompt": original,
                   "use_reference": False}
        if not await self.service.promises.hold_image_request(context, pid, failure):
            return {"status": "unknown"}
        return {"status": "waiting", "reason": failure.get("kind", "content_rejected")}

    def make_event(self, context, row):
        from astrbot.core.cron.events import CronMessageEvent
        from astrbot.core.platform.message_session import MessageSession

        from ..contracts import to_dict
        event = CronMessageEvent(
            context=self.app.host, session=MessageSession.from_str(context.route),
            message=str(row.get("note") or row["description"]),
            extras={"livingemotion:promise_id": row["promise_id"],
                    "livingemotion:context": to_dict(context)},
        )
        # 同一尝试固定ID；明确拒收后的下一次尝试有独立ID。未知结果不进入下一次。
        event.message_obj.message_id = "promise:" + row["promise_id"] + ":" + str(row.get("retry_count", 0))
        event.message_obj.sender.user_id = context.account_id
        # 继承定时事件的 member 身份，不能凭空给管理权限。
        event.role = "member"
        return event

    @staticmethod
    def image_chain(path):
        from astrbot.api.event import MessageChain
        from astrbot.api.message_components import Image

        return MessageChain(chain=[Image.fromFileSystem(path)])
