"""LivingHello 协作使用真实状态应用；仅合成宿主和隔离数据库。"""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from astrbot_plugin_livingemotion.contracts import Context
from astrbot_plugin_livingemotion.runtime.application import SUFFIX, CATCHUP_SUFFIX
from test_application import Message, application
from test_main import hooks, HostMessage, plugin_for


def install_guard(host, flags):
    original = host.get_registered_star
    guard = SimpleNamespace(get_function_coupling=lambda: {
        "contract":"livinghello.function-coupling.v1", "managed":True,
        "integrations":{kind:{"effective":value} for kind,value in flags.items()},
    })
    host.get_registered_star = lambda name: (
        SimpleNamespace(activated=True, star_cls=guard)
        if name == "astrbot_plugin_livinghello" else original(name))


@pytest.mark.asyncio
async def test_closed_coupling_keeps_local_hooks_and_replaces_stale_blocks(tmp_path):
    app, host, _ = await application(tmp_path)
    flags = {"livingemotion":False,"livingmemory":False}
    install_guard(host, flags)
    try:
        app._prepare_catchup = AsyncMock()
        req = SimpleNamespace(extra_user_content_parts=[
            SimpleNamespace(text=SUFFIX+"old"), SimpleNamespace(text=CATCHUP_SUFFIX+"old"),
            SimpleNamespace(text="当前问题")])
        message = Message()
        await app.on_llm_request(message, req)
        assert message.get_extra("livingemotion:ingest") == "accepted"
        app._prepare_catchup.assert_awaited_once()
        assert sum(p.text.startswith(SUFFIX) for p in req.extra_user_content_parts) == 1
        assert "当前问题" in [p.text for p in req.extra_user_content_parts]
        assert not any(p.text in (SUFFIX+"old", CATCHUP_SUFFIX+"old") for p in req.extra_user_content_parts)
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_enabled_coupling_injects_local_state_relationship_and_catchup(tmp_path):
    app, host, _ = await application(tmp_path)
    flags = {"livingemotion":True,"livingmemory":False}
    install_guard(host, flags)
    try:
        message = Message()
        await app.on_message(message)
        context = Context.from_dict(message.extra["livingemotion:context"])
        assert (await app.api.get_capabilities())["mode"] == "active"
        assert (await app.api.get_capabilities(context=context))["mode"] == "active"
        app._prepare_catchup = AsyncMock()
        app._inject_recalled_memory = AsyncMock()
        req = SimpleNamespace(extra_user_content_parts=[])
        await app.on_llm_request(message, req)
        app._prepare_catchup.assert_awaited_once()
        app._inject_recalled_memory.assert_not_awaited()
        assert sum(p.text.startswith(SUFFIX) for p in req.extra_user_content_parts) == 1
        state = json.loads(req.extra_user_content_parts[0].text.split("\n")[-1])
        assert "relationship" in state and "raw_score" in state["relationship"]
        assert "daily_emotions" in state
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_local_observe_only_preserves_empty_injection(tmp_path):
    app, host, _ = await application(tmp_path, {"mode": "observe_only"})
    install_guard(host, {"livingemotion":True,"livingmemory":True})
    try:
        message = Message()
        await app.on_message(message)
        context = Context.from_dict(message.extra["livingemotion:context"])
        assert (await app.api.get_capabilities(context=context))["mode"] == "observe_only"
        req = SimpleNamespace(extra_user_content_parts=[])
        await app.on_llm_request(message, req)
        assert req.extra_user_content_parts == []
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_disabled_coupling_keeps_local_sleep_gate(tmp_path, hooks):
    app, host, _ = await application(tmp_path, {"night_block_chat":True})
    plugin = plugin_for(app, host, hooks)
    install_guard(host, {"livingemotion":False,"livingmemory":False})
    try:
        message = HostMessage()
        await app.on_message(message)
        context = Context.from_dict(message.extra["livingemotion:context"])
        await app.advance_scope(context, action="night.sleep")
        await plugin.observe_message(message)
        req = SimpleNamespace(extra_user_content_parts=[])
        await plugin.supplement_request(message, req)
        await plugin.buffer_final_request(message, req)
        app.on_reply_submitted = AsyncMock(return_value=False)
        await plugin.submit_reply(message)
        app.on_reply_submitted.assert_awaited_once_with(message)
        assert message.stopped and req.extra_user_content_parts == []
        assert message.extra["enable_streaming"] is False
    finally:
        await app.terminate()
