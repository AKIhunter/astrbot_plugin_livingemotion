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
async def test_closed_coupling_removes_stale_blocks_without_reading_or_catchup(tmp_path):
    app, host, _ = await application(tmp_path)
    flags = {"livingemotion":False,"livingmemory":False}
    install_guard(host, flags)
    try:
        app._prepare_catchup = AsyncMock()
        app.on_message = AsyncMock()
        req = SimpleNamespace(extra_user_content_parts=[
            SimpleNamespace(text=SUFFIX+"old"), SimpleNamespace(text=CATCHUP_SUFFIX+"old"),
            SimpleNamespace(text="当前问题")])
        await app.on_llm_request(Message(), req)
        app.on_message.assert_not_awaited()
        app._prepare_catchup.assert_not_awaited()
        assert [p.text for p in req.extra_user_content_parts] == ["当前问题"]
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_explicit_delegation_unlocks_scoped_state_relationship_and_catchup(tmp_path):
    app, host, _ = await application(tmp_path)
    flags = {"livingemotion":True,"livingmemory":False}
    install_guard(host, flags)
    try:
        message = Message()
        await app.on_message(message)
        context = Context.from_dict(message.extra["livingemotion:context"])
        host.congling = SimpleNamespace(enabled_for=lambda _:True,
                                        livingemotion_delegated_for=lambda _:True)
        assert (await app.api.get_capabilities())["mode"] == "observe_only"
        assert (await app.api.get_capabilities(context=context))["mode"] == "active"
        app._prepare_catchup = AsyncMock()
        app._inject_recalled_memory = AsyncMock()
        req = SimpleNamespace(extra_user_content_parts=[])
        await app.on_llm_request(message, req)
        app._prepare_catchup.assert_awaited_once()
        app._inject_recalled_memory.assert_not_awaited()
        assert len(req.extra_user_content_parts) == 1
        state = json.loads(req.extra_user_content_parts[0].text.split("\n")[-1])
        assert "relationship" in state and "raw_score" in state["relationship"]
        assert "daily_emotions" in state
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_unupdated_congling_is_not_silently_overridden(tmp_path):
    app, host, _ = await application(tmp_path)
    install_guard(host, {"livingemotion":True,"livingmemory":True})
    try:
        message = Message()
        await app.on_message(message)
        context = Context.from_dict(message.extra["livingemotion:context"])
        host.congling = SimpleNamespace(enabled_for=lambda _:True)
        assert (await app.api.get_capabilities(context=context))["mode"] == "observe_only"
        req = SimpleNamespace(extra_user_content_parts=[])
        await app.on_llm_request(message, req)
        assert req.extra_user_content_parts == []
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_disabled_coupling_preserves_chat_even_when_emotion_scope_is_sleeping(tmp_path, hooks):
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
        app.on_reply_submitted.assert_not_awaited()
        assert not message.stopped and req.extra_user_content_parts == []
        assert "enable_streaming" not in message.extra
    finally:
        await app.terminate()
