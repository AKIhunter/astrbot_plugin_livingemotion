"""Offline Application/SQLite regression for filtered model diagnostics."""
import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.contracts import Context, SceneKind
from astrbot_plugin_livingemotion.storage.console_data import selected_contexts
from test_application import generation_app, Message
from test_context_emotions import At


@pytest.mark.asyncio
@pytest.mark.parametrize("group,targeted", [("", False), ("test-group", True), ("test-group", False)])
@pytest.mark.parametrize("enabled", [False, True])
async def test_persisted_selection_preserves_live_diagnostics(tmp_path, group, targeted, enabled):
    app, host, native, _, _, binding, _ = await generation_app(tmp_path)
    calls = []
    try:
        native.update(
            emotion_model_enabled=enabled, context_emotions_enabled=True,
            promise_enabled=False, weather_factor_enabled=False,
            diary_enabled=False, dream_enabled=False, memory_read=False,
        )
        await app.refresh_config()

        async def generate(system, data, *_):
            calls.append(json.loads(data))
            return json.dumps({
                "rule_version": "emotion-2", "delta": {"pleasure": 0},
                "confidence": 1, "appraisals": [], "context_appraisals": [],
            })

        binding.generate = generate
        message = Message("filtered-diagnostic", "Synthetic neutral message", group=group)
        if targeted:
            message.message_obj.message = (At(message.get_self_id()),)
        await app.on_message(message)
        if app._actions:
            await asyncio.wait_for(asyncio.gather(*tuple(app._actions)), 3)
        context = Context.from_dict(message.extra["livingemotion:context"])
        selection = {
            "persona_id": context.persona_id, "view_scope": context.scene_kind.value,
            "platform": context.platform, "context_id": context.account_key,
        }
        persisted = await selected_contexts(app.store, app.instance_id, selection)
        assert persisted == [replace(context, route=None)]
        assert context.route
        before = await app.store.get_state(context, "relationship", context.account_id)
        live = await app.console_state(context.account_key)
        filtered = await app.console_state(**selection)
        expected_calls = int(enabled and (not group or targeted))
        expected = "completed" if expected_calls else "skipped"
        assert live["emotion_model_analysis"]["status"] == expected
        assert filtered["emotion_model_analysis"] == live["emotion_model_analysis"]
        assert filtered["context_emotions"] == live["context_emotions"]
        assert await app.store.get_state(context, "relationship", context.account_id) == before
        assert len(calls) == expected_calls and host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("changes", [
    {"bot_id": "other-bot"}, {"persona_id": "other-persona"},
    {"adapter_id": "other-adapter"}, {"platform": "other-platform"},
    {"scene_kind": SceneKind.GROUP}, {"scene_id": "other-scene"},
    {"account_id": "other-account"}, {"instance_id": "other-instance"},
    {"persona_revision": "new-persona-revision"},
    {"identity_revision": "new-identity-revision"}, {"audience": ("other-audience",)},
])
async def test_route_normalization_preserves_identity_isolation(tmp_path, changes):
    app, host, _, _, context, _, _ = await generation_app(tmp_path)
    try:
        # Synthetic diagnostics only: no provider request or persisted state write.
        event = SimpleNamespace(context=context, idempotency_key="offline-diagnostic")
        app._analysis(event, "completed", "completed", new_event=True, applied=True)
        assert app.emotion_model_analysis([replace(context, route=None)])["status"] == "completed"
        assert app.emotion_model_analysis([replace(context, route="different-route")])["applied"]
        changed = replace(context, route=None, **changes)
        assert app.emotion_model_analysis([changed]) == {
            "status": "uncollected", "reason_code": "uncollected", "applied": False,
        }
        assert app._emotion_analyses[context.account_key]["context"] == context
        assert host.sends == 0
    finally:
        await app.terminate()
