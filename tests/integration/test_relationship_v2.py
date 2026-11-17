"""V2 acceptance: final display motion, native addressee and durable accounting."""
from dataclasses import replace
from datetime import datetime, timezone
import json

import pytest

from astrbot_plugin_livingemotion.contracts import Relationship, SceneKind
from astrbot_plugin_livingemotion.domain.appraisal import parse_suggestion
from astrbot_plugin_livingemotion.domain.relationship import (
    RelationshipPolicy, apply_relationship, relationship_evidence,
)
from test_application import Message, application


TEXT_CASES = [
    ("今天收工了，我很开心", 0),
    ("我很难过", 0),
    ("今天温度20度", 0),
    ("你好", 0),
    ("他很感谢你", 0),
    ("我朋友说你是废物", 0),
    ('他说“你是废物”，我并不同意', 0),
    ("不要说你是垃圾", 0),
    ("你不是废物", 0),
    ("我不觉得你真棒", 0),
    ("请翻译“谢谢你”", 0),
    ("谢谢你", .5),
    ("你真棒", .5),
    ("你真聪明，这次解释说得好", .5),
    ("对不起，我不该骂你", .5),
    ("向你道歉，我刚才误会你了", .5),
    ("对不起，我迟到了", 0),
    ("我不会向你道歉", 0),
    ("对不起才怪，我不该骂你", 0),
    ("你这里算错了，因为原文是12，不是21", .5),
    ("我教你一个方法：先检查来源，再计算，因为这样可以避免错误", .5),
    ("尊重你的边界", .5),
    ("我不尊重你的边界", 0),
    ("你辛苦了，好好休息", 1),
    ("我可以帮你问问", 1),
    ("我不想关心你", 0),
    ("我关心你", 1),
    ("谢谢你，我关心你", 1),
    ("你是废物", -1),
    ("闭嘴，不然我就把你的账号封了", -1),
    ("我不会把你的账号封了", 0),
    ("你真棒，但你就是个废物", -1),
    ("谢谢你，不然我就封你的号", -1),
    ("你很烦人", -.5),
    ("不管你的边界", -.5),
    ("答应你的事已经完成", 1),
    ("答应你的事我故意不做", -1),
    ('“你是废物”。谢谢你', .5),
]


@pytest.mark.parametrize("body,expected", TEXT_CASES)
def test_text_scores_at_normal_seed(le_event, body, expected):
    event = replace(le_event, body=body)
    result = apply_relationship(Relationship(score=500), event, now=event.occurred_at)
    actual = (result["relationship"].score - 500) / 10
    assert actual == expected, result
    assert actual == 0 or .5 <= abs(actual) <= 1
    assert sum(c.delta for c in result["contributions"] if c.dimension == "score") == actual * 10
    assert result["trace"]["delta_display"] == actual


@pytest.mark.parametrize("confidence,expected", [(0, 0), (.64, 0), (.65, .5), (.8, .5), (1, .5)])
def test_confidence_gates_without_fractional_points(le_event, confidence, expected):
    result = apply_relationship(Relationship(score=500),
        replace(le_event, body="谢谢你", confidence=confidence), now=le_event.occurred_at)
    assert (result["relationship"].score - 500) / 10 == expected


@pytest.mark.parametrize("score,body,expected", [
    (989, "谢谢你", 0), (986, "谢谢你", 0), (985, "谢谢你", .5),
    (983, "我关心你", .7), (1, "你是废物", 0),
    (4, "你是废物", 0), (5, "你是废物", -.5), (7, "你是废物", -.7),
    (999, "谢谢你", 0),
])
def test_score_room_never_writes_small_tail(le_event, score, body, expected):
    result = apply_relationship(Relationship(score=score),
        replace(le_event, body=body), now=le_event.occurred_at)
    assert (result["relationship"].score - score) / 10 == expected


@pytest.mark.parametrize("negative", [False, True])
@pytest.mark.parametrize("available,expected", [(0, 0), (4, 0), (5, .5), (7, .7), (10, 1)])
def test_daily_remainder_and_independent_buckets(le_event, negative, available, expected):
    day = datetime.fromtimestamp(le_event.occurred_at, timezone.utc).date().isoformat()
    bucket = "negative_days" if negative else "days"
    opposite = "days" if negative else "negative_days"
    runtime = {"version": 1, "scope_key": le_event.context.account_key,
               bucket: {day: 24 - available}, opposite: {day: 24}}
    result = apply_relationship(Relationship(score=500),
        replace(le_event, body="你是废物" if negative else "我关心你"),
        now=le_event.occurred_at, runtime=runtime)
    assert (result["relationship"].score - 500) / 10 == (-expected if negative else expected)
    assert result["runtime"][opposite][day] == 24
    assert result["runtime"][bucket][day] == 24 - available + expected * 10


@pytest.mark.parametrize("field", ["event_cap", "similar_budget", "daily_budget"])
def test_policy_below_minimum_disables_motion(le_event, field):
    result = apply_relationship(Relationship(score=500), replace(le_event, body="谢谢你"),
        now=le_event.occurred_at, policy=RelationshipPolicy(**{field: 4}))
    assert result["relationship"].score == 500
    assert not result["contributions"]


@pytest.mark.parametrize("frozen,special", [(True, False), (False, True)])
def test_protected_relationship_consumes_duplicate_guard(le_event, frozen, special):
    state = Relationship(score=1000 if special else 500, frozen=frozen,
                         reason_codes=("manual_correction",) if special else ())
    event = replace(le_event, body="你是废物")
    first = apply_relationship(state, event, now=event.occurred_at)
    assert first["relationship"] == state
    second = apply_relationship(replace(state, frozen=False, score=500, reason_codes=()),
        event, now=event.occurred_at, runtime=json.loads(json.dumps(first["runtime"])))
    assert second["reason_codes"] == ("duplicate_event",)
    assert second["relationship"].score == 500


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,target,expected", [
    ("none", "", 0), ("At", "bot-account", .5), ("Reply", "bot-account", .5),
    ("At", "someone-else", 0), ("Reply", "someone-else", 0),
    ("both", "bot-account", 0),
])
async def test_native_group_target_and_ledger(tmp_path, kind, target, expected):
    app, host, _ = await application(tmp_path)
    try:
        message = Message("seed", group="room")
        await app.on_message(message)
        context = next(iter(app.bridge.sources.values())).context
        before = await app.current_relationship(context)
        message = Message("evidence", body="谢谢你", group="room")
        parts = [] if kind == "none" else [
            type("Reply" if kind == "Reply" else "At", (), {
                "sender_id" if kind == "Reply" else "qq": target})()]
        if kind == "both":
            parts.append(type("At", (), {"qq": "someone-else"})())
        message.message_obj.message = parts
        _, event = await app.bridge.normalize(message, app.store.clock())
        assert bool(relationship_evidence(event)[0]) == bool(expected)
        await app.on_message(message)
        after = await app.current_relationship(context)
        assert (after.score - before.score) / 10 == expected
        await app.on_message(message)
        assert (await app.current_relationship(context)).score == after.score
        scores = [r for r in await app.store.relationship_ledger(context) if r["dimension"] == "score"]
        assert len(scores) == bool(expected)
        assert host.sends == 0
    finally:
        await app.terminate()


def test_group_you_without_native_target_cannot_be_rescued_by_model(le_event):
    group = replace(le_event.context, scene_kind=SceneKind.GROUP)
    event = replace(le_event, context=group, body="你真棒", signals=("praise",))
    result = apply_relationship(Relationship(score=500), event, now=event.occurred_at)
    assert result["relationship"].score == 500
    assert result["reason_codes"] == ("relationship_subject_unknown",)


def test_private_explicit_other_target_is_not_bot(le_event):
    event = replace(le_event, body="谢谢你", signals=("native_other_target",))
    assert relationship_evidence(event) == ((), "relationship_subject_unknown")


@pytest.mark.parametrize("score", [508.2, 507.9, 512.2, 500.05])
def test_legacy_fractional_scores_do_not_fail_on_machine_rounding(le_event, score):
    result = apply_relationship(Relationship(score=score),
        replace(le_event, body="我关心你"), now=le_event.occurred_at)
    assert result["relationship"].score - score == pytest.approx(10, abs=1e-9)
    assert result["trace"]["delta_display"] == 1


def test_neutral_messages_cannot_block_first_explicit_threat(le_event):
    state, runtime = Relationship(score=500), None
    for n in range(3):
        event = replace(le_event, event_id=f"neutral-{n}", source_id=f"neutral-{n}",
                        occurred_at=le_event.occurred_at+n, body=f"今天{n}度")
        result = apply_relationship(state, event, now=event.occurred_at, runtime=runtime)
        state, runtime = result["relationship"], result["runtime"]
    threat = replace(le_event, event_id="threat", source_id="threat",
                     occurred_at=le_event.occurred_at+4, body="把你的账号封了")
    result = apply_relationship(state, threat, now=threat.occurred_at, runtime=runtime)
    assert result["relationship"].score == 490


@pytest.mark.parametrize("body,signal,expected", [
    ("对不起，我不该骂你", "apology", ("apology",)),
    ("我不觉得你真棒", "praise", ()),
    ("尊重你的边界", "boundary_respected", ("boundary_respected",)),
    ("今天天气晴朗", "insult", ()),
    ("把你的账号封了", "threat", ("threat",)),
])
def test_refinement_requires_literal_current_asserted_evidence(body, signal, expected):
    value = {"rule_version": "emotion-2", "confidence": .8, "delta": {"pleasure": 0},
             "appraisals": [{"signal": signal, "evidence": body}]}
    assert parse_suggestion(value, body)[1] == expected
