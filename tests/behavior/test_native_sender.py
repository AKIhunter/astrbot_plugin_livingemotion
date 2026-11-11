"""Native protocol contract doubles; never connect to a QQ client."""
import asyncio
import sys
from types import ModuleType, SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.adapters.behavior_sender import AstrBotBehaviorSender
from astrbot_plugin_livingemotion.contracts import Context, stable_key
from astrbot_plugin_livingemotion.services.behavior import SendRequest


def modules(monkeypatch):
    class NativeEvent:
        pass
    class Session:
        @staticmethod
        def from_str(route):
            platform, kind, target = route.split(":", 2)
            return SimpleNamespace(platform_name=platform, message_type=SimpleNamespace(value=kind),
                                   session_id=target)
    for name, attr, value in (
        ("astrbot.core.platform.astr_message_event", "MessageSesion", Session),
        ("astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event",
         "AiocqhttpMessageEvent", NativeEvent),
    ):
        module = ModuleType(name)
        setattr(module, attr, value)
        monkeypatch.setitem(sys.modules, name, module)
    return NativeEvent


@pytest.mark.parametrize("group", [False, True])
@pytest.mark.parametrize("response,status", [
    ({"message_id": -456}, "confirmed"),
    ({"status": "ok", "retcode": 0, "data": {"message_id": "789"}}, "confirmed"),
    ({"status": "failed", "retcode": 100, "data": {"message_id": 1}}, "rejected"),
    ({"status": "ok", "retcode": 1, "data": {"message_id": 1}}, "unknown"),
    ({"message_id": True}, "unknown"), ({"message_id": ""}, "unknown"),
    ({"message_id": 0}, "unknown"), (True, "unknown"), (None, "unknown"),
    (TimeoutError(), "unknown"),
])
async def test_native_receipt_once(monkeypatch, group, response, status):
    Event = modules(monkeypatch)
    event = Event()
    event.platform_meta = SimpleNamespace(id="adapter", name="aiocqhttp")
    event.get_group_id = lambda: "333" if group else ""
    event.get_sender_id = lambda: "222"
    event.get_self_id = lambda: "111"
    route = "adapter:" + ("GroupMessage:333" if group else "FriendMessage:222")
    event.unified_msg_origin = route
    context = Context(stable_key("local", "adapter", "aiocqhttp", "qq", "111"),
                      "persona", "adapter", "qq", "group" if group else "private",
                      "333" if group else "222", "222", route=route)
    calls = []
    async def transport(**params):
        calls.append(params)
        if isinstance(response, Exception):
            raise response
        return response
    event.bot = SimpleNamespace(send_private_msg=transport, send_group_msg=transport)
    source = SimpleNamespace(context=context, event=lambda: event)
    async def current(_):
        return source
    async def recorded(_):
        return route
    async def host(*_):
        raise AssertionError("native path must never dispatch a second time")
    async def authorize():
        return True
    sender = AstrBotBehaviorSender(host, make_chain=lambda text: text,
                                  recorded_route=recorded, current_source=current)
    receipt = await sender(SendRequest("intent", context, "合成文本", authorize))
    assert receipt.status == status and len(calls) == 1
    assert calls[0]["self_id"] == 111
    assert calls[0]["group_id" if group else "user_id"] == (333 if group else 222)
    assert receipt.confirmed_parts == (1 if status == "confirmed" else 0)
    assert receipt.intent_id == "intent" and receipt.route == route
    calls.clear()
    async def denied():
        return False
    assert (await sender(SendRequest("denied", context, "test", denied))).status == "rejected"
    assert calls == []
    event.unified_msg_origin = "adapter:FriendMessage:999"
    assert (await sender(SendRequest("wrong-route", context, "test", authorize))).status == "rejected"
    assert calls == []
