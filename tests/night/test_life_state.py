"""Deterministic P2 tests: real persistence, no host/provider/network."""

from dataclasses import replace
from datetime import datetime, timezone
import sqlite3

import pytest

from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import Event, NightState, StateWrite, to_dict
from astrbot_plugin_livingemotion.domain.night import advance_life, LifePolicy
from astrbot_plugin_livingemotion.runtime.night import NightRuntime
from astrbot_plugin_livingemotion.storage import SQLiteStore


def at(value):
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp()


class Harness(NightRuntime):
    def __init__(self, store, config, draws=None):
        self.store, self.config = store, config
        self.draws = list(draws or [])
        self.draw_count = 0
        self.closed = False

    def effective_mode(self, context=None):
        return "active"

    async def validate_context(self, context, generation=None):
        return generation is None or await self.store.get_generation(context) == generation

    def night_random(self, low, high):
        self.draw_count += 1
        value = self.draws.pop(0) if self.draws else low
        assert low <= value <= high
        return value


@pytest.fixture
async def life(tmp_path, le_context):
    clock = [at("2026-11-06T00:30:00")]
    config = Config(
        night_policy_version=2, timezone="UTC", night_schedule_enabled=True,
        persona_shared_state=True, lie_in_min_minutes=0, lie_in_max_minutes=90,
        energy_fatigue_per_minute=0, energy_recovery_per_minute=0,
    )
    store = SQLiteStore(tmp_path / "life.sqlite", config=config, clock=lambda: clock[0])
    await store.open()
    app = Harness(store, config)
    await app.initialize_state_scope(le_context)
    yield app, store, clock, le_context
    await store.close()


async def energy(store, context, value):
    record = await store.get_state(context, "night")
    state = replace(store._night_value(record.value), energy=value, energy_units=int(value * 10)
                    if record.value.get("policy_version") == 2 else None)
    result = await store.write_states(context, await store.get_generation(context), (
        StateWrite("night", to_dict(state), record.version, owner=record.owner),
    ))
    assert result.accepted


def human(context, now, number="1", signals=()):
    return Event("wake-" + number, "test", "message", context, "human", now, "source-" + number,
                 actor_id=context.account_id, signals=signals)


async def test_five_states_cross_midnight_and_persisted_lie_in(life):
    app, store, clock, context = life
    app.draws = [60]
    state = await app.night_snapshot(context)
    assert state.display_state.value == "groggy"
    assert state.drowsy_at == at("2026-11-06T01:00:00")
    assert state.deep_sleep_at == at("2026-11-06T02:30:00")
    assert state.wake_at == at("2026-11-06T09:00:00")
    assert app.draw_count == 1
    for value, display in (
        ("2026-11-06T01:00:00", "drowsy"),
        ("2026-11-06T02:30:00", "deep_sleep"),
        ("2026-11-06T07:30:00", "deep_sleep"),
        ("2026-11-06T08:59:59", "deep_sleep"),
        ("2026-11-06T09:00:00", "awake"),
        ("2026-11-06T13:00:00", "nap"),
        ("2026-11-06T14:30:00", "awake"),
    ):
        clock[0] = at(value)
        state = await app.night_snapshot(context)
        assert state.display_state.value == display
    assert app.draw_count == 1


async def test_display_refresh_never_writes_or_redraws_night(life):
    from astrbot_plugin_livingemotion.runtime.night import NIGHT_DISPLAY_ONLY
    app, store, clock, context = life
    await app.night_snapshot(context)
    before = await store.get_state(context, "night")
    clock[0] += 1800
    token = NIGHT_DISPLAY_ONLY.set(True)
    try:
        for _ in range(5):
            night = await app.night_snapshot(context)
            assert night.updated_at == clock[0]
            await app.availability(context)
    finally:
        NIGHT_DISPLAY_ONLY.reset(token)
    assert await store.get_state(context, "night") == before
    assert app.draw_count == 1


async def test_scheduler_requests_only_yesterday_and_today(life):
    app, store, clock, context = life
    app.config = replace(app.config, diary_enabled=True, diary_backfill_yesterday=True)
    app._contexts, app._actions = {context.scope_key: context}, set()
    app.native_config = to_dict(app.config)
    app._last_cleanup = clock[0]
    requested = []
    async def queue(source, kind, **options):
        requested.append((kind, options.get("day")))
        return {"status": "queued", "reason_code": ""}
    app.queue_experience = queue
    for _ in range(2):
        await app.tick()
    # 候选预筛与生成共用显式目标日期；仍只补昨天和请求今天。
    assert requested == [("diary", "2026-11-05"), ("diary", "2026-11-06")] * 2


async def test_restart_does_not_redraw_and_full_energy_cannot_exit_deep(life):
    app, store, clock, context = life
    app.draws = [90]
    await app.night_snapshot(context)
    path, config = store.path, store.config
    await store.close()
    reopened = SQLiteStore(path, config=config, clock=lambda: clock[0])
    await reopened.open()
    try:
        app = Harness(reopened, config, [17])
        clock[0] = at("2026-11-06T07:45:00")
        state = await app.night_snapshot(context)
        assert state.energy == 100
        assert state.display_state.value == "deep_sleep"
        assert state.wake_at == at("2026-11-06T09:30:00")
        assert app.draw_count == 0
    finally:
        await reopened.close()


async def test_low_energy_two_dice_then_increment_and_duplicate(life):
    app, store, clock, context = life
    clock[0] = at("2026-11-06T01:30:00")
    await app.night_snapshot(context)
    await energy(store, context, 9.9)
    app.draws = [0, 0]
    first = human(context, clock[0])
    assert not (await app.wake_attempt(context, first))["allowed"]
    duplicate = await app.wake_attempt(context, first)
    assert duplicate["status"] == "duplicate"
    assert (await store.get_state(context, "night")).value["wake_score"] == 0
    for value in range(1, 10):
        result = await app.wake_attempt(context, human(context, clock[0], str(value + 1)))
        assert result["allowed"] == (value > 8)
    state = result["night"]
    assert state.display_state.value == "groggy" and state.energy == 9.9
    assert state.wake_score is None and state.wake_failures == 0
    assert app.draw_count == 3  # one lie-in draw and exactly two dice


async def test_first_two_dice_sum_can_wake_immediately(life):
    app, store, clock, context = life
    clock[0] = at("2026-11-06T01:30:00")
    await app.night_snapshot(context)
    await energy(store, context, 1)
    app.draws = [4, 5]
    assert (await app.wake_attempt(context, human(context, clock[0])))["allowed"]


async def test_deep_sleep_never_rolls_or_accumulates_and_admin_can_wake(life):
    app, store, clock, context = life
    clock[0] = at("2026-11-06T03:00:00")
    await app.night_snapshot(context)
    await energy(store, context, 2)
    draws = app.draw_count
    for number in range(12):
        result = await app.wake_attempt(context, human(context, clock[0], str(number)))
        assert not result["allowed"]
    state = await app.night_snapshot(context)
    assert state.wake_score is None and state.wake_failures == 0
    assert app.draw_count == draws
    assert (await app.advance_scope(context, action="night.wake")).display_state.value == "awake"
    assert (await app.night_snapshot(context)).display_state.value == "awake"


@pytest.mark.parametrize("mode,kind,mentioned,allowed", [
    ("chat", "private", False, True), ("chat", "group", True, False),
    ("both", "group", False, False), ("both", "group", True, True),
    ("never", "private", False, False),
])
async def test_wake_eligibility(life, mode, kind, mentioned, allowed):
    app, store, clock, context = life
    app.config = replace(app.config, wake_mode=mode)
    context = replace(context, scene_kind=kind)
    await app.initialize_state_scope(context)
    clock[0] = at("2026-11-06T01:30:00")
    event = human(context, clock[0], signals=("native_bot_mention",) if mentioned else ())
    assert (await app.wake_attempt(context, event))["allowed"] is allowed


async def test_window_starts_only_first_submission_last_round_can_finish(life):
    app, store, clock, context = life
    clock[0] = at("2026-11-06T01:30:00")
    # 只有精力低于舒适线（80）时被叫醒，才进入唤醒窗口并计轮次。
    await app.night_snapshot(context)
    await energy(store, context, 50)
    app.draws = [9, 9]
    await app.wake_attempt(context, human(context, clock[0]))
    starts = []
    for number in range(3):
        result = await app.reply_started(context, f"reply-{number}")
        assert result["allowed"]
        starts.append(result)
        assert result["night"].energy == 50
        assert result["night"].wake_window_deadline is None
    assert not (await app.reply_started(context, "fourth"))["allowed"]
    first = await app.reply_submitted(context, "reply-0", ticket=starts[0]["ticket"])
    assert first["allowed"] and first["night"].energy == 46
    deadline = first["night"].wake_window_deadline
    clock[0] += 30
    last = await app.reply_submitted(context, "reply-2", ticket=starts[2]["ticket"])
    assert last["allowed"] and last["night"].energy == 42
    assert last["night"].wake_window_deadline == deadline
    assert not (await app.reply_submitted(context, "reply-2", ticket=starts[2]["ticket"]))["allowed"]
    assert (await store.get_state(context, "night")).value["energy"] == 42


async def test_failed_generation_counts_but_not_energy_or_window(life):
    app, store, clock, context = life
    clock[0] = at("2026-11-06T01:30:00")
    await app.night_snapshot(context)
    await energy(store, context, 50)
    app.draws = [9, 9]
    await app.wake_attempt(context, human(context, clock[0]))
    started = await app.reply_started(context, "failure")
    assert started["allowed"]
    assert await store.reply_failed(context, "failure")
    state = await app.night_snapshot(context)
    assert state.wake_replies_used == 1 and state.energy == 50
    assert state.first_reply_submitted_at is None
    assert not (await app.reply_submitted(context, "failure", ticket=started["ticket"]))["allowed"]


@pytest.mark.parametrize("expired", ["window", "deep"])
async def test_submission_rechecks_window_or_deep(life, expired):
    app, store, clock, context = life
    clock[0] = at("2026-11-06T01:30:00")
    await app.night_snapshot(context)
    await energy(store, context, 50)
    app.draws = [9, 9]
    await app.wake_attempt(context, human(context, clock[0]))
    first = await app.reply_started(context, "first")
    pending = await app.reply_started(context, "pending")
    assert (await app.reply_submitted(context, "first", ticket=first["ticket"]))["allowed"]
    clock[0] = clock[0] + 600 if expired == "window" else at("2026-11-06T02:30:00")
    assert not (await app.reply_submitted(context, "pending", ticket=pending["ticket"]))["allowed"]


async def test_allow_sleep_off_never_blocks_and_does_not_use_exempt(life):
    app, store, clock, context = life
    app.config = replace(app.config, allow_sleep=False)
    clock[0] = at("2026-11-06T03:30:00")
    availability = await app.availability(context)
    assert availability.available and not availability.block_chat
    assert (await app.reply_started(context, "off"))["allowed"]


def test_fixed_tenth_energy_partition_and_residue():
    state = NightState(updated_at=1000, energy=20)
    policy = LifePolicy(fatigue_units_per_minute=8, recovery_units_per_minute=15)
    direct, _ = advance_life(state, now=1090, fatigue_windows=((0, 2000),), policy=policy)
    stepped = state
    for value in range(1001, 1091):
        stepped, _ = advance_life(stepped, now=value, fatigue_windows=((0, 2000),), policy=policy)
    assert direct.energy_units == stepped.energy_units == 188
    assert direct.energy_remainder == stepped.energy_remainder


async def test_energy_log_and_state_are_one_transaction(life):
    app, store, clock, context = life
    clock[0] = at("2026-11-06T11:00:00")
    started = await app.reply_started(context, "atomic")
    before = await store.get_state(context, "night")
    await store._run(lambda db: db.execute(
        "CREATE TRIGGER fail_energy BEFORE INSERT ON energy_events "
        "BEGIN SELECT RAISE(ABORT,'synthetic log failure'); END"))
    with pytest.raises(sqlite3.IntegrityError):
        await app.reply_submitted(context, "atomic", ticket=started["ticket"])
    assert await store.get_state(context, "night") == before
    assert await store.reply_ticket(context, "atomic") == started["ticket"]
    await store._run(lambda db: db.execute("DROP TRIGGER fail_energy"))
    assert (await app.reply_submitted(context, "atomic", ticket=started["ticket"]))["allowed"]
    history = await store.energy_history(context, category="reply")
    assert history["total"] == 1 and history["items"][0]["delta"] == -4
    assert history["items"][0]["source_id"] == "atomic"
    assert "body" not in history["items"][0]
    assert history["curve"][0]["min"] == 96 and history["curve"][0]["max"] == 100


@pytest.mark.parametrize("operation", ["clear", "switch", "identity"])
async def test_old_reply_ticket_never_survives_boundary(life, operation):
    app, store, clock, context = life
    clock[0] = at("2026-11-06T11:00:00")
    started = await app.reply_started(context, "boundary")
    if operation == "clear":
        await store.clear_scope(context, 0)
    elif operation == "switch":
        await store.switch_state_mode(
            context, shared=False, expected_revision=store.state_owner(context).revision,
            actor_id="operator",
        )
    else:
        context = replace(context, identity_revision="new")
    result = await app.reply_submitted(context, "boundary", ticket=started["ticket"])
    assert not result["allowed"]
    assert (await store.energy_history(context, category="reply"))["total"] == 0


async def test_sleeping_recovery_and_awake_fatigue_do_not_double_charge(life):
    app, store, clock, context = life
    app.config = replace(app.config, energy_fatigue_per_minute=0.8,
                         energy_recovery_per_minute=1.5)
    clock[0] = at("2026-11-06T00:30:00")
    await app.night_snapshot(context)
    await energy(store, context, 50)
    clock[0] += 60
    assert (await app.night_snapshot(context)).energy == 49.2
    clock[0] = at("2026-11-06T01:00:00")
    await app.night_snapshot(context)
    await energy(store, context, 50)
    clock[0] += 60
    assert (await app.night_snapshot(context)).energy == 51.5


def test_configuration_step_and_cross_midnight_validation():
    for update in (
        {"energy_reply_cost": 4.01}, {"energy_reply_cost": float("nan")},
        {"energy_reply_cost": True}, {"lie_in_min_minutes": -1},
        {"lie_in_min_minutes": 90, "lie_in_max_minutes": 0},
        {"deep_sleep_at": "22:00"}, {"nap_start": "13:00", "nap_end": "13:00"},
    ):
        with pytest.raises(ValueError):
            Config(night_policy_version=2, timezone="UTC", **update)
    assert Config(night_policy_version=2, timezone="UTC", energy_reply_cost=0.1)


async def test_night_precedes_overlapping_nap(life):
    app, store, clock, context = life
    app.config = replace(app.config, nap_start="22:00", nap_end="03:00")
    clock[0] = at("2026-11-06T22:30:00")
    assert (await app.night_snapshot(context)).display_state.value == "nap"
    clock[0] = at("2026-11-06T23:30:00")
    assert (await app.night_snapshot(context)).cycle_kind == "night"
    clock[0] = at("2026-11-07T02:30:00")
    assert (await app.night_snapshot(context)).display_state.value == "deep_sleep"


async def test_invalid_low_energy_wake_does_not_draw_dice(life):
    app, store, clock, context = life
    clock[0] = at("2026-11-06T01:30:00")
    await app.night_snapshot(context)
    await energy(store, context, 1)
    app.config = replace(app.config, wake_mode="never")
    draws = app.draw_count
    assert not (await app.wake_attempt(context, human(context, clock[0])))["allowed"]
    assert app.draw_count == draws


async def test_admin_sleep_after_manual_wake_is_effective(life):
    app, store, clock, context = life
    clock[0] = at("2026-11-06T03:00:00")
    await app.advance_scope(context, action="night.wake")
    await app.advance_scope(context, action="night.sleep")
    assert not (await app.availability(context)).available


async def test_restart_cancels_reply_lease_but_keeps_used_round(life):
    app, store, clock, context = life
    clock[0] = at("2026-11-06T01:30:00")
    await app.night_snapshot(context)
    await energy(store, context, 50)
    app.draws = [9, 9]
    await app.wake_attempt(context, human(context, clock[0]))
    started = await app.reply_started(context, "restart")
    await store.recover_inflight()
    assert not (await app.reply_submitted(context, "restart", ticket=started["ticket"]))["allowed"]
    state = await app.night_snapshot(context)
    assert state.wake_replies_used == 1 and state.energy == 50


async def test_rested_energy_skips_wake_window_and_full_wake(life):
    """周期结束后精力在舒适线以上就是自然醒：不需要唤醒窗，也不消耗轮次。"""
    app, store, clock, context = life
    clock[0] = at("2026-11-06T01:30:00")
    await app.night_snapshot(context)
    # 熬到早上醒来，精力 80 以上属于清醒，直接可以参与。
    clock[0] = at("2026-11-06T09:00:00")
    await energy(store, context, 80)
    state = await app.night_snapshot(context)
    assert state.display_state.value == "awake"
    assert (await app.availability(context)).available
    for number in range(5):
        assert (await app.reply_started(context, f"rested-{number}"))["allowed"]
    assert (await app.night_snapshot(context)).display_state.value == "awake"


async def test_low_energy_after_wake_needs_wake_window(life):
    """精力低于舒适线时，回到夜里仍要睡；被叫醒才开唤醒窗并计轮次。"""
    app, store, clock, context = life
    clock[0] = at("2026-11-06T01:30:00")
    await app.night_snapshot(context)
    await energy(store, context, 60)
    app.draws = [9, 9]
    woke = await app.wake_attempt(context, human(context, clock[0]))
    assert woke["allowed"] and woke["reason_code"] == "chat_wake"
    state = await app.night_snapshot(context)
    assert state.wake_session and state.wake_reply_limit == 3


async def test_leftover_wake_session_clears_once_cycle_settled(life):
    """周期已走完时残留的唤醒会话必须清零，否则满精力也会被卡住。"""
    app, store, clock, context = life
    # 白天没有睡眠周期，只有上一轮唤醒会话残留（线上 20:40 的实况）。
    clock[0] = at("2026-11-06T15:00:00")
    await app.night_snapshot(context)
    await energy(store, context, 100)
    record = await store.get_state(context, "night")
    from astrbot_plugin_livingemotion.contracts import StateWrite
    stale = replace(store._night_value(record.value), wake_session="stale",
                    wake_replies_used=3, wake_reply_limit=3, wake_at=None,
                    cycle_id=None, cycle_kind=None, cycle_started_at=None,
                    deep_sleep_at=None, drowsy_at=None, display_state="awake")
    await store.write_states(context, await store.get_generation(context), (
        StateWrite("night", to_dict(stale), record.version, owner=record.owner),
    ))
    state = await app.night_snapshot(context)
    assert state.wake_session is None and state.wake_replies_used == 0
    assert state.display_state.value == "awake"
    assert (await app.availability(context)).available
    assert (await app.reply_started(context, "cleared"))["allowed"]
