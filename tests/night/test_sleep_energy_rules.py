"""Sleep-rule boundaries use virtual time and real SQLite, without providers."""

from dataclasses import replace
from random import Random

import pytest

from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import NightState, StateWrite, to_dict
from astrbot_plugin_livingemotion.domain.night import LifePolicy, advance_life
from astrbot_plugin_livingemotion.runtime.projector import Projector
from astrbot_plugin_livingemotion.storage import SQLiteStore
from test_life_state import Harness, at, human


@pytest.fixture
async def sleep_app(tmp_path, le_context):
    clock = [at("2026-11-16T14:00:00")]
    config = Config(
        night_policy_version=2, timezone="UTC", night_schedule_enabled=True,
        persona_shared_state=True, fatigue_start="00:00", fatigue_end="08:00",
        deep_sleep_at="02:30", wake_at="08:00", nap_start="12:00", nap_end="13:00",
        lie_in_min_minutes=10, lie_in_max_minutes=10,
        wake_reply_limit=10, energy_reply_cost=2, energy_fatigue_per_minute=0.5,
        energy_recovery_per_minute=1,
    )
    store = SQLiteStore(tmp_path / "sleep.sqlite", config=config, clock=lambda: clock[0])
    await store.open()
    app = Harness(store, config)
    await app.initialize_state_scope(le_context)
    await app.night_snapshot(le_context)
    try:
        yield app, store, clock, le_context
    finally:
        await app.store.close()


async def set_energy(app, context, value, **changes):
    record = await app.store.get_state(context, "night")
    state = replace(
        app.store._night_value(record.value), energy=value, energy_units=round(value * 10),
        updated_at=app.store.clock(), quiet_since=app.store.clock(), energy_remainder=0,
        **changes,
    )
    assert (await app.store.write_states(
        context, await app.store.get_generation(context),
        (StateWrite("night", {**to_dict(state), "_runtime": record.value.get("_runtime", {})},
                    record.version, owner=record.owner),),
    )).accepted


@pytest.mark.parametrize("value,display", [(0, "drowsy"), (0.1, "groggy"),
                                         (20, "groggy"), (20.1, "awake"), (100, "awake")])
async def test_daytime_never_recharges_unsleeping_states(sleep_app, value, display):
    app, _, clock, context = sleep_app
    await set_energy(app, context, value)
    clock[0] += 1799
    state = await app.night_snapshot(context)
    assert state.energy == value and state.display_state.value == display


@pytest.mark.parametrize("value", [0, 0.1, 20])
async def test_both_low_energy_states_sleep_at_exactly_thirty_quiet_minutes(sleep_app, value):
    app, _, clock, context = sleep_app
    await set_energy(app, context, value)
    start = clock[0]
    clock[0] = start + 1799
    assert (await app.night_snapshot(context)).cycle_kind != "recovery"
    clock[0] = start + 1800
    state = await app.night_snapshot(context)
    assert state.cycle_kind == "recovery" and state.display_state.value == "deep_sleep"
    assert state.energy == value
    assert state.sleep_started_at == start + 1800
    assert state.base_wake_at == at("2026-11-17T08:00:00")
    assert state.wake_at == at("2026-11-17T08:10:00")


async def test_recovery_to_nap_requires_strictly_more_than_twenty(sleep_app):
    app, _, clock, context = sleep_app
    await set_energy(app, context, 0)
    clock[0] += 1800
    start = clock[0]
    await app.night_snapshot(context)
    clock[0] = start + 1200
    exact = await app.night_snapshot(context)
    assert exact.energy == 20 and exact.display_state.value == "deep_sleep"
    clock[0] += 6
    above = await app.night_snapshot(context)
    assert above.energy == 20.1 and above.display_state.value == "nap"
    assert above.wake_at == exact.wake_at and above.lie_in_minutes == 10


async def test_full_nap_exits_and_does_not_recharge_again_after_reply(sleep_app):
    app, store, clock, context = sleep_app
    await set_energy(app, context, 0)
    clock[0] += 1800 + 6000
    full = await app.night_snapshot(context)
    assert full.energy == 100 and full.display_state.value == "awake"
    assert full.cycle_kind == "awake"
    started = await app.reply_started(context, "after-rest")
    assert (await app.reply_submitted(context, "after-rest", ticket=started["ticket"]))["allowed"]
    clock[0] += 600
    assert (await app.night_snapshot(context)).energy == 98
    assert (await store.energy_history(context, category="reply"))["total"] == 1


async def test_fixed_sleep_overrides_supplementary_nap_and_uses_same_lie_in(sleep_app):
    app, _, clock, context = sleep_app
    app.config = replace(app.config, energy_recovery_per_minute=0.1)
    await set_energy(app, context, 20)
    clock[0] += 1800 + 60
    nap = await app.night_snapshot(context)
    assert nap.display_state.value == "nap"
    draws = app.draw_count
    clock[0] = at("2026-11-17T02:30:00")
    deep = await app.night_snapshot(context)
    assert deep.display_state.value == "deep_sleep"
    assert deep.wake_at == at("2026-11-17T08:10:00")
    assert app.draw_count == draws


async def test_fixed_sleep_completes_at_actual_wake_even_with_zero_recovery(sleep_app):
    app, _, clock, context = sleep_app
    app.config = replace(app.config, energy_recovery_per_minute=0)
    clock[0] = at("2026-11-17T03:00:00")
    await app.night_snapshot(context)
    await set_energy(app, context, 5)
    clock[0] = at("2026-11-17T08:09:59")
    assert (await app.night_snapshot(context)).display_state.value == "deep_sleep"
    clock[0] += 1
    state = await app.night_snapshot(context)
    assert state.energy == 100 and state.display_state.value == "awake"
    clock[0] += 60
    started = await app.reply_started(context, "morning")
    await app.reply_submitted(context, "morning", ticket=started["ticket"])
    clock[0] += 60
    assert (await app.night_snapshot(context)).energy == 98


async def test_midnight_to_fixed_sleep_spends_seventy_five_points(sleep_app):
    app, _, clock, context = sleep_app
    clock[0] = at("2026-11-17T00:00:00")
    await app.night_snapshot(context)
    await set_energy(app, context, 100)
    clock[0] = at("2026-11-17T02:29:59")
    before = await app.night_snapshot(context)
    assert before.display_state.value == "awake" and before.energy == 25.1
    clock[0] += 1
    deep = await app.night_snapshot(context)
    assert deep.energy == 25 and deep.display_state.value == "deep_sleep"
    clock[0] += 60
    assert (await app.night_snapshot(context)).energy == 26


async def test_manual_supplement_uses_next_wake_not_eight_hours(sleep_app):
    app, _, clock, context = sleep_app
    await set_energy(app, context, 0)
    state = await app.advance_scope(context, action="night.sleep")
    assert state.energy == 0
    assert state.wake_at == at("2026-11-17T08:10:00")
    assert state.cycle_kind == "recovery"


async def test_existing_lie_in_after_base_wake_is_reused(sleep_app):
    app, _, clock, context = sleep_app
    clock[0] = at("2026-11-17T08:05:00")
    await app.night_snapshot(context)
    await set_energy(app, context, 0)
    state = await app.advance_scope(context, action="night.sleep")
    assert state.wake_at == at("2026-11-17T08:10:00")
    assert state.base_wake_at == at("2026-11-17T08:00:00")


async def test_plain_human_message_resets_shared_silence_without_energy_charge(sleep_app):
    app, store, clock, context = sleep_app
    await set_energy(app, context, 20)
    start = clock[0]
    clock[0] += 1200
    other = replace(context, scene_kind="group", scene_id="other-group", account_id="other-human")
    await app.initialize_state_scope(other)
    event = human(other, clock[0], "ordinary")
    projection = await Projector(store, lambda: app.config)(event)
    assert (await store.commit_event(event, projection.generation, projection.writes,
                                    projection.contributions, traces=projection.traces)).accepted
    clock[0] = start + 1800
    state = await app.night_snapshot(context)
    assert state.energy == 20 and state.display_state.value == "groggy"
    clock[0] = start + 3000
    assert (await app.night_snapshot(context)).display_state.value == "deep_sleep"
    assert (await store.energy_history(context, category="reply"))["total"] == 0


async def test_restart_preserves_quiet_timer_and_recovery_deadline(sleep_app):
    app, store, clock, context = sleep_app
    await set_energy(app, context, 0)
    start = clock[0]
    clock[0] += 1200
    await app.night_snapshot(context)
    await store.close()
    reopened = SQLiteStore(store.path, config=app.config, clock=lambda: clock[0])
    await reopened.open()
    app.store = reopened
    clock[0] = start + 1800
    state = await app.night_snapshot(context)
    assert state.sleep_started_at == start + 1800
    target, draws = state.wake_at, app.draw_count
    for _ in range(3):
        clock[0] += 60
        assert (await app.night_snapshot(context)).wake_at == target
    assert app.draw_count == draws


async def test_read_only_refresh_does_not_write_or_draw(sleep_app):
    app, store, clock, context = sleep_app
    await set_energy(app, context, 0)
    before = await store.get_state(context, "night")
    draws = app.draw_count
    clock[0] += 3600
    for _ in range(5):
        await app.night_display_snapshot(context)
    assert await store.get_state(context, "night") == before
    assert app.draw_count == draws


@pytest.mark.parametrize("end_energy,expected", [(60, "awake"), (20, "groggy"),
                                                (15, "groggy"), (0, "drowsy")])
async def test_ten_wake_rounds_end_by_energy_and_last_reply_finishes(sleep_app, end_energy, expected):
    app, _, clock, context = sleep_app
    clock[0] = at("2026-11-16T12:05:00")
    await app.night_snapshot(context)
    await set_energy(app, context, min(99, end_energy + 20), cycle_kind="nap",
                     cycle_started_at=clock[0] - 300, wake_at=at("2026-11-16T13:00:00"))
    assert (await app.wake_attempt(context, human(context, clock[0])))["allowed"]
    for number in range(10):
        started = await app.reply_started(context, f"round-{number}")
        assert started["allowed"]
        submitted = await app.reply_submitted(context, f"round-{number}", ticket=started["ticket"])
        assert submitted["allowed"]
        if number < 9:
            assert submitted["night"].display_state.value == "groggy"
    state = await app.night_snapshot(context)
    assert state.energy == end_energy and state.display_state.value == expected
    assert state.wake_session is None
    assert (await app.reply_started(context, "ordinary-after-window"))["allowed"]


async def test_last_failed_attempt_does_not_leave_wake_quota_stuck(sleep_app):
    app, store, clock, context = sleep_app
    app.config = replace(app.config, wake_reply_limit=1)
    clock[0] = at("2026-11-16T12:05:00")
    await app.night_snapshot(context)
    await set_energy(app, context, 60, cycle_kind="nap",
                     cycle_started_at=clock[0] - 300, wake_at=at("2026-11-16T13:00:00"))
    assert (await app.wake_attempt(context, human(context, clock[0])))["allowed"]
    assert (await app.reply_started(context, "failed"))["allowed"]
    assert await store.reply_failed(context, "failed")
    state = await app.night_snapshot(context)
    assert state.energy == 60 and state.wake_session is None
    assert state.display_state.value == "awake"
    assert (await app.reply_started(context, "ordinary"))["allowed"]


async def test_parallel_failure_preserves_other_admitted_reply(sleep_app):
    app, store, clock, context = sleep_app
    app.config = replace(app.config, wake_reply_limit=2)
    clock[0] = at("2026-11-16T12:05:00")
    await app.night_snapshot(context)
    await set_energy(app, context, 60, cycle_kind="nap",
                     cycle_started_at=clock[0] - 300, wake_at=at("2026-11-16T13:00:00"))
    assert (await app.wake_attempt(context, human(context, clock[0])))["allowed"]
    first = await app.reply_started(context, "inflight")
    assert (await app.reply_started(context, "failed-parallel"))["allowed"]
    assert await store.reply_failed(context, "failed-parallel")
    assert (await app.night_snapshot(context)).wake_session
    final = await app.reply_submitted(context, "inflight", ticket=first["ticket"])
    assert final["allowed"] and final["night"].wake_session is None
    assert final["night"].energy == 58


async def test_restart_after_last_admission_finishes_cancelled_wake_window(sleep_app):
    app, store, clock, context = sleep_app
    app.config = replace(app.config, wake_reply_limit=1)
    clock[0] = at("2026-11-16T12:05:00")
    await app.night_snapshot(context)
    await set_energy(app, context, 60, cycle_kind="nap",
                     cycle_started_at=clock[0] - 300, wake_at=at("2026-11-16T13:00:00"))
    assert (await app.wake_attempt(context, human(context, clock[0])))["allowed"]
    started = await app.reply_started(context, "interrupted-last")
    assert started["allowed"]
    await store.recover_inflight()
    state = await app.night_snapshot(context)
    assert state.energy == 60 and state.wake_session is None
    assert state.display_state.value == "awake"
    assert not (await app.reply_submitted(context, "interrupted-last",
                                         ticket=started["ticket"]))["allowed"]
    assert (await app.reply_started(context, "after-restart"))["allowed"]


@pytest.mark.parametrize("days", [1, 3, 30])
async def test_offline_jump_past_fixed_wake_does_not_skip_full_recovery(sleep_app, days):
    from datetime import datetime, timedelta, timezone
    app, _, clock, context = sleep_app
    app.config = replace(app.config, energy_fatigue_per_minute=0,
                         energy_recovery_per_minute=0)
    await set_energy(app, context, 60)
    clock[0] = (datetime(2026, 11, 16, 9, tzinfo=timezone.utc)
                + timedelta(days=days)).timestamp()
    state = await app.night_snapshot(context)
    assert state.energy == 100 and state.display_state.value == "awake"
    assert state.wake_at == clock[0] - 50 * 60
    clock[0] += 60
    assert (await app.night_snapshot(context)).energy == 100


async def test_manual_wake_during_lie_in_stays_awake_until_actual_wake(sleep_app):
    app, _, clock, context = sleep_app
    clock[0] = at("2026-11-17T08:05:00")
    await app.night_snapshot(context)
    await set_energy(app, context, 40)
    await app.advance_scope(context, action="night.wake")
    clock[0] += 60
    state = await app.night_snapshot(context)
    assert state.display_state.value == "awake" and state.energy == 40
    clock[0] = at("2026-11-17T08:11:00")
    assert (await app.night_snapshot(context)).energy == 40


async def test_sleep_disabled_never_recovers_or_draws_supplement_deadline(sleep_app):
    app, _, clock, context = sleep_app
    app.config = replace(app.config, allow_sleep=False)
    await set_energy(app, context, 15)
    draws = app.draw_count
    clock[0] += 7200
    state = await app.night_snapshot(context)
    assert state.energy == 15 and state.display_state.value == "groggy"
    assert app.draw_count == draws
    assert (await app.availability(context)).available


def test_partitioned_replay_matches_direct_settlement():
    initial = NightState(policy_version=2, energy=100, energy_units=1000, updated_at=1000)
    policy = LifePolicy()
    windows = ((1000, 5000),)
    direct, _ = advance_life(initial, now=10000, policy=policy, fatigue_windows=windows)
    random = Random(20261116)
    stepped = initial
    for timestamp in sorted(random.sample(range(1001, 10000), 120)) + [10000]:
        stepped, _ = advance_life(stepped, now=timestamp, policy=policy, fatigue_windows=windows)
    assert stepped == direct


def test_clock_rollback_does_not_change_energy_or_quiet_timer():
    state = NightState(policy_version=2, energy=20, energy_units=200, updated_at=1000,
                       quiet_since=500)
    result, events = advance_life(state, now=999)
    assert result.energy == 20 and result.quiet_since == 500 and result.updated_at == 1000
    assert events == ()


def test_schema_defaults_match_runtime_defaults_and_keep_explicit_settings():
    import json
    from pathlib import Path
    schema = json.loads((Path(__file__).parents[2] / "_conf_schema.json").read_text(encoding="utf-8-sig"))
    config = Config(timezone="UTC")
    policy = LifePolicy()
    for key in ("energy_reply_cost", "energy_fatigue_per_minute", "energy_recovery_per_minute",
                "wake_reply_limit"):
        assert schema[key]["default"] == getattr(config, key)
    assert policy.fatigue_units_per_minute == 5
    assert Config.from_mapping({"timezone": "UTC", "energy_fatigue_per_minute": 0.7}).energy_fatigue_per_minute == 0.7
