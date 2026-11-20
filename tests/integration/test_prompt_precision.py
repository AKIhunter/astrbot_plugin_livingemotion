"""Capture real prompt boundaries with synthetic models; no external requests."""

import asyncio
from copy import deepcopy
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.contracts import (
    BotAffect, NightState, Relationship, canonical_json, prompt_json, to_dict,
)
from astrbot_plugin_livingemotion.domain.context_emotion import expression_items
from astrbot_plugin_livingemotion.domain.dreaming import dream_profile
from astrbot_plugin_livingemotion.prompt_injection import STATE_HEADER, prompt_state
from astrbot_plugin_livingemotion.runtime.application import SUFFIX
from astrbot_plugin_livingemotion.runtime.feeling import maybe_feeling
from astrbot_plugin_livingemotion.tests.behavior.test_console_simulation import (
    setup as simulation_app, submit as simulate,
)
from astrbot_plugin_livingemotion.tests.domain.test_context_emotion import transition
from astrbot_plugin_livingemotion.tests.experience.test_feeling import (
    setup as feeling_app, complete as finish_feeling,
)
from astrbot_plugin_livingemotion.tests.experience.test_manual_daily import (
    make_app as manual_app, submit as manual_generate, finish as finish_manual,
)
from astrbot_plugin_livingemotion.tests.integration.test_application import (
    generation_app, Message,
)
from astrbot_plugin_livingemotion.tests.integration.test_proactive_runtime import proactive_app, drain

MOOD = {
    "joy": .24951, "anger": .0000001, "sadness": .0046154795463250325,
    "fear": .123456789, "surprise": .09999999, "affection": .23456789,
}
ROUNDED_MOOD = {
    "joy": .25, "anger": 0.0, "sadness": .005,
    "fear": .123, "surprise": .1, "affection": .235,
}
ROUNDED_AFFECT = {"pleasure": .25, "arousal": .123, "stress": .005, "social_need": .235}


def affect(now):
    return BotAffect(
        pleasure=MOOD["joy"], arousal=MOOD["fear"], stress=MOOD["sadness"],
        social_need=MOOD["affection"], baseline_pleasure=.123456789,
        baseline_arousal=.23456789, baseline_stress=.0046154795463250325,
        baseline_social_need=.0000001, baseline_refined=True,
        control=.912345678, updated_at=now, control_at=now - .123456,
    )


def test_output_copy_preserves_time_evidence_raw_scores_and_json_values():
    now = 1800000000.123456
    original = {
        "bot": {**to_dict(affect(now)), "context_emotions": [
            {"intensity": .23456789, "label": "害羞", "expires_at": now + 10}],
            "evidence": [{"confidence": .987654321, "occurred_at": now}],
            "unknown_number": .987654321},
        "daily_emotions": {**MOOD, "updated_at": now},
        "human_observation": {"confidence": .87654321, "expires_at": now},
        "relationship": {"raw_score": 500.123456789, "closeness": .500123456,
                         "trust": None, "boundary": .23456789},
        "night": {"energy": 63.456789, "wake_at": now},
    }
    before = canonical_json(original)
    result = prompt_state(original)
    assert {k: result["bot"][k] for k in ROUNDED_AFFECT} == ROUNDED_AFFECT
    assert result["bot"]["baseline_pleasure"] == .123
    assert result["bot"]["baseline_arousal"] == .235
    assert result["bot"]["baseline_stress"] == .005
    assert result["bot"]["baseline_social_need"] == 0.0
    assert result["bot"]["control"] == .912
    assert result["bot"]["baseline_refined"] is True
    assert result["bot"]["context_emotions"][0]["intensity"] == .235
    assert result["bot"]["updated_at"] == now
    assert result["bot"]["control_at"] == original["bot"]["control_at"]
    assert result["bot"]["evidence"] == original["bot"]["evidence"]
    assert result["bot"]["unknown_number"] == .987654321
    assert {k: result["daily_emotions"][k] for k in MOOD} == ROUNDED_MOOD
    assert result["daily_emotions"]["updated_at"] == now
    assert result["human_observation"] == {"confidence": .877, "expires_at": now}
    assert result["relationship"] == {
        "raw_score": 500.123456789, "closeness": .5, "trust": None, "boundary": .235,
    }
    assert result["night"] == {"energy": 63.457, "wake_at": now}
    text = prompt_json(result)
    assert "害羞" in text and "\\u" not in text
    assert json.loads(text) == json.loads(canonical_json(result))
    result["bot"]["evidence"][0]["confidence"] = 0
    assert canonical_json(original) == before


@pytest.mark.parametrize("optional", [None, {}, [], "unknown"])
def test_optional_state_keeps_missing_fields_and_nonnumeric_types(optional):
    original = {"bot": {"pleasure": 1, "stress": None, "arousal": True},
                "daily_emotions": optional}
    assert prompt_state(original) == original


@pytest.mark.parametrize("intensity,expected", [(.19999, []), (.20049, [.2])])
def test_context_visibility_uses_unrounded_threshold_and_output_has_three_decimals(
        le_event, intensity, expected):
    result, event = transition(le_event, "你就是个废物")
    state = result["state"]
    state["items"][0]["intensity"] = intensity
    before = deepcopy(state)
    rows = expression_items(state, event.context, now=event.occurred_at)
    assert [r["intensity"] for r in rows] == expected
    assert state == before


async def test_main_reply_injects_literal_chinese_and_rounded_temporary_state(tmp_path, monkeypatch):
    app, host, _, message, context, binding, clock = await generation_app(tmp_path)
    mood = deepcopy(MOOD)
    state = affect(clock[0])
    night = NightState(energy=63.456789, updated_at=clock[0])
    before = await app.store.get_state(context, "bot")
    async def weather(_):
        return mood
    async def night_snapshot(_):
        return night
    app.weather_emotions = weather
    app.night_snapshot = night_snapshot
    monkeypatch.setattr(
        "astrbot_plugin_livingemotion.runtime.application.current_affect", lambda *a, **k: state)
    try:
        request = SimpleNamespace(extra_user_content_parts=[])
        await app.on_llm_request(message, request)
        part = next(p for p in request.extra_user_content_parts if p.text.startswith(SUFFIX))
        assert part.temporary and part.text.startswith(SUFFIX + "\n" + STATE_HEADER)
        text = part.text[len(SUFFIX + "\n" + STATE_HEADER):]
        assert "TA自己的六种情绪" in text and "\\u" not in text
        payload = json.loads(text)
        assert {k: payload["bot"][k] for k in ROUNDED_AFFECT} == ROUNDED_AFFECT
        assert payload["daily_emotions"] == ROUNDED_MOOD
        assert payload["night"]["energy"] == 63.457 and night.energy == 63.456789
        assert mood == MOOD and state == affect(clock[0])
        assert await app.store.get_state(context, "bot") == before
        assert host.sends == 0 and binding.calls == []
    finally:
        await app.terminate()


async def test_refinement_rounds_dimensions_baselines_and_control_only_in_payload(tmp_path):
    app, host, native, _, context, binding, clock = await generation_app(tmp_path)
    payloads, seeds = [], []
    original_queue = app.queue_refinement
    def queue(event, committed, projection):
        seed = {**projection.refinement, "state": affect(clock[0]),
                "relationship": Relationship(score=500.123456789, trust=.23456789,
                                             boundary=.123456789, updated_at=clock[0] - .123456)}
        seeds.append(seed)
        original_queue(event, committed, replace(projection, refinement=seed))
    async def generate(system, data, *_):
        payloads.append(json.loads(data))
        return "invalid synthetic result"  # Stop before any model-driven state write.
    app.queue_refinement, binding.generate = queue, generate
    try:
        native.update(emotion_model_enabled=True, memory_read=False)
        await app.refresh_config()
        await app.on_message(Message("precision-refinement", "你好"))
        before = await app.store.get_state(context, "bot")
        await asyncio.wait_for(asyncio.gather(*tuple(app._actions)), 3)
        assert len(payloads) == 1
        bot = payloads[0]["bot"]
        assert {k: bot[k] for k in ROUNDED_AFFECT} == ROUNDED_AFFECT
        assert bot["baseline_pleasure"] == .123 and bot["baseline_arousal"] == .235
        assert bot["baseline_stress"] == .005 and bot["baseline_social_need"] == 0.0
        assert bot["control"] == .912 and bot["control_at"] == seeds[0]["state"].control_at
        relation = payloads[0]["relationship"]
        assert relation["trust"] == .235 and relation["boundary"] == .123
        assert relation["score"] == seeds[0]["relationship"].score
        assert relation["updated_at"] == seeds[0]["relationship"].updated_at
        assert seeds[0]["state"] == affect(clock[0])
        assert await app.store.get_state(context, "bot") == before and host.sends == 0
    finally:
        await app.terminate()


async def test_proactive_generation_rounds_mood_and_normalized_relationship(tmp_path):
    app, _, _, context, binding, clock = await proactive_app(tmp_path)
    original_current = app.behavior.current
    async def current(source):
        value = await original_current(source)
        return replace(value, affect=affect(clock[0]),
                       relationship=replace(value.relationship, score=500.123456789,
                                            trust=.23456789, boundary=.123456789))
    app.behavior.current = current
    try:
        await app.tick()
        clock[0] += 1800
        await app.tick()
        await drain(app)
        assert len(binding.calls) == 1
        data = json.loads(binding.calls[0][1])
        assert {k: data["mood"][k] for k in ("pleasure", "social_need", "stress")} == {
            "pleasure": .25, "social_need": .235, "stress": .005}
        assert data["mood"]["control"] == .912
        assert data["mood"]["control_style"] == "更直接、坚定地表达意愿和边界。"
        assert data["relationship"]["closeness"] == .5
        assert data["relationship"]["trust"] == .235 and data["relationship"]["boundary"] == .123
    finally:
        await app.terminate()


async def test_closing_line_rounds_energy_only_in_prompt(tmp_path):
    app, _, native, _, context, _, clock = await generation_app(tmp_path)
    payloads = []
    async def model(context, purpose, system, data, key, **kwargs):
        payloads.append(json.loads(data))
        return "先休息一会儿。"
    try:
        native["closing_random"] = True
        await app.refresh_config()
        app.purpose_model = model
        night = NightState(energy=3.456789, updated_at=clock[0])
        await app._closing_line(context, "precision-closing", night, "low_energy")
        assert payloads[0]["energy"] == 3.457 and night.energy == 3.456789
    finally:
        await app.terminate()


@pytest.mark.parametrize("kind", ["diary", "dream"])
async def test_manual_generation_rounds_output_after_selecting_dream_tone(tmp_path, kind):
    app, model, host, _ = await manual_app(tmp_path)
    capture, snapshots = app.manual_experience.capture, []
    async def snapshot(*args, **kwargs):
        value = replace(await capture(*args, **kwargs), mood=deepcopy(MOOD),
                        current_emotions=deepcopy(MOOD))
        snapshots.append(value)
        return value
    app.manual_experience.capture = snapshot
    try:
        await manual_generate(app, kind)
        await finish_manual(app)
        assert model.calls == 1
        data = model.payloads[0]
        assert data["mood"]["emotions"] == ROUNDED_MOOD
        if kind == "dream":
            assert data["dream"]["emotions"] == ROUNDED_MOOD
            assert data["dream"]["dominant"] == "calm"  # Original max .24951 is below .25.
        assert snapshots[0].mood == MOOD and snapshots[0].current_emotions == MOOD
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.parametrize("kind", ["diary", "dream"])
async def test_automatic_request_rounds_output_and_preserves_material_budget_input(tmp_path, kind):
    app, _, _, _, context, binding, clock = await generation_app(tmp_path)
    try:
        service = await app.experience_service(context)
        counted, counter = [], service.count_tokens
        def count(system, data):
            counted.append(json.loads(data))
            return counter(system, data)
        service.count_tokens = count
        mood = {"dimensions": to_dict(affect(clock[0])), "emotions": deepcopy(MOOD),
                "current_emotions": deepcopy(MOOD), "basis": "daily_recorded_mean"}
        dream = dream_profile(MOOD) if kind == "dream" else None
        before = canonical_json((mood, dream))
        request = service._request(kind, context, "中文人格", (), mood=mood, dream=dream)
        data = json.loads(request.data)
        assert data["mood"]["emotions"] == data["mood"]["current_emotions"] == ROUNDED_MOOD
        assert data["mood"]["dimensions"]["stress"] == .005
        if kind == "dream":
            assert data["dream"]["emotions"] == ROUNDED_MOOD
            assert data["dream"]["dominant"] == "calm"
        assert "中文人格" in request.data and "\\u" not in request.data
        assert counted[0]["mood"] == mood and counted[0]["dream"] == dream
        assert canonical_json((mood, dream)) == before and binding.calls == []
    finally:
        await app.terminate()


@pytest.mark.parametrize("kind", ["feeling", "simulation"])
async def test_feeling_and_simulation_round_six_axes_without_mutating_projection(tmp_path, kind):
    setup = feeling_app if kind == "feeling" else simulation_app
    app, model, host, _ = await setup(tmp_path)
    mood = deepcopy(MOOD)
    async def weather(_):
        return mood
    app.weather_emotions = weather
    try:
        if kind == "feeling":
            await maybe_feeling(app)
            await finish_feeling(app)
            assert model.calls == 1 and model.payloads[0]["emotion"] == ROUNDED_MOOD
        else:
            await simulate(app)
            data = model.calls[0][1]
            assert data["current_emotions"] == ROUNDED_MOOD
            assert json.loads(data["tone"].split("：", 1)[1]) == ROUNDED_MOOD
        assert mood == MOOD and host.sends == 0
    finally:
        await app.terminate()
