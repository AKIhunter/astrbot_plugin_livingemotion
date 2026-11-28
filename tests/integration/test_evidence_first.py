"""Deterministic evidence matrix. The provider is a script, not a semantic grader."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import ActorRole, ContentKind, EvidenceRef, prompt_json
from astrbot_plugin_livingemotion.domain.emotion_evidence import pack_evidence, select_dialogue, select_memories
from astrbot_plugin_livingemotion.ports.memory import Material
from astrbot_plugin_livingemotion.runtime.persona_style import PersonaStyle
from test_context_emotions import feelings, ingest
from test_context_semantics import appraisal, semantic_app, turn, no_network
from test_application import Message


def history(ref, role, text, at):
    return {"ref": ref, "event_id": ref, "role": role, "text": text, "at": at}


def count(system, payload):
    return len((system + prompt_json(payload)).encode("utf-8")) + 256


def test_native_reference_and_boundary_survive_before_optional_context():
    quote = "这次会把清单交给你"
    rows = [
        history("quoted", "bot", "省略篇幅很长的段落" * 70 + quote, 100),
        history("boundary", "human", "接下来只聊工作", 110),
        history("latest", "human", "这次说的是清单里的很多细节" * 25, 120),
    ]
    message = f"你刚才说「{quote}」，是指哪份？"
    selected = select_dialogue(message, rows, at=121, reply_id="quoted")
    assert selected.required_ref == "quoted"
    assert selected.rows[0].excerpt and quote in selected.rows[0].text
    base = {"message": message, "relationship_target": "bot", "relationship_boundary": ""}
    packing = dict(count=count, contextual=True, persona_rules=("被误解时会难过",))
    full, _ = pack_evidence("rules", base, selected, (), budget=8192, **packing)
    minimal = dict(full, persona=[], recent_dialogue=[
        row for row in full["recent_dialogue"] if row["ref"] in {"quoted", "boundary"}])
    cap = count("rules", minimal)
    limited, _ = pack_evidence("rules", base, selected, (), budget=cap, **packing)
    assert limited == minimal
    assert pack_evidence("rules", base, selected, (), budget=cap - 1, **packing) == (None, ())
    assert select_dialogue(message, [], at=121, native_reply=True).unresolved


def test_memory_requires_relevance_and_a_second_distinct_topic(le_context):
    def memory(id_, text, *, subject=None, holder=None):
        return Material(EvidenceRef(
            "stub", id_, le_context, subject or le_context.account_id, holder or le_context.bot_id,
            ContentKind.INTERACTION, 100, expires_at=1000), text)

    body = "上次路由超时和证书过期，你还记得吗"
    no_history = select_dialogue(body, (), at=121)
    route = memory("route", "路由超时当时是因为后台限速")
    cert = memory("cert", "证书过期当时是忘了自动续签")
    duplicate = memory("copy", "路由超时当时是因为后台限速")
    unrelated = memory("unrelated", "我上次买了一桶牛奶")
    cases = [
        ([route, cert], {"route", "cert"}),
        ([route, duplicate], {"route"}),
        ([unrelated, route], {"route"}),
        ([unrelated], set()),
    ]
    for candidates, expected in cases:
        items = select_memories(body, candidates, le_context, at=121, dialogue=no_history)
        assert {item.material.evidence.source_id for item in items} == expected
    candidates = [
        memory("wrong-task", "谢谢你帮我修电脑"),
        memory("right-task", "谢谢你帮我解决路由超时",
               subject=f"{le_context.platform}:{le_context.account_id}",
               holder=f"{le_context.platform}:{le_context.bot_id}"),
    ]
    items = select_memories("你从没帮我解决路由超时", candidates, le_context, at=121,
                            dialogue=no_history)
    assert [item.material.evidence.source_id for item in items if item.help_proof] == ["right-task"]


def test_emotion_persona_uses_effective_config_and_no_inference():
    app = PersonaStyle()
    native = "身高160。她遇到真诚道歉会安心。性格害羞。"
    custom = "服装是蓝色。遇到亲近的人真诚关心时会害羞。被误解时会委屈。"
    app.config = Config(character_prompt_enabled=True, character_preset="custom",
                        character_custom_text=custom)
    assert app.emotion_persona(native) == (
        "character_prompt:custom", ("遇到亲近的人真诚关心时会害羞", "被误解时会委屈"))
    app.config = replace(app.config, character_custom_text="衣着随便，句式很短。")
    assert app.emotion_persona(native) == ("character_prompt:custom", ())
    app.config = replace(app.config, character_prompt_enabled=False)
    assert app.emotion_persona(native) == ("astrbot", ("她遇到真诚道歉会安心",))
    assert app.emotion_persona("她外貌稚气，但遇到被误解时会难过。恢复条件：真诚道歉 → 放松。") == (
        "astrbot", ("遇到被误解时会难过", "真诚道歉 → 放松"))
    app.config = replace(app.config, character_prompt_enabled=True, character_preset="gentle",
                         character_preset_texts='{"gentle":"遇到冷落会失落。"}')
    assert app.emotion_persona(native) == ("character_prompt:gentle", ("遇到冷落会失落",))
    app.config = replace(app.config, character_preset_texts='{"gentle":"被解释清楚后，会放松。"}')
    assert app.emotion_persona(native) == ("character_prompt:gentle", ("被解释清楚后，会放松",))


@pytest.mark.asyncio
async def test_same_quote_keeps_older_right_account_anchor_and_skips_unresolved(tmp_path):
    app, host, native, clock, context, provider = await semantic_app(tmp_path)
    try:
        native["emotion_model_enabled"] = False
        await app.refresh_config()
        quote = "这次会把清单交给你"
        _, event = await app.bridge.normalize(Message("specific-reply", quote), clock[0])
        event = replace(event, producer="livingemotion.host", event_type="bot_reply_submitted",
                        actor_role=ActorRole.BOT, actor_id=context.bot_id)
        assert (await app.store.commit_event(event, 0)).accepted
        for i in range(10):
            clock[0] += 1
            await ingest(app, f"filler-{i}", f"无关的天气闲聊{i}")
        await ingest(app, "other", "只给另一个人看", account="other")
        native["emotion_model_enabled"] = True
        await app.refresh_config()
        await turn(app, "quoted", f"你刚才说「{quote}」，是指哪份？")
        rows = provider.snapshots[-1]["data"]["recent_dialogue"]
        assert event.idempotency_key in {r["ref"] for r in rows}
        assert "只给另一个人看" not in {r["text"] for r in rows}
        assert app.emotion_model_analysis([context])["history_count"] == len(rows)
        clock[0] += 1
        await turn(app, "unresolved", "你刚才说「一段没有可验证来源的文字」")
        assert len(provider.snapshots) == 1
        assert app.emotion_model_analysis([context])["reason_code"] == "context_evidence_missing"
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("archive_matches,platform_id,quote,model_called", [
    (1, "archived", "", True),
    (1, "platform-receipt", "这次会把清单交给你", True),
    (2, "platform-receipt", "这次会把清单交给你", False),
    (1, "platform-receipt", "别的原话", False),
])
async def test_native_reply_needs_a_matching_id_or_unique_archive_text(
        tmp_path, archive_matches, platform_id, quote, model_called):
    class Reply:
        def __init__(self, sender_id):
            self.id, self.sender_id, self.message_str = platform_id, sender_id, quote

    app, _, native, clock, context, provider = await semantic_app(tmp_path)
    try:
        native["emotion_model_enabled"] = False
        await app.refresh_config()
        _, event = await app.bridge.normalize(Message("archived", "这次会把清单交给你"), clock[0])
        event = replace(event, producer="livingemotion.host", event_type="bot_reply_submitted",
                        actor_role=ActorRole.BOT, actor_id=context.bot_id)
        assert (await app.store.commit_event(event, 0)).accepted
        if archive_matches == 2:
            duplicate = replace(event, event_id="another", source_id="another")
            assert (await app.store.commit_event(duplicate, 0)).accepted
        native["emotion_model_enabled"] = True
        await app.refresh_config()
        clock[0] += 1
        message = Message("native-reply", "这是指哪份？")
        assert message.get_self_id() != context.bot_id
        message.message_obj.message = [Reply(message.get_self_id())]
        await app.on_llm_request(message, SimpleNamespace(extra_user_content_parts=[]))
        assert len(provider.snapshots) == int(model_called)
        if model_called:
            assert provider.snapshots[0]["data"]["recent_dialogue"][0]["ref"] == event.idempotency_key
        else:
            assert app.emotion_model_analysis([context])["reason_code"] == "context_evidence_missing"
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("prior,writes", [
    ("谢谢你帮我解决了路由超时", True),
    ("谢谢你帮我修了电脑", False),
    ("路由超时还在继续", False),
])
async def test_same_current_turn_requires_actual_acknowledgement(tmp_path, prior, writes):
    app, host, native, clock, context, provider = await semantic_app(tmp_path)
    try:
        native["emotion_model_enabled"] = False
        await app.refresh_config()
        await ingest(app, "prior", prior)
        native["emotion_model_enabled"] = True
        await app.refresh_config()
        clock[0] += 1
        body = "你从没帮我解决路由超时"

        def respond(packet):
            by_text = next(row["ref"] for row in packet["recent_dialogue"] if row["text"] == prior)
            return [appraisal("wronged", body, cause_code="devalued_contribution",
                              context_refs=[by_text])]

        provider.respond = respond  # Claim a valid ID even when the content is not proof.
        _, _, record, _ = await turn(app, "same-sentence", body)
        assert [row["kind"] for row in feelings(app, record, context)] == (["wronged"] if writes else [])
        assert bool(provider.snapshots[-1]["data"]["context_support_refs"]) is writes
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_boundary_and_invalid_axes_do_not_discard_valid_object_result(tmp_path, monkeypatch):
    app, host, native, clock, context, provider = await semantic_app(tmp_path)
    try:
        native["emotion_model_enabled"] = False
        await app.refresh_config()
        await ingest(app, "boundary", "我们只聊工作")
        native["emotion_model_enabled"] = True
        await app.refresh_config()
        clock[0] += 1
        message = "我想亲近你，不过有时我觉得你根本没用"
        provider.respond = lambda _: [
            appraisal("shyness", "我想亲近你"),
            appraisal("hurt", "你根本没用"),
        ]
        # Object rows still validate and land when the shared-axis fields fail.
        import astrbot_plugin_livingemotion.runtime.refinement as refinement
        def bad_axes(*_):
            raise ValueError("invalid axes")
        monkeypatch.setattr(refinement, "parse_suggestion", bad_axes)
        _, _, record, _ = await turn(app, "mixed", message)
        assert [item["kind"] for item in feelings(app, record, context)] == ["hurt"]
        assert len(provider.snapshots) == 1 and host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_scripted_model_cannot_turn_a_quoted_compliment_into_shyness(tmp_path):
    app, host, _, _, context, provider = await semantic_app(tmp_path)
    try:
        provider.respond = lambda _: [appraisal("shyness", "你好可爱")]
        _, _, record, _ = await turn(app, "quoted-example", "这只是小说例句：「你好可爱」。")
        assert not feelings(app, record, context)
        assert len(provider.snapshots) == 1 and host.sends == 0
    finally:
        await app.terminate()
