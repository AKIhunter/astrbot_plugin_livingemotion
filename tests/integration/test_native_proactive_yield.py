"""Host timestamps, real SQLite and virtual timer; providers/senders are synthetic."""

from dataclasses import replace
from datetime import datetime, timezone
import json
import sqlite3

import pytest

from astrbot_plugin_livingemotion.contracts import rebuild_route
from astrbot_plugin_livingemotion.runtime import proactive_arbiter as arbiter
from astrbot_plugin_livingemotion.storage.proactivity import read_schedule
from test_proactive_runtime import drain, proactive_app


AT = datetime(2026, 11, 20, tzinfo=timezone.utc).timestamp()  # 08:00 Shanghai


def host_db(tmp_path, *, session="adapter:FriendMessage:human", next_at=AT,
            last_at=None, enabled=True, payload=None):
    root = tmp_path / "host"
    data_dir = root / "plugin_data" / "astrbot_plugin_livingemotion"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = root / "data_v4.db"
    with sqlite3.connect(db_path) as db:
        db.execute("""CREATE TABLE cron_jobs(
            id INTEGER, name TEXT, cron_expression TEXT, enabled INTEGER,
            payload TEXT, next_run_time TEXT, last_run_at TEXT)""")
        def timestamp(value):
            return datetime.fromtimestamp(value, timezone.utc).replace(tzinfo=None).isoformat(
                " ") if value is not None else None
        db.execute("INSERT INTO cron_jobs VALUES(1,?,?,?,?,?,?)", (
            "每日早安+撒娇自拍", "0 8 * * *", int(enabled),
            json.dumps({"session": session, "note": "private text"}) if payload is None else payload,
            timestamp(next_at), timestamp(last_at),
        ))
    return data_dir, db_path


@pytest.mark.parametrize("delta,expected", [
    (-901, False), (-900, True), (-1, True), (0, True),
    (1, True), (900, True), (901, False), (12 * 3600, False),
])
def test_exact_window_boundaries(tmp_path, le_context, delta, expected):
    data_dir, _ = host_db(tmp_path, session=rebuild_route(le_context))
    state = arbiter.probe_once(data_dir)
    assert bool(arbiter.yielding_jobs(state, le_context, AT + delta)) is expected
    assert state["jobs"][0]["next_run_at"] == AT
    assert "private text" not in json.dumps(state)


@pytest.mark.parametrize("change", [
    {"adapter_id": "other"}, {"scene_id": "other"}, {"scene_kind": "group"},
])
def test_other_conversations_never_yield(tmp_path, le_context, change):
    data_dir, _ = host_db(tmp_path, session=rebuild_route(le_context))
    assert not arbiter.yielding_jobs(arbiter.probe_once(data_dir),
                                    replace(le_context, **change), AT)


@pytest.mark.parametrize("payload", ["{}", "null", "[]", "invalid", '{"session":null}'])
def test_unknown_target_does_not_block_all_conversations(tmp_path, le_context, payload):
    data_dir, _ = host_db(tmp_path, payload=payload)
    assert not arbiter.yielding_jobs(arbiter.probe_once(data_dir), le_context, AT)


@pytest.mark.parametrize("value,expected", [
    ("2026-11-20 00:00:00", AT),
    ("2026-11-20T08:00:00+08:00", AT),
    ("2026-11-19T19:00:00-05:00", AT),
    ("2026-11-20T00:00:00Z", AT),
    (None, None), ("invalid", None),
])
def test_host_utc_and_explicit_timezones(value, expected):
    assert arbiter._host_timestamp(value) == expected


def test_refreshed_next_run_preserves_recent_execution_window(tmp_path, le_context):
    data_dir, _ = host_db(tmp_path, session=rebuild_route(le_context),
                         next_at=AT + 86400, last_at=AT)
    state = arbiter.probe_once(data_dir)
    assert arbiter.yielding_jobs(state, le_context, AT + 900)
    assert not arbiter.yielding_jobs(state, le_context, AT + 901)


def test_cross_midnight_window(tmp_path, le_context):
    midnight = datetime.fromisoformat("2026-11-21T00:00:00+08:00").timestamp()
    data_dir, _ = host_db(tmp_path, session=rebuild_route(le_context), next_at=midnight)
    state = arbiter.probe_once(data_dir)
    assert arbiter.yielding_jobs(state, le_context, midnight - 900)
    assert arbiter.yielding_jobs(state, le_context, midnight + 900)
    assert not arbiter.yielding_jobs(state, le_context, midnight + 901)


@pytest.mark.parametrize("case", ["disabled", "bad_time", "legacy", "missing"])
def test_unusable_jobs_never_create_global_yield(tmp_path, le_context, case):
    if case == "missing":
        state = arbiter.probe_once(tmp_path / "no-host")
    else:
        data_dir, db_path = host_db(
            tmp_path, session=rebuild_route(le_context), enabled=case != "disabled")
        with sqlite3.connect(db_path) as db:
            if case == "bad_time":
                db.execute("UPDATE cron_jobs SET next_run_time='invalid'")
            elif case == "legacy":
                db.execute("DROP TABLE cron_jobs")
                db.execute("CREATE TABLE cron_jobs(id INTEGER,name TEXT,enabled INTEGER)")
                db.execute("INSERT INTO cron_jobs VALUES(1,'每日早安',1)")
        state = arbiter.probe_once(data_dir)
    assert not arbiter.yielding_jobs(state, le_context, AT)


def test_every_matching_job_is_considered(tmp_path, le_context):
    data_dir, db_path = host_db(tmp_path, session="adapter:FriendMessage:other")
    with sqlite3.connect(db_path) as db:
        for number in range(2, 7):
            db.execute("INSERT INTO cron_jobs SELECT ?,name,cron_expression,enabled,"
                       "payload,next_run_time,last_run_at FROM cron_jobs WHERE id=1", (number,))
        db.execute("UPDATE cron_jobs SET payload=? WHERE id=6",
                   (json.dumps({"session": rebuild_route(le_context)}),))
    assert [j["id"] for j in arbiter.yielding_jobs(
        arbiter.probe_once(data_dir), le_context, AT)] == ["6"]


@pytest.mark.asyncio
@pytest.mark.parametrize("inside", [True, False])
async def test_real_random_opportunity_yields_only_for_same_target(tmp_path, inside):
    app, host, _, context, binding, clock = await proactive_app(tmp_path)
    try:
        data_dir, _ = host_db(
            tmp_path, session=rebuild_route(context) if inside else "adapter:FriendMessage:other",
            next_at=clock[0] + 1800,
        )
        app.data_dir = data_dir
        await app.maybe_proact(context)
        clock[0] += 1800
        await app.maybe_proact(context)
        await drain(app)
        assert host.sends == len(binding.calls) == (0 if inside else 1)
        if inside:
            # When the window ends, the old opportunity is skipped once, then
            # a new ordinary opportunity can generate and send without replay.
            clock[0] += 901
            await app.maybe_proact(context)
            assert (await read_schedule(app.store, context))["last_reason"] == "missed_opportunity"
            clock[0] += 1800
            await app.maybe_proact(context)
            await drain(app)
            assert host.sends == len(binding.calls) == 1
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_normal_tick_refreshes_disabled_host_job(tmp_path, monkeypatch):
    app, host, native, context, binding, clock = await proactive_app(tmp_path)
    try:
        data_dir, db_path = host_db(tmp_path, session=rebuild_route(context), next_at=clock[0])
        app.data_dir = data_dir
        monkeypatch.setattr(arbiter.time, "time", lambda: clock[0])
        native["promise_enabled"] = False
        await app.refresh_config()
        await app._promise_tick()
        await app.maybe_proact(context)
        assert await read_schedule(app.store, context) is None
        with sqlite3.connect(db_path) as db:
            db.execute("UPDATE cron_jobs SET enabled=0")
        clock[0] += arbiter.PROBE_TTL + 1
        await app._promise_tick()
        await app.maybe_proact(context)
        assert (await read_schedule(app.store, context))["next_at"] == clock[0] + 1800
        assert not binding.calls and not host.sends
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_switch_off_bypasses_host_protection(tmp_path):
    app, host, native, context, binding, clock = await proactive_app(tmp_path)
    try:
        data_dir, _ = host_db(tmp_path, session=rebuild_route(context), next_at=clock[0])
        app.data_dir = data_dir
        native["proactive_native_yield"] = False
        await app.refresh_config()
        await app.maybe_proact(context)
        assert (await read_schedule(app.store, context))["next_at"] == clock[0] + 1800
        assert not binding.calls and not host.sends
    finally:
        await app.terminate()
