import asyncio
from dataclasses import replace

import pytest

from astrbot_plugin_livingemotion.api import LivingEmotionAPI
from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import StateWrite, to_dict
from astrbot_plugin_livingemotion.runtime import BackgroundRuntime
from astrbot_plugin_livingemotion.runtime.lifecycle import Lifecycle


async def test_queue_full_is_rejected_not_accepted(le_store, le_context):
    runtime = BackgroundRuntime(le_store, Config(queue_size=1))
    gate = asyncio.Event()
    entered = asyncio.Event()

    async def work():
        entered.set()
        await gate.wait()

    await runtime.start()
    try:
        assert (await runtime.submit("1", le_context, 0, work))["status"] == "queued"
        await entered.wait()
        assert (await runtime.submit("2", le_context, 0, work))["status"] == "queued"
        assert (await runtime.submit("3", le_context, 0, work)) == {
            "status": "rejected", "reason_code": "queue_full",
        }
        await runtime.start()
        assert runtime.health()["workers"] == 1
    finally:
        gate.set()
        await runtime.stop()
    assert runtime.health()["workers"] == runtime.health()["pending"] == 0


async def test_default_model_disabled_and_no_idle_calls(le_store, le_context):
    runtime = BackgroundRuntime(le_store, Config())
    calls = []

    async def work():
        calls.append(1)

    await runtime.start()
    try:
        assert (await runtime.submit("1", le_context, 0, work, model=True, purpose="emotion",
                                     input_tokens=10, output_tokens=10))["reason_code"] == "model_disabled"
        await asyncio.sleep(0.01)
        assert calls == []
        assert (await le_store.health())["counts"]["quota_reservations"] == 0
    finally:
        await runtime.stop()


async def test_model_quota_and_failed_calls_are_charged(le_store, le_context):
    runtime = BackgroundRuntime(le_store, Config(emotion_model_enabled=True, model_daily_limit=2))
    calls = []

    async def work():
        calls.append(1)
        raise RuntimeError("private exception body must not appear")

    await runtime.start()
    try:
        for index in range(3):
            result = await runtime.submit(str(index), replace(le_context, scene_id=str(index)),
                                          0, work, model=True,
                                          purpose="emotion", input_tokens=10, output_tokens=10)
            assert result["status"] == "queued"
        await runtime.join()
        assert len(calls) == 2
        assert "private exception" not in str(runtime.health())
        assert runtime.health()["outcomes"][-1]["reason_code"] == "quota_exhausted"
    finally:
        await runtime.stop()


async def test_token_limits_reject_before_work(le_store, le_context):
    runtime = BackgroundRuntime(le_store, Config(emotion_model_enabled=True))

    async def work():
        pytest.fail("must not execute")

    await runtime.start()
    try:
        assert (await runtime.submit("1", le_context, 0, work, model=True, purpose="emotion",
                                     input_tokens=5000, output_tokens=10))["reason_code"] == "token_limit"
    finally:
        await runtime.stop()


async def test_stale_queued_job_is_cancelled(le_store, le_context):
    runtime = BackgroundRuntime(le_store, Config())
    await runtime.start()
    try:
        await le_store.clear_scope(le_context, 0)

        async def work():
            pytest.fail("stale generation must not run")

        await runtime.submit("stale", le_context, 0, work)
        await runtime.join()
        assert runtime.health()["outcomes"][-1]["reason_code"] == "stale_generation"
    finally:
        await runtime.stop()


async def test_three_reload_cycles_have_no_old_tasks_or_writeback(tmp_path, le_context):
    lifecycle = Lifecycle(tmp_path / "native-data-dir", Config())
    for cycle in range(3):
        await lifecycle.initialize()
        old_api, old_store = lifecycle.api, lifecycle.store
        await lifecycle.initialize()
        assert lifecycle.runtime.health()["workers"] == 1
        entered = asyncio.Event()

        async def work():
            entered.set()
            await asyncio.Event().wait()
            await old_store.write_states(le_context, 0, (StateWrite("bot", {"bad": True}),))

        await lifecycle.runtime.submit(f"job-{cycle}", le_context, 0, work)
        await entered.wait()
        await lifecycle.terminate()
        assert (await old_api.get_health())["status"] == "stopped"
        assert not [task for task in asyncio.all_tasks()
                    if task.get_name().startswith("livingemotion-worker") and not task.done()]
    await lifecycle.terminate()
    assert (tmp_path / "native-data-dir" / "livingemotion.sqlite3").exists()


async def test_facade_r9_and_admin_is_not_authorization(le_store, le_context, le_event):
    runtime = BackgroundRuntime(le_store, Config())
    api = LivingEmotionAPI(le_store, Config(), runtime)
    assert (await api.get_capabilities())["api_version"] == 1
    assert (await api.ingest_event(le_event))["status"] == "accepted"
    assert (await api.ingest_event(le_event))["status"] == "duplicate"
    assert (await api.get_bot_state(le_context))["type"] == "bot"
    assert (await api.get_observation(le_context))["type"] == "observation"
    assert (await api.get_relationship(le_context))["data"]["normalized"] == 0
    availability = await api.get_availability(le_context)
    assert availability["block_chat"] is False
    preview = await api.preview_behavior(le_context)
    assert preview["model_calls"] == preview["sends"] == 0
    assert (await api.get_health())["status"] == "ok"
    assert (await api.get_bot_state({**to_dict(le_context), "admin": True}))["status"] == "rejected"


async def test_disabled_facade_rejects_events(le_store, le_event):
    config = Config(enabled=False)
    runtime = BackgroundRuntime(le_store, config)
    await runtime.start()
    api = LivingEmotionAPI(le_store, config, runtime)
    assert runtime.health()["workers"] == 0
    assert (await api.ingest_event(le_event))["reason_code"] == "plugin_disabled"


async def test_facade_projection_commit_is_atomic(le_store, le_event):
    config = Config()
    runtime = BackgroundRuntime(le_store, config)

    async def project(event):
        return [StateWrite("bot", {"pleasure": 0.3})], []

    api = LivingEmotionAPI(le_store, config, runtime, project_event=project)
    result = await api.ingest_event(le_event)
    assert result["domain_applied"]
    assert (await api.get_bot_state(le_event.context))["data"]["pleasure"] == 0.3


async def test_facade_generation_cannot_refresh_after_project_wait(le_store, le_event):
    config = Config()
    entered, resume = asyncio.Event(), asyncio.Event()

    async def project(event):
        entered.set()
        await resume.wait()
        return [StateWrite("bot", {"pleasure": 0.3})], []

    api = LivingEmotionAPI(le_store, config, BackgroundRuntime(le_store, config),
                           project_event=project)
    task = asyncio.create_task(api.ingest_event(le_event))
    await entered.wait()
    await le_store.clear_scope(le_event.context, 0)
    resume.set()
    assert (await task)["reason_code"] == "stale_generation"
    assert await le_store.get_state(le_event.context, "bot") is None


async def test_lifecycle_persists_host_id_and_rejects_other_instances(tmp_path, le_event):
    lifecycle = Lifecycle(tmp_path / "instance-one", Config())
    await lifecycle.initialize()
    instance_id = lifecycle.instance_id
    assert (await lifecycle.api.ingest_event(le_event))["reason_code"] == "instance_mismatch"
    own_event = replace(le_event, occurred_at=lifecycle.store.clock(),
                        context=replace(le_event.context, instance_id=instance_id))
    assert (await lifecycle.api.ingest_event(own_event))["status"] == "accepted"
    await lifecycle.terminate()
    await lifecycle.initialize()
    assert lifecycle.instance_id == instance_id
    assert (await lifecycle.api.get_capabilities())["instance_id"] == instance_id
    await lifecycle.terminate()
    other = Lifecycle(tmp_path / "instance-two", Config())
    await other.initialize()
    assert other.instance_id != instance_id
    await other.terminate()


async def test_facade_hides_internal_projection_runtime(le_store, le_context):
    await le_store.write_states(le_context, 0, (
        StateWrite("bot", {"pleasure": 0.1, "_runtime": {"internal_budget": 1}}),
    ))
    config = Config()
    api = LivingEmotionAPI(le_store, config, BackgroundRuntime(le_store, config))
    snapshot = await api.get_bot_state(le_context)
    assert snapshot["data"] == {"pleasure": 0.1}
    assert "_runtime" in (await le_store.get_state(le_context, "bot")).value


async def test_model_timeout_retains_reservation(le_store, le_context):
    runtime = BackgroundRuntime(
        le_store, Config(emotion_model_enabled=True, model_timeout_seconds=1),
    )

    async def work():
        await asyncio.Event().wait()

    await runtime.start()
    try:
        await runtime.submit("timeout", le_context, 0, work, purpose="emotion", model=True,
                             input_tokens=1, output_tokens=1)
        await runtime.join()
        assert runtime.health()["outcomes"][-1]["status"] == "unknown"
        assert (await le_store.health())["counts"]["quota_reservations"] == 1
    finally:
        await runtime.stop()


async def test_model_concurrency_is_bounded(le_store, le_context):
    runtime = BackgroundRuntime(le_store, Config(model_concurrency=2))
    active = 0
    maximum = 0

    async def work():
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.001)
        active -= 1

    await runtime.start()
    try:
        for index in range(20):
            await runtime.submit(str(index), le_context, 0, work)
        await runtime.join()
        assert maximum == 2
    finally:
        await runtime.stop()
