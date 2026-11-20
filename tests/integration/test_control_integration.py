"""Exercise real reply/model/storage boundaries with scripted providers and no network."""
import asyncio
import json
import socket
from dataclasses import replace
from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.contracts import BotAffect, StateWrite, to_dict
from astrbot_plugin_livingemotion.domain.dreaming import six_emotions
from astrbot_plugin_livingemotion.domain.emotion import (
    CONTROL_EXPRESSION_NOTE, control_expression, control_value,
)
from astrbot_plugin_livingemotion.prompt_injection import STATE_HEADER
from astrbot_plugin_livingemotion.runtime.application import SUFFIX
from astrbot_plugin_livingemotion.runtime.console import emotion_analysis
from astrbot_plugin_livingemotion.tests.behavior.test_console_simulation import (
    Message as SimulationMessage, setup as simulation_app, submit as simulate,
)
from test_application import Message, generation_app
from test_proactive_runtime import proactive_app, drain
from test_context_semantics import semantic_app, turn


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("control integration tests must not access the network")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


async def save_affect(app, context, affect):
    record = await app.store.get_state(context, "bot")
    assert (await app.store.write_states(context, 0, [
        StateWrite("bot", to_dict(affect), record.version if record else 0,
                   owner=app.store.state_owner(context))])).accepted


@pytest.mark.parametrize("control", [.2, .5, .8])
async def test_reply_without_core_prompt_matches_api_and_page_and_never_calls_model(tmp_path, control):
    app, host, native, message, context, binding, clock = await generation_app(tmp_path)
    try:
        native.update(prompt_core_enabled=False, emotion_model_enabled=False,
                      context_emotions_enabled=False, diary_enabled=False, dream_enabled=False)
        await app.refresh_config()
        state = BotAffect(pleasure=-.6, arousal=.7, stress=.6, social_need=.3,
                          control=control, control_at=clock[0], updated_at=clock[0])
        await save_affect(app, context, state)
        before = await app.store.get_state(context, "bot")
        request = SimpleNamespace(extra_user_content_parts=[])
        await app.on_llm_request(message, request)
        part = next(p for p in request.extra_user_content_parts if p.text.startswith(SUFFIX))
        assert part.temporary and CONTROL_EXPRESSION_NOTE in part.text
        # The v1 header stays one line for existing line-based consumers.
        assert STATE_HEADER.count("\n") == 1
        payload = json.loads(part.text.split("\n", 2)[2])
        assert payload["bot"]["control"] == control
        assert payload["bot"]["control_style"] == control_expression(state)["control_style"]
        expected = six_emotions(state)
        assert payload["daily_emotions"] == {k: round(v, 3) for k, v in expected.items()}
        data = (await app.api.get_current_emotion(context))["data"]
        assert data["emotions"] == emotion_analysis(state)["emotions"] == expected
        assert await app.store.get_state(context, "bot") == before
        assert not binding.calls and host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.parametrize("control", [.2, .8])
async def test_proactive_chat_receives_same_control_strategy_and_emotions(tmp_path, control):
    app, host, _, _, binding, clock = await proactive_app(tmp_path)
    original = app.behavior.current
    state = BotAffect(pleasure=-.6, arousal=.7, stress=.6, social_need=.3,
                      control=control, control_at=clock[0], updated_at=clock[0])
    async def current(context):
        value = await original(context)
        return replace(value, affect=state)
    app.behavior.current = current
    try:
        await app.tick()
        clock[0] += 1800
        await app.tick()
        await drain(app)
        assert len(binding.calls) == 1
        system, text, *_ = binding.calls[0]
        data = json.loads(text)
        assert CONTROL_EXPRESSION_NOTE in system
        assert data["mood"]["control_style"] == control_expression(state)["control_style"]
        assert data["mood"]["control"] == control
        assert data["emotions"] == {k: round(v, 3) for k, v in six_emotions(state).items()}
    finally:
        await app.terminate()


@pytest.mark.parametrize("control", [.2, .8])
@pytest.mark.parametrize("emotion", ["current", "anger"])
async def test_simulation_uses_control_and_preserves_manual_emotion(tmp_path, control, emotion):
    app, model, host, native = await simulation_app(tmp_path)
    try:
        native["enabled"] = True
        await app.refresh_config()
        message = SimulationMessage("control-simulation")
        await app.on_message(message)
        context = next(iter(app._contexts.values()))
        now = app.store.clock()
        state = BotAffect(pleasure=-.6, arousal=.7, stress=.6,
                          control=control, control_at=now, updated_at=now)
        await save_affect(app, context, state)
        result = await simulate(app, emotion=emotion)
        assert result["status"] == "completed" and host.sends == 0
        assert len(model.calls) == 1
        system, data, *_ = model.calls[0]
        assert CONTROL_EXPRESSION_NOTE in system
        assert data["mood"] == control_expression(state)
        assert data["current_emotions"] == {k: round(v, 3) for k, v in six_emotions(state).items()}
        assert data["emotion"] == result["emotion_label"]
        if emotion == "anger":
            assert data["tone"] == "明显生气，语气直接、克制，表达不满但不攻击对方"
    finally:
        await app.terminate()


@pytest.mark.parametrize("confidence,expected", [(.74, .5), (.75, .6)])
async def test_joint_analysis_control_confidence_and_history(tmp_path, confidence, expected):
    app, host, native, _, context, binding, clock = await generation_app(tmp_path)
    calls = []
    async def generate(system, data, *_):
        calls.append((system, data))
        return json.dumps({"rule_version": "emotion-3", "delta": {"arousal": 0},
                           "control": 1, "confidence": confidence, "appraisals": []})
    binding.generate = generate
    try:
        native.update(emotion_model_enabled=True, emotion_quiet_start_hour=0,
                      emotion_quiet_end_hour=0, diary_enabled=False, dream_enabled=False)
        await app.refresh_config()
        await app.on_message(Message("control-joint", "讨论一下这个问题"))
        await drain(app)
        state = await app.store.get_state(context, "bot")
        assert state.value["control"] == pytest.approx(expected)
        assert len(calls) == 1 and "不是开心、好感或知识准确率" in calls[0][0]
        sample = await app.store._run(lambda db: db.execute(
            "SELECT control,control_at FROM emotion_samples ORDER BY at DESC LIMIT 1").fetchone())
        assert sample[0] == pytest.approx(expected)
        assert app.emotion_model_analysis([context])["status"] == "completed"
        assert host.sends == 0
    finally:
        await app.terminate()


async def test_stale_control_result_is_discarded_without_another_call(tmp_path):
    app, _, native, _, context, binding, clock = await generation_app(tmp_path)
    started, release, calls = asyncio.Event(), asyncio.Event(), []
    async def generate(system, data, *_):
        calls.append(data)
        started.set()
        await release.wait()
        return '{"rule_version":"emotion-3","delta":{"arousal":0},"control":1,"confidence":1}'
    binding.generate = generate
    try:
        native.update(emotion_model_enabled=True, emotion_quiet_start_hour=0,
                      emotion_quiet_end_hour=0, diary_enabled=False, dream_enabled=False)
        await app.refresh_config()
        await app.on_message(Message("stale-control", "讨论一下这个问题"))
        await asyncio.wait_for(started.wait(), 1)
        await save_affect(app, context, BotAffect(
            control=.2, control_at=clock[0], updated_at=clock[0]))
        before = await app.store.get_state(context, "bot")
        release.set()
        await drain(app)
        assert await app.store.get_state(context, "bot") == before
        assert len(calls) == 1
        assert app.emotion_model_analysis([context])["status"] == "discarded"
    finally:
        release.set()
        await app.terminate()


async def test_context_only_analysis_preserves_control_and_joint_frequency(tmp_path):
    app, host, _, clock, context, provider = await semantic_app(tmp_path)
    try:
        await turn(app, "control-first-joint", "我们聊聊")
        before = await app.store.get_state(context, "bot")
        assert before.value["control"] == pytest.approx(.52)
        assert len(provider.snapshots) == 1
        clock[0] += 1
        await turn(app, "control-context-only", "我们继续聊")
        after = await app.store.get_state(context, "bot")
        old = BotAffect(**{k: before.value[k] for k in ("control", "control_at")})
        assert after.value["control"] == pytest.approx(control_value(old, clock[0]))
        assert len(provider.snapshots) == 2
        assert "不要四维delta" in provider.snapshots[-1]["system"]
        assert "control" not in provider.snapshots[-1]["response"]
        assert provider.snapshots[-1]["output_token_budget"] <= 512
        assert host.sends == 0
    finally:
        await app.terminate()
