from dataclasses import replace

import pytest
from astrbot_plugin_livingemotion.api import LivingEmotionAPI
from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import Context, Event, StateWrite
from astrbot_plugin_livingemotion.runtime.background import BackgroundRuntime
from astrbot_plugin_livingemotion.runtime.projector import Projector
from astrbot_plugin_livingemotion.storage import SQLiteStore


@pytest.mark.asyncio
async def test_atomic_projection_and_trace(le_store, le_event):
    config = Config()
    api = LivingEmotionAPI(le_store, config, BackgroundRuntime(le_store, config),
                           project_event=Projector(le_store, lambda: config))
    event = replace(le_event, body="我很难过", signals=("sadness",))
    result = await api.ingest_event(event)
    assert result["status"] == "accepted"
    affect = await api.get_bot_state(event.context)
    observation = await api.get_observation(event.context)
    relation = await api.get_relationship(event.context)
    assert affect["data"]["pleasure"] >= 0
    assert observation["data"]["subject_id"] == event.context.account_id
    assert relation["data"]["score"] > 0
    assert "_runtime" not in affect["data"]
    records = await le_store.query_records(event.context, "emotion")
    assert records["total"] == 1
    assert (await api.ingest_event(event))["status"] == "duplicate"
    assert (await le_store.query_records(event.context, "emotion"))["total"] == 1
    assert (await le_store.get_state(event.context, "bot")).value["_runtime"]


@pytest.mark.asyncio
async def test_projection_conflict_never_half_commits(le_store, le_event):
    projection = await Projector(le_store, Config)(le_event)
    writes = (*projection.writes, StateWrite("bot", {}, 999))
    result = await le_store.commit_event(le_event, 0, writes, projection.contributions,
                                        traces=projection.traces)
    assert result.reason_code == "version_conflict"
    assert await le_store.get_state(le_event.context, "bot") is None
    assert (await le_store.query_records(le_event.context, "emotion"))["total"] == 0
    assert await le_store.relationship_ledger(le_event.context) == []
    assert await le_store.human_watermark(le_event.context) == 0


@pytest.mark.asyncio
async def test_management_correction_ledger_audit_and_stale_generation(le_store, le_context):
    result = await le_store.correct_relationship(
        le_context, 0, expected_version=0, actor_id="verified-test-admin",
        reason="synthetic correction", score=300, frozen=True,
    )
    assert result.accepted
    state = await le_store.get_state(le_context, "relationship", le_context.account_id)
    assert state.value["score"] == 300 and state.value["frozen"]
    assert sum(row["delta"] for row in await le_store.relationship_ledger(le_context)) == 300
    assert len(await le_store.audit_records(le_context)) == 1
    rejected = await le_store.correct_relationship(
        le_context, 0, expected_version=0, actor_id="verified-test-admin",
        reason="stale version", score=999,
    )
    assert rejected.reason_code == "version_conflict"
    assert len(await le_store.audit_records(le_context)) == 1
    await le_store.clear_scope(le_context, 0, actor_id="verified-test-admin")
    stale = await le_store.correct_relationship(
        le_context, 0, expected_version=0, actor_id="verified-test-admin",
        reason="cleared", score=500,
    )
    assert stale.reason_code == "stale_generation"


@pytest.mark.asyncio
async def test_runtime_survives_reopen_and_human_watermark_retention(tmp_path, le_event):
    now = [le_event.occurred_at + 1]
    path = tmp_path / "runtime.db"
    store = SQLiteStore(path, clock=lambda: now[0])
    await store.open()
    projection = await Projector(store, Config)(le_event)
    await store.commit_event(le_event, 0, projection.writes, projection.contributions,
                             traces=projection.traces)
    runtime = (await store.get_state(le_event.context, "relationship",
                                    le_event.context.account_id)).value["_runtime"]
    watermark = await store.human_watermark(le_event.context)
    await store.register_context(le_event.context)
    await store.close()
    store = SQLiteStore(path, clock=lambda: now[0])
    await store.open()
    try:
        assert (await store.get_state(le_event.context, "relationship",
                                      le_event.context.account_id)).value["_runtime"] == runtime
        now[0] += 31 * 86400
        await store.cleanup()
        assert await store.human_watermark(le_event.context) == watermark > 0
        assert (await store.list_contexts())[0].route is None
        assert (await store.query_records(le_event.context, "emotion"))["total"] == 0
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_producer_public_comment_isolation_and_neutral_state(le_store, le_event):
    config = Config()
    api = LivingEmotionAPI(le_store, config, BackgroundRuntime(le_store, config),
                           project_event=Projector(le_store, Config),
                           instance_id=await le_store.get_instance_id())
    source = {
        "producer": "bilibot", "bot_account": "bot",
        "adapter_id": "bilibot:bot", "platform": "bili",
        "scene_kind": "public_comment", "scene_id": "video:synthetic",
        "account_id": "author", "persona_id": "native",
        "persona_revision": "native-content",
    }
    resolved = await api.resolve_producer_context(source)
    assert resolved["status"] == "ok"
    context = Context.from_dict(resolved["data"])
    assert context.instance_id == (await api.get_capabilities())["instance_id"]
    assert context.route is None
    event = Event("correlation", "bilibot", "interaction", context, "human",
                  le_event.occurred_at, "comment:123", actor_id="author")
    assert (await api.ingest_event(event))["status"] == "accepted"
    affect = (await api.get_bot_state(context))["data"]
    assert affect["reason_codes"] == ["rule_interaction"]
    assert 0 <= affect["pleasure"] < 0.01
    assert (await api.get_relationship(context))["data"]["familiarity"] is not None
    private = await api.resolve_producer_context({
        **source, "scene_kind": "private", "scene_id": "author",
    })
    assert Context.from_dict(private["data"]).scope_key != context.scope_key
    assert (await api.get_relationship(private["data"]))["data"]["score"] == 0
    availability = await api.get_availability(context)
    assert availability["available"] is False and availability["block_chat"] is False
    assert (await api.resolve_producer_context({**source, "instance_id": "forged"}))[
        "status"
    ] == "rejected"
    with pytest.raises(ValueError):
        replace(context, route="fabricated:GroupMessage:synthetic")
