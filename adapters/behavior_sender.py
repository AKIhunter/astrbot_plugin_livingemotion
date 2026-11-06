"""Narrow AstrBot 4.29.4 sender. The host's bool is not a delivery receipt."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from ..contracts import Context
from ..services.behavior import SendReceipt, SendRequest


class AstrBotBehaviorSender:
    def __init__(
        self, send_message: Callable[[str, object], Awaitable[object]], *,
        make_chain: Callable[[str], object],
        recorded_route: Callable[[Context], Awaitable[str | None]],
    ):
        self.send_message = send_message
        self.make_chain = make_chain
        self.recorded_route = recorded_route

    async def __call__(self, request: SendRequest) -> SendReceipt:
        route = await self.recorded_route(request.context)
        if not route or route != request.context.route:
            return SendReceipt(request.intent_id, request.context.route or "", "rejected")
        chain = self.make_chain(request.text)
        if not await request.authorize():
            return SendReceipt(request.intent_id, route, "rejected")
        # Do not parse, synthesize or fall back to an account/group ID.
        result = await self.send_message(route, chain)
        return SendReceipt(
            request.intent_id, route, "rejected" if result is False else "unknown",
        )
