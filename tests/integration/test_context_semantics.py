"""Semantic wiring with scripted providers; no claim of measured LLM comprehension."""
import asyncio
import json
import socket
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.contracts import ActorRole, Context, StateWrite
from astrbot_plugin_livingemotion.domain.context_emotion import LABELS
from astrbot_plugin_livingemotion.storage.console_data import write_relationship_override
from astrbot_plugin_livingemotion.storage.context_emotions import PERSON_KIND
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
        _, _, increased, _ = await turn(app, "increase", "这是新的刺激方式")
        value = increased.value["_account_affect"]["context_emotions"]["items"][0]
        assert value["intensity"] > original["intensity"]
        assert value["expires_at"] == original["expires_at"]
        assert provider.snapshots[-1]["data"]["context_emotions"]
        clock[0] += 1
        provider.respond = lambda p: [appraisal(kind, p["message"], action="none")]
        _, _, unchanged, _ = await turn(app, "none", "继续讲原来的事")
        assert unchanged.value["_account_affect"]["context_emotions"]["items"][0]["intensity"] < value["intensity"]
        clock[0] += 1
        provider.respond = lambda p: [appraisal(kind, p["message"], action="decrease", strength=.3)]
        _, _, decreased, _ = await turn(app, "decrease", "刚才那样说不妥，我收回一些")
        assert decreased.value["_account_affect"]["context_emotions"]["items"][0]["intensity"] < .4
        clock[0] += 1
        provider.respond = lambda p: [appraisal(kind, p["message"], action="clear")]
        _, _, cleared, expression = await turn(app, "clear", "这件事解释清楚了，放下吧")
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
@pytest.mark.parametrize("change", ["new_message", "provider", "persona", "clear", "relationship"])
async def test_context_only_late_results_are_discarded(tmp_path, change):
    app, host, _, clock, context, provider = await semantic_app(tmp_path)
    release = asyncio.Event()
    try:
        await turn(app, "charge", "先说一句")
        provider.started.clear()
        provider.release = release
        provider.respond = lambda p: [appraisal("hurt", p["message"])]
        message, _, before = await ingest(app, "delayed", "再见，我不想见到你")
        await asyncio.wait_for(provider.started.wait(), 2)
        if change == "new_message":
            clock[0] += 1
            _, _, before = await ingest(app, "newer", "刚才说得过了")
            # Keep the newer event off the provider so only the old result is tested.
            newer_key = next(k for k in app._refinement_tasks if k != message.extra["livingemotion:event_key"]
                             and not app._refinement_tasks[k]["task"].done())
            app._refinement_tasks[newer_key]["task"].cancel()
        elif change == "provider":
            provider.fingerprint = "changed"
        elif change == "persona":
            host.prompt = "changed native persona"
        elif change == "clear":
            await app.store.clear_scope(context, await app.store.get_generation(context))
            before = None
        else:
            await write_relationship_override(app.store, context, expected_version=1,
                actor_id="offline-test", reason="edit while analyzing", score=60)
            before = await app.store.get_state(context, "relationship", context.account_id)
        release.set()
        await app.await_context_refinement(message.extra["livingemotion:event_key"])
        assert await app.store.get_state(context, "relationship", context.account_id) == before
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
        message, _, record, expression = await turn(app, "timeout", "你就是个废物")
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
async def test_user_dimension_person_write_retries_on_version_conflict(tmp_path, monkeypatch):
    app, host, _, clock, context, provider = await semantic_app(
        tmp_path, context_emotions_dimension="user")
    try:
        provider.respond = lambda p: []
        await turn(app, "warm", "先聊一句")
        original, raced = app.store.refine_context_emotions, []

        async def racing(event, generation, write, trace):
            if not raced:
                # The same QQ's record changes after the model verdict but before the write.
                current = await app.store.context_emotion_record(context)
                def bump(db):  # Store work runs on the connection's worker thread.
                    return app.store._write_person(db, context, StateWrite(
                        PERSON_KIND, current.value, current.version, context.account_id), clock[0])
                await app.store._run(bump)
                raced.append(True)
            return await original(event, generation, write, trace)

        monkeypatch.setattr(app.store, "refine_context_emotions", racing)
        clock[0] += 601
        body = "你的存在对我没有任何价值"
        provider.respond = lambda p: [appraisal("hurt", body)]
        await turn(app, "joint", body)
        assert raced == [True]
        record = await app.store.context_emotion_record(context)
        # 1 warm-up, 2 the racing write, 3 this verdict replayed on the latest record.
        assert record.version == 3 and [row["kind"] for row in record.value[
            "context_emotions"]["items"]] == ["hurt"]
        assert app.emotion_model_analysis([context])["reason_code"] == "completed"
        assert len(provider.snapshots) == 2  # A conflict replays the verdict, never the paid call.
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
        body = "你就是个废物" if failure != "oversize" else "你就是个废物" * 10000
        message, _, record, expression = await turn(app, "failure", body)
        assert not feelings(app, record, context)
        assert not expression["bot"].get("context_emotions")
        await app.on_llm_request(message, SimpleNamespace(extra_user_content_parts=[]))
        assert len(provider.snapshots) == (0 if failure == "oversize" else 1)
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
        assert [r["text"] for r in history] == [f"本对象对话{i}" for i in range(4, 12)]
        assert all(len(r["text"]) <= 400 for r in history)
        # A mismatched persona or identity cannot reuse any of those rows.
        _, normalized = await app.bridge.normalize(Message("current", "接着聊"), clock[0])
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
        _, _, record, expression = await turn(app, "after-many", "我不想再搭理你")
        assert feelings(app, record, context)
        assert expression["bot"]["context_emotions"]
        clock[0] += 1
        provider.respond = lambda p: [appraisal("hurt", p["message"], action="clear")]
        _, _, cleared, expression = await turn(app, "after-many-repair", "误会已经解开")
        assert not feelings(app, cleared, context)
        assert not expression["bot"].get("context_emotions")
        assert len(cleared.value["_account_affect"]["context_emotions"]["seen"]) <= 16
    finally:
        await app.terminate()
