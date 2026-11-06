"""Native hook wiring with synthetic host results; no platform sends."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.contracts import Context
from test_application import Message, application


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
        await app.on_message(message)
        context = Context.from_dict(message.extra["livingemotion:context"])
        before = await app.night_snapshot(context)
        assert before.wake_session and before.first_reply_submitted_at is None
        request = SimpleNamespace(extra_user_content_parts=[])
        await app.on_llm_request(message, request)
        started = await app.night_snapshot(context)
        assert started.wake_replies_used == 1 and started.display_state.value == "drowsy"
        assert started.first_reply_submitted_at is None
        # LivingHello's v1 availability check preserves only this real admitted event.
        assert not (await app.api.get_availability(context))["block_chat"]
        assert await app.on_reply_submitted(message) is True
        submitted = await app.night_snapshot(context)
        assert submitted.first_reply_submitted_at == clock[0]
        assert submitted.wake_window_deadline == clock[0] + 600
        assert submitted.energy == pytest.approx(before.energy - 4)
        assert await app.on_reply_submitted(message) is True
        assert (await app.night_snapshot(context)).energy == submitted.energy
        events = await app.store.energy_history(context, category="reply")
        assert events["total"] == 1
        assert host.sends == 0
        # A new source cannot use the old generation's final-round admission.
        newer = FinalMessage(identifier="new")
        await app.on_message(newer)
        await app.on_llm_request(newer, SimpleNamespace(extra_user_content_parts=[]))
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
        await app.on_message(message)
        context = Context.from_dict(message.extra["livingemotion:context"])
        await app.on_llm_request(message, SimpleNamespace(extra_user_content_parts=[]))
        started = await app.night_snapshot(context)
        assert started.wake_replies_used == 1
        message.result.result_content_type = SimpleNamespace(name=kind)
        assert await app.on_reply_submitted(message) is None
        after = await app.night_snapshot(context)
        assert after.energy == started.energy
        assert after.wake_replies_used == 1
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
        await app.on_llm_request(message, SimpleNamespace(extra_user_content_parts=[]))
        clock[0] = datetime(2026, 11, 6, 3, tzinfo=timezone.utc).timestamp()
        assert await app.on_reply_submitted(message) is False
        context = Context.from_dict(message.extra["livingemotion:context"])
        assert (await app.night_snapshot(context)).display_state.value == "deep_sleep"
        events = await app.store.energy_history(context, category="reply")
        assert events["total"] == 0 and host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_new_human_cancels_old_final_result(tmp_path):
    app, host, _, _ = await at_time(tmp_path, 12, config={"night_schedule_enabled": False})
    try:
        old, new = FinalMessage(identifier="old"), FinalMessage(identifier="new")
        await app.on_llm_request(old, SimpleNamespace(extra_user_content_parts=[]))
        await app.on_message(new)
        assert await app.on_reply_submitted(old) is False
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.asyncio
async def test_native_at_required_for_group_chat_wake(tmp_path):
    app, host, _, _ = await at_time(tmp_path, 1, 30, config={"wake_mode": "both"})
    try:
        ordinary = FinalMessage(identifier="ordinary", group="group")
        await app.on_message(ordinary)
        context = Context.from_dict(ordinary.extra["livingemotion:context"])
        assert (await app.night_snapshot(context)).display_state.value == "drowsy"
        explicit = FinalMessage(identifier="native-at", group="group")
        At = type("At", (), {})
        at = At()
        at.qq = explicit.get_self_id()
        explicit.message_obj.message = [at]
        await app.on_message(explicit)
        assert (await app.night_snapshot(context)).display_state.value == "awake"
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
        await app.on_llm_request(message, SimpleNamespace(extra_user_content_parts=[]))
        message.result.result_content_type = SimpleNamespace(name=content_type)
        assert await app.on_reply_submitted(message) is allowed
        context = Context.from_dict(message.extra["livingemotion:context"])
        assert (await app.store.energy_history(context, category="reply"))["total"] == 0
        assert host.sends == 0
    finally:
        await app.terminate()
