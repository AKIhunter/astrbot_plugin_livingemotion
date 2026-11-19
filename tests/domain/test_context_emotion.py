"""Deterministic evidence, holder, time, duplication and compatibility regressions."""
from dataclasses import replace
import json
import random

import pytest

from astrbot_plugin_livingemotion.contracts import (
    ActorRole, BotAffect, ContextAppraisal, Relationship, to_dict,
)
from astrbot_plugin_livingemotion.domain.context_emotion import (
    apply_context_emotions, empty_state, expression_items, human_labels,
    parse_context_appraisals, read_state,
)
from astrbot_plugin_livingemotion.domain.emotion import (
    apply_emotion, expression_context, serialize_expression,
)


def transition(event, body, state=None, *, offset=0, score=500, **kwargs):
    at = event.occurred_at + offset
    event = replace(event, source_id="source-" + str(offset), body=body, occurred_at=at)
    return apply_context_emotions(state, event, Relationship(score=score),
                                  now=at, enabled=True, **kwargs), event


@pytest.mark.parametrize("body,kind", [
    ("你就是个废物", "hurt"),
    ("你从来没帮过我", "hurt"),
    ("虽然你没做错，但我就是要怪你", "wronged"),
    ("你好可爱，我一直看着你呢", "shyness"),
])
def test_explicit_current_evidence(le_event, body, kind):
    result, _ = transition(le_event, body)
    assert result["applied"]
    assert [r["kind"] for r in result["state"]["items"]] == [kind]
    assert result["state"]["items"][0]["holder"] == "bot"
    assert result["state"]["items"][0]["target"] == le_event.context.account_id


@pytest.mark.parametrize("body", [
    '他说“你好可爱”', '请翻译“你就是废物”', "他说你好可爱",
    "你不是废物", "我不是说你没用", "你不可爱", "我不喜欢你",
    "代码写得好", "你的计算错了，因为原文是12", "如何实现害羞情绪",
    "我害羞了", "我被老板骂了，好委屈", "比如你从来没帮过我",
    "你说他是废物", "你觉得我是废物",
    "你觉得我好可爱", "你说她很可爱",
])
def test_counterexamples_do_not_create_bot_feelings(le_event, body):
    result, _ = transition(le_event, body)
    assert not result["state"]["items"]


def test_help_acknowledgement_is_proof_not_a_feeling(le_event):
    helped, _ = transition(le_event, "谢谢你帮我解决了问题")
    assert not helped["state"]["items"] and helped["state"]["support"]
    result, _ = transition(le_event, "你从来没帮过我", helped["state"], offset=1)
    assert [r["kind"] for r in result["state"]["items"]] == ["wronged"]
    assert len(result["state"]["items"][0]["evidence_refs"]) == 2


def test_expired_help_proof_does_not_create_wronged(le_event):
    helped, _ = transition(le_event, "谢谢你帮我解决了问题")
    result, _ = transition(le_event, "你从来没帮过我", helped["state"], offset=86401)
    assert [r["kind"] for r in result["state"]["items"]] == ["hurt"]


@pytest.mark.parametrize("score,maximum", [(200, 0), (300, .25), (500, .60)])
def test_shyness_respects_relationship_stage(le_event, score, maximum):
    result, _ = transition(le_event, "你好可爱", score=score)
    values = result["state"]["items"]
    assert max((r["intensity"] for r in values), default=0) <= maximum


def test_explicit_boundary_blocks_and_clears_shyness(le_event):
    result, _ = transition(le_event, "你好可爱", relationship_note="只聊工作，保持专业")
    assert not result["state"]["items"]
    shy, _ = transition(le_event, "你好可爱")
    cleared, _ = transition(le_event, "正常聊就好", shy["state"], offset=1)
    assert not cleared["state"]["items"]


@pytest.mark.parametrize("kind,body,half_life,ttl", [
    ("wronged", "虽然你没做错，但我就是要怪你", 1800, 7200),
    ("shyness", "你好可爱", 480, 2400),
])
def test_half_life_expiration_and_clock_rollback(le_event, kind, body, half_life, ttl):
    first, event = transition(le_event, body)
    state = first["state"]
    intensity = state["items"][0]["intensity"]
    at = event.occurred_at
    assert read_state(state, event.context, now=at + half_life)["items"][0][
        "intensity"] == pytest.approx(intensity / 2)
    assert not read_state(state, event.context, now=at + ttl)["items"]
    assert read_state(state, event.context, now=at - 10)["items"][0]["intensity"] == intensity
    assert not expression_items(state, event.context, now=at + ttl)


def test_duplicate_and_repeated_words_do_not_renew_incident(le_event):
    first, event = transition(le_event, "你好可爱")
    duplicate = apply_context_emotions(first["state"], event, Relationship(score=500),
                                      now=event.occurred_at, enabled=True)
    assert duplicate["state"] == first["state"] and not duplicate["applied"]
    repeated, _ = transition(le_event, "你好可爱", first["state"], offset=600)
    assert repeated["state"]["items"][0]["expires_at"] == first["state"]["items"][0]["expires_at"]
    assert not repeated["applied"]


def test_new_stimuli_obey_cooldown_and_growth_cap(le_event):
    first, _ = transition(le_event, "你好可爱")
    limited, _ = transition(le_event, "你真可爱", first["state"], offset=10)
    assert not limited["applied"]
    after, _ = transition(le_event, "你真可爱", first["state"], offset=301)
    decayed = .5 * 2 ** (-301 / 480)
    assert after["state"]["items"][0]["intensity"] <= decayed + .10
    again, _ = transition(le_event, "你太可爱", after["state"], offset=302)
    assert not again["applied"]


def test_source_timestamp_and_processing_timestamp_are_separate(le_event):
    first, event = transition(le_event, "你好可爱")
    later = replace(event, source_id="within-second", body="正常聊就好",
                    occurred_at=event.occurred_at + .1)
    result = apply_context_emotions(first["state"], later, Relationship(score=500),
                                    now=event.occurred_at + .9, enabled=True)
    assert not result["state"]["items"]


@pytest.mark.parametrize("repair,expected", [
    ("对不起，是我误会你了", True),
    ("对不起，但我只是开玩笑，你太敏感", False),
    ("对不起，今天开会迟到了", False),
])
def test_repairs_match_active_account_incident(le_event, repair, expected):
    first, _ = transition(le_event, "你就是个废物")
    result, _ = transition(le_event, repair, first["state"], offset=1)
    decayed = first["state"]["items"][0]["intensity"] * 2 ** (-1 / 1800)
    assert result["state"]["items"][0]["intensity"] == pytest.approx(
        decayed * (.4 if expected else 1))


def test_model_cannot_invent_context_proof_or_reuse_quoted_evidence(le_event):
    event = replace(le_event, body="你从来没帮过我")
    appraisal = ContextAppraisal("wronged", "devalued_contribution", event.body,
                                .9, .75, ("invented-proof",))
    raw = {"delta": {"pleasure": 0}, "context_appraisals": [to_dict(appraisal)]}
    legacy, accepted, reasons = parse_context_appraisals(
        raw, event, Relationship(score=500), empty_state())
    assert legacy == {"delta": {"pleasure": 0}} and not accepted and reasons
    result = apply_context_emotions(None, event, Relationship(score=500),
                                    now=event.occurred_at, enabled=True, appraisals=(appraisal,))
    assert result["state"]["items"][0]["kind"] == "hurt"
    quoted = replace(event, body='他说“你从来没帮过我”')
    _, accepted, _ = parse_context_appraisals(
        raw, quoted, Relationship(score=500), empty_state(), support_refs=("invented-proof",))
    assert not accepted


@pytest.mark.parametrize("change", [
    {"actor_role": ActorRole.BOT}, {"actor_id": "another-account"},
    {"reliable_source": False}, {"event_type": "diary"},
    {"confidence": .5},
])
def test_non_current_or_wrong_actor_cannot_mutate(le_event, change):
    event = replace(le_event, body="你好可爱", **change)
    result = apply_context_emotions(None, event, Relationship(score=500),
                                    now=event.occurred_at, enabled=True)
    assert not result["applied"] and not result["state"]["items"]


def test_subject_isolation_and_corrupt_optional_metadata(le_event):
    first, event = transition(le_event, "你好可爱")
    other = replace(event.context, account_id="someone-else")
    assert not read_state(first["state"], other, now=event.occurred_at)["items"]
    corrupt = {**first["state"], "items": [{"kind": "shyness", "intensity": float("nan")}]}
    assert read_state(corrupt, event.context, now=event.occurred_at) == empty_state()


def test_human_observation_does_not_change_four_axis_transition(le_event):
    event = replace(le_event, body="我害羞了")
    legacy = apply_emotion(BotAffect(), event, now=event.occurred_at)
    extended = apply_emotion(BotAffect(), event, now=event.occurred_at, context_observations=True)
    assert extended["affect"] == legacy["affect"]
    assert extended["observation"].labels == ("shyness",)
    assert human_labels("我不害羞") == ()
    assert human_labels("我被老板骂了，好委屈") == ("wronged",)


def test_expression_budget_keeps_valid_json_and_old_keys(le_event):
    feeling, event = transition(le_event, "你好可爱")
    rows = expression_items(feeling["state"], event.context, now=event.occurred_at)
    value = expression_context(BotAffect(), None, now=event.occurred_at, context_emotions=rows)
    value["relationship"] = {"score": 50, "raw_score": 500, "description": "很长的关系说明" * 2000}
    encoded = serialize_expression(value)
    assert len(encoded) <= 4000
    parsed = json.loads(encoded)
    assert parsed["bot"]["pleasure"] == 0 and parsed["relationship"]["score"] == 50
    assert len(json.loads(serialize_expression(expression_context(
        BotAffect(), None, now=event.occurred_at, context_emotions=rows)))["bot"][
            "context_emotions"]) == 1


def test_seeded_timing_sequences_remain_bounded_and_never_renew(le_event):
    rng = random.Random(20261116)
    state, at, deadline = None, 0, None
    for index in range(120):
        at += rng.randrange(1, 70)
        body = "你" + ("真" * (index % 4)) + "好可爱"
        result, event = transition(le_event, body, state, offset=at)
        state = result["state"]
        assert len(json.dumps(state, ensure_ascii=True)) <= 4096
        assert all(0 <= r["intensity"] <= .60 for r in state["items"])
        if state["items"] and deadline is None:
            deadline = state["items"][0]["expires_at"]
        if state["items"] and event.occurred_at < deadline:
            assert state["items"][0]["expires_at"] == deadline
