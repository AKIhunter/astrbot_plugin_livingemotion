"""Real plugin stores, synthetic bodies, no host network or provider calls."""
import asyncio
from dataclasses import replace
import json
from pathlib import Path
from types import MethodType, SimpleNamespace
import zipfile

import pytest

from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import BehaviorIntent
from astrbot_plugin_livingemotion.diagnostic_bundle import DiagnosticRecorder, WINDOW
from astrbot_plugin_livingemotion.runtime import night
from astrbot_plugin_livingemotion.runtime.application import Application
from astrbot_plugin_livingemotion.runtime.diagnostics import prepare
from astrbot_plugin_livingemotion.storage import console_data
from astrbot_plugin_livingemotion.storage.behavior_logs import simulation_record
from astrbot_plugin_livingemotion.storage.experiences import owner_key
from astrbot_plugin_livingemotion.storage.promise_store import PromiseStore


@pytest.fixture
def diagnostic_app(le_store):
    recorder = DiagnosticRecorder(le_store.path.parent, "LE", __file__,
                                  clock=lambda: le_store.clock() + 1)
    le_store.diagnostics = recorder
    app = SimpleNamespace(data_dir=le_store.path.parent, config=Config(), closed=False,
                          host=SimpleNamespace(get_config=lambda: {}),
                          diagnostics=recorder, effective_mode=lambda: "active")
    try:
        yield app
    finally:
        le_store.diagnostics = None
        recorder.close()


def test_settings_export_is_complete_and_omits_notification_account(diagnostic_app, le_export):
    app = diagnostic_app
    fields = set("""
        enabled mode timezone persona_shared_state provider_id fallback_provider_id
        behavior_provider_id embedding_provider_id model_timeout_seconds window_days event_days
        promise_enabled promise_tick_seconds promise_trace_ttl_hours emotion_model_enabled
        behavior_emotional_share model_daily_limit coupling_promise_actions allow_sleep
        catchup_provider_id night_policy_version fatigue_start deep_sleep_at wake_at
        nap_enabled nap_start lie_in_max_minutes closing_enabled closing_random
        closing_lead_minutes closing_provider_id energy_reply_cost behavior_daily_limit
        catchup_enabled catchup_reply_enabled wake_autocatchup_enabled wake_greeting_enabled
        dream_enabled dream_provider_id dream_per_night dream_owner_notify diary_enabled
        diary_at diary_backfill_yesterday diary_provider_id autonomy_enabled group_autonomy_enabled
        proactive_native_yield scheduler_seconds model_input_tokens model_output_tokens
        emotion_provider_id context_emotions_enabled dream_owner_qq_set providers
    """.split())
    default = json.loads(le_export(app)["settings.json"])
    assert len(default) == len(fields) == 55 and set(default) == fields
    assert default["dream_owner_qq_set"] is False
    assert default["providers"] == []
    assert default["closing_random"] == Config().closing_random
    assert default["scheduler_seconds"] == Config().scheduler_seconds

    number = "174593268"
    app.config = Config.from_mapping({
        "dream_owner_qq": number, "dream_owner_notify": True, "closing_random": True,
        "diary_at": "21:17", "dream_provider_id": "dream-route", "scheduler_seconds": 37,
    })
    exported = le_export(app)
    settings = json.loads(exported["settings.json"])
    assert set(settings) == fields
    assert settings["dream_owner_qq_set"] is True and settings["dream_owner_notify"] is True
    assert settings["closing_random"] is True and settings["diary_at"] == "21:17"
    assert settings["dream_provider_id"] == "dream-route" and settings["scheduler_seconds"] == 37
    assert number not in "\n".join(exported.values())


async def test_experience_export_projects_four_sources_and_respects_window(
        diagnostic_app, le_store, le_context, le_export):
    app = diagnostic_app
    now = le_store.clock()
    before = now - WINDOW - 2
    owner = owner_key(le_context.instance_id, le_context.persona_id)
    other_owner = "private-auto-owner-sentinel"
    day = "2027-01-15"
    request_id = "private-client-id-sentinel"
    archived_body = json.dumps({
        "title": "private-title-sentinel", "theme": "private-theme-sentinel",
        "body": "private-archive-sentinel",
    })
    def seed(db):
        db.executemany("INSERT INTO experiences VALUES(?,?,?,?,?,?,?,?,?,?)", (
            ("diary-entry", le_context.scope_key, owner, 0, "diary", day,
             before, None, 1, archived_body),
            ("dream-entry", le_context.scope_key, owner, 0, "dream", "night-1:2",
             now - 50, now + 100, 0, archived_body),
            ("old-entry", le_context.scope_key, owner, 0, "diary", "2027-01-01",
             before, None, 1, archived_body),
        ))
        db.executemany("INSERT INTO experience_daily VALUES(?,?,?,?,?,?,?,?)", (
            (owner, "diary", day, "UTC", "diary-entry", 4, "manual", now - 3),
            (owner, "dream", day, "UTC", "deleted-entry", 2, "auto", now - 4),
        ))
        db.executemany("INSERT INTO experience_jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            (request_id, owner, "private-persona-sentinel", "diary", day, "UTC",
             "failed", "model_preflight_http_error:429", None, 4, before, now - 7,
             "private-generation-snapshot-sentinel"),
            ("old-job", owner, "private-persona-sentinel", "diary", day, "UTC",
             "cancelled", "reload_before_dispatch", None, 4, before - 1, before,
             "private-generation-snapshot-sentinel"),
            ("safe-but-private-id", owner, "private-persona-sentinel", "dream", "bad-day", "UTC",
             "private-job-status", "model_preflight_http_error:private-suffix", None, 0,
             now - 16, None, "private-generation-snapshot-sentinel"),
        ))
        db.executemany("INSERT INTO experience_auto_status VALUES(?,?,?,?)", (
            (owner, "dream", now - 9, "{broken-private-json"),
            (other_owner, "dream", now - 10, json.dumps({
                "status": {"nested": "private-auto-status"},
                "reason_code": "private-auto-reason", "model_reason_code": "model_body_missing",
                "day": "bad-auto-day", "http_status": "429", "body": "private-auto-body",
            })),
            (other_owner, "diary", before, "{}"),
        ))
        attempts = [
            ("first", "experience_attempt", "failed", now - 4),
            ("second", "experience_attempt", "failed", now - 9),
            ("third", "experience_attempt", "succeeded", now - 11),
            ("too-old", "experience_attempt", "failed", before),
            ("other-pool", "model", "failed", now - 4),
        ]
        db.executemany("INSERT INTO quota_reservations VALUES(?,?,?,?,?,?,?,?,?,?,?)", (
            (key, le_context.scope_key, 0, "night-1", "dream", pool, 1,
             status, stamp, None, "private-reservation-reason")
            for key, pool, status, stamp in attempts
        ))

    await le_store._run(seed)
    await le_store.record_auto_experience_status(le_context, "diary", {
        "status": "queued", "reason_code": "queued", "attempted_at": before - 1,
    })
    await le_store.record_auto_experience_status(le_context, "diary", {
        "status": "failed", "reason_code": "model_preflight_http_error",
        "day": day, "http_status": 429, "attempted_at": before, "finished_at": now - 1,
    })
    await PromiseStore(le_store).ensure()
    contents = le_export(app)
    records = [json.loads(line) for line in contents["experiences.jsonl"].splitlines()]
    entries = {r["kind"]: r for r in records if r["source"] == "entry"}
    assert set(entries) == {"diary", "dream"}
    assert entries["diary"]["created_at"] == before and entries["diary"]["updated_at"] == now - 3
    assert entries["diary"]["day"] == day and entries["diary"]["revision"] == 4
    assert entries["diary"]["origin"] == "manual" and entries["diary"]["pinned"] == 1
    assert entries["dream"]["experience_id"] == "dream-entry"
    assert entries["dream"]["day"] is None and entries["dream"]["origin"] is None
    jobs = {r["kind"]: r for r in records if r["source"] == "job"}
    assert set(jobs) == {"diary", "dream"}
    assert jobs["diary"]["request_id"] == app.diagnostics.redactor.alias(request_id)
    assert jobs["diary"]["started_at"] == before and jobs["diary"]["finished_at"] == now - 7
    assert jobs["diary"]["status"] == "failed"
    assert jobs["diary"]["reason_code"] == "model_preflight_http_error"
    assert jobs["diary"]["http_status"] == 429
    assert jobs["dream"]["day"] is None and jobs["dream"]["status"] == "unknown"
    assert jobs["dream"]["reason_code"] == "unknown"
    auto = {r["kind"]: r for r in records if r["source"] == "auto"}
    assert set(auto) == {"diary", "dream"}
    assert auto["diary"]["day"] == day and auto["diary"]["status"] == "failed"
    assert auto["diary"]["started_at"] == before and auto["diary"]["finished_at"] == now - 1
    assert auto["diary"]["reason_code"] == "model_preflight_http_error"
    assert auto["diary"]["http_status"] == 429
    assert auto["diary"]["owner_key"] == entries["diary"]["owner_key"] != owner
    assert auto["dream"]["status"] == auto["dream"]["reason_code"] == "unknown"
    assert auto["dream"]["model_reason_code"] == "model_body_missing"
    assert auto["dream"]["day"] is None and auto["dream"]["http_status"] is None
    attempts = [r for r in records if r["source"] == "attempts"]
    assert {(r["purpose"], r["period"], r["status"], r["count"]) for r in attempts} == {
        ("dream", "night-1", "succeeded", 1), ("dream", "night-1", "failed", 2),
    }
    manifest = json.loads(contents["manifest.json"])
    assert manifest["skipped"] == []
    experience_file = manifest["files"]["experiences.jsonl"]
    assert experience_file["records"] == 8 and experience_file["invalid"] == 1
    combined = "\n".join(contents.values())
    for forbidden in (owner, other_owner, "private-", "safe-but-private-id", "bad-day",
                      "bad-auto-day", "old-entry", "old-job", "deleted-entry", "generation_snapshot_json",
                      "value_json", le_context.scope_key):
        assert forbidden not in combined


async def test_scheduler_export_distinguishes_running_failure_recovery_and_cancel(
        diagnostic_app, le_store, le_export, le_log, monkeypatch):
    app = diagnostic_app
    app.store, app.instance_id, app._task_fault = le_store, "isolated", ""
    app._tick_loop = MethodType(night.NightRuntime._tick_loop, app)
    waits, permits = asyncio.Queue(), asyncio.Queue()
    entered, unblock = asyncio.Event(), asyncio.Event()
    wall = le_store.clock()
    elapsed = 0.0
    action = "refresh_error"

    async def sleep(delay):
        await waits.put(delay)
        await permits.get()

    async def refresh(*args):
        if action == "blocked":
            entered.set()
            await unblock.wait()
        if action == "refresh_error":
            raise OSError("private-refresh-error")

    async def tick():
        if action == "tick_error":
            raise RuntimeError("private-tick-error")

    async def advance(next_action, *, after=0):
        nonlocal action, wall, elapsed
        action = next_action
        wall = round(wall + .1, 3)
        elapsed += after
        await permits.put(None)
        assert await asyncio.wait_for(waits.get(), 2) == app.config.scheduler_seconds

    def snapshot():
        return json.loads(le_export(app)["environment.json"])["scheduler"]

    app.tick = tick
    monkeypatch.setattr(night, "asyncio", SimpleNamespace(sleep=sleep, CancelledError=asyncio.CancelledError))
    monkeypatch.setattr(night, "wall_clock", lambda: wall)
    monkeypatch.setattr(night, "monotonic", lambda: elapsed)
    monkeypatch.setattr(console_data, "refresh_relationship_lists", refresh)
    monkeypatch.setattr(console_data, "relationship_list_delay", lambda *_: 3600)

    assert snapshot()["task_state"] == "absent"
    Application._start_scheduler(app)
    try:
        assert await asyncio.wait_for(waits.get(), 2) == app.config.scheduler_seconds
        await advance("refresh_error")  # The first failure is recorded even at monotonic zero.
        first = snapshot()["fault"]
        assert first["stage"] == "relationship_refresh" and first["exception_type"] == "OSError"
        assert first["first_at"] == first["at"] == wall and first["count"] == 1

        await advance("refresh_error", after=1)
        duplicate = snapshot()
        assert duplicate["task_fault"] == "scheduler_tick_failed"
        assert duplicate["fault"]["count"] == 2 and duplicate["fault"]["first_at"] == first["at"]
        assert duplicate["started_at"] == duplicate["finished_at"] == wall
        assert duplicate["last_success_at"] is None and duplicate["in_flight"] is False

        await advance("tick_error", after=1)
        fault = snapshot()["fault"]
        assert fault["stage"] == "tick" and fault["exception_type"] == "RuntimeError"
        assert fault["first_at"] == wall and fault["count"] == 1
        filename, location = fault["site"].split(":")
        line, function = location.split()
        assert filename == Path(__file__).name and line.isdigit() and function == "tick"
        await advance("tick_error", after=1800)
        assert snapshot()["fault"]["count"] == 2

        await advance("success")
        recovered = snapshot()
        assert recovered["last_success_at"] == wall and recovered["fault"] is None
        assert recovered["task_fault"] == "" and recovered["task_state"] == "running"

        action = "blocked"
        wall = round(wall + .1, 3)
        await permits.put(None)
        await asyncio.wait_for(entered.wait(), 2)
        contents = le_export(app)
        blocked = json.loads(contents["environment.json"])["scheduler"]
        assert blocked["stage"] == "relationship_refresh" and blocked["in_flight"] is True
        assert blocked["started_at"] == wall and blocked["last_success_at"] == recovered["last_success_at"]
        rows = [json.loads(line) for line in contents["runtime.jsonl"].splitlines()]
        failures = [row for row in rows if row["operation"] == "scheduler_tick_failed"]
        assert [(r["stage"], r["count"]) for r in failures] == [
            ("relationship_refresh", 1), ("tick", 1), ("tick", 2),
        ]
        assert le_log.text.count("[LE-scheduler] tick 失败") == 3
        for private in ("private-refresh-error", "private-tick-error", "Traceback", str(__file__)):
            assert private not in "\n".join(contents.values()) and private not in le_log.text
    finally:
        app._scheduler.cancel()
        with pytest.raises(asyncio.CancelledError):
            await app._scheduler

    cancelled = snapshot()
    assert cancelled["task_state"] == "cancelled" and cancelled["in_flight"] is False
    assert cancelled["finished_at"] == wall and cancelled["fault"] is None
    Application._start_scheduler(app)
    try:
        rebuilt = snapshot()
        assert rebuilt["task_state"] == "running"
        assert rebuilt["started_at"] is None and rebuilt["last_success_at"] is None
        assert rebuilt["fault"] is None
    finally:
        app._scheduler.cancel()
        with pytest.raises(asyncio.CancelledError):
            await app._scheduler


@pytest.mark.asyncio
async def test_real_sources_and_capture_do_not_export_private_fields(le_store, le_event):
    recorder = DiagnosticRecorder(le_store.path.parent, "LE", __file__,
                                  clock=le_store.clock, credentials=["synthetic-secret-for-export"])
    le_store.diagnostics = recorder
    app = SimpleNamespace(data_dir=le_store.path.parent, config=Config(), closed=False,
                          host=SimpleNamespace(get_config=lambda: {"provider": [
                              {"id": "route-1", "api_type": "openai", "api_key": "synthetic-secret-for-export"}]}),
                          diagnostics=recorder, effective_mode=lambda: "active")
    try:
        event = replace(le_event, body="private-body-sentinel")
        await le_store.register_context(event.context)
        result = await le_store.commit_event(event, 0, traces=[{
            "kind": "emotion", "before": {"pleasure": .1}, "after": {"pleasure": .2},
            "body": "private-trace-sentinel", "reason_codes": ["care"],
            "context_emotions": {"after": [{"kind": "hurt", "intensity": .2,
                                           "evidence": "private-evidence-sentinel"}]}}])
        assert result.accepted
        intent = BehaviorIntent("offline-intent", event.context, "share", le_store.clock() - .5,
                                le_store.clock() + 3600, 0)
        await le_store.create_intent(intent)
        await simulation_record(le_store, "offline-simulation", {
            "request_id": "offline-simulation", "created_at": le_store.clock() - .5,
            "status": "completed", "text": "private-simulation-sentinel"})
        promises = PromiseStore(le_store)
        created = await promises.create(event.context, description="private-promise-sentinel",
                                        note="private-note-sentinel", due_at=le_store.clock() + 300,
                                        bucket="soon")
        await promises.move(created["promise_id"], status="running")
        app.diagnostics.clock = lambda: le_store.clock() + 1
        _, snapshot, sources = prepare(app)
        bundle = recorder.export(snapshot, sources)
        try:
            with zipfile.ZipFile(bundle.path) as archive:
                contents = {name: archive.read(name).decode() for name in archive.namelist()}
            combined = "\n".join(contents.values())
            for secret in ("private-body-sentinel", "private-trace-sentinel",
                           "private-simulation-sentinel", "private-promise-sentinel",
                           "private-note-sentinel", "synthetic-secret-for-export",
                           "private-evidence-sentinel"):
                assert secret not in combined
            assert '"api_type": "openai"' in contents["settings.json"]
            manifest = json.loads(contents["manifest.json"])
            assert manifest["files"]["events.jsonl"]["records"] == 1
            assert manifest["files"]["emotion.jsonl"]["records"] == 1
            assert manifest["skipped"] == []
            assert '"intensity": 0.2' in contents["emotion.jsonl"]
            assert '"simulated": true' in contents["behavior.jsonl"]
            assert '"simulated": false' in contents["behavior.jsonl"]
            assert '"status": "running"' in contents["promises.jsonl"]
            assert '"operation": "event"' in contents["runtime.jsonl"]
            assert '"operation": "promise_transition"' in contents["runtime.jsonl"]
        finally:
            bundle.close()
    finally:
        recorder.close()
        le_store.diagnostics = None


@pytest.mark.asyncio
async def test_diagnostics_do_not_validate_business_clock_after_commit(le_store, le_context):
    await le_store.register_context(le_context)
    original_run, original_clock = le_store._run, le_store.clock
    def failed_clock():
        raise AssertionError("business clock must not be read after commit")
    def failed_recorder(*_):
        raise RuntimeError("synthetic diagnostic failure")
    recorder = SimpleNamespace(record=failed_recorder, dropped=0)
    le_store.diagnostics = recorder
    async def commit_then_break_clock(operation):
        result = await original_run(operation)
        le_store.clock = failed_clock
        return result
    le_store._run = commit_then_break_clock
    try:
        intent = BehaviorIntent("clock-intent", le_context, "share",
                                original_clock() - 1, original_clock() + 3600, 0)
        assert (await le_store.create_intent(intent))["status"] == "created"
        le_store.clock = original_clock
        result = await le_store.transition_intent(
            le_context, intent.intent_id, 0, expected_status="pending",
            status="cancelled", reason_code="offline_cancel")
        assert result["status"] == "updated"
        assert recorder.dropped == 2
    finally:
        le_store._run, le_store.clock = original_run, original_clock
        le_store.diagnostics = None
