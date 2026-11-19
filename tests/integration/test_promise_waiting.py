"""重试预算、旧等待迁移、未知收尾与取消竞争；真实SQLite，零外部请求。"""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import Context
from astrbot_plugin_livingemotion.runtime.promise_service import PromiseService
from astrbot_plugin_livingemotion.storage.promise_store import PromiseStore
from test_application import application, Message
from test_promise_actions import scenario, add
from test_promise_cancellation import seed


@pytest.mark.parametrize("value", [0, 1, 3, 10])
async def test_retry_config_save_runtime_dto_match(tmp_path, value):
    app, host, native = await application(tmp_path, {"timezone": "UTC"})
    try:
        await app.update_config(
            {"promise_retry_limit": value, "promise_wait_timeout_hours": 1},
            expected_revision=app.revision, actor_id="offline-admin", reason="offline test")
        assert native["promise_retry_limit"] == app.config.promise_retry_limit == value
        assert app._promises().retry_limit == value
        field = next(f for f in app.config_dto()["fields"] if f["key"] == "promise_retry_limit")
        assert (field["min"], field["max"], field["value"]) == (0, 10, value)
        wait = next(f for f in app.config_dto()["fields"] if f["key"] == "promise_wait_timeout_hours")
        assert (wait["min"], wait["max"], wait["unit"]) == (1, 168, "小时")
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.parametrize("field,value", [
    ("promise_retry_limit", -1), ("promise_retry_limit", 11),
    ("promise_retry_limit", True), ("promise_retry_limit", "3"),
    ("promise_wait_timeout_hours", 0), ("promise_wait_timeout_hours", 169),
])
def test_retry_wait_config_rejects_invalid_values(field, value):
    with pytest.raises(ValueError, match=field):
        Config.from_mapping({field: value})


@pytest.mark.parametrize("kind", ["provider_error", "result_unknown", "delivery_unknown"])
async def test_waiting_deadline_survives_notice_and_restart_and_preserves_evidence(scenario, kind):
    s = scenario
    s.app.config.promise_wait_timeout_hours = 1
    s.app.send_promise_notice = AsyncMock(return_value="sent")
    pid = await seed(s, "窗边", kind=kind)
    row = await s.service.promises.get(pid)
    since, payload = row["waiting_since"], row["action_result_json"]
    s.clock[0] += 1800
    await s.service.run_due()
    assert s.app.send_promise_notice.await_count == 1
    s.service = PromiseService(s.service.store, s.app)
    assert (await s.service.promises.get(pid))["waiting_since"] == since
    s.clock[0] += 1801
    await s.service.run_due()
    row = await s.service.promises.get(pid)
    assert row["status"] == "failed" and row["last_error"] == "waiting_timeout"
    assert row["action_result_json"] == payload and row["sent_at"] is None
    assert await s.service.promises.count_active(s.context) == 0
    assert s.peer.calls == 0 and not s.sends


async def test_old_waiting_timestamp_migrates_without_resetting_deadline(scenario):
    s = scenario
    pid = await seed(s, "旧图", kind="result_unknown")
    old = s.clock[0] - 7200
    await s.service.store._run(lambda db: db.execute(
        "UPDATE promises SET updated_at=?,waiting_since=0 WHERE promise_id=?", (old, pid)))
    store = PromiseStore(s.service.store)
    await store.ensure()
    assert (await store.get(pid))["waiting_since"] == old
    assert await store.expire_waiting(now=s.clock[0], timeout_seconds=3600) == 1


async def test_unknown_counts_toward_capacity_and_cancellation_preserves_payload(scenario):
    s = scenario
    s.app.config.promise_max_active = 1
    pid = await add(s)
    await s.service.promises.move(pid, status="running", expect=("scheduled",))
    artifact = {"request_id": "uncertain", "kind": "result_unknown", "prompt": "猫"}
    await s.service.promises.hold_image_failure(s.context, pid, artifact, state="unknown")
    before = await s.service.promises.get(pid)
    assert await s.service.promises.count_active(s.context) == 1
    assert (await s.service.remember(s.context, [("稍后", "提醒喝水")]))[0]["status"] == "limit_reached"
    assert (await s.service.cancel(s.context, pid[:8]))["status"] == "cancelled"
    after = await s.service.promises.get(pid)
    assert after["action_result_json"] == before["action_result_json"]
    assert after["action_state"] == "unknown" and after["sent_at"] is None
    s.clock[0] += 86401
    await s.service.run_due()
    assert s.peer.calls == 0 and not s.sends


async def test_console_cancel_uses_persisted_context_and_does_not_send(tmp_path):
    app, host, _ = await application(tmp_path, {"timezone": "UTC"})
    try:
        message = Message("source", "请画猫")
        await app.on_message(message)
        context = Context.from_dict(message.get_extra("livingemotion:context"))
        result = (await app._promises().remember(context, [("稍后", "提醒喝水")]))[0]
        app._contexts.clear()
        receipt = await app.console_action(
            context.account_key, "promise.cancel", promise_id=result["promise_id"],
            expected_revision=app.revision, actor_id="offline-admin", reason="offline test",
            confirmed=True)
        assert receipt["status"] == "cancelled"
        assert receipt["model_calls"] == receipt["sends"] == host.sends == 0
        assert receipt["upstream_cancellation_confirmed"] is False
    finally:
        await app.terminate()


@pytest.mark.parametrize("limit", [0, 3, 10])
async def test_explicit_text_failure_retries_configured_count_across_restart(scenario, limit):
    s = scenario
    s.app.config.promise_retry_limit = limit
    s.app.send_promise_notice = AsyncMock(return_value="rejected")
    # 此矩阵检验确定失败预算；睡眠等待有独立矩阵，不能把它当重试消耗。
    s.app.night_snapshot = AsyncMock(return_value=SimpleNamespace(
        display_state=SimpleNamespace(value="awake")))
    pid = await seed(s, "提醒喝水")
    s.clock[0] += 61
    for attempt in range(limit + 2):
        await s.service.run_due()
        s.service = PromiseService(s.service.store, s.app)
        s.clock[0] += 301
    row = await s.service.promises.get(pid)
    assert row["status"] == "failed" and row["retry_count"] == limit
    assert s.app.send_promise_notice.await_count == limit + 1
    assert s.peer.calls == 0 and not s.sends


async def test_image_delivery_unknown_is_not_reported_as_generation_failure(scenario):
    s = scenario
    s.app.send_result = OSError("isolated uncertain delivery")
    s.app.send_promise_notice = AsyncMock(return_value="sent")
    pid = await add(s)
    await s.service.run_due()
    row = await s.service.promises.get(pid)
    artifact = json.loads(row["action_result_json"])
    assert row["status"] == "unknown" and artifact["kind"] == "delivery_unknown"
    assert artifact["stage"] == "delivery" and artifact["path"] == str(s.file)
    assert "收到" in s.app.send_promise_notice.call_args.args[1]
    s.clock[0] += 301
    await s.service.run_due()
    assert s.peer.calls == 1 and len(s.sends) == 1


async def test_sleep_wait_does_not_consume_retry_budget(scenario):
    s = scenario
    s.app.config.promise_retry_limit = 0
    s.app.send_promise_notice = AsyncMock(return_value="rejected")
    s.app.night_snapshot = AsyncMock(return_value=SimpleNamespace(
        display_state=SimpleNamespace(value="deep_sleep"), wake_window_deadline=s.clock[0] + 3600))
    pid = await seed(s, "提醒喝水")
    s.clock[0] += 61
    await s.service.run_due()
    row = await s.service.promises.get(pid)
    assert row["status"] == "scheduled" and row["retry_count"] == 0
    assert row["due_at"] >= s.clock[0] + 3600
