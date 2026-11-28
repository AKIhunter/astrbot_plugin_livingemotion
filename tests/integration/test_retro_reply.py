"""Native hook wiring with synthetic host results; no platform sends."""

from dataclasses import replace
from datetime import datetime, timezone
import json
from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.contracts import Context, StateWrite, to_dict
from test_application import Message, application, request_to_model


CONFIG = {
    "timezone": "UTC", "night_policy_version": 2, "night_schedule_enabled": True,
    "persona_shared_state": True, "allow_sleep": True, "lie_in_min_minutes": 0,
    "lie_in_max_minutes": 0, "catchup_enabled": False, "catchup_reply_enabled": False,
    "wake_reply_limit": 1,
}


class FinalMessage(Message):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.result = SimpleNamespace(chain=[SimpleNamespace(text="synthetic reply")])
        self.stopped = False

    def get_result(self):
        return self.result

    def stop_event(self):
        self.stopped = True

    def is_stopped(self):
        return self.stopped


async def at_time(tmp_path, hour, minute=0, config=None):
    app, host, native = await application(tmp_path, {**CONFIG, **(config or {})})
    now = datetime(2026, 11, 6, hour, minute, tzinfo=timezone.utc).timestamp()
    clock = [now]
    app.store.clock = lambda: clock[0]
    return app, host, native, clock


async def seed_nap(app, message):
    """原生唤醒钩子从未满精力的小憩开始，不能把夜间疲劳当成睡眠。"""
    source, _ = await app.bridge.normalize(message, app.store.clock())
    context = source.context
    await app.initialize_state_scope(context)
    await app.night_snapshot(context)
    record = await app.store.get_state(context, "night")
    state = replace(app.store._night_value(record.value),
                    energy=99, energy_units=990, cycle_kind="nap")
    assert (await app.store.write_states(context, await app.store.get_generation(context), (
        StateWrite("night", to_dict(state), record.version, owner=record.owner),
    ))).accepted


async def test_veto_before_admission_preserves_last_wake_round(tmp_path):
    app, _, _, _ = await at_time(tmp_path, 1, 30)
    try:
        first = FinalMessage(identifier="wake-replay")
        await seed_nap(app, first)
        request = SimpleNamespace(extra_user_content_parts=[])
        await app.on_llm_request(first, request)
        context = Context.from_dict(first.extra["livingemotion:context"])
        first.stop_event()
        await app.admit_llm_request(first, request)
        assert first.get_extra("livingemotion:reply_attempt") is None
        assert first.get_extra("livingemotion:reply_lease") is None
        assert context.scope_key not in app._pending_replies
        assert (await app.night_snapshot(context)).wake_replies_used == 0

        retry = FinalMessage(identifier="wake-replay")
        await request_to_model(app, retry)
        assert not retry.stopped and retry.get_extra("livingemotion:reply_lease")
        assert (await app.night_snapshot(context)).wake_replies_used == 1
        assert await app.on_reply_submitted(retry) is True
    finally:
        await app.terminate()


@pytest.mark.parametrize("change", ["source_reset", "native_config", "persona"])
async def test_admission_rechecks_prepared_context_before_spending_round(tmp_path, change):
    app, host, native, _ = await at_time(tmp_path, 12)
    try:
        message = FinalMessage(identifier="stale-reply")
        request = SimpleNamespace(extra_user_content_parts=[])
        await app.on_llm_request(message, request)
        context = Context.from_dict(message.extra["livingemotion:context"])
        generation = await app.store.get_generation(context)
        if change == "source_reset":
            assert (await app.store.clear_scope(context, generation)).accepted
        elif change == "native_config":
            native["mode"] = "observe_only"
        else:
            host.persona_id = "changed-persona"
        await app.admit_llm_request(message, request)
        assert message.stopped and message.get_extra("livingemotion:reply_lease") is None
        attempts = await app.store._run(lambda db: db.execute(
            "SELECT COUNT(*) FROM reply_attempts").fetchone()[0])
        assert attempts == 0
    finally:
        await app.terminate()


async def test_diagnostics_explain_duplicate_stop_and_distinguish_raw_events(tmp_path, le_export):
    app, _, _, clock = await at_time(tmp_path, 12)
    app.diagnostics.clock = lambda: clock[0] + 1
    try:
        # The native adapter reuses the original message ID, but makes a fresh
        # host event object on each delivery.
        messages = [FinalMessage(identifier="private-platform-message-id", body="private-chat-body")
                    for _ in range(2)]
        raw_events = [("notice", {"notice_type": "notify", "sub_type": "poke"}),
                      ("request", {"request_type": "friend", "sub_type": "private-unknown-value"})]
        for message in messages:
            message.message_obj.raw_message = {"post_type": "message", "message_type": "private",
                                               "raw_message": "private-wire-body"}
            await request_to_model(app, message)
        assert not messages[0].stopped and messages[1].stopped
        for category, detail in raw_events:
            message = FinalMessage(identifier=f"private-{category}-id", body="")
            message.message_obj.raw_message = {"post_type": category, **detail}
            await app.on_message(message)

        clock[0] += 1
        exported = le_export(app)
        rows = [json.loads(line) for line in exported["runtime.jsonl"].splitlines()]
        ready, = [row for row in rows if row.get("stage") == "reply_admission" and row["status"] == "accepted"]
        stopped, = [row for row in rows if row.get("stage") == "admit_final_request" and row["status"] == "stopped"]
        assert stopped["reason_code"] == "reply_exists"
        assert stopped["reply_id"] == ready["reply_id"]
        assert stopped["event_id"] == ready["event_id"]
        assert stopped["event_key"] == ready["event_key"]
        assert stopped["flow_id"] != ready["flow_id"]
        assert stopped["native_post_type"] == ready["native_post_type"] == "message"
        ingest = {r["native_post_type"]: r for r in rows if r.get("stage") == "ingest"}
        assert ingest["notice"]["native_sub_type"] == "poke"
        assert ingest["request"]["native_request_type"] == "friend"
        assert ingest["request"]["native_sub_type"] == "other"
        assert "private-" not in "\n".join(exported.values())
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_persisted_life_state_with_missing_timezone_stays_intact(tmp_path):
    app, _, native, clock = await at_time(tmp_path, 1, 30)
    try:
        message = FinalMessage(identifier="before-timezone-change")
        await app.on_message(message)
        context = Context.from_dict(message.extra["livingemotion:context"])
        before = await app.night_snapshot(context)
        native["timezone"] = ""
        native["night_schedule_enabled"] = False
        await app.refresh_config()
        clock[0] += 60
        assert await app.night_snapshot(context) == before
        assert await app.advance_scope(context) == before
        assert (await app.reply_started(context, "pending-timezone"))["allowed"] is False
        assert (await app.reply_submitted(context, "pending-timezone"))["allowed"] is False
        assert (await app.availability(context)).block_chat is True
        result = await app.api.ingest_event({
            "event_id": "archive-only", "producer": "synthetic", "event_type": "message",
            "context": message.extra["livingemotion:context"], "actor_role": "human",
            "actor_id": context.account_id, "occurred_at": clock[0], "source_id": "archive-only",
            "body": "synthetic pending-timezone message",
        })
        assert result["domain_applied"] is True
        unchanged = await app.night_snapshot(context)
        assert unchanged.energy_units == before.energy_units
        assert unchanged.wake_replies_used == before.wake_replies_used
        native["timezone"] = "UTC"
        native["night_schedule_enabled"] = True
        await app.refresh_config()
        assert (await app.night_snapshot(context)).energy_units is not None
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_last_admitted_round_finishes_and_submission_window_starts_once(tmp_path):
    app, host, _, clock = await at_time(tmp_path, 1, 30)
    try:
        message = FinalMessage(identifier="wake")
        await seed_nap(app, message)
        await app.on_message(message)
        context = Context.from_dict(message.extra["livingemotion:context"])
        before = await app.night_snapshot(context)
        assert before.wake_session and before.first_reply_submitted_at is None
        request = SimpleNamespace(extra_user_content_parts=[])
        await request_to_model(app, message, request)
        started = await app.night_snapshot(context)
        assert started.wake_replies_used == 1 and started.display_state.value == "groggy"
        assert started.first_reply_submitted_at is None
        # LivingHello's v1 availability check preserves only this real admitted event.
        assert not (await app.api.get_availability(context))["block_chat"]
        assert await app.on_reply_submitted(message) is True
        submitted = await app.night_snapshot(context)
        assert submitted.wake_session is None
        assert submitted.first_reply_submitted_at is None
        assert submitted.wake_window_deadline is None
        assert submitted.energy == pytest.approx(before.energy - app.config.energy_reply_cost)
        assert submitted.display_state.value == "awake"
        assert await app.on_reply_submitted(message) is True
        assert (await app.night_snapshot(context)).energy == submitted.energy
        events = await app.store.energy_history(context, category="reply")
        assert events["total"] == 1
        assert host.sends == 0
        # A new source cannot use the old generation's final-round admission.
        newer = FinalMessage(identifier="new")
        await app.on_message(newer)
        await request_to_model(app, newer)
        # A valid new chat wake may establish a new bounded window, never renew the old one.
        assert (await app.night_snapshot(context)).wake_replies_used <= 1
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["GENERAL_RESULT", "AGENT_RUNNER_ERROR"])
async def test_native_generation_error_keeps_round_without_reply_energy_or_window(tmp_path, kind):
    app, _, _, _ = await at_time(tmp_path, 1, 30)
    try:
        message = FinalMessage(identifier="native-generation-failed")
        await seed_nap(app, message)
        await app.on_message(message)
        context = Context.from_dict(message.extra["livingemotion:context"])
        await request_to_model(app, message)
        started = await app.night_snapshot(context)
        assert started.wake_replies_used == 1
        message.result.result_content_type = SimpleNamespace(name=kind)
        assert await app.on_reply_submitted(message) is None
        after = await app.night_snapshot(context)
        assert after.energy == started.energy
        # 唯一一轮生成失败也结束唤醒窗，保留失败尝试记录而不阻断后续普通聊天。
        assert after.wake_replies_used == 0 and after.wake_session is None
        assert after.display_state.value == "awake"
        assert after.first_reply_submitted_at is None and after.wake_window_deadline is None
        assert (await app.store.energy_history(context, category="reply"))["total"] == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_deep_sleep_preempts_already_started_reply(tmp_path):
    app, host, _, clock = await at_time(tmp_path, 1, 30)
    try:
        message = FinalMessage(identifier="wake")
        await app.on_message(message)
        await request_to_model(app, message)
        clock[0] = datetime(2026, 11, 6, 3, tzinfo=timezone.utc).timestamp()
        assert await app.on_reply_submitted(message) is False
        context = Context.from_dict(message.extra["livingemotion:context"])
        assert (await app.night_snapshot(context)).display_state.value == "deep_sleep"
        events = await app.store.energy_history(context, category="reply")
        assert events["total"] == 0 and host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("new_count", [0, 1, 2])
async def test_private_new_messages_never_cancel_inflight_reply(tmp_path, new_count):
    app, host, _, clock = await at_time(tmp_path, 12, config={"night_schedule_enabled": False})
    try:
        old = FinalMessage(identifier="old")
        await request_to_model(app, old)
        newer = []
        for index in range(new_count):
            # 超过 LivingHello 旧版 15 秒连发窗口，确认时间差不再驱动丢弃。
            clock[0] += 16
            message = FinalMessage(identifier=f"new-{index}")
            await app.on_message(message)
            await request_to_model(app, message)
            newer.append(message)
        context = Context.from_dict(old.extra["livingemotion:context"])
        # 旧回复照常投递；同一个事件重复回调不会产生第二次投递。
        assert await app.on_reply_submitted(old) is True
        assert await app.on_reply_submitted(old) is True
        # 生成期间进来的每条新消息也按自己的轮次得到回复。
        for message in newer:
            assert await app.on_reply_submitted(message) is True
        assert old.result.chain and all(message.result.chain for message in newer)
        history = await app.store.energy_history(context, category="reply")
        assert history["total"] == 1 + new_count
        assert len(app._host_submissions) == 1 + new_count
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_native_at_required_for_group_chat_wake(tmp_path):
    app, host, _, _ = await at_time(tmp_path, 1, 30, config={"wake_mode": "both"})
    try:
        ordinary = FinalMessage(identifier="ordinary", group="group")
        await seed_nap(app, ordinary)
        await app.on_message(ordinary)
        context = Context.from_dict(ordinary.extra["livingemotion:context"])
        assert (await app.night_snapshot(context)).display_state.value == "nap"
        explicit = FinalMessage(identifier="native-at", group="group")
        At = type("At", (), {})
        at = At()
        at.qq = explicit.get_self_id()
        explicit.message_obj.message = [at]
        await app.on_message(explicit)
        assert (await app.night_snapshot(context)).display_state.value == "groggy"
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("content_type,allowed", [
    ("STREAMING_FINISH", None), ("STREAMING_RESULT", False), ("AGENT_RUNNER_ERROR", None),
])
async def test_stream_notifications_never_count_as_native_submission(tmp_path, content_type, allowed):
    app, host, _, _ = await at_time(tmp_path, 12, config={"night_schedule_enabled": False})
    try:
        message = FinalMessage(identifier="stream-notification")
        await request_to_model(app, message)
        message.result.result_content_type = SimpleNamespace(name=content_type)
        assert await app.on_reply_submitted(message) is allowed
        context = Context.from_dict(message.extra["livingemotion:context"])
        assert (await app.store.energy_history(context, category="reply"))["total"] == 0
        assert host.sends == 0
    finally:
        await app.terminate()
