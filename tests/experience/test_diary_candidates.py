"""Virtual clock, synthetic events/model, real scheduler and SQLite; never sends."""
import asyncio
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from astrbot_plugin_livingemotion.contracts import (
    ActorRole, Event, NightState, SceneKind, StateWrite, to_dict,
)
from astrbot_plugin_livingemotion.tests.experience.test_restart_private import restarted


async def add_context(app, original, name, *, material=False, **changes):
    context = replace(original, scene_id=name, account_id=name, **changes)
    await app.store.register_context(context)
    await app.initialize_state_scope(context)
    app._contexts[context.account_key] = context
    if material:
        event = Event(
            name, "synthetic", "message", context, ActorRole.HUMAN,
            app.store.clock(), name, actor_id=name, body=f"我在{name}会话读了一本书。",
        )
        assert (await app.api.ingest_event(event))["status"] == "accepted"
    return context


@pytest.mark.parametrize("empty_count", [1, 70])
async def test_tick_backfills_old_session_without_filling_service_cache(
    tmp_path, monkeypatch, empty_count,
):
    app, model, host, _, old, clock = await restarted(
        tmp_path, monkeypatch, extra={"diary_backfill_yesterday": True})
    try:
        clock[0] = datetime(2026, 11, 10, 0, 15, tzinfo=timezone.utc).timestamp()
        for index in range(empty_count):
            newest = await add_context(app, old, f"empty-{index}")
        # Latest context really has no yesterday material; its state is from today.
        await app.tick()
        await asyncio.wait_for(app.runtime.join(), 3)
        status = app.experience_status(old, "diary")
        assert status["status"] == "created", status
        saved, _ = await app.store.load_experience(status["experience_id"])
        assert saved.context.account_key == old.account_key
        assert saved.period == "2026-11-09" and saved.body
        assert "今天我读完了一本书" in str(model.payloads)
        assert app.experience_status(newest, "diary")["reason_code"] == "diary_not_due"
        await app.tick()
        await asyncio.wait_for(app.runtime.join(), 3)
        assert model.calls == 1 and host.sends == 0
        assert len(app._services) <= 2  # Empty prefilters must not use the 64-service cache.
        assert (await app.store.query_persona_experiences(
            app.instance_id, old.persona_id, "diary"))["total"] == 1
    finally:
        await app.terminate()


async def test_material_candidate_with_revoked_registration_falls_back(tmp_path, monkeypatch):
    app, model, host, _, old, _ = await restarted(tmp_path, monkeypatch)
    try:
        candidate = await add_context(app, old, "revoked", material=True)
        await app.store.register_context(replace(candidate, identity_revision="revoked"))
        result = await app.queue_diary_candidates([old, candidate], "2026-11-09")
        assert result["status"] == "queued", result
        await asyncio.wait_for(app.runtime.join(), 3)
        saved, _ = await app.store.load_experience(result["experience_id"])
        assert saved.context == old
        assert "revoked会话" not in str(model.payloads)
        assert model.calls == 1 and host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.parametrize("reason", [
    "generation_in_progress", "model_result_unknown", "model_daily_limit",
    "experience_attempt_limit", "daily_content_preserved", "experience_exists",
    "duplicate_job", "",
])
async def test_dispatch_or_budget_result_stops_candidate_fallback(tmp_path, monkeypatch, reason):
    app, model, host, _, old, _ = await restarted(tmp_path, monkeypatch)
    try:
        newest = await add_context(app, old, "qualified", material=True)
        calls = []
        async def queue(context, kind, **kwargs):
            calls.append(context)
            return {"status": "queued" if not reason else "skipped", "reason_code": reason}
        monkeypatch.setattr(app, "queue_experience", queue)
        result = await app.queue_diary_candidates([old, newest], "2026-11-09")
        assert result["reason_code"] == reason and calls == [newest]
        assert model.calls == host.sends == 0
    finally:
        await app.terminate()


async def test_tick_keeps_personas_separate_and_ignores_public_comments(tmp_path, monkeypatch):
    app, model, host, _, old, _ = await restarted(tmp_path, monkeypatch)
    try:
        other = await add_context(app, old, "other", persona_id="other-persona")
        public = await add_context(app, old, "public", scene_kind=SceneKind.PUBLIC_COMMENT)
        batches = []
        async def candidates(contexts, day):
            batches.append(tuple(contexts))
            return {"status": "skipped"}
        monkeypatch.setattr(app, "queue_diary_candidates", candidates)
        await app.tick()
        assert batches == [(old,), (other,)]
        assert all(public not in batch for batch in batches)
        assert model.calls == host.sends == 0
    finally:
        await app.terminate()


async def test_all_empty_reports_material_skip_without_model(tmp_path, monkeypatch):
    app, model, host, _, old, clock = await restarted(
        tmp_path, monkeypatch, extra={"diary_backfill_yesterday": True})
    try:
        clock[0] = datetime(2026, 11, 11, 0, 15, tzinfo=timezone.utc).timestamp()
        newest = await add_context(app, old, "empty")
        result = await app.queue_diary_candidates([old, newest], "2026-11-10")
        assert result["reason_code"] == "no_qualified_material"
        assert app.experience_status(newest, "diary")["reason_code"] == "no_qualified_material"
        assert model.calls == host.sends == 0
    finally:
        await app.terminate()


async def set_sleep(app, context, now, *, phase="asleep", elapsed=4200, wake_at=None):
    record = await app.store.get_state(context, "night")
    state = NightState(
        phase=phase, energy=20 if phase == "drowsy" else 50, updated_at=now,
        sleep_started_at=now - elapsed if phase == "asleep" else None,
        wake_at=(now + 7200 if wake_at is None else wake_at) if phase == "asleep" else None,
    )
    result = await app.store.write_states(context, 0, [
        StateWrite("night", to_dict(state), record.version)])
    assert result.accepted
    return state


@pytest.mark.parametrize("phase,elapsed,expired,allowed", [
    ("awake", 4200, False, False),
    ("drowsy", 4200, False, False),
    ("asleep", 1800, False, False),
    ("asleep", 3599, False, False),
    ("asleep", 3600, False, True),
    ("asleep", 4200, False, True),
    ("asleep", 4200, True, False),
])
async def test_sleep_boundary_generates_and_archives_once(
    tmp_path, monkeypatch, phase, elapsed, expired, allowed,
):
    app, model, host, _, context, clock = await restarted(tmp_path, monkeypatch, dream=True)
    try:
        await set_sleep(app, context, clock[0], phase=phase, elapsed=elapsed,
                        wake_at=clock[0] if expired else None)
        await app.tick()
        await asyncio.wait_for(app.runtime.join(), 3)
        rows = await app.store.query_persona_experiences(
            app.instance_id, context.persona_id, "dream")
        assert rows["total"] == int(allowed)
        assert model.calls == int(allowed) and host.sends == 0
        if allowed:
            status = app.experience_status(context, "dream")
            assert status["status"] == "created", status
            saved, _ = await app.store.load_experience(status["experience_id"])
            assert saved.body and saved.emotion_snapshot["label"]
            assert saved.emotion_snapshot["emotions"] and saved.dream_profile
            assert saved.dream_profile["sleep_started_at"] == clock[0] - elapsed
            assert "今天我读完了一本书" in str(model.payloads)
            assert saved.context.route is None
            await app.tick()
            await asyncio.wait_for(app.runtime.join(), 3)
            assert model.calls == 1
        else:
            assert app.experience_status(context, "dream")["reason_code"] == "dream_requires_live_rem"
    finally:
        await app.terminate()


@pytest.mark.parametrize("fault", ["wake", "persona"])
async def test_dream_rechecks_sleep_and_persona_before_commit(tmp_path, monkeypatch, fault):
    app, model, host, _, context, clock = await restarted(tmp_path, monkeypatch, dream=True)
    try:
        model.release.clear()
        result = await app.queue_experience(context, "dream")
        assert result["status"] == "queued", result
        await asyncio.wait_for(model.started.wait(), 2)
        if fault == "wake":
            await set_sleep(app, context, clock[0], phase="awake")
        else:
            host.prompt = "Different synthetic persona"
        model.release.set()
        await asyncio.wait_for(app.runtime.join(), 3)
        assert app.experience_status(context, "dream")["status"] != "created"
        assert (await app.store.query_persona_experiences(
            app.instance_id, context.persona_id, "dream"))["total"] == 0
        assert model.calls == 1 and host.sends == 0
    finally:
        model.release.set()
        await app.terminate()
