"""Deterministic API-to-SQLite tests with synthetic persona/model; no paid requests."""
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import itertools
import json
import random
from types import SimpleNamespace
from uuid import uuid4

import pytest

from astrbot_plugin_livingemotion.contracts import ContentKind, Experience
from astrbot_plugin_livingemotion.runtime.application import Application
from astrbot_plugin_livingemotion.services.manual_experience import accepted_day
from astrbot_plugin_livingemotion.storage.experiences import owner_key
from astrbot_plugin_livingemotion.tests.integration.test_application import Host, NativeConfig, TestBridge


class Binding:
    fingerprint = "synthetic-one"
    def __init__(self):
        self.calls = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.release.set()
        self.error = None
        self.payloads = []
        self.response = None

    def count(self, system, data):
        return len(system.encode()) + len(data.encode())

    async def generate(self, system, data, output, timeout):
        self.calls += 1
        self.payloads.append(json.loads(data))
        assert output == 8192 and timeout == 90
        self.started.set()
        await self.release.wait()
        if self.error:
            raise self.error
        return self.response if self.response is not None else json.dumps(
            {"body": f"我在想象中自省。第{self.calls}次。", "source_ids": []})


async def make_app(tmp_path, settings=None):
    host = Host()
    host.default_persona = "native"
    async def get_persona(identifier):
        return SimpleNamespace(system_prompt="Synthetic persona " + identifier, begin_dialogs=[])
    host.get_persona = get_persona
    native = NativeConfig({"enabled": False, "mode": "observe_only",
                           "diary_enabled": False, "dream_enabled": False,
                           "persona_mode": "explicit", "persona_id": "native",
                           "timezone": "Asia/Shanghai", "model_daily_limit": 1,
                           **(settings or {})})
    app = Application(host, native, tmp_path, bridge_factory=TestBridge)
    await app.initialize()
    app.store.clock = lambda: datetime(2026, 11, 9, 5, 0, tzinfo=timezone.utc).timestamp()
    binding = Binding()
    async def model(kind):
        return binding
    app.manual_model_binding = model
    return app, binding, host, native


async def submit(app, kind="diary", request_id=None, persona="native"):
    return await app.console_experience_generate(
        request_id or str(uuid4()), persona, kind, actor_id="verified-admin")


async def finish(app):
    await asyncio.wait_for(app.manual_experience.queue.join(), 3)


@pytest.mark.asyncio
async def test_disabled_empty_direct_and_daily_overwrite_pin(tmp_path):
    app, model, host, _ = await make_app(tmp_path)
    try:
        state = await app.console_state()
        assert {a["id"] for a in state["actions"] if a["enabled"]} == {"diary.generate", "dream.generate"}
        first = await submit(app)
        await finish(app)
        task = await app.console_experience_task(first["request_id"])
        assert task["status"] == "succeeded" and task["day"] == "2026-11-09"
        old, generation = await app.store.load_experience(task["experience_id"])
        assert old.context.route is None and old.context.platform == "console"
        assert "无已验证当日经历" in model.payloads[0]["grounding"]
        await app.store.pin_experience(old, replace(old, pinned=True), generation,
                                       actor_id="admin", reason="synthetic pin")
        second = await submit(app)
        await finish(app)
        new_task = await app.console_experience_task(second["request_id"])
        new, _ = await app.store.load_experience(new_task["experience_id"])
        assert old.experience_id == new.experience_id and new.pinned and new.body != old.body
        assert (await app.console_records(kind="diary", persona_id="native"))["total"] == 1
        assert (await app.console_records(kind="dream", persona_id="native"))["total"] == 0
        await submit(app, "dream")
        await finish(app)
        assert (await app.console_records(kind="dream", persona_id="native"))["total"] == 1
        assert model.calls == 3 and host.sends == 0
        assert (await app.store.quota_usage(period="2026-11-09", pool="model")) == 3
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_idempotency_double_click_refresh_and_midnight(tmp_path):
    app, model, _, _ = await make_app(tmp_path)
    try:
        model.release.clear()
        first = await submit(app)
        await model.started.wait()
        for _ in range(5):
            assert (await submit(app, request_id=first["request_id"]))["request_id"] == first["request_id"]
            assert (await submit(app))["request_id"] == first["request_id"]
            assert (await app.console_state())["experience"]["diary"]["request_id"] == first["request_id"]
        app.store.clock = lambda: datetime(2026, 11, 10, 1, tzinfo=timezone.utc).timestamp()
        model.release.set()
        await finish(app)
        result = await app.console_experience_task(first["request_id"])
        assert result["day"] == "2026-11-09" and result["status"] == "succeeded" and model.calls == 1
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["clear", "pin", "model", "persona", "invalid_json", "timeout"])
async def test_failure_preserves_old_body(fault, tmp_path):
    app, model, _, native = await make_app(tmp_path)
    try:
        first = await submit(app)
        await finish(app)
        task = await app.console_experience_task(first["request_id"])
        old, generation = await app.store.load_experience(task["experience_id"])
        model.started.clear()
        model.release.clear()
        second = await submit(app)
        await model.started.wait()
        if fault == "clear":
            await app.store.clear_scope(old.context, generation, actor_id="admin")
        elif fault == "pin":
            await app.store.pin_experience(old, replace(old, pinned=True), generation,
                                           actor_id="admin", reason="concurrent pin")
        elif fault == "model":
            model.fingerprint = "changed"
        elif fault == "persona":
            native["persona_id"] = "another"
        elif fault == "invalid_json":
            model.error = ValueError("invalid model payload")
        elif fault == "timeout":
            model.error = TimeoutError()
        model.release.set()
        await finish(app)
        result = await app.store.experience_job(second["request_id"], owner_key(app.instance_id, "native"))
        assert result["status"] != "succeeded"
        current = await app.store.load_experience(old.experience_id)
        if fault == "clear":
            assert current is None
        else:
            assert current[0].body == old.body
        if fault == "timeout":
            assert result["status"] == "unknown"
        assert model.calls == 2
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_reload_does_not_redispatch(tmp_path):
    app, model, _, _ = await make_app(tmp_path)
    model.release.clear()
    task = await submit(app)
    await model.started.wait()
    await app.terminate()
    app2, model2, _, _ = await make_app(tmp_path)
    try:
        result = await submit(app2, request_id=task["request_id"])
        assert result["status"] == "unknown" and model2.calls == 0
    finally:
        await app2.terminate()


@pytest.mark.asyncio
async def test_legacy_today_dream_merge_keeps_pin_other_day_persona(tmp_path):
    app, model, _, _ = await make_app(tmp_path)
    try:
        context = app.private_archive_context("native", "old")
        for index, persona, offset, pinned in [(0, "native", 0, False), (1, "native", 1, True),
                                               (2, "native", -86400, False), (3, "other", 0, False)]:
            entry = Experience(str(index), replace(context, persona_id=persona), ContentKind.DREAM,
                               f"night:{index}", app.store.clock() + offset, f"Old synthetic {index}", pinned=pinned)
            await app.store.save_experience(entry, 0)
        await submit(app, "dream")
        await finish(app)
        records = await app.console_records(kind="dream", persona_id="native")
        assert records["total"] == 2 and any(row["pinned"] for row in records["items"])
        assert (await app.console_records(kind="dream", persona_id="other"))["total"] == 1
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_seeded_auto_manual_clear_interleavings(tmp_path):
    seed = 20261109
    rng = random.Random(seed)
    # Barrier-controlled model completion, not sleep-based timing.
    for index, operations in enumerate(itertools.permutations(("manual", "auto", "clear"))):
        app, model, _, _ = await make_app(tmp_path / str(index))
        try:
            context = app.private_archive_context("native", "old")
            model.release.clear()
            for operation in operations:
                if operation == "manual":
                    await submit(app)
                    await model.started.wait()
                elif operation == "auto":
                    entry = Experience("auto", context, ContentKind.DIARY, "2026-11-09",
                                       app.store.clock(), "Synthetic automatic")
                    await app.store.save_auto_daily(entry, ((context, 0),), timezone="Asia/Shanghai", day="2026-11-09")
                elif operation == "clear":
                    await app.store.clear_scope(context, await app.store.get_generation(context))
            for _ in range(rng.randint(1, 8)):
                await app.console_state()  # Refresh cannot create model work.
            model.release.set()
            await finish(app)
            rows = await app.console_records(kind="diary", persona_id="native")
            assert rows["total"] <= 1, (seed, operations)
            assert model.calls <= 1, (seed, operations)
        finally:
            await app.terminate()


@pytest.mark.parametrize("stamp,zone,expected", [
    ("2026-11-09T16:01:00+00:00", "", "2026-11-10"),
    ("2026-11-01T05:30:00+00:00", "America/New_York", "2026-11-01"),
    ("2026-11-01T06:30:00+00:00", "America/New_York", "2026-11-01"),
])
def test_date_timezone_default_and_dst(stamp, zone, expected):
    assert accepted_day(datetime.fromisoformat(stamp).timestamp(), zone)[0] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [
    '{"body":"a valid body","error":{"code":500}}',
    '{"body":""}', '{"body":"<script>unsafe</script>"}',
    '{"body":"valid","source_ids":["unauthorized-source"]}', 'not JSON',
])
async def test_real_parser_rejects_invalid_result_preserving_archive(response, tmp_path):
    app, model, _, _ = await make_app(tmp_path)
    try:
        first = await submit(app)
        await finish(app)
        saved = await app.console_experience_task(first["request_id"])
        old, _ = await app.store.load_experience(saved["experience_id"])
        model.response = response
        second = await submit(app)
        await finish(app)
        result = await app.console_experience_task(second["request_id"])
        assert result["status"] == "failed"
        assert (await app.store.load_experience(old.experience_id))[0].body == old.body
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_storage_abort_atomic_and_auto_precheck_no_model(tmp_path):
    from astrbot_plugin_livingemotion.services.experience import ExperiencePolicy, ExperienceService
    app, model, _, _ = await make_app(tmp_path)
    try:
        first = await submit(app)
        await finish(app)
        result = await app.console_experience_task(first["request_id"])
        old, _ = await app.store.load_experience(result["experience_id"])
        automatic = SimpleNamespace(config=replace(app.config, enabled=True, mode="active", diary_enabled=True))
        service = ExperienceService(app.store, automatic, policy=ExperiencePolicy(
            timezone="Asia/Shanghai"))
        skipped = await service.queue_diary(old.context)
        assert skipped["reason_code"] == "daily_content_preserved" and model.calls == 1
        await service.close()
        await app.store._run(lambda db: db.execute(
            "CREATE TRIGGER synthetic_fail_daily BEFORE UPDATE ON experience_daily "
            "BEGIN SELECT RAISE(ABORT,'synthetic storage failure'); END"))
        second = await submit(app)
        await finish(app)
        assert (await app.console_experience_task(second["request_id"]))["status"] == "failed"
        assert (await app.store.load_experience(old.experience_id))[0].body == old.body
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_queue_bounded_and_shutdown_cancels_undispatched(tmp_path):
    app, model, _, _ = await make_app(tmp_path)
    try:
        model.release.clear()
        await submit(app)
        await model.started.wait()
        now = app.store.clock()
        for index in range(16):
            app.store.clock = lambda index=index: now + (index + 1) * 86400
            assert (await submit(app))["status"] == "queued"
        app.store.clock = lambda: now + 20 * 86400
        with pytest.raises(Exception, match="queue_full"):
            await submit(app)
        assert app.manual_experience.queue.qsize() == 16 and model.calls == 1
        await app.manual_experience.close()
        assert model.calls == 1 and app.manual_experience.queue.empty()
    finally:
        await app.terminate()
