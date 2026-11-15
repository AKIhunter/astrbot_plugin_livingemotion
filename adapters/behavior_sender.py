"""Narrow AstrBot 4.29.4 sender. The host's bool is not a delivery receipt."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import logging
import re

from ..contracts import Context, stable_key
from ..services.behavior import SendReceipt, SendRequest


logger = logging.getLogger("astrbot_plugin_livingemotion.promise")

# 分段之间的间隔：同一瞬间连发三条容易被适配器合并或触发频率限制。
BUBBLE_GAP = 0.35


class AstrBotBehaviorSender:
    def __init__(
        self, send_message: Callable[[str, object], Awaitable[object]], *,
        make_chain: Callable[[str], object],
        recorded_route: Callable[[Context], Awaitable[str | None]],
        current_source=None,
    ):
        self.send_message = send_message
        self.make_chain = make_chain
        self.recorded_route = recorded_route
        self.current_source = current_source

    def _native_transport(self, source, context, route):
        """Accept only the host's real QQ event and its already recorded session."""
        event = source.event() if source else None
        if event is None or getattr(event.platform_meta, "name", "") != "aiocqhttp":
            return None
        from astrbot.core.platform.astr_message_event import MessageSesion
        from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
        if not isinstance(event, AiocqhttpMessageEvent):
            raise ValueError("native_source_invalid")
        session = MessageSesion.from_str(route)
        kind = getattr(session.message_type, "value", session.message_type)
        group = context.scene_kind.value == "group"
        target = str(event.get_group_id() if group else event.get_sender_id())
        self_id = str(event.get_self_id())
        if (context.platform != "qq" or source.context != context
                or event.unified_msg_origin != route
                or event.platform_meta.id != context.adapter_id
                or session.platform_name != context.adapter_id
                or kind != ("GroupMessage" if group else "FriendMessage")
                or str(session.session_id) != target or target != context.scene_id
                or str(event.get_sender_id()) != context.account_id
                or bool(event.get_group_id()) != group
                or context.bot_id != stable_key(context.instance_id, context.adapter_id,
                                                "aiocqhttp", "qq", self_id)
                or not re.fullmatch(r"[1-9][0-9]{0,19}", target)
                or not re.fullmatch(r"[1-9][0-9]{0,19}", self_id)):
            raise ValueError("native_route_invalid")
        client = event.bot
        method = client.send_group_msg if group else client.send_private_msg
        return method, {"group_id" if group else "user_id": int(target), "self_id": int(self_id)}

    @staticmethod
    def _receipt(intent_id, route, response):
        value = response
        if isinstance(value, dict) and ("status" in value or "retcode" in value):
            if value.get("status") == "failed" and type(value.get("retcode")) is int and value["retcode"] != 0:
                return SendReceipt(intent_id, route, "rejected")
            if value.get("status") != "ok" or type(value.get("retcode")) is not int or value["retcode"] != 0:
                return SendReceipt(intent_id, route, "unknown")
            value = value.get("data")
        message_id = value.get("message_id") if isinstance(value, dict) else None
        if ((type(message_id) is int or isinstance(message_id, str))
                and re.fullmatch(r"-?[0-9]{1,20}", str(message_id)) and int(message_id) != 0):
            return SendReceipt(intent_id, route, "confirmed", str(message_id), 1, 1)
        return SendReceipt(intent_id, route, "unknown")

    @staticmethod
    def _bubbles(text: str) -> list[str]:
        """按空行切段：主动行为自己分的段要变成多个气泡。

        一个气泡里塞三段回车，读起来就是一坨；分成几条才像在说话。
        任何换行都算分段——聊天里换行本来就是"这句说完了"的意思。
        最多 6 条，避免模型偶尔刷一大段把对面淹了。
        """
        raw = str(text or "").replace("\r\n", "\n").strip()
        if not raw:
            return []
        chunks = [chunk.strip() for chunk in re.split(r"\n+", raw) if chunk.strip()]
        if not chunks:
            return [raw]
        if len(chunks) > 6:
            # 超过 6 段就并回来：宁可少分，也别一口气刷六条以上。
            head = chunks[:5]
            head.append("\n".join(chunks[5:]))
            return head
        return chunks

    async def __call__(self, request: SendRequest) -> SendReceipt:
        route = await self.recorded_route(request.context)
        if not route or route != request.context.route:
            logger.warning("[LE-send] 路由不可用 recorded=%r context=%r",
                           route, request.context.route)
            return SendReceipt(request.intent_id, request.context.route or "", "rejected")
        native = None
        if self.current_source and not getattr(request, "host_only", False):
            source = await self.current_source(request.context)
            if source is not None:
                try:
                    native = self._native_transport(source, request.context, route)
                except (ValueError, AttributeError):
                    # 有实时事件却校验不过：上下文被换掉了，拒发。
                    logger.warning("[LE-send] 原生通道校验失败 route=%s", route)
                    return SendReceipt(request.intent_id, route, "rejected")
            # source 为 None（重启后 sources 为空）时不拒绝：
            # route 已由桥接按会话表重建，走宿主通道同样送到同一个会话。
        if not await request.authorize():
            logger.warning("[LE-send] 提交授权失败 route=%s", route)
            return SendReceipt(request.intent_id, route, "rejected")
        parts = self._bubbles(request.text)
        if not parts:
            return SendReceipt(request.intent_id, route, "rejected")
        if native:
            method, parameters = native
            confirmed, receipt_id = 0, None
            status = "confirmed"
            for index, part in enumerate(parts):
                try:
                    response = await method(
                        **parameters, message=[{"type": "text", "data": {"text": part}}])
                except Exception:
                    # Submission may have happened. Do not dispatch again via the host.
                    status = "unknown"
                    break
                one = self._receipt(request.intent_id, route, response)
                if one.status != "confirmed":
                    status = one.status
                    break
                confirmed += 1
                receipt_id = receipt_id or one.receipt_id
                if index + 1 < len(parts):
                    await asyncio.sleep(BUBBLE_GAP)
            if status == "confirmed" and confirmed != len(parts):
                status = "unknown"
            return SendReceipt(request.intent_id, route, status, receipt_id,
                               confirmed, len(parts))
        # 宿主通道拿不到平台 message_id，但它确实把消息交给了适配器。
        # 记 "sent"（已受理）而不是 "unknown"：unknown 会触发重发，
        # 承诺这类直发会因此把同一句说两遍。
        confirmed, result = 0, True
        for index, part in enumerate(parts):
            result = await self.send_message(route, self.make_chain(part))
            if result is False:
                break
            confirmed += 1
            if index + 1 < len(parts):
                await asyncio.sleep(BUBBLE_GAP)
        logger.warning("[LE-send] 宿主通道 route=%s native=%s parts=%d/%d result=%r",
                       route, bool(native), confirmed, len(parts), result)
        # 宿主返回的 bool 不是投递凭据，回执状态只能是 unknown；
        # 用 channel 告诉上游“这是宿主通道”，由业务层决定怎么算。
        return SendReceipt(
            request.intent_id, route,
            "rejected" if result is False else "unknown",
            confirmed_parts=confirmed, total_parts=len(parts), channel="host",
        )
