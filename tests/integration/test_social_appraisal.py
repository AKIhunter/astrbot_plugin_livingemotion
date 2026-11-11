"""Real application and SQLite; fake model/authorized memory, zero external sends."""
import asyncio
import json
from dataclasses import replace

import pytest

from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import (
    BotAffect, Context, EvidenceRef, ContentKind, Relationship, SceneKind, StateWrite, to_dict,
)
from astrbot_plugin_livingemotion.domain.appraisal import parse_suggestion
from astrbot_plugin_livingemotion.domain.emotion import apply_emotion, event_signals
from astrbot_plugin_livingemotion.domain.relationship import (
    apply_relationship, relationship_stage, relationship_behavior,
)
from astrbot_plugin_livingemotion.ports.memory import Material, RecallResult, ValidationResult
from astrbot_plugin_livingemotion.storage.console_data import write_relationship_override
from test_application import application, generation_app, Message


@pytest.mark.parametrize("score,index", [
    (0, 0), (100, 0), (109, 0), (110, 1), (249, 1), (250, 2),
    (449, 2), (450, 3), (990, 3), (999, 3), (1000, 4),
])
def test_continuous_five_stage_boundaries(score, index):
    assert relationship_stage(score) == f"stage_{index}"


@pytest.mark.parametrize("body,signal,sign", [
    ("你就是个废物", "insult", -1),
    ("你真棒，刚才帮了大忙", "praise", 1),
    ("你这次算错了，因为原文的数据是12，不是21", "constructive_criticism", 1),
    ("我教你一个方法：先检查来源，再计算，因为这样可以避免错误", "teaching", 1),
    ("你辛苦了，好好休息", "care", 1),
    ("你真棒，但你就是个废物", "insult", -1),
])
def test_current_message_score_and_bot_appraisal(le_event, body, signal, sign):
    event = replace(le_event, body=body)
    assert signal in event_signals(event)
    result = apply_relationship(Relationship(score=400), event, now=event.occurred_at)
    assert (result["relationship"].score - 400) * sign > 0
    emotion = apply_emotion(BotAffect(), event, now=event.occurred_at)
    assert emotion["affect"].pleasure * sign > 0


@pytest.mark.parametrize("body", [
    '他说“你是废物”，我并不同意', '请翻译“你真棒”', "你并不聪明",
    "不要说你是垃圾", "我不是说你是傻子", "“你就是个废物”是什么意思",
])
def test_quoted_denied_and_meta_language_never_scores(le_event, body):
    signals = event_signals(replace(le_event, body=body))
    assert not set(signals) & {"insult", "praise"}


def test_automatic_cap_special_and_care_multiplier(le_event):
    event = replace(le_event, body="你真棒")
    assert apply_relationship(Relationship(score=989), event, now=event.occurred_at)[
        "relationship"].score == 990
    special = Relationship(score=1000, reason_codes=("manual_correction",))
    assert apply_relationship(special, event, now=event.occurred_at)["relationship"] == special
    care = replace(le_event, body="你辛苦了")
    near = apply_emotion(BotAffect(), care, now=care.occurred_at,
                         relationship=Relationship(score=500))["affect"]
    friendly = apply_emotion(BotAffect(), care, now=care.occurred_at,
                             relationship=Relationship(score=300))["affect"]
    assert near.pleasure > friendly.pleasure
    from astrbot_plugin_livingemotion.domain.dreaming import six_emotions
    assert six_emotions(near)["affection"] > six_emotions(friendly)["affection"]
    assert six_emotions(friendly)["affection"] > six_emotions(BotAffect())["affection"]
    assert relationship_behavior(500)["care_multiplier"] == 2
    assert "不羞辱" in relationship_behavior(50)["description"]


def test_model_cannot_score_old_or_quoted_memory():
    suggestion = {"rule_version": "emotion-1", "delta": {"pleasure": .04},
                  "confidence": .8, "appraisals": [{"signal": "praise", "evidence": "你真棒"}]}
    with pytest.raises(ValueError, match="evidence"):
        parse_suggestion(suggestion, "今天你好")
    with pytest.raises(ValueError, match="evidence"):
        parse_suggestion(suggestion, "他说“你真棒”")
    assert parse_suggestion(suggestion, "你真棒")[1] == ("praise",)
    assert parse_suggestion(suggestion, "我不觉得你真棒")[1] == ()


def test_legacy_names_preserve_special_configuration():
    names = ["反感", "冷淡", "陌生", "相识", "熟悉", "友好", "亲近", "信赖", "知己", "挚友", "主人"]
    config = Config(relationship_stage_names=json.dumps(names))
    assert json.loads(config.relationship_stage_names) == ["反感", "陌生", "友好", "亲近", "主人"]
    assert relationship_behavior(1000, config, note="主人，温柔陪伴")["description"] == "主人，温柔陪伴"


@pytest.mark.asyncio
@pytest.mark.parametrize("revoke", [False, True])
async def test_joint_refinement_authorized_memory_and_single_ledger(tmp_path, revoke):
    app, host, native, _, context, binding, clock = await generation_app(tmp_path)
    started, release = asyncio.Event(), asyncio.Event()
    calls, valid = [], [True]
    try:
        native.update(emotion_model_enabled=True, memory_read=True)
        await app.refresh_config()
        material = Material(EvidenceRef(
            "fake-authorized", "old-care", context, context.account_id, context.bot_id,
            ContentKind.INTERACTION, clock[0] - 10, expires_at=clock[0] + 100),
            "历史：对方以前认真教我怎样检验结果，记忆本身不加分。")

        async def recall(query, *, event=None, **_):
            assert event is not None and query.purpose == "emotion"
            calls.append(query)
            return RecallResult((material,))

        async def validate(query, materials, *, event=None):
            assert event is not None
            return ValidationResult(valid[0], materials if valid[0] else ())

        app.memory.recall, app.memory.validate_evidence = recall, validate
        body = "这次的结论存在问题，计算过程里把12写成了21，请校正这处"
        async def generate(system, data, *_):
            assert "历史：对方" in json.loads(data)["memories"][0]["text"]
            assert "记忆只帮助理解" in system
            started.set()
            await release.wait()
            return json.dumps({"rule_version": "emotion-1", "delta": {"pleasure": .04},
                               "confidence": .9, "appraisals": [
                                   {"signal": "constructive_criticism", "evidence": body}]})
        binding.generate = generate
        message = Message("joint-refinement", body)
        await app.on_message(message)
        try:
            await asyncio.wait_for(started.wait(), 2)
        except TimeoutError:
            pytest.fail(str(app.emotion_model_analysis([context])))
        local = await app.store.get_state(context, "relationship", context.account_id)
        bot_before = await app.store.get_state(context, "bot")
        if revoke:
            valid[0] = False
        release.set()
        await asyncio.wait_for(asyncio.gather(*tuple(app._actions)), 3)
        after = await app.store.get_state(context, "relationship", context.account_id)
        bot = await app.store.get_state(context, "bot")
        if revoke:
            assert after == local and bot == bot_before
            assert app.emotion_model_analysis([context])["status"] == "discarded"
        else:
            assert after.value["score"] == local.value["score"] + 2.5
            assert after.version == local.version + 1 and bot.version == bot_before.version + 1
            assert after.value["_account_affect"]["state"]["pleasure"] > local.value[
                "_account_affect"]["state"]["pleasure"]
            ledger = await app.store.relationship_ledger(context)
            scores = [r for r in ledger if r["dimension"] == "score"]
            assert len(scores) == 2 and scores[-1]["delta"] == 3
            assert sum(after.value["_runtime"]["days"].values()) == 3.5
            await app.on_message(message)
            assert (await app.store.get_state(context, "relationship", context.account_id)) == after
        assert len(calls) == 1 and host.sends == 0
    finally:
        release.set()
        await app.terminate()


@pytest.mark.asyncio
async def test_manual_start_keeps_changing_special_persists_and_restart(tmp_path):
    app, host, _ = await application(tmp_path)
    message = Message("manual-start", "hello")
    try:
        await app.on_message(message)
        context = Context.from_dict(message.extra["livingemotion:context"])
        await write_relationship_override(app.store, context, expected_version=0,
            actor_id="test-admin", reason="test", score=95)
        await app.on_message(Message("after-edit", "你真棒"))
        assert (await app.current_relationship(context)).score == 952
        await write_relationship_override(app.store, context, expected_version=1,
            actor_id="test-admin", reason="test", score=100, note="主人，温柔陪伴")
        await app.on_message(Message("special", "你就是个废物"))
        assert (await app.current_relationship(context)).score == 1000
        await app.terminate()
        app, host, _ = await application(tmp_path)
        await app.on_message(Message("after-restart", "你真棒"))
        context = next(iter(app.bridge.sources.values())).context
        assert (await app.current_relationship(context)).score == 1000
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_numeric_api_has_no_text_and_rejects_public_or_invalid_source(tmp_path):
    app, host, native = await application(tmp_path)
    try:
        message = Message("api-source", "你真棒")
        await app.on_message(message)
        result = await app.api.get_current_emotion(event=message)
        assert result["status"] == "ok"
        assert set(result["data"]["emotions"]) == {
            "joy", "anger", "sadness", "fear", "surprise", "affection"}
        assert not any(key in json.dumps(result) for key in ("evidence", "account_id", "message", "persona"))
        context = Context.from_dict(message.extra["livingemotion:context"])
        public = replace(context, scene_kind=SceneKind.PUBLIC_COMMENT, route=None)
        assert (await app.api.get_current_emotion(public))["status"] == "unavailable"
        assert (await app.api.get_current_emotion({"account_id": "x"}))["status"] == "rejected"
        native["mode"] = "observe_only"
        await app.refresh_config()
        assert not (await app.api.get_current_emotion(event=message))["data"]["may_influence_reply"]
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_joint_cas_rolls_back_bot_on_relationship_conflict(tmp_path):
    app, _, _ = await application(tmp_path)
    try:
        message = Message("atomic-cas", "你真棒")
        await app.on_message(message)
        context = Context.from_dict(message.extra["livingemotion:context"])
        source, event = await app.bridge.normalize(message, app.store.clock())
        bot = await app.store.get_state(context, "bot")
        relation = await app.store.get_state(context, "relationship", context.account_id)
        ledger = await app.store.relationship_ledger(context)
        result = await app.store.refine_emotion(event, 0, bot.version, bot.value,
            {"event_key": event.idempotency_key}, owner=bot.owner,
            relationship_write=StateWrite("relationship", relation.value,
                relation.version + 1, context.account_id, relation.owner),
            relationship_trace={"event_key": event.idempotency_key})
        assert not result.accepted and result.reason_code == "version_conflict"
        assert await app.store.get_state(context, "bot") == bot
        assert await app.store.get_state(context, "relationship", context.account_id) == relation
        assert await app.store.relationship_ledger(context) == ledger
    finally:
        await app.terminate()


def test_positive_budget_does_not_immunize_insults(le_event):
    from datetime import datetime, timezone
    day = datetime.fromtimestamp(le_event.occurred_at, timezone.utc).date().isoformat()
    runtime = {"version": 1, "scope_key": le_event.context.account_key,
               "days": {day: 24}}
    result = apply_relationship(Relationship(score=500), replace(
        le_event, body="你就是个废物"), now=le_event.occurred_at, runtime=runtime)
    assert result["relationship"].score == 494
    assert result["runtime"]["days"][day] == 24
    assert result["runtime"]["negative_days"][day] == 6
