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
            if kind in {"content_rejected", "prompt_too_long"}:
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
                    "为同一张图片整理提示词，只允许等义局部替换，不规避内容规则。"
                    "不能改变人物、年龄、衣着覆盖度、场景、风格、姿势或表情。"
                    "若必须改变画面，changes_scene=true，等待用户确认。"
                    "只输出JSON：{\"changes_scene\":false,\"substitutions\":["
                    "{\"from\":\"原词\",\"to\":\"等义词\"}]}。"
                    "只有描述过长时可用shortened_prompt代替substitutions，保留全部画面要点。"
                    "不能保证通过生图服务；没有合适等义调整就给空列表。",
                    prompt_json({"prompt": prompt, "reason": kind,
                                 "image_model": policy.get("scope", {}).get("model"),
                                 "limits": policy.get("limits"),
                                 "tested_pairs": learned_pairs}),
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
                    if isinstance(repair, dict) and repair.get("notice"):
                        artifact.update(kind="prompt_adjustment_required", notice=repair["notice"])
                    return await self.hold(context, pid, artifact, prompt, original)
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
                if kind in {"content_rejected", "prompt_too_long"}:
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
