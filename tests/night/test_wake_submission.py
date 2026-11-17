"""在途回复跨正常睡醒边界：虚拟时间、真实数据库，无模型与平台调用。"""

from dataclasses import replace

import pytest

from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import NightState, SleepState, StateWrite, to_dict
from astrbot_plugin_livingemotion.storage import SQLiteStore
from test_life_state import Harness, human


# 故障请求获准、周期结束和宿主提交的时间，直接保留小数秒边界。
START = 1794795200.049583
WAKE = 1794795442.728494
FINISH = WAKE + 90.23


@pytest.fixture
async def admitted(tmp_path, le_context):
    clock = [START]
    config = Config(
        night_policy_version=2, timezone="UTC", night_schedule_enabled=False,
        nap_enabled=False, persona_shared_state=True, wake_reply_limit=3,
        wake_window_minutes=10, energy_fatigue_per_minute=0,
        energy_recovery_per_minute=0,
        energy_reply_cost=4,
    )
    store = SQLiteStore(tmp_path / "wake.sqlite", config=config, clock=lambda: clock[0])
    await store.open()
    try:
        app = Harness(store, config)
        await app.initialize_state_scope(le_context)
        state = NightState(
            policy_version=2, energy=99, energy_units=990, updated_at=START,
            cycle_id="incident-cycle", cycle_kind="nap", cycle_started_at=START - 600,
            wake_at=WAKE, base_wake_at=WAKE,
            display_state=SleepState.NAP,
        )
        record = await store.get_state(le_context, "night")
        assert (await store.write_states(le_context, await store.get_generation(le_context), (
            StateWrite("night", to_dict(state), record.version if record else 0,
                       owner=store.state_owner(le_context)),
        ))).accepted
        assert (await app.wake_attempt(le_context, human(le_context, START)))["allowed"]
        started = await app.reply_started(le_context, "inflight")
        assert started["allowed"] and started["night"].wake_session
        yield app, store, clock, le_context, started["ticket"]
    finally:
        await store.close()


async def mutate_state(store, context, **changes):
    record = await store.get_state(context, "night")
    state = replace(store._night_value(record.value), **changes)
    assert (await store.write_states(context, await store.get_generation(context), (
        StateWrite("night", {**to_dict(state), "_runtime": record.value.get("_runtime", {})},
                   record.version, owner=record.owner),
    ))).accepted


@pytest.mark.parametrize("finish", [WAKE - 0.001, WAKE, WAKE + 0.001, FINISH])
@pytest.mark.parametrize("tick_first", [False, True])
async def test_admitted_reply_finishes_across_normal_wake(admitted, finish, tick_first):
    app, store, clock, context, ticket = admitted
    clock[0] = finish
    if tick_first:
        state = await app.advance_scope(context)
        assert state.cycle_id == "incident-cycle"
        if finish >= WAKE:
            assert state.wake_session is None
    submitted = await app.reply_submitted(context, "inflight", ticket=ticket)
    assert submitted["allowed"] is True
    assert submitted["night"].energy == 95
    if finish >= WAKE:
        assert submitted["night"].wake_window_deadline is None
        assert submitted["night"].wake_replies_used == 0
    again = await app.reply_submitted(context, "inflight", ticket=ticket)
    assert again["allowed"] is False and again["status"] == "duplicate"
    history = await store.energy_history(context, category="reply")
    assert history["total"] == 1 and history["items"][0]["delta"] == -4
    row = await store._run(lambda db: dict(db.execute(
        "SELECT status,submitted_at FROM reply_attempts WHERE reply_id='inflight'",
    ).fetchone()))
    assert row == {"status": "submitted", "submitted_at": finish}


@pytest.mark.parametrize("case", [
    "window", "deep", "replaced_session", "early_clear", "missing_wake",
    "changed_cycle", "ticket", "generation",
])
async def test_wake_completion_does_not_bypass_rejection(admitted, case):
    app, store, clock, context, ticket = admitted
    if case == "window":
        # 保持线上十分钟配置，延后正常睡醒，单独验证窗口到期仍拦截。
        await mutate_state(store, context, wake_at=START + 1200)
        first = await app.reply_started(context, "first")
        assert (await app.reply_submitted(context, "first", ticket=first["ticket"]))["allowed"]
        clock[0] += 600
    elif case == "deep":
        await mutate_state(store, context, deep_sleep_at=START + 1)
        clock[0] += 2
    elif case == "replaced_session":
        await mutate_state(store, context, wake_session="replacement")
    elif case == "early_clear":
        await mutate_state(store, context, wake_session=None)
    elif case == "missing_wake":
        await mutate_state(store, context, wake_session=None, wake_at=None)
        clock[0] = FINISH
    elif case == "changed_cycle":
        await mutate_state(store, context, wake_session=None, cycle_id="different-cycle")
        clock[0] = FINISH
    elif case == "ticket":
        clock[0] = FINISH
        ticket = {**ticket, "started_at": START - 1}
    elif case == "generation":
        clock[0] = FINISH
        await store.clear_scope(context, 0)
    before = (await store.energy_history(context, category="reply"))["total"]
    result = await app.reply_submitted(context, "inflight", ticket=ticket)
    assert result["allowed"] is False
    if case not in ("ticket", "generation"):
        assert result["reason_code"] == "reply_submission_expired"
        assert await store.reply_ticket(context, "inflight") is None
    assert (await store.energy_history(context, category="reply"))["total"] == before
