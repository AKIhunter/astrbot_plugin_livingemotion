"""Real SQLite/CAS checks for persisted joy budgets; no model or external delivery."""
from dataclasses import replace
import json

import pytest

from astrbot_plugin_livingemotion.api import LivingEmotionAPI
from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import canonical_json
from astrbot_plugin_livingemotion.runtime.background import BackgroundRuntime
from astrbot_plugin_livingemotion.runtime.projector import Projector, account_affect
from astrbot_plugin_livingemotion.storage import SQLiteStore
from test_application import generation_app, Message


def facade(store):
    config = Config(night_policy_version=2, timezone="UTC")
    store.config = config
    return LivingEmotionAPI(store, config, BackgroundRuntime(store, config),
                            project_event=Projector(store, lambda: config))


async def test_shared_window_follows_owner_and_accounts_remain_independent(le_store, le_event):
    api = facade(le_store)
    le_store.clock = lambda: le_event.occurred_at
    one = le_event.context
    two = replace(one, scene_kind="group", scene_id="group", account_id="human-2")
    for context in (one, two):
        await le_store.initialize_state_mode(context, shared=True)
    first = replace(le_event, body="你真棒")
    second = replace(le_event, context=two, actor_id=two.account_id, body="谢谢你",
                     source_id="second", signals=("native_bot_mention",))
    assert (await api.ingest_event(first))["status"] == "accepted"
    before = await le_store.get_state(one, "bot")
    assert (await api.ingest_event(second))["status"] == "accepted"
    after = await le_store.get_state(two, "bot")
    assert after.owner == before.owner
    assert after.value["pleasure"] == pytest.approx(before.value["pleasure"])
    assert after.value["_runtime"]["joy_window"] == before.value["_runtime"]["joy_window"]
    for context in (one, two):
        record = await le_store.get_state(context, "relationship", context.account_id)
        personal = account_affect(record, context)
        assert personal is not None
        assert personal[0].pleasure == pytest.approx(.05)
        assert len(personal[1]["joy_window"]) == 1
    isolated = replace(two, persona_id="different")
    await le_store.initialize_state_mode(isolated, shared=True)
    event = replace(second, context=isolated, source_id="isolated")
    assert (await api.ingest_event(event))["status"] == "accepted"
    assert (await le_store.get_state(isolated, "bot")).value["pleasure"] == pytest.approx(.05)


async def test_sqlite_restart_and_conflict_do_not_reset_or_double_charge(tmp_path, le_event):
    at = le_event.occurred_at
    path = tmp_path / "joy.sqlite3"
    store = SQLiteStore(path, clock=lambda: at)
    await store.open()
    first = replace(le_event, body="你真棒")
    try:
        await store.initialize_state_mode(le_event.context, shared=True)
        api = facade(store)
        assert (await api.ingest_event(first))["status"] == "accepted"
        before = (await store.get_state(le_event.context, "bot")).value["_runtime"]["joy_window"]
    finally:
        await store.close()
    store = SQLiteStore(path, clock=lambda: at)
    await store.open()
    try:
        api = facade(store)
        assert (await store.get_state(le_event.context, "bot")).value["_runtime"]["joy_window"] == before
        stale_event = replace(first, source_id="stale", body="我关心你")
        stale = await api._project_event(stale_event)
        latest_event = replace(first, source_id="latest", body="你很烦人")
        assert (await api.ingest_event(latest_event))["status"] == "accepted"
        latest = await store.get_state(le_event.context, "bot")
        rejected = await store.commit_event(stale_event, 0, stale.writes, stale.contributions,
                                            traces=stale.traces)
        assert rejected.reason_code == "version_conflict"
        assert (await store.get_state(le_event.context, "bot")).value == latest.value
        assert (await api.ingest_event(first))["status"] == "duplicate"
        assert (await store.get_state(le_event.context, "bot")).value == latest.value
        assert (await api.ingest_event(stale_event))["status"] == "accepted"
        final = await store.get_state(le_event.context, "bot")
        assert sum(max(0, row[1]) for row in final.value["_runtime"]["joy_window"]) == pytest.approx(.05)
        assert len(canonical_json(final.value)) < 65536
        await store.clear_scope(le_event.context, 0)
        result = await store.commit_event(stale_event, 0, stale.writes)
        assert not result.accepted
    finally:
        await store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("intervene", [False, True])
async def test_model_replacement_uses_seed_budget_and_fences_newer_state(tmp_path, intervene):
    import asyncio
    app, host, native, _, context, binding, _ = await generation_app(tmp_path)
    release, started = asyncio.Event(), asyncio.Event()
    try:
        native["emotion_model_enabled"] = True
        await app.refresh_config()

        async def generate(*_):
            started.set()
            await release.wait()
            return json.dumps({"rule_version": "emotion-2", "delta": {"pleasure": .12},
                               "confidence": 1, "appraisals": [
                                   {"signal": "praise", "evidence": "你真棒"}]})

        binding.generate = generate
        message = Message("joy-model", "你真棒")
        await app.on_message(message)
        await asyncio.wait_for(started.wait(), 2)
        local = await app.store.get_state(context, "bot")
        assert len(local.value["_runtime"]["joy_window"]) == 1
        if intervene:
            await app.on_message(Message("newer", "你好"))
        current = await app.store.get_state(context, "bot")
        release.set()
        await asyncio.wait_for(asyncio.gather(*tuple(app._actions)), 2)
        after = await app.store.get_state(context, "bot")
        assert after.version == current.version + (0 if intervene else 1)
        assert len(after.value["_runtime"]["joy_window"]) == 1
        assert sum(max(0, row[1]) for row in after.value["_runtime"]["joy_window"]) == pytest.approx(.05)
        record = await app.store.get_state(context, "relationship", context.account_id)
        assert len(account_affect(record, context)[1]["joy_window"]) == 1
        assert host.sends == 0
    finally:
        release.set()
        await app.terminate()
