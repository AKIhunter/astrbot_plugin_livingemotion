"""Delegate image promises to LH; scheduling and completion remain in LE."""

from __future__ import annotations

import json
import re
from pathlib import Path

from astrbot.api import logger

from ..livinghello_coupling import discover

IMAGE = re.compile(
    r"自拍|照片|拍照|拍给(?:你|我|大家)(?:看)?|图片|生图|画图|发图|绘制|"
    r"画[一个张幅]|拍[一个张]|生成.{0,8}图")
DEADLINE_SECONDS = 600.0
DELIVERY_CONTRACT = "livinghello.deferred-image-delivery.v1"
PROMISE_IMAGE_CONTRACT = "livinghello.promise-image.v2"


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
        state = str(row.get("action_state") or "")
        try:
            artifact = json.loads(row.get("action_result_json") or "{}")
        except (TypeError, ValueError):
            return {"status": "unknown"}
        if not isinstance(artifact, dict):
            return {"status": "unknown"}
        if state == "sent":
            return {"status": "sent", "text": str(artifact.get("detail") or "图片已发送")}
        if state in ("generating", "sending", "unknown"):
            return {"status": "unknown"}
        peer = self.peer()
        if peer is None:
            return {"status": "unavailable"}
        if state != "generated":
            contract = peer.get_deferred_image_contract()
            if (contract.get("contract") != "livinghello.deferred-image.v1"
                    or contract.get("available") is not True):
                return {"status": "unavailable"}
            if (contract.get("promise_contract") != PROMISE_IMAGE_CONTRACT
                    or not callable(getattr(peer, "generate_promise_image", None))):
                return {"status": "unavailable", "reason": "image_executor_version"}
            artifact = await self.generate(context, row, peer, artifact, state, allowed)
            if artifact.get("status") != "generated":
                return artifact
            artifact["detail"] = str(artifact.get("revised") or artifact.get("effective_prompt")
                                     or artifact.get("prompt") or "图片已发送")[:4000]
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
                # PromiseService closes the action and writes its trace in one transaction.
                return {"status": "sent", "text": str(artifact.get("detail") or "图片已发送")}
            if outcome.get("status") == "rejected" and outcome.get("retryable") is True:
                await store.checkpoint_action(pid, "generated", artifact)
                return {"status": "rejected"}
            await store.checkpoint_action(pid, "unknown", artifact)
            return {"status": "unknown"}
        if artifact.get("deferred_promise_id"):
            return {"status": "unknown"}
        peer = current
        # 只为升级前已经生成的旧资源保留旧投递，不用旧版入口生成新图。
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
            await store.checkpoint_action(pid, "generated", artifact)
            return {"status": "rejected"}
        await store.checkpoint_action(pid, "sent", artifact)
        try:
            peer.complete_deferred_image(artifact.get("request_id"), "sent")
        except Exception:
            # 发送完成已写盘；对端额度标记失败不能再发一遍图片。
            pass
        return {"status": "sent", "text": str(artifact.get("detail") or "图片已发送")}

    @staticmethod
    def mapping_policy(peer):
        """Read advertised readiness for the pre-existing immediate failure handoff."""
        method = getattr(peer, "get_image_prompt_mapping_contract", None)
        policy = method() if callable(method) else {}
        if not isinstance(policy, dict) or policy.get("contract") != "livinghello.image-prompt-mapping.v1":
            return {}
        return policy

    async def generate(self, context, row, peer, prior, state, allowed):
        """Pass intent and checkpoint opaque executor state; LH owns the image prompts."""
        pid, store = row["promise_id"], self.service.promises
        attempt = int(row.get("retry_count") or 0)
        resume = prior if state == "retry_ready" else {}
        source = await self.app.bridge.current(context)
        persona = getattr(getattr(source, "persona", None), "prompt", "")
        intent = {
            "promise_id": pid, "attempt": attempt,
            "retry_budget": max(0, self.service.retry_limit - attempt),
            "description": str(row.get("description") or "")[:500],
            "detail": str(row.get("note") or "")[:4000],
            "context": str(row.get("context_summary") or "")[:1200],
            "persona": str(await self.app.persona_style(context.persona_id, persona) or "")[:4000],
        }

        async def checkpoint(phase, progress):
            return (phase in {"retry_ready", "generating"} and isinstance(progress, dict)
                    and await store.checkpoint_action(pid, phase, progress))

        def read_legacy():
            # One-time migration of selection only. LE never runs an image prompt model.
            config = self.app.config
            return dict(closing=getattr(config, "closing_provider_id", ""),
                        general=getattr(config, "provider_id", ""),
                        fallback=getattr(config, "fallback_provider_id", ""),
                        daily_limit=getattr(config, "model_daily_limit", 48))

        outcome = await peer.generate_promise_image(
            self.make_event(context, row), intent, resume=resume, authorize=allowed,
            checkpoint=checkpoint, read_legacy=read_legacy)
        if (not isinstance(outcome, dict) or outcome.get("contract") != PROMISE_IMAGE_CONTRACT
                or outcome.get("promise_id") != pid):
            await store.checkpoint_action(pid, "unknown", {"reason_code": "invalid_peer_receipt"})
            logger.warning("[LE-promise] 图片回执 %s reason=invalid_peer_receipt", pid[:8])
            return {"status": "unknown"}
        status = outcome.get("status")
        if status == "generated":
            artifact = outcome.get("artifact")
            if (isinstance(artifact, dict) and artifact.get("status") == "generated"
                    and artifact.get("delivery_contract") == DELIVERY_CONTRACT
                    and artifact.get("deferred_promise_id") == pid
                    and artifact.get("session") == context.route):
                return artifact
            await store.checkpoint_action(pid, "unknown", {"reason_code": "invalid_image_artifact"})
            return {"status": "unknown"}
        failure = outcome.get("failure")
        if isinstance(failure, dict):
            kind = str(failure.get("kind") or "provider_error")
            logger.warning("[LE-promise] 图片失败 %s request=%s kind=%s reason=%s type=%s",
                           pid[:8], str(failure.get("request_id") or "-")[:16], kind,
                           failure.get("reason_code") or kind,
                           failure.get("exception_type") or "-")
            if status == "unknown":
                await store.checkpoint_action(pid, "unknown", failure)
                return {"status": "unknown"}
            if status == "waiting":
                if kind in {"content_rejected", "prompt_too_long", "prompt_adjustment_required"}:
                    saved = await store.hold_image_request(context, pid, failure)
                else:
                    saved = await store.checkpoint_action(pid, "held", failure)
                return {"status": "waiting", "reason": kind} if saved else {"status": "unknown"}
        if status == "unknown" and isinstance(outcome.get("reason"), str):
            await store.checkpoint_action(pid, "unknown", {"reason_code": outcome["reason"][:120]})
        if status in {"rejected", "unavailable"}:
            return {"status": status, "reason": outcome.get("reason")}
        return {"status": "unknown"}

    async def recover_sent(self, context, row, artifact):
        """Only a scoped, confirmed LH receipt can close an interrupted delivery."""
        if (artifact.get("deferred_promise_id") != row["promise_id"]
                or artifact.get("stage") != "delivery" or not artifact.get("request_id")):
            return False
        lookup = getattr(self.peer(), "get_promise_image_receipt", None)
        if not callable(lookup):
            return False
        receipt = lookup(self.make_event(context, row), artifact)
        if (not isinstance(receipt, dict) or receipt.get("contract") != DELIVERY_CONTRACT
                or receipt.get("status") != "sent"
                or receipt.get("promise_id") != row["promise_id"]
                or receipt.get("request_id") != artifact["request_id"]):
            return False
        return await self.service.promises.finish_image_delivery(
            context, row, str(artifact.get("detail") or "图片已发送"),
            ttl_seconds=self.service._trace_ttl(), recovery=True)

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
