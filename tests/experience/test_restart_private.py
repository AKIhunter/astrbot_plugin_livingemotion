"""Full Application restart, virtual time, fake models; no live message or network."""
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.contracts import Context, NightState, StateWrite, to_dict
from astrbot_plugin_livingemotion.runtime.application import Application
from astrbot_plugin_livingemotion.runtime import lifecycle, feeling
from astrbot_plugin_livingemotion.tests.integration.test_application import Host, Message, NativeConfig, TestBridge
from astrbot_plugin_livingemotion.tests.experience.test_manual_daily import Binding


async def restarted(tmp_path, monkeypatch, *, dream=False, extra=None):
    clock = [datetime(2026, 11, 9, 12, tzinfo=timezone.utc).timestamp()]
    store_type = lifecycle.SQLiteStore
    monkeypatch.setattr(lifecycle, "SQLiteStore",
                        lambda path, **kw: store_type(path, clock=lambda: clock[0], **kw))
    monkeypatch.setattr(Application, "_start_scheduler", lambda self: None)
    async def no_feeling(app):
        pass
    monkeypatch.setattr(feeling, "maybe_feeling", no_feeling)
    host = Host()
    host.default_persona = "native"
    async def persona(identifier):
        return (SimpleNamespace(system_prompt=host.prompt, begin_dialogs=[])
                if identifier == host.persona_id else None)
    host.get_persona = persona
    native = NativeConfig({
        "timezone": "UTC", "diary_at": "12:00", "diary_enabled": not dream,
        "dream_enabled": dream, "night_enabled": dream, "night_schedule_enabled": False,
        "diary_backfill_yesterday": False, "provider_id": "fake",
        "autonomy_enabled": False, "catchup_enabled": False, **(extra or {})})
    first = Application(host, native, tmp_path, bridge_factory=TestBridge)
    await first.initialize()
    message = Message(body="今天我读完了一本书。", identifier="before-restart")
    await first.on_message(message)
    context = Context.from_dict(message.extra["livingemotion:context"])
    if dream:
        record = await first.store.get_state(context, "night")
        night = NightState(phase="asleep", updated_at=clock[0],
                           sleep_started_at=clock[0], wake_at=clock[0] + 10800)
        assert (await first.store.write_states(context, 0, [
            StateWrite("night", to_dict(night), record.version)])).accepted
    await first.terminate()
    clock[0] += 4200
    app = Application(host, native, tmp_path, bridge_factory=TestBridge)
    await app.initialize()
    model = Binding()
    async def binding(purpose, route=None):
        assert route is None  # A restart cannot resurrect a messaging route.
        return model
    app._select_model_binding = binding
    context = next(iter(app._contexts.values()))
    assert context.route is None and await app.bridge.current(context) is None
    return app, model, host, native, context, clock


@pytest.mark.parametrize("kind", ["diary", "dream"])
async def test_restart_without_new_messages_generates_once_and_never_sends(tmp_path, monkeypatch, kind):
    app, model, host, _, context, _ = await restarted(tmp_path, monkeypatch, dream=kind == "dream")
    try:
        assert not await app.validate_context(context)
        assert await app.validate_automatic_experience(context)
        async def forbidden(*args, **kwargs):
            raise AssertionError("Private restart cannot borrow external memory authorization")
        app.memory.recall = forbidden
        await app.tick()
        await asyncio.wait_for(app.runtime.join(), 3)
        status = app.experience_status(context, kind)
        assert status["status"] == "created", status
        entry, _ = await app.store.load_experience(status["experience_id"])
        assert entry.context.route is None and entry.body
        assert "今天我读完了一本书" in str(model.payloads)
        await app.tick()
        await asyncio.wait_for(app.runtime.join(), 3)
        assert model.calls == 1 and host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.parametrize("fault", ["persona", "config", "clear", "provider", "registered"])
async def test_private_generation_rechecks_authorization_after_model(tmp_path, monkeypatch, fault):
    app, model, host, native, context, _ = await restarted(tmp_path, monkeypatch)
    try:
        model.release.clear()
        result = await app.queue_experience(context, "diary")
        assert result["status"] == "queued", result
        await asyncio.wait_for(model.started.wait(), 2)
        if fault == "persona":
            host.prompt = "Changed native persona"
        elif fault == "config":
            native["diary_enabled"] = False
        elif fault == "clear":
            await app.store.clear_scope(context, 0)
        elif fault == "provider":
            model.fingerprint = "changed-model"
        else:
            await app.store.register_context(replace(context, persona_revision="new-revision"))
        model.release.set()
        await asyncio.wait_for(app.runtime.join(), 3)
        assert app.experience_status(context, "diary")["status"] != "created"
        assert (await app.store.query_persona_experiences(
            app.instance_id, context.persona_id, "diary"))["total"] == 0
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.parametrize("fault", ["persona_missing", "unregistered", "public", "instance", "explicit"])
async def test_invalid_persistent_source_is_blocked_before_model_and_reported(tmp_path, monkeypatch, fault):
    app, model, host, native, context, _ = await restarted(tmp_path, monkeypatch)
    try:
        if fault == "persona_missing":
            host.persona_id = "removed"
        elif fault == "unregistered":
            context = replace(context, persona_revision="forged")
        elif fault == "public":
            context = replace(context, scene_kind="public_comment")
        elif fault == "instance":
            context = replace(context, instance_id="foreign")
        else:
            native.update(persona_mode="explicit", persona_id="different")
            app.config = app.config.from_mapping(native)
        result = await app.queue_experience(context, "diary")
        assert result["status"] == "rejected", result
        assert model.calls == 0 and host.sends == 0
        assert result["attempted_at"] == app.store.clock()
    finally:
        await app.terminate()


async def test_tick_reports_missing_persona_without_live_source(tmp_path, monkeypatch):
    app, model, host, _, context, _ = await restarted(tmp_path, monkeypatch)
    try:
        host.persona_id = "removed"
        await app.tick()
        result = await app.store.auto_experience_status(app.instance_id, context.persona_id, "diary")
        assert result["reason_code"] == "persona_unavailable"
        assert model.calls == 0
    finally:
        await app.terminate()


async def test_automatic_dream_still_requires_one_hour_sleep(tmp_path, monkeypatch):
    app, model, host, _, context, clock = await restarted(tmp_path, monkeypatch, dream=True)
    try:
        old = await app.store.get_state(context, "night")
        night = NightState(phase="asleep", updated_at=clock[0],
                          sleep_started_at=clock[0] - 1800, wake_at=clock[0] + 7200)
        assert (await app.store.write_states(context, 0, [
            StateWrite("night", to_dict(night), old.version)])).accepted
        result = await app.queue_experience(context, "dream")
        assert result["reason_code"] == "dream_requires_live_rem"
        assert model.calls == host.sends == 0
    finally:
        await app.terminate()


async def test_private_automatic_generation_preserves_manual_daily_content(tmp_path, monkeypatch):
    from astrbot_plugin_livingemotion.tests.experience.test_manual_daily import submit, finish
    app, model, host, _, context, _ = await restarted(tmp_path, monkeypatch)
    async def binding(kind):
        return model
    app.manual_model_binding = binding
    try:
        manual = await submit(app)
        await finish(app)
        task = await app.console_experience_task(manual["request_id"])
        assert task["status"] == "succeeded"
        old = (await app.store.load_experience(task["experience_id"]))[0]
        await app.tick()
        await app.runtime.join()
        assert (await app.store.load_experience(task["experience_id"]))[0] == old
        assert (await app.queue_experience(context, "diary"))["reason_code"] == "daily_content_preserved"
        assert model.calls == 1 and host.sends == 0
    finally:
        await app.terminate()


async def test_new_message_invalidates_old_attempt_then_retry_saves_once(tmp_path, monkeypatch):
    app, model, host, _, context, _ = await restarted(tmp_path, monkeypatch)
    try:
        model.release.clear()
        first = await app.queue_experience(context, "diary")
        assert first["status"] == "queued"
        await asyncio.wait_for(model.started.wait(), 2)
        message = Message("after-restart", body="又读了一章。")
        await app.on_message(message)
        updated = Context.from_dict(message.extra["livingemotion:context"])
        # Test private writing again after the real source is no longer retained.
        app.bridge.sources.clear()
        model.release.set()
        await asyncio.wait_for(app.runtime.join(), 3)
        assert app.experience_status(context, "diary")["status"] != "created"
        second = await app.queue_experience(updated, "diary")
        assert second["status"] == "queued", second
        await asyncio.wait_for(app.runtime.join(), 3)
        assert app.experience_status(updated, "diary")["status"] == "created"
        assert (await app.store.query_persona_experiences(
            app.instance_id, updated.persona_id, "diary"))["total"] == 1
        assert (await app.queue_experience(updated, "diary"))["reason_code"] == "daily_content_preserved"
        assert model.calls == 2 and host.sends == 0
    finally:
        await app.terminate()
