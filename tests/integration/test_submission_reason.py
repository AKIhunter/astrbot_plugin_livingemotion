"""宿主提交保留底层拒绝原因；兼容既有 bool 回调，无实际发送。"""

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from astrbot_plugin_livingemotion.contracts import Context, StateWrite, to_dict
from test_retro_reply import FinalMessage, at_time


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", [
    "reply_submission_expired", "reply_ticket_required", "reply_not_started",
    "stale_generation", "reply_context_changed",
])
async def test_host_hook_keeps_submission_rejection_reason(tmp_path, reason):
    app, host, _, _ = await at_time(tmp_path, 12, config={"night_schedule_enabled": False})
    try:
        message = FinalMessage(identifier="denied")
        await app.on_llm_request(message, SimpleNamespace(extra_user_content_parts=[]))
        app.reply_submitted = AsyncMock(return_value={
            "allowed": False, "status": "rejected", "reason_code": reason,
        })
        assert await app.on_reply_submitted(message) is False
        assert message.get_extra("_at_guard_delivery_blocked") == reason
        context = Context.from_dict(message.get_extra("livingemotion:context"))
        assert (await app.store.energy_history(context, category="reply"))["total"] == 0
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("finish", [1794795442.728494, 1794795532.958494])
async def test_real_host_submission_survives_normal_wake(tmp_path, finish):
    app, host, _, clock = await at_time(tmp_path, 10, 13, config={
        "night_schedule_enabled": False, "nap_enabled": False, "wake_reply_limit": 3,
        "energy_fatigue_per_minute": 0, "energy_recovery_per_minute": 0,
    })
    try:
        clock[0] = 1794795200.049583
        message = FinalMessage(identifier="inflight")
        await app.on_message(message)
        context = Context.from_dict(message.get_extra("livingemotion:context"))
        record = await app.store.get_state(context, "night")
        state = replace(app.store._night_value(record.value), energy=100, energy_units=1000,
                        cycle_id="incident-cycle", cycle_kind="night",
                        cycle_started_at=clock[0] - 600, drowsy_at=clock[0] - 300,
                        deep_sleep_at=None, wake_at=1794795442.728494,
                        wake_session="admitted-wake", wake_reply_limit=3)
        assert (await app.store.write_states(context, await app.store.get_generation(context), (
            StateWrite("night", to_dict(state), record.version, owner=record.owner),
        ))).accepted
        await app.on_llm_request(message, SimpleNamespace(extra_user_content_parts=[]))
        assert message.get_extra("livingemotion:reply_lease")
        clock[0] = finish
        # 真实宿主钩子内部先 tick 清理会话，再走真实提交事务。
        assert await app.on_reply_submitted(message) is True
        assert await app.on_reply_submitted(message) is True
        assert message.get_extra("_at_guard_delivery_blocked") is None
        assert (await app.store.energy_history(context, category="reply"))["total"] == 1
        assert (await app.night_snapshot(context)).wake_window_deadline is None
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_record_host_submission_preserves_bool_interface(tmp_path):
    app, host, _, _ = await at_time(tmp_path, 12, config={"night_schedule_enabled": False})
    try:
        message = FinalMessage(identifier="accepted")
        await app.on_llm_request(message, SimpleNamespace(extra_user_content_parts=[]))
        context = Context.from_dict(message.get_extra("livingemotion:context"))
        identifier = message.get_extra("livingemotion:reply_lease")["attempt_id"]
        assert await app.record_host_submission(context, identifier, "synthetic") is True
        assert await app.record_host_submission(context, identifier, "synthetic") is True
        assert await app.record_host_submission(context, "unstarted", "synthetic") is False
        assert (await app.store.energy_history(context, category="reply"))["total"] == 1
        assert host.sends == 0
    finally:
        await app.terminate()

@pytest.mark.asyncio
async def test_archive_version_conflict_allows_delivery_and_retries(tmp_path):
    """归档事件撞版本时不能吞掉已经通过 reply_submitted 的回复。"""
    app, host, _, _ = await at_time(tmp_path, 12, config={"night_schedule_enabled": False})
    try:
        message = FinalMessage(identifier="archive-conflict")
        await app.on_llm_request(message, SimpleNamespace(extra_user_content_parts=[]))
        context = Context.from_dict(message.get_extra("livingemotion:context"))
        identifier = message.get_extra("livingemotion:reply_lease")["attempt_id"]
        app.api.ingest_event = AsyncMock(return_value={
            "status": "rejected", "reason_code": "version_conflict",
        })
        app._retry_reply_archive = AsyncMock()
        assert await app.record_host_submission(context, identifier, "synthetic") is True
        assert message.get_extra("_at_guard_delivery_blocked") is None
        await asyncio.sleep(0)
        app._retry_reply_archive.assert_awaited_once()
        assert (await app.store.energy_history(context, category="reply"))["total"] == 1
        assert host.sends == 0
    finally:
        await app.terminate()
