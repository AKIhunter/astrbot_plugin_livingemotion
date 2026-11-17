"""Deterministic joy invariants; no provider, platform, timers or wall-clock waits."""
from copy import deepcopy
from dataclasses import replace
import json
import random

import pytest

from astrbot_plugin_livingemotion.contracts import BotAffect, Relationship, to_dict
from astrbot_plugin_livingemotion.domain.appraisal import local_appraisals, parse_suggestion
from astrbot_plugin_livingemotion.domain.dreaming import six_emotions
from astrbot_plugin_livingemotion.domain.emotion import (
    DIMENSIONS, RULE_VERSION, apply_emotion, decay_affect, emotion_policy,
)
from astrbot_plugin_livingemotion.domain.relationship import apply_relationship


def joy(state):
    return six_emotions(state)["joy"]


def seed(at):
    return BotAffect(pleasure=.6, stress=.25, updated_at=at)


def model(**delta):
    return {"rule_version": RULE_VERSION, "delta": delta, "confidence": 1}


@pytest.mark.parametrize("body,direction,score", [
    ("后者。坏，腾子给你降智了", -1, 0),
    ("你前面理解有误，因为我问的是逻辑，不是版本", 0, 5),
    ("今天温度20度", 0, 0),
    ("你好", 0, 0),
    ("这次你讲清楚了，你真棒", 1, 5),
])
def test_confirmed_direction_and_unchanged_relationship(le_event, body, direction, score):
    event = replace(le_event, body=body)
    before = seed(event.occurred_at)
    result = apply_emotion(before, event, now=event.occurred_at,
                           policy=emotion_policy("normal"))
    delta = joy(result["affect"]) - joy(before)
    if direction == 0:
        assert delta == pytest.approx(0, abs=1e-12)
    else:
        assert delta * direction > 0
    assert -.10 - 1e-12 <= delta <= .05 + 1e-12
    relation = apply_relationship(Relationship(score=500), event, now=event.occurred_at)
    assert relation["relationship"].score - 500 == score
    if direction == 0:
        assert result["runtime"]["joy_window"] == []


@pytest.mark.parametrize("body", [
    "不是给你降智", "并非给你降智了", "我没说给你降智",
    "请翻译“给你降智了”", "我朋友说给你降智了", "例如给你降智",
    "你没有被降智", "你能力没有下降了",
])
def test_disappointment_requires_asserted_current_evidence(body):
    assert "disappointment" not in local_appraisals(body)


@pytest.mark.parametrize("kind,signals,allowed", [
    ("group", (), False), ("group", ("native_bot_mention",), True),
    ("group", ("native_bot_reply",), True),
    ("group", ("native_bot_mention", "native_other_target"), False),
    ("private", ("native_other_target",), False), ("private", (), True),
])
@pytest.mark.parametrize("suggestion", [None, model(pleasure=.12, stress=-.12)])
def test_native_target_cannot_be_bypassed_by_model(le_event, kind, signals, allowed, suggestion):
    event = replace(le_event, body="你真棒", context=replace(le_event.context, scene_kind=kind),
                    signals=signals)
    before = seed(event.occurred_at)
    result = apply_emotion(before, event, now=event.occurred_at, model_suggestion=suggestion)
    delta = joy(result["affect"]) - joy(before)
    assert (0 < delta <= .05 + 1e-12) if allowed else abs(delta) < 1e-12
    if not allowed:
        assert "joy_target_unknown" in result["reason_codes"]


@pytest.mark.parametrize("body", [
    "你好", "你前面理解有误，因为我问的是逻辑，不是版本",
])
@pytest.mark.parametrize("stress", [-.12, .12])
def test_neutral_joy_compensates_stress_and_model_pleasure(le_event, body, stress):
    event = replace(le_event, body=body)
    before = seed(event.occurred_at)
    result = apply_emotion(before, event, now=event.occurred_at,
                           model_suggestion=model(pleasure=.12, stress=stress))
    assert "model_refined" in result["reason_codes"]
    assert joy(result["affect"]) == pytest.approx(joy(before), abs=1e-12)
    assert result["runtime"]["joy_window"] == []


@pytest.mark.parametrize("preset", ["gentle", "normal", "intense"])
def test_cross_family_positive_negative_budgets_are_independent(le_event, preset):
    state, runtime = seed(le_event.occurred_at), None
    deltas = []
    for n, body in enumerate(["你真棒", "谢谢你", "你辛苦了", "你是废物", "你很烦人",
                               "答应你我故意不做", "尊重你的边界"]):
        event = replace(le_event, body=body, source_id=str(n), event_id=str(n))
        result = apply_emotion(state, event, now=event.occurred_at, runtime=runtime,
                               policy=emotion_policy(preset))
        deltas.append(joy(result["affect"]) - joy(state))
        state, runtime = result["affect"], result["runtime"]
    assert sum(max(0, d) for d in deltas) == pytest.approx(.05, abs=1e-12)
    assert sum(max(0, -d) for d in deltas) == pytest.approx(.10, abs=1e-12)
    assert deltas[-1] == pytest.approx(0, abs=1e-12)


def test_sliding_expiry_and_natural_decay_are_separate(le_event):
    at = le_event.occurred_at
    event = replace(le_event, body="你真棒")
    first = apply_emotion(seed(at), event, now=at)
    second_event = replace(event, source_id="next", event_id="next", occurred_at=at + 299)
    second = apply_emotion(first["affect"], second_event, now=at + 299, runtime=first["runtime"])
    assert second["trace"]["joy"]["stimulus_delta"] == pytest.approx(0, abs=1e-12)
    assert joy(second["affect"]) < joy(first["affect"])
    third_event = replace(event, source_id="third", event_id="third", occurred_at=at + 300)
    third = apply_emotion(second["affect"], third_event, now=at + 300, runtime=second["runtime"])
    assert third["trace"]["joy"]["stimulus_delta"] == pytest.approx(.05, abs=1e-12)
    assert third["runtime"]["joy_window"][0][0] == at + 300


def test_delayed_stimulus_records_receive_time_and_decayed_cap(le_event):
    at, now = le_event.occurred_at, le_event.occurred_at + 1800
    result = apply_emotion(BotAffect(), replace(le_event, body="谢谢你"), now=now)
    assert joy(result["affect"]) == pytest.approx(.025)
    assert result["runtime"]["joy_window"] == [[now, .025]]


@pytest.mark.parametrize("problem", ["duplicate_event", "older_event", "clock_before_state",
                                    "future_event", "expired_event"])
def test_rejected_transitions_do_not_consume_budget(le_event, problem):
    at = le_event.occurred_at
    first = apply_emotion(seed(at), replace(le_event, body="你真棒"), now=at)
    event, now = replace(le_event, body="谢谢你", event_id="other", source_id="other"), at
    if problem == "duplicate_event":
        event = replace(event, source_id=le_event.source_id)
    elif problem == "older_event":
        event = replace(event, occurred_at=at - 1)
    elif problem == "clock_before_state":
        event, now = replace(event, occurred_at=at - 1), at - 1
    elif problem == "future_event":
        event = replace(event, occurred_at=at + 1)
    else:
        event = replace(event, occurred_at=at - 7200)
    result = apply_emotion(first["affect"], event, now=now, runtime=first["runtime"])
    assert result["reason_codes"] == (problem,)
    assert result["runtime"]["joy_window"] == first["runtime"]["joy_window"]


def test_restart_legacy_metadata_saturation_and_capacity(le_event):
    at = le_event.occurred_at
    first = apply_emotion(seed(at), replace(le_event, body="你真棒"), now=at)
    state = BotAffect(**{**to_dict(first["affect"]), "evidence": ()})
    runtime = json.loads(json.dumps(first["runtime"]))
    copied = deepcopy(runtime)
    follow = replace(le_event, body="谢谢你", source_id="next")
    second = apply_emotion(state, follow, now=at, runtime=runtime)
    assert runtime == copied
    assert second["trace"]["joy"]["stimulus_delta"] == pytest.approx(0, abs=1e-12)
    runtime.pop("joy_window")
    assert apply_emotion(state, follow, now=at, runtime=runtime)["trace"]["joy"][
        "stimulus_delta"] == pytest.approx(.05, abs=1e-12)
    saturated = BotAffect(pleasure=1, stress=0, updated_at=at)
    neutral = apply_emotion(saturated, le_event, now=at, model_suggestion=model(stress=.12))
    assert joy(neutral["affect"]) == 1
    runtime["joy_window"] = [[at, .05 / 192] for _ in range(192)]
    full = apply_emotion(state, follow, now=at, runtime=runtime)
    assert len(full["runtime"]["joy_window"]) == 192
    assert full["trace"]["joy"]["stimulus_delta"] == pytest.approx(0, abs=1e-12)
    runtime["joy_window"].pop()
    assert len(apply_emotion(state, follow, now=at, runtime=runtime)["runtime"]["joy_window"]) <= 192


@pytest.mark.parametrize("bad", [
    None, {}, [[1]], [[True, .01]], [[1, float("nan")]], [[1, .06]], [[1, -.11]],
    [[1, .01]] * 193,
])
def test_invalid_window_fails_closed(le_event, bad):
    runtime = {"version": 1, "scope_key": le_event.context.scope_key, "joy_window": bad}
    with pytest.raises(ValueError, match="joy_window"):
        apply_emotion(BotAffect(), le_event, now=le_event.occurred_at, runtime=runtime)


@pytest.mark.parametrize("version", ["emotion-1", "emotion-2", "emotion-3"])
def test_old_model_versions_use_new_limits(le_event, version):
    suggestion = {**model(pleasure=.12), "rule_version": version,
                  "appraisals": [{"signal": "praise", "evidence": "你真棒"}]}
    parsed, signals = parse_suggestion(suggestion, "你真棒")
    event = replace(le_event, body="你真棒", signals=signals)
    result = apply_emotion(seed(event.occurred_at), event, now=event.occurred_at,
                           model_suggestion=parsed)
    assert "model_refined" in result["reason_codes"]
    assert result["trace"]["joy"]["stimulus_delta"] <= .05 + 1e-12


def test_seeded_sequences_preserve_budgets_and_bounded_state(le_event):
    rng = random.Random(20261117)
    state, runtime, now = seed(le_event.occurred_at), None, le_event.occurred_at
    bodies = ["你真棒", "谢谢你", "你是废物", "你好", "我关心你", "给你降智了",
              "你这里算错了，因为原文是12"]
    for n in range(1000):
        now += rng.choice([0, 1, 17, 301])
        at = now - rng.choice([0, 0, 1, 7201])
        event = replace(le_event, occurred_at=at, source_id=str(n // 2),
                        event_id=str(n), body=rng.choice(bodies))
        original = deepcopy(runtime)
        result = apply_emotion(state, event, now=now, runtime=runtime,
                               model_suggestion=model(pleasure=rng.uniform(-.12, .12)))
        assert runtime == original
        state, runtime = result["affect"], result["runtime"]
        rows = runtime.get("joy_window", [])
        assert len(rows) <= 192
        assert sum(max(0, row[1]) for row in rows) <= .05 + 1e-10
        assert sum(max(0, -row[1]) for row in rows) <= .10 + 1e-10
        assert all(-1 <= getattr(state, k) <= 1 for k in DIMENSIONS)
        if n % 13 == 0:
            runtime = json.loads(json.dumps(runtime))
    assert joy(decay_affect(state, now=now + 10**6)) < 1e-10
