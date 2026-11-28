"""Semantic wiring with scripted providers; no claim of measured LLM comprehension."""
import asyncio
import json
import socket
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.contracts import ActorRole, Context, StateWrite
from astrbot_plugin_livingemotion.domain.context_emotion import LABELS, empty_state
from astrbot_plugin_livingemotion.storage.console_data import write_relationship_override
from astrbot_plugin_livingemotion.storage.context_emotions import PERSON_KIND, person_value
from test_context_emotions import group_ingest, injected, local_app, ingest, feelings
from test_application import Message


CAUSE = {"wronged": "admitted_unfair_blame", "hurt": "direct_devaluation",
         "shyness": "warm_attention"}


def appraisal(kind, body, *, action="increase", strength=.5, **fields):
    return {"kind": kind, "cause_code": CAUSE[kind], "evidence": body,
            "confidence": .9, "strength": strength, "action": action,
            "holder": "bot", "target": "current_interlocutor", **fields}


class ScriptedProvider:
    fingerprint = "isolated-semantic-provider"

    def __init__(self):
        self.respond = lambda payload: []
        self.snapshots = []
        self.started = asyncio.Event()
        self.release = None

    def count(self, system, data):
        return len((system + data).encode("utf-8")) + 256

    async def generate(self, system, data, output_tokens, timeout):
        payload = json.loads(data)
        value = self.respond(payload)
        result = {"context_appraisals": value}
        if "不要四维delta" not in system:
            result.update(rule_version="emotion-3", delta={"pleasure": 0},
                          confidence=.9, control=.6, appraisals=[])
        text = json.dumps(result, ensure_ascii=False)
        self.snapshots.append({"system": system, "data": payload,
                               "input_budget_count": self.count(system, data),
                               "output_token_budget": output_tokens, "response": result})
        self.started.set()
        if self.release is not None:
            await self.release.wait()
        return text


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*_, **__):
        raise AssertionError("semantic tests must not connect to a real provider")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


async def semantic_app(path, **options):
    app, host, native, clock = await local_app(
        path, emotion_quiet_start_hour=0, emotion_quiet_end_hour=0,
        catchup_enabled=False, catchup_reply_enabled=False, memory_read=False,
        diary_enabled=False, dream_enabled=False, **options)
    provider = ScriptedProvider()

    async def binding(context, **_):
        return provider
    app.model_binding = binding
    _, context, _ = await ingest(app, "setup", "你好")
    await write_relationship_override(app.store, context, expected_version=0,
        actor_id="offline-test", reason="semantic fixture", score=50)
    native["emotion_model_enabled"] = True
    await app.refresh_config()
    return app, host, native, clock, context, provider


async def turn(app, identifier, body, **kwargs):
    message = Message(identifier, body, **kwargs)
    request = SimpleNamespace(extra_user_content_parts=[])
    await app.on_llm_request(message, request)
    from astrbot_plugin_livingemotion.runtime.application import SUFFIX
    blocks = [p.text for p in request.extra_user_content_parts if p.text.startswith(SUFFIX)]
    assert len(blocks) == 1
    context = Context.from_dict(message.extra["livingemotion:context"])
    record = await app.store.get_state(context, "relationship", context.account_id)
    return message, context, record, json.loads(blocks[0].split("\n")[-1])


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,history,body", [
    ("wronged", "我知道你已经尽了力", "反正最后的锅你来背，理由我懒得听"),
    ("hurt", "认真说，这件事让我很失望", "你的存在对我没有任何价值"),
    ("shyness", "和你相处让我觉得很安心", "突然想把脸靠近一点，你会不会躲开"),
])
async def test_paraphrases_reach_current_reply_without_keyword_gate(tmp_path, kind, history, body):
    app, host, _, clock, context, provider = await semantic_app(tmp_path)
    try:
        provider.respond = lambda p: []
        await turn(app, "history", history)
        clock[0] += 1
        provider.respond = lambda p: [appraisal(kind, body)]
        _, _, record, expression = await turn(app, "semantic", body)
        assert feelings(app, record, context)[0]["kind"] == kind
        assert expression["bot"]["context_emotions"][0]["kind"] == kind
        snapshot = provider.snapshots[-1]
        assert history in [r["text"] for r in snapshot["data"]["recent_dialogue"]]
        assert len(provider.snapshots) == 2  # Joint, then one uncharged-cooldown fallback.
        assert snapshot["output_token_budget"] <= 512
        assert snapshot["input_budget_count"] <= 8192
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("history,body,kind", [
    ("这是我们一直互叫的昵称，我在笑", "你这个小废物", None),
    ("我已经忍了很久，现在是认真的", "你这个小废物", "hurt"),
    ("来练习一句小说对白", "你好可爱", None),
    ("今晚只想和你多待一会", "你好可爱", "shyness"),
    ("这只是例句，不是在说你", "假如我说你就是废物，会怎样", None),
    ("演戏结束，我现在认真说", "你就是个废物，开玩笑才怪", "hurt"),
    ("今天我在说自己的感受", "我被人否定了，好受伤", None),
    ("我在回忆别人的一句话", "他说你没做错却要你承担责任", None),
])
async def test_context_controls_scripted_decision_and_empty_suppresses_keywords(
        tmp_path, history, body, kind):
    app, host, _, clock, context, provider = await semantic_app(tmp_path)
    try:
        await turn(app, "prior", history)
        clock[0] += 1
        provider.respond = lambda p: [appraisal(kind, body)] if kind else []
        _, _, record, expression = await turn(app, "same-words", body)
        rows = feelings(app, record, context)
        assert [r["kind"] for r in rows] == ([kind] if kind else [])
        assert bool(expression["bot"].get("context_emotions")) == bool(kind)
        assert history in [r["text"] for r in provider.snapshots[-1]["data"]["recent_dialogue"]]
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["wronged", "hurt", "shyness"])
async def test_semantic_increase_decrease_clear_and_none_with_existing_state(tmp_path, kind):
    app, _, _, clock, context, provider = await semantic_app(tmp_path)
    try:
        body = "这是第一句刺激"
        provider.respond = lambda p: [appraisal(kind, p["message"], strength=.6)]
        _, _, record, _ = await turn(app, "create", body)
        original = record.value["_account_affect"]["context_emotions"]["items"][0]
        clock[0] += 1
        latest, _, increased, _ = await turn(app, "increase", "这是新的刺激方式")
        refs = (latest.extra["livingemotion:event_key"],)
        value = increased.value["_account_affect"]["context_emotions"]["items"][0]
        assert value["intensity"] > original["intensity"]
        assert value["expires_at"] == original["expires_at"]
        assert provider.snapshots[-1]["data"]["context_emotions"]
        clock[0] += 1
        provider.respond = lambda p: [appraisal(kind, p["message"], action="none")]
        _, _, unchanged, _ = await turn(app, "none", "继续讲原来的事")
        assert unchanged.value["_account_affect"]["context_emotions"]["items"][0]["intensity"] < value["intensity"]
        clock[0] += 1
        provider.respond = lambda p: [
            appraisal(kind, p["message"], action="decrease", strength=.3, context_refs=refs)]
        _, _, decreased, _ = await turn(app, "decrease", "我收回刚才那句新的刺激方式的说法")
        assert refs[0] in {row["ref"] for row in provider.snapshots[-1]["data"]["recent_dialogue"]}
        assert decreased.value["_account_affect"]["context_emotions"]["items"][0]["intensity"] < .4
        clock[0] += 1
        provider.respond = lambda p: [appraisal(kind, p["message"], action="clear", context_refs=refs)]
        _, _, cleared, expression = await turn(app, "clear", "我收回之前那句新的刺激方式的整句话")
        assert refs[0] in {row["ref"] for row in provider.snapshots[-1]["data"]["recent_dialogue"]}
        assert not cleared.value["_account_affect"]["context_emotions"]["items"]
        assert not expression["bot"].get("context_emotions")
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_context_only_preserves_four_axes_relation_ledger_and_deduplicates(tmp_path):
    app, host, _, clock, context, provider = await semantic_app(tmp_path)
    try:
        await turn(app, "charge-joint", "先聊一句")
        clock[0] += 1
        body = "我不再觉得你的陪伴有意义"
        provider.respond = lambda p: [appraisal("hurt", body)]
        message, _, before = await ingest(app, "context-only", body)
        bot = await app.store.get_state(context, "bot")
        ledger = await app.store.relationship_ledger(context)
        # Join exactly the event queued by ingestion.
        await app.await_context_refinement(message.extra["livingemotion:event_key"])
        after = await app.store.get_state(context, "relationship", context.account_id)
        assert feelings(app, after, context)[0]["kind"] == "hurt"
        assert await app.store.get_state(context, "bot") == bot
        assert await app.store.relationship_ledger(context) == ledger
        clean = lambda v: {k: x for k, x in v.items() if k != "_account_affect"}
        assert clean(before.value) == clean(after.value)
        personal = lambda v: {k: x for k, x in v["_account_affect"].items()
                              if not k.startswith("context_emotions")}
        assert personal(before.value) == personal(after.value)
        n = len(provider.snapshots)
        await app.on_llm_request(message, SimpleNamespace(extra_user_content_parts=[]))
        await app.on_llm_request(message, SimpleNamespace(extra_user_content_parts=[]))
        assert len(provider.snapshots) == n == 2
        period = datetime.fromtimestamp(clock[0], timezone.utc).date().isoformat()
        assert await app.store.quota_usage(period=period) == 2
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [
    "neutral", "provider", "persona", "route", "clear", "relationship", "correction", "expired",
])
async def test_context_only_late_result_respects_origin_fences(tmp_path, change):
    app, host, _, clock, context, provider = await semantic_app(tmp_path)
    release = asyncio.Event()
    try:
        await turn(app, "charge", "先说一句")
        provider.started.clear()
        provider.release = release
        provider.respond = lambda p: [appraisal("hurt", p["message"])]
        message, _, before = await ingest(app, "delayed", "再见，我不想见到你")
        await asyncio.wait_for(provider.started.wait(), 2)
        if change == "neutral":
            clock[0] += 1
            _, _, before = await ingest(app, "newer", "那我们继续检查下一项配置。")
        elif change == "provider":
            provider.fingerprint = "changed"
        elif change == "persona":
            host.prompt = "changed native persona"
        elif change == "route":
            source = app.bridge.source(context)
            app.bridge.sources[context.account_key] = replace(
                source, context=replace(context, route=context.route + ":changed"))
        elif change == "clear":
            await app.store.clear_scope(context, await app.store.get_generation(context))
            before = None
        elif change == "relationship":
            await write_relationship_override(app.store, context, expected_version=1,
                actor_id="offline-test", reason="edit while analyzing", score=60)
            before = await app.store.get_state(context, "relationship", context.account_id)
        elif change == "correction":
            result = await app.store.correct_relationship(
                context, before.generation, expected_version=before.version,
                actor_id="offline-test", reason="direct correction while analyzing", score=60,
            )
            assert result.accepted
            before = await app.store.get_state(context, "relationship", context.account_id)
        else:
            clock[0] += 7200
        bot = await app.store.get_state(context, "bot")
        ledger = await app.store.relationship_ledger(context)
        release.set()
        await app.await_context_refinement(message.extra["livingemotion:event_key"])
        after = await app.store.get_state(context, "relationship", context.account_id)
        if change == "neutral":
            assert after.version == before.version + 1
            assert [row["kind"] for row in feelings(app, after, context)] == ["hurt"]
        else:
            assert after == before
        assert await app.store.get_state(context, "bot") == bot
        assert await app.store.relationship_ledger(context) == ledger
        assert len(provider.snapshots) == 2
    finally:
        release.set()
        await app.terminate()


@pytest.mark.asyncio
async def test_wait_timeout_keeps_background_analysis_and_writes_back_once(tmp_path, monkeypatch):
    import astrbot_plugin_livingemotion.runtime.refinement as refinement
    monkeypatch.setattr(refinement, "CONTEXT_WAIT_SECONDS", .03)
    app, host, _, _, context, provider = await semantic_app(tmp_path)
    release = asyncio.Event()
    try:
        provider.release = release
        provider.respond = lambda p: [appraisal("hurt", p["message"])]
        message, _, record, expression = await turn(app, "timeout", "你的存在对我没有任何价值")
        # 回复不等分析：这次回复不带对象情绪，记录也未改动。
        assert not feelings(app, record, context)
        assert not expression["bot"].get("context_emotions")
        assert await app.store.get_state(context, "relationship", context.account_id) == record
        release.set()
        await asyncio.gather(*tuple(app._actions), return_exceptions=True)
        await app.runtime.join()
        after = await app.store.get_state(context, "relationship", context.account_id)
        assert feelings(app, after, context)[0]["kind"] == "hurt"
        assert app.emotion_model_analysis([context])["reason_code"] == "completed"
        # 下一次回复直接读到已写回的结果，不再发起第二次模型调用。
        request = SimpleNamespace(extra_user_content_parts=[])
        await app.on_llm_request(message, request)
        from astrbot_plugin_livingemotion.runtime.application import SUFFIX
        block = next(p.text for p in request.extra_user_content_parts if p.text.startswith(SUFFIX))
        assert json.loads(block.split("\n")[-1])["bot"]["context_emotions"][0]["kind"] == "hurt"
        assert len(provider.snapshots) == 1
        assert host.sends == 0
    finally:
        release.set()
        await app.terminate()


@pytest.mark.asyncio
async def test_native_request_does_not_wait_for_model_after_confirmed_local_change(
        tmp_path, monkeypatch):
    import astrbot_plugin_livingemotion.runtime.refinement as refinement
    monkeypatch.setattr(refinement, "CONTEXT_WAIT_SECONDS", 30)
    app, _, _, _, context, provider = await semantic_app(tmp_path)
    release = asyncio.Event()
    try:
        provider.release = release
        provider.respond = lambda p: [appraisal("hurt", p["message"])]
        message, _, local = await ingest(app, "realtime", "你就是个废物")
        await asyncio.wait_for(provider.started.wait(), 2)
        bot = await app.store.get_state(context, "bot")
        ledger = await app.store.relationship_ledger(context)
        items = await asyncio.wait_for(injected(app, message), 2)
        assert [row["kind"] for row in items] == ["hurt"]
        assert not release.is_set() and len(provider.snapshots) == 1
        release.set()
        await asyncio.gather(*tuple(app._actions))
        assert await app.store.get_state(context, "relationship", context.account_id) == local
        assert await app.store.get_state(context, "bot") == bot
        assert await app.store.relationship_ledger(context) == ledger
    finally:
        release.set()
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("dimension", ["conversation", "user"])
async def test_lane_coalesces_near_repeats_without_delaying_neutral_or_sharing_evidence(
        tmp_path, monkeypatch, dimension):
    import astrbot_plugin_livingemotion.runtime.refinement as refinement
    monkeypatch.setattr(refinement, "CONTEXT_WAIT_SECONDS", 30)
    app, _, _, clock, context, provider = await semantic_app(
        tmp_path, context_emotions_dimension=dimension)
    release = asyncio.Event()
    repeated = "和你说话对我已经没有任何价值。"
    distinct = "突然想把脸靠近一点，你会不会躲开"
    neutral = ["接下来是普通技术讨论。", "把第二项列出来。", "这里使用默认端口。",
               "这个变量叫 timeout。", "我记下这个参数了。", "继续下一项。"]
    try:
        provider.release = release
        first, _, _ = await ingest(app, "first", repeated)
        await asyncio.wait_for(provider.started.wait(), 2)
        first_task = app._refinement_tasks[first.extra["livingemotion:event_key"]]["task"]
        clock[0] += 1
        duplicate, _, _ = await ingest(app, "active-repeat", " " + repeated)
        assert duplicate.extra["livingemotion:event_key"] not in app._refinement_tasks
        assert not await asyncio.wait_for(injected(app, duplicate), 2)
        for index, body in enumerate(neutral):
            clock[0] += 7
            message, _, _, _ = await asyncio.wait_for(turn(app, f"neutral-{index}", body), 2)
            assert message.extra["livingemotion:event_key"] not in app._refinement_tasks
        queued, _, _ = await ingest(app, "queued", distinct)
        duplicate, _, _ = await ingest(app, "pending-repeat", distinct)
        assert duplicate.extra["livingemotion:event_key"] not in app._refinement_tasks
        assert app._refinement_tasks[queued.extra["livingemotion:event_key"]]["task"] is first_task

        other, _, _ = await ingest(app, "other-person", repeated, account="other")
        scene, _ = await group_ingest(app, "other-scene", repeated, "group", context.account_id)
        assert app._refinement_tasks[other.extra["livingemotion:event_key"]]["task"] is not first_task
        assert (app._refinement_tasks[scene.extra["livingemotion:event_key"]]["task"] is first_task
                ) == (dimension == "user")
        assert [p["data"]["message"] for p in provider.snapshots].count(distinct) == 0
        release.set()
        await asyncio.wait_for(asyncio.gather(*tuple(app._actions)), 3)
        assert sorted(p["data"]["message"] for p in provider.snapshots) == sorted(
            [repeated, repeated, repeated, distinct])
    finally:
        release.set()
        await app.terminate()


@pytest.mark.asyncio
async def test_alternative_technical_updates_skip_but_qualified_status_dispatches(tmp_path):
    updates = (
        "请求返回的是 200 状态码。",
        "这个端口当前没有进程占用。",
        "命令的退出码是 0。",
        "测试通过了 12 项。",
        "配置文件已加载。",
        "接下来检查日志。",
    )
    app, host, _, clock, _, provider = await semantic_app(tmp_path)
    try:
        start = clock[0]
        for offset, body in zip((0, 8, 18, 28, 38, 48), updates, strict=True):
            clock[0] = start + offset
            await turn(app, f"technical-{offset}", body)
            await asyncio.gather(*tuple(app._actions))
        assert [packet["data"]["message"] for packet in provider.snapshots] == []

        charged = updates[0][:-1] + "，你的存在对我没有任何价值。"
        uncertain = updates[1][:-1] + "？"
        for body in (charged, uncertain):
            clock[0] += 1
            await turn(app, f"technical-{clock[0] - start}", body)
            await asyncio.gather(*tuple(app._actions))
        assert [packet["data"]["message"] for packet in provider.snapshots] == [charged, uncertain]
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("body", ["能说清楚一点吗？", "请求返回的是 200 状态码。"])
async def test_coalescing_keeps_different_native_reply_anchors(tmp_path, body):
    class Reply:
        def __init__(self, sender, reply_id):
            self.sender_id, self.id = sender, reply_id

    app, _, _, clock, context, provider = await semantic_app(tmp_path)
    release = asyncio.Event()
    try:
        anchors = {}
        for reply_id in ("first-reply", "second-reply"):
            _, event = await app.bridge.normalize(Message(reply_id, reply_id), clock[0])
            event = replace(event, producer="livingemotion.host", event_type="bot_reply_submitted",
                            actor_role=ActorRole.BOT, actor_id=context.bot_id)
            assert (await app.store.commit_event(event, 0)).accepted
            anchors[reply_id] = event.idempotency_key
        provider.release = release
        for i, reply_id in enumerate(("first-reply", "first-reply", "second-reply")):
            clock[0] += 1
            message = Message(f"reply-{i}", body)
            message.message_obj.message = (Reply(message.get_self_id(), reply_id),)
            await app.on_message(message)
            assert message.extra["livingemotion:ingest"] == "accepted"
            assert (message.extra["livingemotion:event_key"] in app._refinement_tasks) == (i != 1)
            if i == 0:
                await asyncio.wait_for(provider.started.wait(), 2)
        release.set()
        await asyncio.wait_for(asyncio.gather(*tuple(app._actions)), 3)
        for packet, anchor in zip(provider.snapshots, anchors.values(), strict=True):
            assert anchor in {row["ref"] for row in packet["data"]["recent_dialogue"]}
    finally:
        release.set()
        await app.terminate()


async def person_items(app, context):
    """用户维度下该 QQ 人级记录里的对象情绪条目。"""
    record = await app.store.context_emotion_record(context)
    assert record is not None and record.kind == PERSON_KIND
    return record.value["context_emotions"]["items"]


@pytest.mark.asyncio
async def test_user_dimension_model_writes_person_record_shared_across_scenes(tmp_path):
    app, host, _, clock, context, provider = await semantic_app(
        tmp_path, context_emotions_dimension="user")
    try:
        provider.respond = lambda p: []
        await turn(app, "joint-empty", "先聊一句")
        clock[0] += 601
        body = "你的存在对我没有任何价值"
        provider.respond = lambda p: [appraisal("hurt", body)]
        _, _, record, expression = await turn(app, "joint", body)
        assert "不要四维delta" not in provider.snapshots[-1]["system"]  # Joint analysis.
        assert expression["bot"]["context_emotions"][0]["kind"] == "hurt"
        # The scene relationship record keeps no object emotion; the person record owns it.
        assert "context_emotions" not in record.value["_account_affect"]
        items = await person_items(app, context)
        assert [row["kind"] for row in items] == ["hurt"] and items[0]["intensity"] == pytest.approx(.45)
        provider.respond = lambda p: []
        group_message, group = await group_ingest(app, "group-hello", "你好", "g1", "human")
        await app.await_context_refinement(group_message.extra["livingemotion:event_key"])
        assert await person_items(app, group) == items  # Same QQ in a group reads the private stimulus.
        # The dedicated object analysis (joint analysis still cooling down in this scene) updates
        # the same record; this scene's four axes, relationship record and ledger are untouched.
        clock[0] += 1
        followup = "我不想再见到你"
        provider.respond = lambda p: [appraisal("hurt", followup, strength=.6)]
        ledger = await app.store.relationship_ledger(context)
        n = len(provider.snapshots)
        message, _, _ = await ingest(app, "context-only", followup)
        bot = await app.store.get_state(context, "bot")   # After the local-rule projection.
        before = await app.store.get_state(context, "relationship", context.account_id)
        await app.await_context_refinement(message.extra["livingemotion:event_key"])
        assert len(provider.snapshots) == n + 1
        assert "不要四维delta" in provider.snapshots[-1]["system"]
        assert await app.store.get_state(context, "bot") == bot
        assert await app.store.get_state(context, "relationship", context.account_id) == before
        assert await app.store.relationship_ledger(context) == ledger
        increased = await person_items(app, group)
        assert increased[0]["kind"] == "hurt" and increased[0]["intensity"] > items[0]["intensity"]
        # A group reply for the same QQ carries the private-chat stimulus.
        assert [row["kind"] for row in await injected(app, group_message)] == ["hurt"]
        assert app.emotion_model_analysis([context])["reason_code"] == "completed"
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("dimension", ["conversation", "user"])
@pytest.mark.parametrize("conflicts", [1, 3])
async def test_deferred_write_cas_retries_latest_record_only(
        tmp_path, monkeypatch, dimension, conflicts):
    app, host, _, clock, context, provider = await semantic_app(
        tmp_path, context_emotions_dimension=dimension)
    try:
        original, versions, accepted = app.store.calibrate_context_emotions, [], []

        async def racing(event, generation, **kwargs):
            current = kwargs["target"]
            version = current.version if current else 0
            if len(versions) < conflicts:
                if dimension == "user":
                    value = (current.value if current else person_value(
                        context, empty_state(), kwargs["fingerprint"], kwargs["epoch"]))
                    kind = PERSON_KIND
                else:
                    value = {**current.value, "_racing_write": len(versions) + 1}
                    kind = "relationship"
                result = await app.store.write_states(
                    context, generation, (StateWrite(kind, value, version, context.account_id),))
                assert result.accepted
            versions.append(version)
            result = await original(event, generation, **kwargs)
            if result.accepted:
                accepted.append((event, generation, kwargs))
            return result

        monkeypatch.setattr(app.store, "calibrate_context_emotions", racing)
        clock[0] += 1
        body = "你的存在对我没有任何价值"
        provider.respond = lambda p: [appraisal("hurt", body)]
        await turn(app, "joint", body)
        assert len(versions) == min(conflicts + 1, 3)
        assert versions == list(range(versions[0], versions[0] + len(versions)))
        record = await app.store.context_emotion_record(context)
        assert record.version == versions[0] + min(conflicts + 1, 3)
        if dimension == "conversation":
            assert record.value["_racing_write"] == conflicts
        if conflicts == 1:
            event, generation, kwargs = accepted.pop()
            duplicate = await original(event, generation, **kwargs)
            assert duplicate.reason_code == "duplicate_event"
            assert await app.store.context_emotion_record(context) == record
            values = await app.api.get_current_emotion(context)
            assert values["data"]["context_emotions"]["hurt"] == pytest.approx(.45)
        else:
            assert not accepted
            assert app.emotion_model_analysis([context])["reason_code"] == "version_conflict"
        assert len(provider.snapshots) == 1  # Retry the CAS, not the provider.
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_context_analysis_log_line_and_judgement(tmp_path, monkeypatch):
    import astrbot_plugin_livingemotion.runtime.refinement as refinement
    app, _, _, clock, context, provider = await semantic_app(tmp_path)
    try:
        lines = []
        monkeypatch.setattr(refinement.logger, "info",
                            lambda pattern, *args: lines.append(pattern % args))
        body = "你的存在对我没有任何价值"
        provider.respond = lambda p: [appraisal("hurt", body)]
        await turn(app, "logged", body)
        lines = [line for line in lines if line.startswith("[LE-对象情绪]")]
        assert len(lines) == 1
        line = lines[0]
        assert line.startswith(f"[LE-对象情绪] human@私聊 内容=「{body}」 "
                               f"判定=[hurt:increase 强度0.5 把握0.9] "
                               f"结果=已写入({LABELS['hurt']}0.45) 原因=context_hurt ")
        assert line.endswith("s") and "耗时=" in line
    finally:
        await app.terminate()
    judge = refinement._judgement
    assert judge("not json") == "非JSON:not json"
    assert judge({"appraisals": []}) == "缺字段" and judge({"context_appraisals": "x"}) == "格式无效"
    assert judge({"context_appraisals": []}) == "空"
    assert judge({"context_appraisals": [{"kind": "shyness", "action": "none",
                                          "strength": .3, "confidence": .8}]}) == "shyness:none 强度0.3 把握0.8"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["quota", "invalid_json", "unknown", "oversize"])
async def test_no_lexical_fallback_or_retry_after_failure(tmp_path, failure):
    options = ({"model_daily_limit": 1} if failure == "quota" else
               {"model_input_tokens": 128} if failure == "oversize" else {})
    app, _, _, clock, context, provider = await semantic_app(tmp_path, **options)
    try:
        if failure == "quota":
            await turn(app, "exhaust", "先聊一句")
            clock[0] += 1
        elif failure in ("invalid_json", "unknown"):
            original = provider.generate
            async def fail(*args):
                await original(*args)
                if failure == "unknown":
                    from astrbot_plugin_livingemotion.runtime.background import ModelResultUnknown
                    raise ModelResultUnknown("unknown")
                return "{invalid"
            provider.generate = fail
        body = "你的存在对我没有任何价值"
        if failure == "oversize":
            body *= 10000
        message, _, record, expression = await turn(app, "failure", body)
        assert not feelings(app, record, context)
        assert not expression["bot"].get("context_emotions")
        await app.on_llm_request(message, SimpleNamespace(extra_user_content_parts=[]))
        assert len(provider.snapshots) == (0 if failure == "oversize" else 1)
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_realtime_failures_never_change_legacy_provider_routing(tmp_path):
    app, _, native, clock, _, provider = await semantic_app(tmp_path)
    try:
        native["emotion_provider_id"] = "synthetic-dedicated"
        await app.refresh_config()
        routes = []

        async def binding(_context, *, purpose=""):
            routes.append(purpose)
            return provider

        app.model_binding = binding
        generate = provider.generate

        async def invalid(*args):
            await generate(*args)
            return "{invalid"

        provider.generate = invalid
        for i, body in enumerate(("我不想听你解释了", "和你说话没有意义", "也许我高估了你")):
            clock[0] += 1
            _, context, record, _ = await turn(app, f"failed-{i}", body)
            assert not feelings(app, record, context)
        assert len(provider.snapshots) == 3
        assert set(routes) == {"emotion"}
        assert not getattr(app, "_emotion_failures", 0)
        assert not getattr(app, "_emotion_blocked_until", 0)
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_recent_history_is_latest_authorized_and_bounded(tmp_path):
    app, _, _, clock, context, provider = await semantic_app(tmp_path)
    try:
        # Historical ingestion is rule-only, to avoid unrelated model jobs.
        app.native_config["emotion_model_enabled"] = False
        await app.refresh_config()
        for i in range(12):
            clock[0] += 1
            await ingest(app, f"history-{i}", f"本对象对话{i}")
        await ingest(app, "foreign", "其它对象秘密", account="other")
        app.native_config["emotion_model_enabled"] = True
        await app.refresh_config()
        await turn(app, "current", "接着聊")
        history = provider.snapshots[-1]["data"]["recent_dialogue"]
        assert [r["text"] for r in history] == ["本对象对话10", "本对象对话11"]
        assert all(len(r["text"]) <= 400 for r in history)
        # A mismatched persona or identity cannot reuse any of those rows.
        _, normalized = await app.bridge.normalize(Message("current", "接着聊"), clock[0])
        assert len(await app.store.recent_dialogue(normalized)) == 8  # Old storage API unchanged.
        for field in ("persona_revision", "identity_revision"):
            alien = replace(normalized, context=replace(context, **{field: "different"}))
            assert not await app.store.recent_dialogue(alien)
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_bot_submitted_reply_is_included_but_other_accounts_are_excluded(tmp_path):
    app, _, _, clock, context, provider = await semantic_app(tmp_path)
    try:
        _, normalized = await app.bridge.normalize(Message("stored-human", "请帮我查一下"), clock[0])
        bot = replace(normalized, event_id="stored-bot", source_id="stored-bot",
                      actor_id=context.bot_id, actor_role=ActorRole.BOT,
                      producer="livingemotion.host", event_type="bot_reply_submitted",
                      body="我已经帮你查清楚了")
        assert (await app.store.commit_event(bot, 0)).accepted
        await turn(app, "read-bot", "你根本没有帮上忙")
        history = provider.snapshots[-1]["data"]["recent_dialogue"]
        assert any(r["role"] == "bot" and r["text"] == bot.body for r in history)
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_many_empty_turns_do_not_freeze_later_emotion_or_repair(tmp_path):
    app, _, _, clock, context, provider = await semantic_app(tmp_path)
    try:
        for i in range(18):
            clock[0] += 1
            await turn(app, f"empty-{i}", "正常聊天")
        provider.respond = lambda p: [appraisal("hurt", p["message"])]
        message, _, record, expression = await turn(app, "after-many", "我不想再搭理你")
        assert feelings(app, record, context)
        assert expression["bot"]["context_emotions"]
        clock[0] += 1
        ref = message.extra["livingemotion:event_key"]
        provider.respond = lambda p: [
            appraisal("hurt", p["message"], action="clear", context_refs=(ref,))]
        _, _, cleared, expression = await turn(
            app, "after-many-repair", "我收回刚才那句不想再搭理你的话")
        assert ref in {row["ref"] for row in provider.snapshots[-1]["data"]["recent_dialogue"]}
        assert not feelings(app, cleared, context)
        assert not expression["bot"].get("context_emotions")
        assert len(cleared.value["_account_affect"]["context_emotions"]["seen"]) <= 16
    finally:
        await app.terminate()
