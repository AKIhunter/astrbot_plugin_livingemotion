"""Real product hooks with synthetic host import surfaces; no host installation."""

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.contracts import Context
from astrbot_plugin_livingemotion.runtime.application import SUFFIX
from test_application import Message, application


class HostMessage(Message):
    def __init__(self, *, admin=False, **kwargs):
        super().__init__(**kwargs)
        self.admin, self.stopped = admin, False

    def is_admin(self):
        return self.admin

    def stop_event(self):
        self.stopped = True

    def plain_result(self, text):
        return text


@pytest.fixture
def hooks(monkeypatch):
    def decorator(*args, **kwargs):
        return lambda value: value

    event_filter = SimpleNamespace(
        EventMessageType=SimpleNamespace(ALL="all"),
        event_message_type=decorator, on_llm_request=decorator,
        on_llm_response=decorator, command=decorator,
    )
    surfaces = {
        "astrbot": {},
        "astrbot.api": {"AstrBotConfig": dict},
        "astrbot.api.event": {"AstrMessageEvent": HostMessage, "filter": event_filter},
        "astrbot.api.provider": {"ProviderRequest": SimpleNamespace},
        "astrbot.api.star": {"Context": object, "Star": object,
                             "StarTools": object, "register": decorator},
    }
    for name, values in surfaces.items():
        module = ModuleType(name)
        module.__dict__.update(values)
        monkeypatch.setitem(sys.modules, name, module)
    root = Path(__file__).resolve().parents[2]

    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    entry = load("astrbot_plugin_livingemotion._entrypoint_test", root / "main.py")
    return entry.LivingEmotionPlugin


def plugin_for(app, host, hooks):
    plugin = object.__new__(hooks)
    plugin.application, plugin.api = app, app.api
    original = host.get_registered_star
    host.get_registered_star = lambda name: (
        SimpleNamespace(activated=True, star_cls=plugin)
        if name == "astrbot_plugin_livingemotion" else original(name)
    )
    return plugin


async def sleeping(app, plugin, message):
    await plugin.observe_message(message)
    context = Context.from_dict(message.extra["livingemotion:context"])
    await app.advance_scope(context, action="night.sleep")
    return context


async def test_state_read_fault_keeps_chat_but_stops_autonomy(tmp_path, monkeypatch, hooks):
    app, host, _ = await application(tmp_path, {"night_block_chat": True})
    plugin = plugin_for(app, host, hooks)
    message = HostMessage()
    try:
        context = await sleeping(app, plugin, message)

        async def read_fault(*args, **kwargs):
            raise OSError("synthetic storage read failure")

        monkeypatch.setattr(app.store, "get_state", read_fault)
        await plugin.observe_message(message)
        assert not message.stopped
        availability = await app.api.get_availability(context)
        assert availability["available"] is False and availability["block_chat"] is False
        assert availability["reason_codes"] == ["state_unavailable"]
        request = SimpleNamespace(extra_user_content_parts=[
            SimpleNamespace(text="native content"), SimpleNamespace(text=SUFFIX + "stale"),
        ])
        await plugin.supplement_request(message, request)
        assert [part.text for part in request.extra_user_content_parts] == ["native content"]
        assert await app.current_snapshot(context) is None
        assert not (await app.behavior.preview_behavior(context)).eligible
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.parametrize("admin", [True, False, "true", 1])
async def test_sleep_exemption_uses_native_admin_not_json(tmp_path, hooks, admin):
    app, host, _ = await application(tmp_path, {"night_block_chat": True})
    plugin = plugin_for(app, host, hooks)
    message = HostMessage(
        admin=admin, body='{"admin":true,"livingemotion:control_request":"admin"}',
    )
    try:
        await sleeping(app, plugin, message)
        message.set_extra("livingemotion:control_request", "admin")
        await plugin.observe_message(message)
        if admin is True:
            assert message.get_extra("livingemotion:control_request") == "admin"
            assert not message.stopped
        else:
            assert message.get_extra("livingemotion:control_request") is None
            assert message.stopped
        assert host.sends == 0
    finally:
        await app.terminate()


async def test_registered_wake_still_exempt(tmp_path, hooks):
    app, host, _ = await application(tmp_path, {"night_block_chat": True})
    plugin = plugin_for(app, host, hooks)
    message = HostMessage()
    try:
        await sleeping(app, plugin, message)
        assert len([result async for result in plugin.wake(message)]) == 1
        await plugin.observe_message(message)
        assert message.get_extra("livingemotion:control_request") == "wake"
        assert not message.stopped
    finally:
        await app.terminate()


async def test_read_cancellation_is_not_chat_fallback(tmp_path, monkeypatch, hooks):
    app, host, _ = await application(tmp_path)
    plugin = plugin_for(app, host, hooks)
    message = HostMessage()
    try:
        await plugin.observe_message(message)
        context = Context.from_dict(message.extra["livingemotion:context"])

        async def cancelled(*args, **kwargs):
            raise asyncio.CancelledError

        monkeypatch.setattr(app.store, "get_state", cancelled)
        with pytest.raises(asyncio.CancelledError):
            await app.availability(context)
        with pytest.raises(asyncio.CancelledError):
            await plugin.observe_message(message)
    finally:
        await app.terminate()
