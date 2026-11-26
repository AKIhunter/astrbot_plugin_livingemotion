"""Offline real Application/SQLite matrix: no provider requests or host sends."""
import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace
from pathlib import Path

import pytest

from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import (
    ContentKind, Context, EvidenceRef, StateWrite, account_person_key,
)
from astrbot_plugin_livingemotion.domain.context_emotion import empty_state, expression_items
from astrbot_plugin_livingemotion.ports.memory import Material, RecallResult, ValidationResult
from astrbot_plugin_livingemotion.runtime.application import SUFFIX, ApplicationError
from astrbot_plugin_livingemotion.runtime.projector import (
    account_context_emotions, attach_context_emotions,
)
from astrbot_plugin_livingemotion.storage.console_data import write_relationship_override
from astrbot_plugin_livingemotion.storage.context_emotions import PERSON_KIND
from test_application import application, generation_app, Message

NOW = 1793919600.0
OPTIONS = {"context_emotions_enabled": True, "promise_enabled": False,
           "weather_factor_enabled": False}


async def local_app(path, **options):
    app, host, native = await application(path, {**OPTIONS, **options})
    clock = [NOW]
    app.store.clock = app.memory.clock = lambda: clock[0]
    return app, host, native, clock


async def ingest(app, identifier, body, **source):
    message = Message(identifier, body, **source)
    await app.on_message(message)
    assert message.extra["livingemotion:ingest"] == "accepted"
    context = Context.from_dict(message.extra["livingemotion:context"])
    record = await app.store.get_state(context, "relationship", context.account_id)
    return message, context, record


def feelings(app, record, context):
    return expression_items(account_context_emotions(
        record, context, now=app.store.clock()), context, now=app.store.clock())


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_local_proof_observation_and_switch(tmp_path, enabled):
    app, host, _, clock = await local_app(tmp_path, context_emotions_enabled=enabled)
    try:
        _, context, proof = await ingest(app, "ack", "谢谢你帮我解决了问题")
        assert not feelings(app, proof, context)
        clock[0] += 1
        message, context, record = await ingest(app, "denial", "你从来没帮过我")
        assert [r["kind"] for r in feelings(app, record, context)] == (["wronged"] if enabled else [])
        result = await app.api.get_current_emotion(event=message)
        assert result["status"] == "ok"
        assert set(result["data"]["emotions"]) == {
            "joy", "anger", "sadness", "fear", "surprise", "affection"}
        assert ("context_emotions" in result["data"]) == enabled
        assert not any(k in json.dumps(result) for k in (
            "evidence_refs", "account_id", "cause_code", "message", "persona"))
        clock[0] += 1
        _, human, _ = await ingest(app, "self-report", "我被老板骂了，好委屈", account="other")
        observation = await app.store.get_state(human, "observation", human.account_id)
        assert ("wronged" in observation.value["labels"] if observation else False) == enabled
        assert host.sends == 0 and not app._actions
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("options", [
    {"mode": "observe_only"}, {"enabled": False},
])
async def test_observe_or_disabled_does_not_collect_or_inject(tmp_path, options):
    app, host, _, clock = await local_app(tmp_path, **options)
    try:
        message = Message("blocked-collection", "虽然你没做错，但我就是要怪你")
        await app.on_message(message)
        raw = message.extra.get("livingemotion:context")
        if raw:
            context = Context.from_dict(raw)
            record = await app.store.get_state(context, "relationship", context.account_id)
            assert not feelings(app, record, context)
        request = SimpleNamespace(extra_user_content_parts=[])
        await app.on_llm_request(message, request)
        assert not any(p.text.startswith(SUFFIX) for p in request.extra_user_content_parts)
        assert host.sends == 0 and not app._actions
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("score,note,expected", [
    (20, "", False), (30, "", True), (50, "", True),
    (50, "只聊工作，保持专业", False),
])
async def test_shyness_manual_relation_and_boundary(tmp_path, score, note, expected):
    app, host, _, clock = await local_app(tmp_path)
    try:
        _, context, _ = await ingest(app, "start", "你好")
        await write_relationship_override(app.store, context, expected_version=0,
            actor_id="test-admin", reason="offline", score=score, note=note)
        clock[0] += 1
        message, context, record = await ingest(app, "warm", "你好可爱，我一直看着你呢")
        rows = feelings(app, record, context)
        assert bool(rows) == expected
        if expected:
            assert rows[0]["kind"] == "shyness"
            assert rows[0]["intensity"] <= (.25 if score == 30 else .60)
        request = SimpleNamespace(extra_user_content_parts=[])
        await app.on_llm_request(message, request)
        parts = [p.text for p in request.extra_user_content_parts if p.text.startswith(SUFFIX)]
        assert len(parts) == 1
        parsed = json.loads(parts[0].split("\n")[-1])
        assert bool(parsed["bot"].get("context_emotions")) == expected
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_config_relationship_description_blocks_shyness(tmp_path):
    app, _, native, clock = await local_app(tmp_path)
    try:
        _, context, _ = await ingest(app, "start", "你好")
        await write_relationship_override(app.store, context, expected_version=0,
            actor_id="test", reason="offline", score=50)
        clock[0] += 1
        _, _, record = await ingest(app, "warm", "你好可爱")
        assert feelings(app, record, context)
        native["relationship_stage_descriptions"] = '["","","","只聊工作，保持专业"]'
        await app.refresh_config()
        result = await app.api.get_current_emotion(context)
        assert result["status"] == "ok" and result["data"]["context_emotions"] == {}
        state = await app.console_state(context.account_key)
        assert state["user_emotion"]["context_emotions"] == []
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_account_scene_and_persona_revision_isolation(tmp_path):
    app, host, _, clock = await local_app(tmp_path)
    try:
        _, private, record = await ingest(app, "a", "虽然你没做错，但我就是要怪你", account="a")
        assert feelings(app, record, private)[0]["kind"] == "wronged"
        for index, source in enumerate([
            {"account": "b"}, {"account": "a", "group": "g1"},
            {"account": "b", "group": "g1"}, {"account": "a", "group": "g2"},
        ]):
            clock[0] += 1
            _, context, other = await ingest(app, f"other-{index}", "你好", **source)
            assert not feelings(app, other, context)
            assert (await app.api.get_current_emotion(context))["data"]["context_emotions"] == {}
        assert not account_context_emotions(record, replace(
            private, persona_revision="different"), now=clock[0])["items"]
        assert not account_context_emotions(record, replace(
            private, identity_revision="different"), now=clock[0])["items"]
        assert not account_context_emotions(record, replace(
            private, audience=("different",)), now=clock[0])["items"]
        global_state = await app.console_state(persona_id=private.persona_id, view_scope="global")
        assert global_state["user_emotion"] is None
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_restart_decay_repair_and_expired_reenable(tmp_path):
    app, _, native, clock = await local_app(tmp_path)
    try:
        _, context, record = await ingest(app, "unfair", "虽然你没做错，但我就是要怪你")
        original = record.value["_account_affect"]["context_emotions"]["items"][0]["intensity"]
        await app.terminate()
        app, _, native, clock = await local_app(tmp_path)
        clock[0] += 1800
        _, context, record = await ingest(app, "after-restart", "你好")
        assert feelings(app, record, context)[0]["intensity"] == pytest.approx(original / 2, abs=.0001)
        clock[0] += 1
        _, _, repaired = await ingest(app, "repair", "对不起，是我误会你了")
        assert not feelings(app, repaired, context)  # .25 × .4 is below expression threshold.
        native["context_emotions_enabled"] = False
        await app.refresh_config()
        clock[0] = NOW + 7201
        native["context_emotions_enabled"] = True
        await app.refresh_config()
        _, _, expired = await ingest(app, "expired", "你好")
        assert not feelings(app, expired, context)
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_duplicate_local_only_and_old_numeric_results_unchanged(tmp_path):
    values = []
    for enabled in [False, True]:
        app, host, _, _ = await local_app(tmp_path / str(enabled), context_emotions_enabled=enabled)
        try:
            message, context, record = await ingest(app, "unfair", "虽然你没做错，但我就是要怪你")
            before = await app.store.get_state(context, "bot")
            await app.on_message(message)
            assert await app.store.get_state(context, "relationship", context.account_id) == record
            assert await app.store.get_state(context, "bot") == before
            result = (await app.api.get_current_emotion(context))["data"]
            values.append({k: result[k] for k in ("emotions", "dominant", "affect", "labels")})
            assert host.sends == 0
        finally:
            await app.terminate()
    assert values[0] == values[1]


@pytest.mark.asyncio
async def test_config_four_surfaces_and_invalid_save(tmp_path):
    app, _, native, _ = await local_app(tmp_path, context_emotions_enabled=False)
    try:
        schema = json.loads((Path(__file__).parents[2]
                             / "_conf_schema.json").read_text(encoding="utf-8-sig"))
        assert schema["context_emotions_enabled"]["type"] == "bool"
        assert schema["context_emotions_enabled"]["default"] == Config().context_emotions_enabled is False
        dto = app.config_dto()
        field = next(f for f in dto["fields"] if f["key"] == "context_emotions_enabled")
        assert field["type"] == "boolean" and field["level"] == 0 and not field["parent"]
        assert field["section"] == "emotion" and "情绪" in field["details"]
        assert "参与中" in field["details"] and "仅观察" in field["details"]
        assert "参与中" in schema["context_emotions_enabled"]["description"]
        containing = [group["id"] for group in dto["groups"]
                      if "context_emotions_enabled" in group["field_keys"]]
        assert containing == ["emotion"]
        other_values = {k: v for k, v in dto["values"].items()
                        if k != "context_emotions_enabled"}
        revision = app.revision
        with pytest.raises(ApplicationError):
            await app.update_config({"context_emotions_enabled": "true"},
                expected_revision=revision, actor_id="test", reason="invalid boolean")
        assert app.revision == revision and native["context_emotions_enabled"] is False
        await app.update_config({"context_emotions_enabled": True},
            expected_revision=revision, actor_id="test", reason="enable local feature")
        assert app.config.context_emotions_enabled and native.saved["context_emotions_enabled"]
        assert {k: v for k, v in app.config_dto()["values"].items()
                if k != "context_emotions_enabled"} == other_values
        _, context, record = await ingest(app, "unfair", "虽然你没做错，但我就是要怪你")
        assert feelings(app, record, context)
        await app.update_config({"context_emotions_enabled": False},
            expected_revision=app.revision, actor_id="test", reason="disable local feature")
        assert "context_emotions" not in (await app.api.get_current_emotion(context))["data"]
        assert (await app.console_state(context.account_key))["user_emotion"]["context_emotions"] == []
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("output", ["old", "valid", "invalid"])
async def test_joint_model_replaces_original_snapshot_once(tmp_path, output):
    app, host, native, _, context, binding, clock = await generation_app(tmp_path)
    calls = []
    try:
        native.update(context_emotions_enabled=True, emotion_model_enabled=True,
                      promise_enabled=False, weather_factor_enabled=False)
        await app.refresh_config()
        body = "虽然你没做错，但我就是要怪你"

        async def generate(system, data, *_):
            calls.append(json.loads(data))
            assert "context_appraisals" in system
            result = {"rule_version": "emotion-2", "delta": {"pleasure": .04},
                      "confidence": .9, "control": .62, "appraisals": []}
            if output != "old":
                result["context_appraisals"] = ([{
                    "kind": "wronged", "cause_code": "admitted_unfair_blame",
                    "evidence": body, "confidence": .9, "strength": .75,
                }] if output == "valid" else [{"kind": "jealousy", "evidence": body}])
            return json.dumps(result)

        binding.generate = generate
        message, _, _ = await ingest(app, "refinement", body)
        await asyncio.wait_for(asyncio.gather(*tuple(app._actions)), 3)
        record = await app.store.get_state(context, "relationship", context.account_id)
        items = record.value["_account_affect"]["context_emotions"]["items"]
        assert ([r["intensity"] for r in items] == pytest.approx([.675])
                if output == "valid" else not items)
        assert app.emotion_model_analysis([context])["applied"]
        assert len(calls) == 1
        before = record
        await app.on_message(message)
        assert await app.store.get_state(context, "relationship", context.account_id) == before
        assert len(calls) == 1 and host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [
    "none", "revoke", "new_message", "provider", "relationship", "clear",
])
async def test_authorized_help_memory_and_late_result_fences(tmp_path, change):
    app, host, native, _, context, binding, clock = await generation_app(tmp_path)
    started, release, authorized = asyncio.Event(), asyncio.Event(), [True]
    calls = []
    try:
        native.update(context_emotions_enabled=True, emotion_model_enabled=True, memory_read=True,
                      promise_enabled=False, weather_factor_enabled=False)
        await app.refresh_config()
        material = Material(EvidenceRef(
            "fake-authorized", "help", context, context.account_id, context.bot_id,
            ContentKind.INTERACTION, clock[0] - 10, expires_at=clock[0] + 100),
            "谢谢你帮我解决了问题")

        async def recall(*_, **__):
            return RecallResult((material,))

        async def validate(query, materials, **_):
            return ValidationResult(authorized[0], materials if authorized[0] else ())

        app.memory.recall, app.memory.validate_evidence = recall, validate
        body = "你从来没帮过我"

        async def generate(system, data, *_):
            payload = json.loads(data)
            calls.append(payload)
            started.set()
            await release.wait()
            return json.dumps({"rule_version": "emotion-2", "delta": {"pleasure": 0},
                "control": .6, "confidence": .9, "context_appraisals": [{
                    "kind": "wronged", "cause_code": "devalued_contribution",
                    "evidence": body, "confidence": .9, "strength": .75,
                    "context_refs": payload["context_support_refs"],
                }]})

        binding.generate = generate
        await ingest(app, "with-memory", body)
        await asyncio.wait_for(started.wait(), 2)
        local = await app.store.get_state(context, "relationship", context.account_id)
        assert not feelings(app, local, context)  # No lexical guess before the model.
        if change == "revoke":
            authorized[0] = False
        elif change == "new_message":
            clock[0] += 1
            await ingest(app, "newer", "对不起，是我误会你了")
            local = await app.store.get_state(context, "relationship", context.account_id)
        elif change == "provider":
            binding.fingerprint = "changed-binding"
        elif change == "relationship":
            await write_relationship_override(app.store, context, expected_version=0,
                actor_id="test", reason="manual edit while running", score=50)
            local = await app.store.get_state(context, "relationship", context.account_id)
        elif change == "clear":
            await app.store.clear_scope(context, await app.store.get_generation(context))
            local = await app.store.get_state(context, "relationship", context.account_id)
        release.set()
        await asyncio.wait_for(asyncio.gather(*tuple(app._actions)), 3)
        result = await app.store.get_state(context, "relationship", context.account_id)
        if change == "none":
            assert feelings(app, result, context)[0]["kind"] == "wronged"
            assert result.version == local.version + 1
        else:
            assert result == local
            assert not app.emotion_model_analysis([context])["applied"]
        assert len(calls) == (2 if change == "new_message" else 1) and host.sends == 0
    finally:
        release.set()
        await app.terminate()


def test_capacity_fallback_preserves_all_legacy_data():
    payload = {"_account_affect": {"state": {}, "runtime": {}}, "_runtime": {},
               "legacy": "x" * 65400}
    state = {**empty_state(), "seen": [["a" * 64, NOW]]}
    result = attach_context_emotions(payload, state)
    assert result == payload  # Optional block dropped; no truncation or legacy-data removal.


@pytest.mark.asyncio
async def test_nonce_recovery_only_across_restart_with_unchanged_native_persona(tmp_path):
    app, host, _, clock = await local_app(tmp_path)
    try:
        _, context, record = await ingest(app, "unfair", "虽然你没做错，但我就是要怪你")
        fingerprint = app.context_emotion_fingerprint(context)
        changed = replace(context, persona_revision="different")
        assert not account_context_emotions(record, changed, now=clock[0],
            fingerprint=fingerprint, epoch=app._context_emotion_epoch)["items"]
        assert account_context_emotions(record, changed, now=clock[0],
            fingerprint=fingerprint, epoch="different-process")["items"]
        assert not account_context_emotions(record, changed, now=clock[0],
            fingerprint="different-persona-content", epoch="different-process")["items"]
        host.prompt = "Changed native personality"
        clock[0] += 1
        _, _, changed_record = await ingest(app, "changed-persona", "你好")
        assert not changed_record.value["_account_affect"].get("context_emotions", empty_state())["items"]
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_bad_optional_metadata_and_clear_do_not_poison_legacy(tmp_path):
    app, _, _, clock = await local_app(tmp_path)
    try:
        message, context, record = await ingest(app, "unfair", "虽然你没做错，但我就是要怪你")
        payload = dict(record.value)
        payload["_account_affect"] = {**payload["_account_affect"],
                                    "context_emotions": {"version": "bad"}}
        source, event = await app.bridge.normalize(Message("corruption-write"), clock[0])
        assert (await app.store.commit_event(event, 0, [StateWrite(
            "relationship", payload, record.version, context.account_id, record.owner)])).accepted
        result = await app.api.get_current_emotion(context)
        assert result["status"] == "ok" and result["data"]["context_emotions"] == {}
        clock[0] += 1
        _, _, restored = await ingest(app, "restore", "虽然你没做错，但我就是要怪你")
        assert feelings(app, restored, context)[0]["kind"] == "wronged"
        await app.store.clear_scope(context, await app.store.get_generation(context))
        assert await app.store.get_state(context, "relationship", context.account_id) is None
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_console_collected_zero_subthreshold_decay_and_global_isolation(tmp_path):
    app, _, native, clock = await local_app(tmp_path)
    try:
        _, context, _ = await ingest(app, "neutral", "你好")
        state = await app.console_state(context.account_key)
        assert state["context_emotions"]["emotions"] == {}  # No collection yet.
        clock[0] += 1
        _, context, _ = await ingest(app, "unfair", "虽然你没做错，但我就是要怪你")
        before = await app.console_state(context.account_key)
        assert before["context_emotions"]["emotions"]["hurt"] == 0.0
        assert before["context_emotions"]["emotions"]["shyness"] == 0.0
        clock[0] += 3600
        after = await app.console_state(context.account_key)
        dto = after["context_emotions"]
        assert dto["enabled"] and dto["context_id"] == context.account_key
        assert dto["target"] == context.account_id and dto["scope_kind"] == "account"
        assert dto["emotions"]["wronged"] == pytest.approx(
            before["context_emotions"]["emotions"]["wronged"] / 4, abs=.0001)
        assert 0 < dto["emotions"]["wronged"] < .2
        assert after["user_emotion"]["context_emotions"] == []
        global_state = await app.console_state(persona_id=context.persona_id, view_scope="global")
        assert global_state["context_emotions"] == {
            "version": 1, "scope_kind": "account", "context_id": "", "target": "",
            "enabled": True, "dimension": "conversation", "emotions": {}}
        clock[0] += 7201
        expired = await app.console_state(context.account_key)
        assert expired["context_emotions"]["emotions"] == {
            "wronged": 0.0, "hurt": 0.0, "shyness": 0.0}
        native["context_emotions_enabled"] = False
        await app.refresh_config()
        disabled = await app.console_state(context.account_key)
        assert not disabled["context_emotions"]["enabled"]
        assert disabled["context_emotions"]["emotions"] == {}
    finally:
        await app.terminate()


async def shared(app, context):
    """用户维度下该对象此刻可见的对象情绪（经 API 读取，已过表达门槛）。"""
    return (await app.api.get_current_emotion(context))["data"]["context_emotions"]


async def injected(app, message):
    """本次回复注入块里的对象情绪。"""
    from astrbot_plugin_livingemotion.runtime.application import SUFFIX
    request = SimpleNamespace(extra_user_content_parts=[])
    await app.on_llm_request(message, request)
    block = next(p.text for p in request.extra_user_content_parts if p.text.startswith(SUFFIX))
    return json.loads(block.split("\n")[-1])["bot"].get("context_emotions") or []


class At:
    def __init__(self, qq):
        self.qq = qq


async def group_ingest(app, identifier, body, group, account):
    """群聊里 @Bot 的消息：群消息只有明确指向 Bot 才算对 TA 的刺激。"""
    message = Message(identifier, body, group=group, account=account)
    message.message_obj.message = (At(message.get_self_id()),)
    await app.on_message(message)
    assert message.extra["livingemotion:ingest"] == "accepted"
    return message, Context.from_dict(message.extra["livingemotion:context"])


@pytest.mark.asyncio
async def test_user_dimension_shares_one_person_record_across_scenes(tmp_path):
    app, host, native, clock = await local_app(tmp_path, context_emotions_dimension="user")
    try:
        _, private, _ = await ingest(app, "private", "你好", account="a")
        clock[0] += 1
        _, group = await group_ingest(app, "unfair", "虽然你没做错，但我就是要怪你", "g1", "a")
        person = await app.store.context_emotion_record(group)
        assert person.kind == "context_emotion" and person.record_key == "a" and person.version == 1
        scene_record = await app.store.get_state(group, "relationship", "a")
        assert "context_emotions" not in scene_record.value.get("_account_affect", {})  # Not in the scene.
        intensity = person.value["context_emotions"]["items"][0]["intensity"]
        clock[0] += 1
        _, second_group = await group_ingest(app, "second-group", "你好", "g2", "a")
        _, stranger = await group_ingest(app, "stranger", "你好", "g1", "b")
        message, back, _ = await ingest(app, "back-to-private", "你好", account="a")
        # Same QQ reads one record from private chat and every group; other QQs are unaffected.
        for context in (private, second_group, back):
            assert await shared(app, context) == {"wronged": pytest.approx(intensity, abs=.01)}
        assert await shared(app, stranger) == {}
        # A QQ without a person record yet is a valid read at version 0, not an error.
        fresh = await app.api.get_current_emotion(stranger)
        assert fresh["status"] == "ok" and fresh["data"]["context_emotions_state_version"] == 0
        assert await app.store.context_emotion_record(private) == person
        assert [row["kind"] for row in await injected(app, message)] == ["wronged"]
        result = await app.api.get_current_emotion(second_group)
        assert result["data"]["context_emotions_state_version"] == 1
        state = await app.console_state(persona_id=back.persona_id, view_scope="global",
                                         context_id=account_person_key(back))
        dto = state["context_emotions"]
        assert dto["dimension"] == "user" and dto["scope_kind"] == "account"
        assert dto["target"] == "a" and dto["context_id"] == state["context_id"]
        assert dto["emotions"]["wronged"] == pytest.approx(intensity, abs=.01)
        # The person key selects every conversation of that QQ, across scene kinds.
        assert {(c["account_id"], c["view_scope"]) for c in state["contexts"]} == {
            ("a", "private"), ("a", "group")}
        overall = await app.console_state(persona_id=back.persona_id, view_scope="global")
        assert overall["context_emotions"]["dimension"] == "user"
        assert overall["context_emotions"]["emotions"] == {}
        # Clearing the scene that produced the stimulus removes it everywhere for that QQ.
        await app.store.clear_scope(group, await app.store.get_generation(group))
        assert await app.store.context_emotion_record(back) is None
        assert await shared(app, back) == {}
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_user_dimension_restart_dimension_switch_and_persona_change(tmp_path):
    app, host, native, clock = await local_app(tmp_path, context_emotions_dimension="user")
    try:
        _, private, _ = await ingest(app, "hello", "你好", account="a")
        await group_ingest(app, "unfair", "虽然你没做错，但我就是要怪你", "g1", "a")
        original = (await app.store.context_emotion_record(private)).value[
            "context_emotions"]["items"][0]["intensity"]
        await app.terminate()
        app, host, native, clock = await local_app(tmp_path, context_emotions_dimension="user")
        clock[0] += 1800
        _, context, _ = await ingest(app, "after-restart", "你好", account="a")
        assert await shared(app, context) == {"wronged": pytest.approx(original / 2, abs=.0001)}
        # Back to conversation dimension: scene records are read; the person record stays, unread.
        native["context_emotions_dimension"] = "conversation"
        await app.refresh_config()
        assert await shared(app, context) == {}
        scene_record = await app.store.context_emotion_record(context)
        assert scene_record is not None and scene_record.kind == "relationship"
        native["context_emotions_dimension"] = "user"
        await app.refresh_config()
        clock[0] += 1
        # A repair in private chat settles the feeling carried over from the group.
        _, context, _ = await ingest(app, "repair", "对不起，是我误会你了", account="a")
        assert await shared(app, context) == {}
        await group_ingest(app, "unfair-again", "虽然你没做错，但我就是要怪你", "g1", "a")
        host.prompt = "Changed native personality"
        clock[0] += 1
        _, context, _ = await ingest(app, "changed-persona", "你好", account="a")
        assert await shared(app, context) == {}  # Same process: a new persona starts over.
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_user_dimension_reprojects_when_person_record_changes_first(tmp_path, monkeypatch):
    app, host, native, clock = await local_app(tmp_path, context_emotions_dimension="user")
    try:
        _, private, _ = await ingest(app, "hello", "你好", account="a")
        _, group = await group_ingest(app, "unfair", "虽然你没做错，但我就是要怪你", "g1", "a")
        before = await app.store.context_emotion_record(group)
        assert before is not None and before.version == 1
        original = app.store.commit_event
        bumped = []

        async def racing_commit(event, generation, writes=(), contributions=(), **options):
            if not bumped:
                # The same QQ is updated from another scene between projection and commit.
                def bump(db):  # Store work runs on the connection's worker thread.
                    return app.store._write_person(db, group, StateWrite(
                        PERSON_KIND, before.value, before.version, "a"), clock[0])
                await app.store._run(bump)
                bumped.append(True)
            return await original(event, generation, writes, contributions, **options)

        monkeypatch.setattr(app.store, "commit_event", racing_commit)
        clock[0] += 1
        message, context, _ = await ingest(app, "again", "你就是个废物", account="a")
        assert bumped == [True]
        assert message.extra["livingemotion:ingest"] == "accepted"
        after = await app.store.context_emotion_record(context)
        items = after.value["context_emotions"]["items"]
        # 1 first stimulus, 2 the racing write, 3 this event after re-projection.
        assert after.version == 3 and {r["kind"] for r in items} == {"wronged", "hurt"}
        assert await app.store.context_emotion_record(group) == after
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_dimension_config_surfaces_and_invalid_save(tmp_path):
    app, _, native, _ = await local_app(tmp_path)
    try:
        schema = json.loads((Path(__file__).parents[2]
                             / "_conf_schema.json").read_text(encoding="utf-8-sig"))
        field = schema["context_emotions_dimension"]
        assert field["type"] == "string" and field["options"] == ["conversation", "user"]
        assert field["default"] == Config().context_emotions_dimension == "conversation"
        dto = app.config_dto()
        control = next(f for f in dto["fields"] if f["key"] == "context_emotions_dimension")
        assert control["type"] == "enum" and control["level"] == 0 and not control["parent"]
        assert control["section"] == "quick_start"
        assert [option["value"] for option in control["options"]] == ["conversation", "user"]
        assert control["options"][1]["label"] == "用户维度 · 同一 QQ 互通"
        assert "用户维度" in control["details"] and "设置" in control["details"]
        assert [group["id"] for group in dto["groups"]
                if "context_emotions_dimension" in group["field_keys"]] == ["quick_start"]
        assert dto["values"]["context_emotions_dimension"] == "conversation"
        revision = app.revision
        with pytest.raises(ApplicationError):
            await app.update_config({"context_emotions_dimension": "account"},
                expected_revision=revision, actor_id="test", reason="invalid dimension")
        assert app.revision == revision and app.config.context_emotions_dimension == "conversation"
        assert not hasattr(native, "saved") or "context_emotions_dimension" not in native.saved
        await app.update_config({"context_emotions_dimension": "user"},
            expected_revision=app.revision, actor_id="test", reason="share by QQ")
        assert app.config.context_emotions_dimension == "user"
        assert native.saved["context_emotions_dimension"] == "user"
        with pytest.raises(ValueError):
            Config(context_emotions_dimension="account")
    finally:
        await app.terminate()
