"""Deterministic evidence, holder, time, duplication and compatibility regressions."""
from dataclasses import replace
import json
import random

import pytest

from astrbot_plugin_livingemotion.contracts import (
    ActorRole, BotAffect, ContextAppraisal, Relationship, to_dict,
)
from astrbot_plugin_livingemotion.domain.context_emotion import (
    POLICIES, apply_context_emotions, apply_deferred_context_emotions,
    apply_realtime_context_emotions, context_help_topic, empty_state, expression_items,
    human_labels, parse_context_appraisals, read_state,
)
from astrbot_plugin_livingemotion.domain.emotion_evidence import select_dialogue
from astrbot_plugin_livingemotion.domain.emotion import (
    apply_emotion, expression_context, serialize_expression,
)

HELP = "谢谢你帮我解决了路由超时"
DENIAL = "你从没帮我解决路由超时"
REPAIR = "路由超时确实是你帮我解决的，刚才那句我收回，对不起"
WARM = "你真的好可爱。我喜欢跟你待在一起。"
HURT = "你就是个废物"


def deferred(state, event, *appraisals, at=None, **kwargs):
    return apply_deferred_context_emotions(
        state, event, Relationship(score=500), now=event.occurred_at if at is None else at,
        appraisals=appraisals, **kwargs)


def history(ref, text, at, *, role="human"):
    return {"ref": ref, "event_id": ref, "role": role, "text": text, "at": at}


def transition(event, body, state=None, *, offset=0, score=500, **kwargs):
    at = event.occurred_at + offset
    event = replace(event, source_id="source-" + str(offset), body=body, occurred_at=at)
    return apply_realtime_context_emotions(state, event, Relationship(score=score),
                                           now=at, enabled=True, **kwargs), event


@pytest.mark.parametrize("body,kind", [
    ("你就是个废物", "hurt"),
    (DENIAL + "。你就是个废物", "hurt"),
    ("虽然你没做错，但我就是要怪你", "wronged"),
    (WARM, "shyness"),
])
def test_explicit_current_evidence(le_event, body, kind):
    result, _ = transition(le_event, body)
    assert result["applied"]
    assert [r["kind"] for r in result["state"]["items"]] == [kind]
    assert result["state"]["items"][0]["holder"] == "bot"
    assert result["state"]["items"][0]["target"] == le_event.context.account_id


@pytest.mark.parametrize("body", [
    '他说“我喜欢你”', '请翻译“你就是废物”', "他说我喜欢你",
    "你不是废物", "我不是说你没用", "你好可爱", "我不喜欢你", "我喜欢你写的代码",
    "代码写得好", "你的计算错了，因为原文是12", "如何实现害羞情绪",
    "我害羞了", "我被老板骂了，好委屈", "比如你从来没帮过我", "你从来没帮过我", DENIAL,
    "你说他是废物", "你觉得我是废物",
    "你觉得我好可爱", "你说她很可爱",
])
def test_counterexamples_do_not_create_bot_feelings(le_event, body):
    result, _ = transition(le_event, body)
    assert not result["state"]["items"]


def test_help_acknowledgement_is_proof_not_a_feeling(le_event):
    helped, _ = transition(le_event, HELP)
    assert not helped["state"]["items"] and helped["state"]["support"]
    unrelated, _ = transition(le_event, "你从没帮我解决路由配置", helped["state"], offset=1)
    vague, _ = transition(le_event, "你从来没帮过我", helped["state"], offset=1)
    assert not unrelated["state"]["items"] and not vague["state"]["items"]
    result, _ = transition(le_event, DENIAL, helped["state"], offset=1)
    assert [r["kind"] for r in result["state"]["items"]] == ["wronged"]
    assert len(result["state"]["items"][0]["evidence_refs"]) == 2


def test_expired_help_proof_does_not_create_wronged(le_event):
    helped, _ = transition(le_event, HELP)
    result, _ = transition(le_event, DENIAL, helped["state"], offset=86401)
    assert not result["state"]["items"]


@pytest.mark.parametrize("prior", [
    "小王发来一句话：" + HELP,
    "我听小王说过：" + HELP,
    "我替朋友感谢你帮我解决了路由超时",
    "客户写道，" + HELP,
    "同事说" + HELP,
    f"有人说：「{HELP}」",
    "如果真解决了，" + HELP,
    "谢谢你明天帮我解决路由超时",
    "谢谢你帮我解决了问题",
])
def test_reported_prospective_or_vague_help_is_not_live_or_packed_proof(le_event, prior):
    first, _ = transition(le_event, prior)
    assert not context_help_topic(prior)
    assert not first["state"]["support"]
    assert not transition(le_event, DENIAL, first["state"], offset=1)[0]["state"]["items"]
    selected = select_dialogue(DENIAL, [history("prior", prior, 100)], at=101)
    assert not any(item.help_proof for item in selected.rows)


def test_packed_proof_requires_prior_human_same_exact_topic(le_event):
    same = history("same", HELP, 100)
    same_time = history("same-time", HELP, 101)
    other = history("other", "谢谢你帮我解决了路由配置", 100)
    bot = history("bot", HELP, 100, role="bot")
    for row in (other, same_time, bot):
        assert not any(x.help_proof for x in select_dialogue(DENIAL, [row], at=101).rows)
    assert [row.ref for row in select_dialogue(DENIAL, [same], at=101).rows if row.help_proof] == ["same"]
    _, event = transition(le_event, DENIAL)
    judgement = ContextAppraisal("wronged", "devalued_contribution", DENIAL, context_refs=("ref",))
    assert not deferred(None, event, judgement, support_refs=("ref",), help_refs={"ref": ""})["applied"]
    assert not deferred(None, event, judgement, support_refs=("ref",),
                        help_refs={"ref": context_help_topic(other["text"])})["applied"]


@pytest.mark.parametrize("kind,cause,independent", [
    ("hurt", "direct_devaluation", HURT),
    ("wronged", "admitted_unfair_blame", "你没做错，但我就是要怪你"),
])
def test_model_cannot_relabel_explicit_denial_but_independent_evidence_survives(
        le_event, kind, cause, independent):
    _, denial = transition(le_event, DENIAL)
    _, event = transition(le_event, DENIAL + "。" + independent, offset=1)
    invalid = ContextAppraisal(kind, cause, DENIAL)
    valid = ContextAppraisal(kind, cause, independent)
    assert not deferred(None, denial, invalid)["applied"]
    assert not deferred(None, event, invalid)["applied"]
    assert deferred(None, event, valid)["state"]["items"][0]["kind"] == kind


def test_repair_ends_the_old_incident_but_a_new_denial_can_sting(le_event):
    helped, _ = transition(le_event, HELP)
    first, original = transition(le_event, DENIAL, helped["state"], offset=1)
    repeat, _ = transition(le_event, DENIAL, first["state"], offset=2)
    assert not repeat["applied"]
    insincere, _ = transition(
        le_event, "路由超时确实是你帮我解决的才怪", repeat["state"], offset=2.5)
    assert not insincere["applied"]
    repaired, repair_event = transition(le_event, REPAIR, repeat["state"], offset=3)
    tied = replace(original, source_id="tied-denial", occurred_at=repair_event.occurred_at)
    assert not apply_context_emotions(
        repaired["state"], tied, Relationship(score=500), now=tied.occurred_at,
        enabled=True)["applied"]
    new, event = transition(le_event, DENIAL, repaired["state"], offset=4)
    new_row, = new["state"]["items"]
    assert new_row["intensity"] > repaired["state"]["items"][0]["intensity"]
    assert new_row["incident_key"] != first["state"]["items"][0]["incident_key"]
    assert new_row["started_at"] == event.occurred_at
    assert not transition(le_event, DENIAL, new["state"], offset=5)[0]["applied"]
    appraisal = ContextAppraisal("wronged", "devalued_contribution", DENIAL,
                                 context_refs=(helped["state"]["support"][0]["ref"],))
    assert not apply_deferred_context_emotions(
        new["state"], original, Relationship(score=500), now=event.occurred_at,
        appraisals=(appraisal,))["applied"]
    other = replace(event, context=replace(event.context, account_id="other"), actor_id="other")
    assert not apply_context_emotions(
        repaired["state"], other, Relationship(score=500), now=event.occurred_at,
        enabled=True)["applied"]


def test_repairing_active_topic_a_does_not_supersede_pending_topic_b(le_event):
    helped, _ = transition(le_event, HELP)
    active, _ = transition(le_event, DENIAL, helped["state"], offset=1)
    other_help = "谢谢你帮我修好了打印机"
    pending, older = transition(le_event, "打印机这次的功劳可不能算你的", offset=2)
    assert not pending["applied"]
    repaired, repair_event = transition(le_event, REPAIR, active["state"], offset=3)
    assert repaired["state"]["marks"]["wronged"] == active["state"]["marks"]["wronged"]

    appraisal = ContextAppraisal("wronged", "devalued_contribution", older.body,
                                 context_refs=("packed-b",))
    kwargs = {"support_refs": ("packed-b",), "help_refs": {"packed-b": context_help_topic(other_help)}}
    late = deferred(repaired["state"], older, appraisal, at=repair_event.occurred_at + 1, **kwargs)
    item, = late["state"]["items"]
    assert late["state"]["wronged_topic"] == context_help_topic(other_help)
    assert item["started_at"] == older.occurred_at
    assert not deferred(late["state"], older, appraisal, at=repair_event.occurred_at + 2, **kwargs)["applied"]


@pytest.mark.parametrize("action", ["clear", "decrease"])
def test_deferred_repair_must_match_topic_but_does_not_block_other_kinds(le_event, action):
    helped, _ = transition(le_event, HELP)
    first, _ = transition(le_event, DENIAL, helped["state"], offset=1)
    _, event = transition(le_event, "就之前那件事，我收回那句话。你的存在对我没有价值", offset=2)
    repair = ContextAppraisal("wronged", "devalued_contribution", "就之前那件事，我收回那句话",
                             strength=.2, action=action, context_refs=("packed-proof",))
    harm = ContextAppraisal("hurt", "direct_devaluation", "你的存在对我没有价值")
    args = {"now": event.occurred_at, "appraisals": (repair, harm),
            "support_refs": ("packed-proof",)}
    wrong = apply_deferred_context_emotions(
        first["state"], event, Relationship(), **args,
        help_refs={"packed-proof": context_help_topic("谢谢你帮我修好了打印机")})
    assert {r["kind"] for r in wrong["state"]["items"]} == {"wronged", "hurt"}
    assert wrong["state"]["items"][0] == wrong["trace"]["before"][0]
    assert "context_help_topic_mismatch" in wrong["trace"]["reason_codes"]
    right = apply_deferred_context_emotions(
        first["state"], event, Relationship(), **args,
        help_refs={"packed-proof": context_help_topic(HELP)})
    values = {row["kind"]: row["intensity"] for row in right["state"]["items"]}
    assert "hurt" in values
    if action == "clear":
        assert "wronged" not in values
    else:
        assert values["wronged"] == pytest.approx(right["trace"]["before"][0]["intensity"] - .2)


@pytest.mark.parametrize("action", ["clear", "decrease"])
@pytest.mark.parametrize("apology", [
    "对不起，是我误会你了",
    "对不起，我不该说你是主讲人",
    "同事说：我不该骂你",
    "我引用了「我不该骂你」",
    "如果我不该骂你，我会道歉",
    "对不起才怪，我不该骂你",
    "我为会议迟到向你道歉",
    "关于会议迟到，我收回之前给你的安排",
])
def test_unrelated_or_unreliable_apology_cannot_repair_hurt_locally_or_by_model(
        le_event, action, apology):
    hurt, incident = transition(le_event, HURT)
    reply, event = transition(le_event, apology, hurt["state"], offset=1)
    assert not reply["applied"]
    repair = ContextAppraisal("hurt", "direct_devaluation", apology, action=action,
                              context_refs=(incident.idempotency_key,))
    calibrated = deferred(reply["state"], event, repair, support_refs=(incident.idempotency_key,))
    assert not calibrated["applied"]
    assert calibrated["state"]["items"] == calibrated["trace"]["before"]


@pytest.mark.parametrize("action", ["clear", "decrease"])
def test_a_local_repair_is_not_repeated_by_model_and_late_hurt_stays_repaired(le_event, action):
    hurt, _ = transition(le_event, HURT)
    _, pending = transition(le_event, "你的存在对我没有价值", offset=1)
    local, event = transition(le_event, "对不起，我刚才不该骂你", hurt["state"], offset=2)
    assert local["trace"]["reason_codes"] == ["context_cause_repaired"]
    assert local["state"]["items"][0]["intensity"] == pytest.approx(
        local["trace"]["before"][0]["intensity"] * .4)
    repair = ContextAppraisal("hurt", "direct_devaluation", "我刚才不该骂你", action=action)
    assert not deferred(local["state"], event, repair, at=event.occurred_at + 301)["applied"]
    appraisal = ContextAppraisal("hurt", "direct_devaluation", pending.body)
    assert "context_cause_already_repaired" in deferred(
        local["state"], pending, appraisal, at=event.occurred_at + 301)["trace"]["reason_codes"]


def test_pointed_semantic_hurt_repair_requires_active_incident_reference(le_event):
    hurt, incident = transition(le_event, HURT)
    body = "刚才那样说不妥，我收回那句话"
    _, event = transition(le_event, body, offset=1)
    appraisal = ContextAppraisal("hurt", "direct_devaluation", body, action="clear")
    assert not deferred(hurt["state"], event, appraisal)["applied"]
    linked = replace(appraisal, context_refs=(incident.idempotency_key,))
    assert not deferred(hurt["state"], event, linked)["applied"]
    assert deferred(hurt["state"], event, linked,
                    support_refs=linked.context_refs)["trace"]["reason_codes"] == ["context_hurt_cleared"]


@pytest.mark.parametrize("body,linked", [
    ("我收回刚才那句不想再搭理你的说法", True),
    ("我收回刚才关于不想再搭理你的说法", True),
    ("我收回刚才不想再搭理你那句话", True),
    ("我收回刚才关于会议迟到的说法", False),
])
def test_named_semantic_repair_checks_words_from_the_linked_incident(le_event, body, linked):
    _, incident = transition(le_event, "我不想再搭理你")
    hurt = deferred(None, incident, ContextAppraisal("hurt", "direct_devaluation", incident.body))
    _, event = transition(le_event, body, offset=1)
    ref = incident.idempotency_key
    appraisal = ContextAppraisal("hurt", "direct_devaluation", body, action="clear", context_refs=(ref,))
    assert not deferred(hurt["state"], event, appraisal, support_refs=(ref,))["applied"]
    result = deferred(hurt["state"], event, appraisal, support_refs={ref: incident.body})
    assert result["applied"] is linked
    assert bool(result["state"]["items"]) is not linked


@pytest.mark.parametrize("score,maximum", [(200, 0), (300, .25), (500, .60)])
def test_shyness_respects_relationship_stage(le_event, score, maximum):
    result, _ = transition(le_event, WARM, score=score)
    values = result["state"]["items"]
    assert bool(values) == bool(maximum)
    assert max((r["intensity"] for r in values), default=0) <= maximum


def test_explicit_boundary_blocks_and_clears_shyness(le_event):
    result, _ = transition(le_event, WARM, relationship_note="只聊工作，保持专业")
    assert not result["state"]["items"]
    shy, _ = transition(le_event, WARM)
    cleared, _ = transition(le_event, "正常聊就好", shy["state"], offset=1)
    assert not cleared["state"]["items"]


@pytest.mark.parametrize("release", [
    "我不介意暧昧的文案",
    "不用再只聊工作了",  # The active restriction is about intimacy, not work.
    "同事说：我收回之前的别暧昧的要求",
    "他写道：「我收回之前的要求，现在可以暧昧了」。",
    "如果不用再保持专业了，就轻松一点",
    "可以参考保持专业的文档",
    "我收回之前的要求，现在可以暧昧了。开玩笑的。",
    "我收回之前的要求，现在可以暧昧了，才怪。",
])
def test_unrelated_or_reported_release_leaves_boundary_active_across_round_trip(le_event, release):
    warm, _ = transition(le_event, WARM)
    boundary = "我希望接下来我们别再暧昧了"
    protected, _ = transition(le_event, boundary, warm["state"], offset=1)
    stored = json.loads(json.dumps(protected["state"]))
    assert stored["boundary"] and not stored["items"]
    unchanged, _ = transition(le_event, release, stored, offset=2)
    assert unchanged["state"]["boundary"]
    assert not transition(le_event, WARM, unchanged["state"], offset=3)[0]["state"]["items"]
    rows = [history("set", boundary, 100), history("unrelated", release, 101)]
    assert [r.ref for r in select_dialogue(WARM, rows, at=102).rows if r.boundary] == ["set"]


def test_matching_new_release_never_restores_old_shyness(le_event):
    warm, _ = transition(le_event, WARM)
    _, pending = transition(le_event, "突然想把脸靠近一点", offset=1)
    protected, setting = transition(le_event, "接下来我们只谈工作，保持专业", warm["state"], offset=2)
    same_time, _ = transition(le_event, "不用再只谈工作了", protected["state"], offset=2)
    assert same_time["state"]["boundary"]
    released, withdrawal = transition(le_event, "现在不用再只谈工作了", protected["state"], offset=3)
    assert not released["state"]["boundary"] and not released["state"]["items"]
    assert not deferred(released["state"], pending,
                        ContextAppraisal("shyness", "warm_attention", pending.body),
                        at=withdrawal.occurred_at)["applied"]
    assert not expression_items(released["state"], setting.context, now=withdrawal.occurred_at)
    assert transition(le_event, WARM, released["state"], offset=4)[0]["state"]["items"]
    rows = [history("set", setting.body, 100), history("release", withdrawal.body, 101)]
    assert not any(row.boundary for row in select_dialogue(WARM, rows, at=102).rows)


def test_independent_boundary_is_not_removed_when_another_is_released(le_event):
    work, _ = transition(le_event, "我们只聊工作")
    both, _ = transition(le_event, "以后别暧昧", work["state"], offset=1)
    only_intimacy, _ = transition(le_event, "不用再只聊工作了", both["state"], offset=2)
    assert only_intimacy["state"]["boundary"]
    release, _ = transition(le_event, "我收回之前的要求，现在可以暧昧了", only_intimacy["state"], offset=3)
    assert not release["state"]["boundary"]


@pytest.mark.parametrize("body,evidence", [
    ("小王说，你就是废物", "你就是废物"),
    ("小王说你就是废物", "你就是废物"),
    ("我抄了一句：「你就是废物」", "你就是废物"),
    ("「你就是废物", "你就是废物"),
    ("如果你就是废物呢", "你就是废物"),
])
def test_semantic_excerpt_cannot_strip_away_quote_or_third_party_frame(le_event, body, evidence):
    local, event = transition(le_event, body)
    assert not local["state"]["items"]
    assert not deferred(None, event, ContextAppraisal("hurt", "direct_devaluation", evidence))["applied"]


def test_deferred_kind_ordering_event_time_decay_and_local_dedup(le_event):
    local, event = transition(le_event, WARM + "你的价值还不如零")
    warm = ContextAppraisal("shyness", "warm_attention", "我喜欢跟你待在一起")
    hurt = ContextAppraisal("hurt", "direct_devaluation", "你的价值还不如零", strength=.6)
    at = event.occurred_at + 240
    result = deferred(local["state"], event, warm, hurt, at=at)
    rows = {item["kind"]: item for item in result["state"]["items"]}
    previous = local["state"]["items"][0]
    assert rows["shyness"]["intensity"] == pytest.approx(previous["intensity"] * 2 ** (-240 / 480))
    assert rows["hurt"]["intensity"] == pytest.approx(.6 * 2 ** (-240 / 1800))
    assert rows["hurt"]["started_at"] == event.occurred_at
    assert rows["hurt"]["expires_at"] == event.occurred_at + POLICIES["hurt"][2]
    assert set(result["trace"]["reason_codes"]) == {"context_hurt", "context_event_duplicate"}
    assert not deferred(result["state"], event, warm, hurt, at=at + 1)["applied"]


def test_one_late_kind_can_expire_while_another_remains_eligible(le_event):
    _, event = transition(le_event, "突然想把脸靠近一点。你的存在对我没有价值")
    appraisals = (ContextAppraisal("shyness", "warm_attention", "突然想把脸靠近一点"),
                  ContextAppraisal("hurt", "direct_devaluation", "你的存在对我没有价值"))
    result = deferred(None, event, *appraisals, at=event.occurred_at + POLICIES["shyness"][2])
    assert [row["kind"] for row in result["state"]["items"]] == ["hurt"]
    assert set(result["trace"]["reason_codes"]) == {"context_hurt", "context_kind_expired"}


def test_newer_same_kind_update_blocks_only_that_kind(le_event):
    _, event = transition(le_event, "突然想把脸靠近一点。你的存在对我没有价值")
    warm, _ = transition(le_event, WARM, offset=1)
    ordinary, later = transition(le_event, "那我们继续检查下一项配置", warm["state"], offset=2)
    assert not ordinary["applied"]
    late = deferred(ordinary["state"], event,
                    ContextAppraisal("shyness", "warm_attention", "突然想把脸靠近一点"),
                    ContextAppraisal("hurt", "direct_devaluation", "你的存在对我没有价值"),
                    at=later.occurred_at)
    assert {row["kind"] for row in late["state"]["items"]} == {"hurt", "shyness"}
    assert set(late["trace"]["reason_codes"]) == {"context_hurt", "context_kind_superseded"}


@pytest.mark.parametrize("kind,body,half_life,ttl", [
    ("wronged", "虽然你没做错，但我就是要怪你", 1800, 7200),
    ("shyness", WARM, 480, 2400),
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
    first, event = transition(le_event, WARM)
    duplicate = apply_context_emotions(first["state"], event, Relationship(score=500),
                                      now=event.occurred_at, enabled=True)
    assert duplicate["state"] == first["state"] and not duplicate["applied"]
    repeated, _ = transition(le_event, WARM, first["state"], offset=600)
    assert repeated["state"]["items"][0]["expires_at"] == first["state"]["items"][0]["expires_at"]
    assert not repeated["applied"]


def test_new_stimuli_obey_cooldown_and_growth_cap(le_event):
    first, _ = transition(le_event, WARM)
    limited, _ = transition(le_event, "我真的喜欢你", first["state"], offset=10)
    assert not limited["applied"]
    after, _ = transition(le_event, "我真的喜欢你", first["state"], offset=301)
    decayed = .5 * 2 ** (-301 / 480)
    assert after["state"]["items"][0]["intensity"] <= decayed + .10
    again, _ = transition(le_event, "我很喜欢你", after["state"], offset=302)
    assert not again["applied"]


def test_source_timestamp_and_processing_timestamp_are_separate(le_event):
    first, event = transition(le_event, WARM)
    later = replace(event, source_id="within-second", body="正常聊就好",
                    occurred_at=event.occurred_at + .1)
    result = apply_context_emotions(first["state"], later, Relationship(score=500),
                                    now=event.occurred_at + .9, enabled=True)
    assert not result["state"]["items"]


@pytest.mark.parametrize("repair,expected", [
    ("对不起，我不该贬低你", True),
    ("对不起，但我只是开玩笑，你太敏感", False),
    ("对不起，今天开会迟到了", False),
])
def test_repairs_match_active_account_incident(le_event, repair, expected):
    first, _ = transition(le_event, "你就是个废物")
    result, _ = transition(le_event, repair, first["state"], offset=1)
    decayed = first["state"]["items"][0]["intensity"] * 2 ** (-1 / 1800)
    assert result["state"]["items"][0]["intensity"] == pytest.approx(
        decayed * (.4 if expected else 1))


def test_model_cannot_invent_context_proof_or_change_subject(le_event):
    event = replace(le_event, body="你从来没帮过我")
    appraisal = ContextAppraisal("wronged", "devalued_contribution", event.body,
                                .9, .75, ("invented-proof",))
    raw = {"delta": {"pleasure": 0}, "context_appraisals": [to_dict(appraisal)]}
    legacy, accepted, reasons = parse_context_appraisals(
        raw, event, Relationship(score=500), empty_state())
    assert legacy == {"delta": {"pleasure": 0}} and not accepted and reasons
    result = apply_context_emotions(None, event, Relationship(score=500),
                                    now=event.occurred_at, enabled=True, appraisals=(appraisal,))
    assert not result["state"]["items"]
    # A verbatim excerpt cannot make a foreign holder valid.
    quoted = replace(event, body='他说“你从来没帮过我”')
    raw["context_appraisals"][0]["holder"] = "human"
    _, accepted, _ = parse_context_appraisals(
        raw, quoted, Relationship(score=500), empty_state(), support_refs=("invented-proof",))
    assert not accepted


@pytest.mark.parametrize("change", [
    {"actor_role": ActorRole.BOT}, {"actor_id": "another-account"},
    {"reliable_source": False}, {"event_type": "diary"},
    {"confidence": .5},
])
def test_non_current_or_wrong_actor_cannot_mutate(le_event, change):
    event = replace(le_event, body=WARM, **change)
    result = apply_context_emotions(None, event, Relationship(score=500),
                                    now=event.occurred_at, enabled=True)
    assert not result["applied"] and not result["state"]["items"]


def test_subject_isolation_and_corrupt_optional_metadata(le_event):
    first, event = transition(le_event, WARM)
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
    feeling, event = transition(le_event, WARM)
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
        body = (WARM, "我真的喜欢你", "我很喜欢你", "我特别喜欢你")[index % 4]
        result, event = transition(le_event, body, state, offset=at)
        state = result["state"]
        assert len(json.dumps(state, ensure_ascii=True)) <= 4096
        assert all(0 <= r["intensity"] <= .60 for r in state["items"])
        if state["items"] and deadline is None:
            deadline = state["items"][0]["expires_at"]
        if state["items"] and event.occurred_at < deadline:
            assert state["items"][0]["expires_at"] == deadline
