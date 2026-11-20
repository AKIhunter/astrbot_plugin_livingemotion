"""Virtual clock + temporary SQLite: no host actions or provider calls."""
import asyncio
import json
from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.runtime.console import Console
from astrbot_plugin_livingemotion.runtime.night import NightRuntime
from astrbot_plugin_livingemotion.storage import SQLiteStore
from astrbot_plugin_livingemotion.storage.console_data import (
    query_relationships, refresh_relationship_lists, relationship_list_delay,
    write_relationship_override,
)
from astrbot_plugin_livingemotion.storage.promise_store import PromiseStore


def local_time(value, timezone="Asia/Shanghai"):
    return datetime.fromisoformat(value).replace(tzinfo=ZoneInfo(timezone)).timestamp()


def selection(context, **changes):
    return {"persona_id": context.persona_id, "view_scope": "global", **changes}


async def score(store, context, value, version=0):
    await store.register_context(context)
    await store.get_generation(context)
    await write_relationship_override(store, context, score=value, expected_version=version,
                                      actor_id="offline", reason="synthetic score")


async def test_daily_score_order_freeze_reopen_and_midnight(le_store, le_context):
    clock = [local_time("2026-11-20T23:59:58")]
    le_store.clock = lambda: clock[0]
    people = [replace(le_context, account_id=f"user-{i}") for i in range(13)]
    for i, context in enumerate(people):
        await score(le_store, context, 60 + i / 10)
    params = selection(le_context)
    first = await query_relationships(le_store, "local", params, daily_list=True)
    assert [n["score"] for n in first["items"]] == sorted(
        [60 + i / 10 for i in range(13)], reverse=True)[:10]
    assert first["total"] == 13 and first["list_snapshot"]["initial"]
    await score(le_store, people[0], 99, version=1)
    clock[0] += 1
    await refresh_relationship_lists(le_store, "local", le_store.config)
    reopened = SQLiteStore(le_store.path, clock=le_store.clock)
    await reopened.open()
    try:
        old = await query_relationships(reopened, "local", params, daily_list=True)
        assert old["items"] == first["items"] and old["list_snapshot"] == first["list_snapshot"]
        targeted = await query_relationships(reopened, "local", params, query="user-0", daily_list=True)
        assert targeted["items"][0]["score"] == 60
        assert targeted["live_items"][0]["score"] == targeted["nodes"][0]["score"] == 99
        assert targeted["live_items"][0]["version"] == 2
        clock[0] += 1
        await refresh_relationship_lists(reopened, "local", reopened.config)
        next_day = await query_relationships(reopened, "local", params, daily_list=True)
        assert next_day["items"][0]["account_id"] == "user-0"
        assert next_day["list_snapshot"]["day"] == "2026-11-21"
        assert next_day["list_snapshot"]["computed_at"] == clock[0]
        assert not next_day["list_snapshot"]["initial"]
        assert next_day["list_snapshot"]["scheduled_for"] == clock[0]
    finally:
        await reopened.close()


async def test_snapshot_selection_isolation_new_people_and_cleared_generation(le_store, le_context):
    clock = [local_time("2026-11-20T12:00:00")]
    le_store.clock = lambda: clock[0]
    qq = replace(le_context, platform="qq", account_id="target")
    other = replace(qq, platform="other")
    persona = replace(qq, persona_id="other-persona")
    instance = replace(qq, instance_id="other-instance")
    for context, value in [(qq, 61), (other, 62), (persona, 63), (instance, 64)]:
        await score(le_store, context, value)
    await refresh_relationship_lists(le_store, "local", le_store.config)
    result = await query_relationships(le_store, "local", selection(qq), daily_list=True)
    assert [(n["platform"], n["score"]) for n in result["items"]] == [("other", 62), ("qq", 61)]
    filtered = await query_relationships(le_store, "local", selection(qq, platform="qq"), daily_list=True)
    assert filtered["total"] == 1 and filtered["items"][0]["score"] == 61
    new = replace(qq, account_id="new")
    await score(le_store, new, 90)
    today = await query_relationships(le_store, "local", selection(qq), daily_list=True)
    assert today["total"] == 2 and len(today["nodes"]) == 3
    cleared = await le_store.clear_scope(qq, await le_store.get_generation(qq),
                                         actor_id="offline", reason_code="synthetic_clear")
    assert cleared.accepted
    hidden = await query_relationships(le_store, "local", selection(qq, platform="qq"), daily_list=True)
    assert hidden["total"] == 0, hidden["items"]  # A stale daily row never resurrects a cleared scope.
    clock[0] = local_time("2026-11-21T00:00:00")
    tomorrow = await query_relationships(le_store, "local", selection(qq), daily_list=True)
    assert tomorrow["items"][0]["account_id"] == "new"


@pytest.mark.parametrize("day,hours", [("2026-03-08T00:00:00", 23), ("2026-11-01T00:00:00", 25)])
def test_midnight_delay_uses_timezone_calendar(day, hours):
    config = replace(Config(), timezone="America/New_York")
    assert relationship_list_delay(local_time(day, config.timezone), config) == hours * 3600


async def test_background_updates_at_midnight_without_page(le_store, le_context, monkeypatch):
    clock = [local_time("2026-11-20T23:59:58")]
    le_store.clock = lambda: clock[0]
    await score(le_store, le_context, 61.2)
    delays = []
    ticks = []

    async def sleep(delay):
        if delays:
            raise asyncio.CancelledError
        delays.append(delay)
        clock[0] += delay

    async def tick():
        ticks.append(clock[0])

    monkeypatch.setattr(asyncio, "sleep", sleep)
    app = SimpleNamespace(closed=False, config=replace(Config(), enabled=True, scheduler_seconds=60),
                          store=le_store, instance_id="local", tick=tick)
    with pytest.raises(asyncio.CancelledError):
        await NightRuntime._tick_loop(app)
    assert delays == [2] and ticks == [clock[0]]
    result = await query_relationships(le_store, "local", selection(le_context), daily_list=True)
    assert result["list_snapshot"]["day"] == "2026-11-21"
    assert result["list_snapshot"]["computed_at"] == local_time("2026-11-21T00:00:00")


async def test_active_promise_panel_has_required_fields_and_never_mutates(le_store, le_context):
    await le_store.register_context(le_context)
    promises = PromiseStore(le_store)
    created = await promises.create(le_context, description="synthetic reminder", note="",
                                    bucket="稍后", due_at=le_store.clock() + 60)
    await le_store._run(lambda db: db.execute(
        "UPDATE promises SET status='waiting',retry_count=2,waiting_since=?,action_result_json=? "
        "WHERE promise_id=?", (le_store.clock(), json.dumps({"prompt_retry_count": 1}), created["promise_id"])))
    before = await promises.get(created["promise_id"])
    service = SimpleNamespace(promises=promises, retry_limit=3, wait_timeout=600)
    app = SimpleNamespace(config=replace(Config(), promise_enabled=True), store=le_store,
                          _promises=lambda: service)
    panel = await Console._promise_panel(app, "")
    assert panel["total"] == 1
    row = panel["items"][0]
    assert row["retry_count"] == 2 and row["prompt_retry_count"] == 1
    assert row["waiting_deadline"] == le_store.clock() + 600
    assert row["target_id"] == le_context.scene_id
    assert await promises.get(created["promise_id"]) == before
