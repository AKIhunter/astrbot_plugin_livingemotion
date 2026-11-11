"""Real SQLite and worker queue; deterministic time, synthetic models, legal sources."""
import asyncio
import json
from dataclasses import replace

import pytest

from astrbot_plugin_livingemotion.runtime.background import ModelResultUnknown
from astrbot_plugin_livingemotion.contracts import ContentKind, EvidenceRef
from astrbot_plugin_livingemotion.ports.memory import Material, RecallResult
from astrbot_plugin_livingemotion.runtime.feeling import maybe_feeling, feeling_state, parse_feeling
from astrbot_plugin_livingemotion.storage.feeling import (
    INTERVAL, claim_feeling, feeling_key, finish_feeling, read_feeling, set_feeling_sources,
)
from astrbot_plugin_livingemotion.tests.experience.test_manual_daily import make_app
from astrbot_plugin_livingemotion.tests.integration.test_application import Message

TEXT = "想起你说的话，心里悄悄暖了一点。"


async def setup(tmp_path, settings=None):
    app, model, host, native = await make_app(tmp_path, {
        "enabled": True, "mode": "active", "emotion_model_enabled": False,
        "model_daily_limit": 20, "night_enabled": False, "memory_read": False,
        **(settings or {})})
    async def binding(*args, **kwargs):
        return model
    async def generate(system, data, output, timeout):
        assert output == 256
        model.calls += 1
        model.payloads.append(json.loads(data))
        model.started.set()
        await model.release.wait()
        if model.error:
            raise model.error
        return model.response or json.dumps({"text": TEXT})
    model.generate = generate
    app._select_model_binding = binding
    return app, model, host, native


async def complete(app):
    await asyncio.wait_for(app._feeling_task, 3)


@pytest.mark.asyncio
async def test_first_boundary_refresh_restart_and_missed_windows(tmp_path):
    app, model, host, _ = await setup(tmp_path)
    now = app.store.clock()
    try:
        await maybe_feeling(app)
        await complete(app)
        first = await feeling_state(app)
        assert first["text"] == TEXT and first["status"] == "succeeded"
        assert first["next_due"] == now + INTERVAL
        for _ in range(5):
            await app.console_state()
            await maybe_feeling(app)
        assert model.calls == 1 and host.sends == 0
        app.store.clock = lambda: now + INTERVAL - .01
        await maybe_feeling(app)
        assert model.calls == 1
        app.store.clock = lambda: now + INTERVAL
        await maybe_feeling(app)
        await complete(app)
        assert model.calls == 2
    finally:
        await app.terminate()
    app, model, _, _ = await setup(tmp_path)
    try:
        app.store.clock = lambda: now + INTERVAL + 1
        await maybe_feeling(app)
        assert model.calls == 0 and (await feeling_state(app))["text"] == TEXT
        app.store.clock = lambda: now + INTERVAL * 10
        await maybe_feeling(app)
        await complete(app)
        await maybe_feeling(app)
        assert model.calls == 1
        assert (await feeling_state(app))["next_due"] == now + INTERVAL * 11
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_overlapping_scheduler_claims_one_request(tmp_path):
    app, model, _, _ = await setup(tmp_path)
    try:
        model.release.clear()
        await asyncio.gather(*(maybe_feeling(app) for _ in range(12)))
        await asyncio.wait_for(model.started.wait(), 2)
        assert model.calls == 1
        await asyncio.gather(*(maybe_feeling(app) for _ in range(12)))
        assert model.calls == 1
        model.release.set()
        await complete(app)
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["invalid", "timeout", "unknown", "model", "persona", "config", "clear"])
async def test_failure_old_text_and_paid_result_never_retried(fault, tmp_path):
    app, model, _, native = await setup(tmp_path)
    now = app.store.clock()
    try:
        await maybe_feeling(app)
        await complete(app)
        model.started.clear()
        model.release.clear()
        app.store.clock = lambda: now + INTERVAL
        await maybe_feeling(app)
        await asyncio.wait_for(model.started.wait(), 2)
        if fault == "invalid":
            model.response = '{"text":"太短"}'
        elif fault == "timeout":
            model.error = TimeoutError()
        elif fault == "unknown":
            model.error = ModelResultUnknown()
        elif fault == "model":
            model.fingerprint = "changed"
        elif fault == "persona":
            native["persona_id"] = "another"
        elif fault == "config":
            native["model_daily_limit"] = 21
        elif fault == "clear":
            pid, _, rev = await app.manual_persona()
            c = app.private_archive_context(pid, rev)
            await app.store.clear_scope(c, await app.store.get_generation(c))
        model.release.set()
        await complete(app)
        record = await read_feeling(app.store, feeling_key(app.instance_id, "native"))
        assert record["status"] != "succeeded"
        assert record["text"] == ("" if fault == "clear" else TEXT)
        if fault in ("timeout", "unknown"):
            assert record["status"] == "unknown"
        await maybe_feeling(app)
        assert model.calls == 2
        assert await app.store.quota_usage(period="2026-11-09", pool="model") == 2
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_disabled_observe_quota_and_shutdown(tmp_path):
    for mode in ("observe_only", "active"):
        app, model, _, _ = await setup(tmp_path / mode, {"mode": mode, "model_daily_limit": 1})
        try:
            c = app.private_archive_context("native", "quota")
            await app.store.reserve_quota("used", c, 0, period="2026-11-09",
                                         purpose="feeling", limit=1, global_limit=1)
            await maybe_feeling(app)
            if mode == "active":
                await complete(app)
                assert (await feeling_state(app))["status"] == "failed"
            assert model.calls == 0
        finally:
            await app.terminate()
    app, model, _, _ = await setup(tmp_path / "stop")
    now = app.store.clock()
    model.release.clear()
    await maybe_feeling(app)
    await model.started.wait()
    await app.terminate()
    app, model, _, _ = await setup(tmp_path / "stop")
    try:
        app.store.clock = lambda: now + 1
        await maybe_feeling(app)
        assert (await feeling_state(app))["status"] == "unknown" and model.calls == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_legal_local_memory_emotion_and_source_clear(tmp_path):
    app, model, host, _ = await setup(tmp_path)
    try:
        message = Message("feeling-grounding", "谢谢你耐心教我，今天很开心。")
        await app.on_message(message)
        assert message.extra["livingemotion:ingest"] == "accepted"
        await maybe_feeling(app)
        await complete(app)
        assert any("耐心教我" in p["text"] for p in model.payloads[0]["memories"])
        assert set(model.payloads[0]["emotion"]) == {"joy", "anger", "sadness", "fear", "surprise", "affection"}
        context = next(iter(app._contexts.values()))
        await app.store.clear_scope(context, await app.store.get_generation(context))
        assert (await feeling_state(app))["text"] == ""
        await maybe_feeling(app)
        assert model.calls == 1 and host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_claim_deadline_tombstone_and_late_completion(tmp_path):
    app, _, _, _ = await setup(tmp_path)
    try:
        now = app.store.clock()
        key = feeling_key(app.instance_id, "native")
        slot = await claim_feeling(app.store, key, "rev", deadline_seconds=90)
        assert slot
        app.store.clock = lambda: now + 91
        assert await claim_feeling(app.store, key, "rev", deadline_seconds=90) is None
        assert (await read_feeling(app.store, key))["status"] == "unknown"
        assert not await finish_feeling(app.store, key, slot["run_id"], status="succeeded", text=TEXT)
        app.store.clock = lambda: now + INTERVAL * 4
        newer = await claim_feeling(app.store, key, "rev", deadline_seconds=90)
        assert newer and newer["run_id"] != slot["run_id"]
        assert not await finish_feeling(app.store, key, slot["run_id"], status="failed")
        assert (await read_feeling(app.store, key))["run_id"] == newer["run_id"]
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("settings,expected", [
    ({"diary_provider_id": "saved-diary", "dream_provider_id": "saved-dream"}, "diary"),
    ({"dream_provider_id": "saved-dream"}, "dream"),
    ({}, "feeling"),
])
async def test_saved_experience_model_without_live_route(settings, expected, tmp_path):
    app, model, _, _ = await setup(tmp_path, settings)
    try:
        selected = []
        async def binding(purpose, route=None):
            selected.append((purpose, route))
            return model
        app._select_model_binding = binding
        await maybe_feeling(app)
        await complete(app)
        assert selected and all(purpose == expected and route is None for purpose, route in selected)
        assert (await feeling_state(app))["status"] == "succeeded"
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["allowed", "wrong_scope", "revoked", "no_event", "read_disabled"])
async def test_livingmemory_original_event_authorization_and_no_fabricated_route(case, tmp_path):
    app, model, host, _ = await setup(tmp_path, {"memory_read": case != "read_disabled"})
    try:
        message = Message("livingmemory-feeling", "今天谢谢你的关心。")
        await app.on_message(message)
        context = next(iter(app._contexts.values()))
        calls = []
        class Backend:
            permitted = True
            def cache_token(self):
                return "synthetic-livingmemory"
            async def fetch(self, request, event):
                calls.append((request.context, event))
                assert event is message and request.context.route == message.unified_msg_origin
                source = replace(context, account_id="another") if case == "wrong_scope" else context
                material = Material(EvidenceRef(
                    "livingmemory", "synthetic-real-source", source, source.account_id,
                    source.bot_id, ContentKind.INTERACTION, app.store.clock(),
                    source_ids=("legal-source",)), "记得你曾在我失落时温柔陪伴。")
                return RecallResult((material,))
            async def validate(self, request, materials, event):
                return self.permitted and event is message
        backend = Backend()
        app.memory.backend = backend
        if case == "no_event":
            app.bridge.sources.clear()
        if case == "revoked":
            model.release.clear()
        await maybe_feeling(app)
        if case == "revoked":
            await asyncio.wait_for(model.started.wait(), 2)
            backend.permitted = False
            model.release.set()
        await complete(app)
        if case in ("no_event", "read_disabled"):
            assert calls == []
        else:
            assert calls == [(context, message)]
        present = any("失落时温柔陪伴" in p["text"] for p in model.payloads[0]["memories"])
        assert present == (case in ("allowed", "revoked"))
        if case == "revoked":
            assert (await feeling_state(app))["text"] == ""
        else:
            assert (await feeling_state(app))["text"] == TEXT
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.parametrize("raw", [TEXT, json.dumps({"text": TEXT}), "```json\n" + json.dumps({"text": TEXT}) + "\n```"])
def test_short_phrase_tolerant_parser(raw):
    assert parse_feeling(raw) == TEXT


@pytest.mark.parametrize("raw", ["太短", '{"text":"太短","error":"bad"}', "<script>想起你说的话心里悄悄暖了一点</script>",
                                "密码：想起你说的话心里悄悄暖了一点", "想起你说的话，账号123456让我温暖。",
                                '{"text":"想起你说的话心里悄悄暖了一点","source_ids":["private"]}'])
def test_short_phrase_rejects_unsafe_invalid(raw):
    with pytest.raises(ValueError):
        parse_feeling(raw)
