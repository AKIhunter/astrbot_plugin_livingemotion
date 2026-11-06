"""Copied into fresh host roots only; it never imports product implementation."""

import sys

from astrbot.api.event import filter
from astrbot.api.star import Star, register


@register("livingemotion_retro_probe", "P8 verifier", "Synthetic hook sentinel", "0.0.1")
class RetroProbe(Star):
    @filter.on_llm_request(priority=-sys.maxsize)
    async def request_probe(self, event, request):
        event.set_extra("retro:request_called", True)
        if event.get_extra("retro:restore_streaming"):
            event.set_extra("enable_streaming", True)
        if event.get_extra("retro:late_live"):
            event.set_extra("action_type", "live")
        event.set_extra("retro:request_sentinel_streaming", event.get_extra("enable_streaming"))

    @filter.on_decorating_result(priority=-sys.maxsize)
    async def decorate_probe(self, event):
        order = event.get_extra("retro:hook_order", [])
        order.append("sentinel")
        event.set_extra("retro:hook_order", order)
        if event.get_extra("retro:cancel"):
            if event.get_extra("retro:clear_before_stop"):
                event.clear_result()
            event.stop_event()
