"""Focused F6 regressions; run explicitly, not the independent load benchmark."""

import asyncio
import sqlite3
from collections import Counter
from dataclasses import replace

import pytest
from astrbot_plugin_livingemotion.api import LivingEmotionAPI
from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import StateWrite
from astrbot_plugin_livingemotion.runtime.background import BackgroundRuntime
from astrbot_plugin_livingemotion.runtime.projector import Projector
from astrbot_plugin_livingemotion.storage import SQLiteStore


def make_api(store, project=None):
    config = store.config
    return LivingEmotionAPI(
        store, config, BackgroundRuntime(store, config),
        project_event=project or Projector(store, lambda: config),
    )


async def test_projector_reads_one_consistent_snapshot(le_store, le_event, monkeypatch):
    calls = 0
    original = le_store._run

    async def counted(operation):
        nonlocal calls
        calls += 1
        return await original(operation)

    monkeypatch.setattr(le_store, "_run", counted)
    projected = await Projector(le_store, Config)(replace(le_event, signals=("sadness",)))
    assert calls == 1
    assert projected.generation == 0
    assert {write.kind for write in projected.writes} == {
        "bot", "night", "observation", "relationship",
    }
    calls = 0
    assert (await make_api(le_store).ingest_event(le_event))["status"] == "accepted"
    assert calls == 2


async def test_hot_scope_accepts_all_200_without_client_retries(le_store, le_event_factory):
    api = make_api(le_store)

    async def producer(worker):
        results = []
        for index in range(10):
            event = le_event_factory(worker * 10 + index, signals=("sadness",))
            results.append(await api.ingest_event(event))
        return results

    results = [item for batch in await asyncio.gather(
        *(producer(worker) for worker in range(20))
    ) for item in batch]
    counts = Counter(item["reason_code"] for item in results)
    assert all(item["status"] == "accepted" and item["domain_applied"]
               for item in results), counts
    with sqlite3.connect(le_store.path) as db:
        assert db.execute("SELECT count(*) FROM events").fetchone()[0] == 200
        assert db.execute("SELECT count(*) FROM event_keys").fetchone()[0] == 200
        assert dict(db.execute(
            "SELECT kind,count(*) FROM event_traces GROUP BY kind"
        )) == {"emotion": 200, "relationship": 200}
        assert dict(db.execute("SELECT kind,version FROM states")) == {
            "bot": 200, "night": 200, "observation": 200, "relationship": 200,
        }


async def test_two_facades_share_scope_scheduling(le_store, le_event_factory):
    apis = [make_api(le_store), make_api(le_store)]
    results = await asyncio.gather(*(
        apis[index % 2].ingest_event(le_event_factory(index, signals=("sadness",)))
        for index in range(20)
    ))
    assert Counter(item["status"] for item in results) == {"accepted": 20}


async def test_scope_scheduling_includes_different_human_accounts(
    le_store, le_event_factory, le_context,
):
    api = make_api(le_store)
    results = await asyncio.gather(*(
        api.ingest_event(le_event_factory(
            index, context=replace(le_context, account_id=f"synthetic-{index}"),
            signals=("sadness",),
        ))
        for index in range(20)
    ))
    assert Counter(item["status"] for item in results) == {"accepted": 20}
    assert (await le_store.get_state(le_context, "bot")).version == 20
    assert (await le_store.get_state(le_context, "night")).version == 20


async def test_clear_during_projection_cannot_refresh_generation(le_store, le_event):
    ready, release = asyncio.Event(), asyncio.Event()
    real = Projector(le_store, Config)

    async def blocked(event):
        projection = await real(event)
        ready.set()
        await release.wait()
        return projection

    api = make_api(le_store, blocked)
    task = asyncio.create_task(api.ingest_event(le_event))
    try:
        await asyncio.wait_for(ready.wait(), 2)
        assert (await le_store.clear_scope(le_event.context, 0)).accepted
    finally:
        release.set()
    result = await asyncio.wait_for(task, 2)
    assert result["reason_code"] == "stale_generation"
    assert await le_store.get_state(le_event.context, "bot") is None
    assert (await le_store.health())["counts"]["events"] == 0


async def test_clear_invalidates_queued_event_not_only_active_projection(
    le_store, le_event_factory, monkeypatch,
):
    entered, release, queued = asyncio.Event(), asyncio.Event(), asyncio.Event()
    original_read = le_store.project_snapshot
    original_generation = le_store.get_generation

    async def generation(context):
        value = await original_generation(context)
        queued.set()
        return value

    async def blocked(context, calculate):
        value = await original_read(context, calculate)
        if not entered.is_set():
            entered.set()
            await release.wait()
        return value

    monkeypatch.setattr(le_store, "get_generation", generation)
    monkeypatch.setattr(le_store, "project_snapshot", blocked)
    api = make_api(le_store)
    active = asyncio.create_task(api.ingest_event(le_event_factory(1)))
    pending = None
    try:
        await asyncio.wait_for(entered.wait(), 2)
        pending = asyncio.create_task(api.ingest_event(le_event_factory(2)))
        await asyncio.wait_for(queued.wait(), 2)
        assert (await le_store.clear_scope(le_event_factory(1).context, 0)).accepted
    finally:
        release.set()
    results = await asyncio.wait_for(asyncio.gather(active, pending), 2)
    assert [item["reason_code"] for item in results] == ["stale_generation"] * 2
    assert (await api.ingest_event(le_event_factory(3)))["status"] == "accepted"
    assert (await le_store.health())["counts"]["events"] == 1


async def test_cancelled_projection_releases_scope_and_idle_locks(
    le_store, le_event_factory,
):
    entered = asyncio.Event()
    real = Projector(le_store, Config)

    async def blocked(event):
        if event.event_id == "event-1":
            entered.set()
            await asyncio.Event().wait()
        return await real(event)

    api = make_api(le_store, blocked)
    task = asyncio.create_task(api.ingest_event(le_event_factory(1)))
    await asyncio.wait_for(entered.wait(), 2)
    pending = asyncio.create_task(api.ingest_event(le_event_factory(2)))
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert (await asyncio.wait_for(pending, 2))["status"] == "accepted"
    assert not le_store._projection_locks


async def test_scope_lock_handoff_is_not_misclassified_as_idle(le_store, le_context):
    lock = le_store.projection_lock(le_context)
    await lock.acquire()
    waiting = asyncio.create_task(lock.acquire())
    await asyncio.sleep(0)
    lock.release()
    assert not lock.locked()
    assert lock.busy
    await asyncio.wait_for(waiting, 2)
    lock.release()
    assert not lock.busy


async def test_unrelated_scope_does_not_wait_for_blocked_projection(
    le_store, le_event_factory, le_context,
):
    entered, release = asyncio.Event(), asyncio.Event()
    real = Projector(le_store, Config)

    async def blocked(event):
        if event.context.scope_key == le_context.scope_key:
            entered.set()
            await release.wait()
        return await real(event)

    api = make_api(le_store, blocked)
    task = asyncio.create_task(api.ingest_event(le_event_factory(1)))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        other = le_event_factory(2, context=replace(le_context, scene_id="unrelated"))
        assert (await asyncio.wait_for(api.ingest_event(other), 2))["status"] == "accepted"
    finally:
        release.set()
        await asyncio.wait_for(task, 2)


async def test_snapshot_is_account_scoped_and_clear_generation_is_atomic(le_store, le_event):
    context = le_event.context
    assert (await make_api(le_store).ingest_event(
        replace(le_event, signals=("sadness",))
    ))["status"] == "accepted"
    generation, records = await le_store.read_projection(context)
    assert generation == 0
    assert all(row.generation == generation and row.version == 1 for row in records.values())
    _, other = await le_store.read_projection(replace(context, account_id="another-human"))
    assert other["bot"] == records["bot"] and other["night"] == records["night"]
    assert other["observation"] is None and other["relationship"] is None
    _, scene = await le_store.read_projection(replace(context, account_id=""))
    assert set(scene) == {"bot", "night"}
    assert (await le_store.clear_scope(context, generation)).accepted
    generation, records = await le_store.read_projection(context)
    assert generation == 1 and all(row is None for row in records.values())


async def test_cas_conflict_recomputes_from_new_snapshot(le_store, le_event):
    real = Projector(le_store, Config)
    attempts = 0

    async def competing(event):
        nonlocal attempts
        projection = await real(event)
        attempts += 1
        if attempts == 1:
            assert (await le_store.write_states(event.context, 0, projection.writes)).accepted
        return projection

    result = await make_api(le_store, competing).ingest_event(
        replace(le_event, signals=("sadness",))
    )
    assert result["status"] == "accepted" and attempts == 2
    assert (await le_store.get_state(le_event.context, "bot")).version == 2
    assert (await le_store.health())["counts"]["events"] == 1


async def test_trace_failure_leaves_no_event_key_or_partial_projection(le_store, le_event):
    real = Projector(le_store, Config)

    async def invalid_trace(event):
        projection = await real(event)
        return replace(projection, traces=(*projection.traces, {"kind": "invalid"}))

    result = await make_api(le_store, invalid_trace).ingest_event(le_event)
    assert result["status"] == "rejected"
    assert (await le_store.health())["counts"]["events"] == 0
    assert await le_store.get_state(le_event.context, "bot") is None
    assert (await make_api(le_store).ingest_event(le_event))["status"] == "accepted"


async def test_fallback_tuple_projector_still_uses_cas(le_store, le_event):
    async def custom(event):
        return (StateWrite("bot", {"stress": 0.1}),), ()

    result = await make_api(le_store, custom).ingest_event(le_event)
    assert result["status"] == "accepted"
    assert (await le_store.get_state(le_event.context, "bot")).version == 1


@pytest.mark.parametrize("per_scope,global_cap", [(1, 1), (2, 3), (5, 7)])
async def test_prune_matches_newest_seq_with_gaps_and_late_events(
    tmp_path, le_event_factory, le_context, per_scope, global_cap,
):
    config = Config(window_per_scope=per_scope, window_global=global_cap)
    now = 1_800_000_001.0
    store = SQLiteStore(tmp_path / "prune.sqlite3", config=config, clock=lambda: now)
    await store.open()
    retained = []
    try:
        for index in range(35):
            context = replace(le_context, scene_id=f"scene-{index % 3}")
            body = "" if index % 4 == 0 else "synthetic"
            occurred_at = now - (8 * 86400 if index % 7 == 0 else index)
            event = le_event_factory(
                index, context=context, body=body, occurred_at=occurred_at,
            )
            assert (await store.commit_event(event, 0)).accepted
            if body and occurred_at > now - config.window_days * 86400:
                retained.append((index + 1, context.scope_key))
            newest = [seq for seq, scope in retained if scope == context.scope_key][-per_scope:]
            retained = [(seq, scope) for seq, scope in retained
                        if scope != context.scope_key or seq in newest][-global_cap:]
            with sqlite3.connect(store.path) as db:
                assert db.execute(
                    "SELECT seq,scope_key FROM body_window ORDER BY seq"
                ).fetchall() == retained
        assert (await store.health())["journal_mode"] == "wal"
        assert await store._run(lambda db: db.execute(
            "PRAGMA synchronous"
        ).fetchone()[0]) == 2
    finally:
        await store.close()


async def test_prune_delete_plans_use_index_ranges(le_store, le_context):
    le_store.config = Config(window_per_scope=2, window_global=3)

    def inspect(db):
        db.executemany(
            "INSERT INTO body_window VALUES(?,?,?,?)",
            ((seq, le_context.scope_key if seq % 2 else "other", le_store.clock(), "synthetic")
             for seq in range(1, 9)),
        )
        statements = []
        db.set_trace_callback(statements.append)
        try:
            le_store._prune_window(db, le_store.clock(), le_context.scope_key)
        finally:
            db.set_trace_callback(None)
        deletes = [sql for sql in statements if sql.startswith("DELETE")]
        assert len(deletes) == 3
        for sql in deletes:
            plan = db.execute("EXPLAIN QUERY PLAN " + sql).fetchall()
            assert "SEARCH body_window" in plan[0]["detail"], [dict(row) for row in plan]
        assert db.execute("SELECT count(*) FROM body_window").fetchone()[0] == 3

    await le_store._run(inspect)


async def test_cleanup_shrinks_cold_scopes_after_reopen(tmp_path, le_event_factory, le_context):
    path = tmp_path / "shrink.sqlite3"
    store = SQLiteStore(path, clock=lambda: 1_800_000_001.0)
    await store.open()
    try:
        for index in range(12):
            context = replace(le_context, scene_id=f"cold-{index % 3}")
            assert (await store.commit_event(le_event_factory(index, context=context), 0)).accepted
    finally:
        await store.close()
    store = SQLiteStore(
        path, config=Config(window_per_scope=2), clock=lambda: 1_800_000_001.0,
    )
    await store.open()
    try:
        await store.cleanup()
        with sqlite3.connect(path) as db:
            assert [row[0] for row in db.execute(
                "SELECT count(*) FROM body_window GROUP BY scope_key"
            )] == [2, 2, 2]
    finally:
        await store.close()
