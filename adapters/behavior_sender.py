"""Narrow AstrBot 4.29.4 sender. The host's bool is not a delivery receipt."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import re

from ..contracts import Context, stable_key
from ..services.behavior import SendReceipt, SendRequest


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

    async def __call__(self, request: SendRequest) -> SendReceipt:
        route = await self.recorded_route(request.context)
        if not route or route != request.context.route:
            return SendReceipt(request.intent_id, request.context.route or "", "rejected")
        native = None
        if self.current_source:
            source = await self.current_source(request.context)
            if source is None:
                return SendReceipt(request.intent_id, route, "rejected")
            try:
                native = self._native_transport(source, request.context, route)
            except (ValueError, AttributeError):
                return SendReceipt(request.intent_id, route, "rejected")
        if not await request.authorize():
            return SendReceipt(request.intent_id, route, "rejected")
        if native:
            method, parameters = native
            try:
                response = await method(
                    **parameters, message=[{"type": "text", "data": {"text": request.text}}])
            except Exception:
                # Submission may have happened. Do not dispatch again via the host.
                return SendReceipt(request.intent_id, route, "unknown")
            return self._receipt(request.intent_id, route, response)
        # Do not parse, synthesize or fall back to an account/group ID.
        result = await self.send_message(route, self.make_chain(request.text))
        return SendReceipt(
            request.intent_id, route, "rejected" if result is False else "unknown",
        )
