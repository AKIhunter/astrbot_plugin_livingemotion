"""延迟图片的显式动作契约；只有生成与发送均完成才兑现。"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..contracts import prompt_json, stable_key
from ..livinghello_coupling import discover

IMAGE = re.compile(r"自拍|照片|图片|生图|画图|发图|绘制|画[一个张幅]|拍[一个张]|生成.{0,8}图")
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
            return await self.app._preparation_guard(
                context, generation, revision, delivery=True)

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
            # 失败待办沿用明确的原画面或用户新调整，不让模型自动改写被拒绝的请求。
            prompt = artifact.get("prompt") if state == "retry_ready" else None
            source = await self.app.bridge.current(context)
            persona_prompt = getattr(getattr(source, "persona", None), "prompt", "")
            if prompt is None:
                prompt = await self.app.purpose_model(
                    context, "closing",
                    "把已约定的图片需求写成具体画面描述，保留人物、场景与风格。"
                    "只输出生图描述，不声称图片已经完成。不使用参考图片。",
                    prompt_json({
                        "persona": await self.app.persona_style(context.persona_id, persona_prompt),
                        "promised": row.get("description"),
                        "detail": row.get("note"),
                        "context": row.get("context_summary"),
                    }),
                    stable_key("promise-image-prompt", pid),
                    max_output_tokens=500, delivery=True,
                )
            if not str(prompt or "").strip():
                return {"status": "unavailable"}
            if not await allowed():
                return {"status": "rejected"}
            event = self.make_event(context, row)
            prior = artifact
            # 必须在可能收费之前写盘；kill 后留下 generating，禁止自动补发。
            if not await store.checkpoint_action(pid, "generating", artifact):
                return {"status": "rejected"}
            artifact = await peer.generate_deferred_image(event, str(prompt).strip())
            failure = artifact.get("failure")
            if isinstance(failure, dict):
                phase = "retry_ready" if failure.get("kind") == "rate_limited" else "held"
                await store.checkpoint_action(pid, phase, failure)
                return {"status": "rejected" if phase == "retry_ready" else "waiting",
                        "reason": failure.get("kind", "result_unknown")}
            if artifact.get("status") == "unavailable":
                await store.checkpoint_action(pid, state, prior)
                return artifact
            if artifact.get("status") != "generated":
                await store.checkpoint_action(pid, "unknown")
                return {"status": "unknown"}
            artifact["detail"] = str(artifact.get("revised") or prompt)[:4000]
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
