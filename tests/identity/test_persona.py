from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from astrbot_plugin_livingemotion.adapters.persona import (
    AstrBotPersonaSource,
    NativePersona,
    PersonaAdapter,
)
from astrbot_plugin_livingemotion.tests.memory.fakes import context


async def test_same_resolver_foreground_background_and_switch_back_invalidates():
    native = NativePersona("p1", "native text")
    calls = []

    async def resolve(route, explicit):
        calls.append((route, explicit))
        return native

    adapter = PersonaAdapter(resolve)
    foreground = await adapter.resolve(context())
    background = await adapter.resolve(context())
    assert foreground == background
    assert foreground.context.bot_id == context().bot_id
    assert adapter.foreground_suffix("state", max_chars=3) == "sta"
    assert "native text" not in adapter.foreground_suffix("state")
    native = NativePersona("p2", "another native text")
    assert not await adapter.validate(foreground)
    native = NativePersona("p1", "native text")
    assert not await adapter.validate(foreground)
    assert all(route == context().route and explicit is None for route, explicit in calls)


async def test_prompt_change_with_same_persona_id_invalidates():
    resolver = AsyncMock(return_value=NativePersona("p", "first"))
    adapter = PersonaAdapter(resolver)
    snapshot = await adapter.resolve(context())
    resolver.return_value = NativePersona("p", "changed")
    assert not await adapter.validate(snapshot)


async def test_explicit_none_and_no_model_identity_fallback():
    native = AsyncMock(return_value=NativePersona("chosen", "text"))
    adapter = PersonaAdapter(native, mode="explicit", persona_id="chosen")
    result = await adapter.resolve(context())
    native.assert_awaited_once_with(context().route, "chosen")
    assert result.context.persona_id == "chosen"
    disabled = PersonaAdapter(native, mode="none")
    assert (await disabled.resolve(context())).prompt == ""
    assert native.await_count == 1
    native.side_effect = RuntimeError("provider-model-id-is-not-a-persona")
    assert not await adapter.validate(result)
    with pytest.raises(ValueError):
        PersonaAdapter(native, mode="explicit")
    with pytest.raises(ValueError):
        await adapter.resolve(context(route=None))


async def test_native_bridge_uses_actual_host_selection_and_current_conversation():
    manager = SimpleNamespace(
        resolve_selected_persona=AsyncMock(
            return_value=("session-selected", {"prompt": "original native"}, None, False),
        )
    )
    conversation = AsyncMock(return_value="conversation-selected")
    source = AstrBotPersonaSource(
        manager,
        conversation_persona=conversation,
        platform_name=lambda route: "aiocqhttp",
        render=lambda native: native["prompt"],
    )
    adapter = PersonaAdapter(source)
    first = await adapter.resolve(context())
    assert first.context.persona_id == "session-selected"
    manager.resolve_selected_persona.assert_awaited_once_with(
        umo=context().route,
        conversation_persona_id="conversation-selected",
        platform_name="aiocqhttp",
    )
    conversation.return_value = "new-conversation-persona"
    await adapter.resolve(context())
    assert (
        manager.resolve_selected_persona.call_args.kwargs["conversation_persona_id"]
        == "new-conversation-persona"
    )


async def test_native_none_and_webchat_special_fail_closed():
    manager = SimpleNamespace(
        resolve_selected_persona=AsyncMock(
            return_value=("[%None]", None, None, False),
        )
    )
    source = AstrBotPersonaSource(
        manager,
        conversation_persona=AsyncMock(return_value=None),
        platform_name=lambda route: "webchat",
        render=lambda native: native["prompt"],
    )
    assert (await source(context().route, None)).prompt == ""
    manager.resolve_selected_persona.return_value = (None, None, None, True)
    with pytest.raises(ValueError, match="native_webchat_special"):
        await source(context().route, None)
    with pytest.raises(ValueError, match="explicit_lookup"):
        await source(context().route, "explicit")
