"""规则开关用虚拟时间和真实 SQLite 验证，不调用模型或发送端。"""
from dataclasses import replace
from random import Random

import pytest

from astrbot_plugin_livingemotion.contracts import NightState
from astrbot_plugin_livingemotion.domain.night import LifePolicy, advance_life, life_policy
from astrbot_plugin_livingemotion.storage import SQLiteStore
from test_life_state import at
from test_sleep_energy_rules import set_energy, sleep_app


@pytest.mark.parametrize("daytime,follow_wake", [
    (False, False), (False, True), (True, False), (True, True),
])
@pytest.mark.parametrize("energy", [0, 15, 20, 60, 99, 100])
async def test_two_switches_are_independent(sleep_app, daytime, follow_wake, energy):
    app, _, clock, context = sleep_app
    app.config = replace(app.config, energy_daytime_recovery_enabled=daytime,
                         recovery_follow_wake_at=follow_wake)
    await set_energy(app, context, energy)
    clock[0] += 600
    state = await app.night_snapshot(context)
    expected = min(100, energy + 10) if daytime else energy
    assert state.energy == expected
    assert state.cycle_kind != "recovery"


async def test_daytime_switch_never_recharges_awake_fatigue_window(sleep_app):
    app, _, clock, context = sleep_app
    app.config = replace(app.config, energy_daytime_recovery_enabled=True)
    clock[0] = at("2026-11-17T00:00:00")
    await app.night_snapshot(context)
    await set_energy(app, context, 60)
    clock[0] += 600
    state = await app.night_snapshot(context)
    assert state.energy == 55 and state.display_state.value == "awake"


@pytest.mark.parametrize("daytime", [False, True])
async def test_sleep_recovery_works_with_either_daytime_switch(sleep_app, daytime):
    app, _, clock, context = sleep_app
    app.config = replace(app.config, energy_daytime_recovery_enabled=daytime)
    await set_energy(app, context, 30)
    await app.advance_scope(context, action="night.sleep")
    clock[0] += 600
    assert (await app.night_snapshot(context)).energy == 40


@pytest.mark.parametrize("minutes", [1, 120, 1440])
async def test_custom_duration_starts_at_actual_auto_sleep(sleep_app, minutes):
    app, _, clock, context = sleep_app
    app.config = replace(app.config, recovery_follow_wake_at=False,
                         recovery_max_minutes=minutes)
    await set_energy(app, context, 0)
    draws = app.draw_count
    start = clock[0] + 1800
    clock[0] = start
    state = await app.night_snapshot(context)
    assert state.cycle_kind == "recovery"
    assert state.wake_at == start + minutes * 60
    assert state.base_wake_at is None and state.deep_sleep_at is None
    assert app.draw_count == draws


async def test_custom_deadline_exits_at_low_energy_without_immediate_reentry(sleep_app):
    app, _, clock, context = sleep_app
    app.config = replace(app.config, recovery_follow_wake_at=False,
                         recovery_max_minutes=1, energy_recovery_per_minute=0)
    await set_energy(app, context, 0)
    state = await app.advance_scope(context, action="night.sleep")
    deadline = state.wake_at
    clock[0] = deadline - 1
    assert (await app.night_snapshot(context)).display_state.value == "deep_sleep"
    clock[0] = deadline
    state = await app.night_snapshot(context)
    assert state.energy == 0 and state.cycle_kind == "awake"
    assert state.display_state.value == "drowsy" and state.quiet_since == deadline
    clock[0] += 1799
    assert (await app.night_snapshot(context)).cycle_kind == "awake"
    clock[0] += 1
    resumed = await app.night_snapshot(context)
    assert resumed.cycle_kind == "recovery" and resumed.wake_at == clock[0] + 60


async def test_custom_nap_finishes_early_at_full_energy(sleep_app):
    app, _, clock, context = sleep_app
    app.config = replace(app.config, recovery_follow_wake_at=False, recovery_max_minutes=120)
    await set_energy(app, context, 90)
    state = await app.advance_scope(context, action="night.sleep")
    target = state.wake_at
    clock[0] += 600
    full = await app.night_snapshot(context)
    assert full.energy == 100 and full.cycle_kind == "awake"
    assert full.wake_at == target and full.display_state.value == "awake"
    await set_energy(app, context, 90)
    clock[0] += 600
    assert (await app.night_snapshot(context)).energy == 90


async def test_custom_expiry_preserves_partial_energy(sleep_app):
    app, _, clock, context = sleep_app
    app.config = replace(app.config, recovery_follow_wake_at=False, recovery_max_minutes=1)
    await set_energy(app, context, 50)
    state = await app.advance_scope(context, action="night.sleep")
    clock[0] = state.wake_at
    final = await app.night_snapshot(context)
    assert final.energy == 51 and final.cycle_kind == "awake"


@pytest.mark.parametrize("offline", [False, True])
async def test_fixed_night_overrides_custom_duration_and_finishes_full(sleep_app, offline):
    app, _, clock, context = sleep_app
    app.config = replace(app.config, recovery_follow_wake_at=False,
                         recovery_max_minutes=1440, energy_recovery_per_minute=0)
    await set_energy(app, context, 0)
    initial = await app.advance_scope(context, action="night.sleep")
    assert initial.wake_at == at("2026-11-17T14:00:00")
    if not offline:
        clock[0] = at("2026-11-17T02:30:00")
        deep = await app.night_snapshot(context)
        assert deep.cycle_kind == "night" and deep.display_state.value == "deep_sleep"
        assert deep.wake_at == at("2026-11-17T08:10:00")
    clock[0] = at("2026-11-17T09:00:00")
    state = await app.night_snapshot(context)
    assert state.energy == 100 and state.display_state.value == "awake"
    assert state.wake_at == at("2026-11-17T08:10:00")


async def test_custom_deadline_is_not_rewritten_after_config_change_or_restart(sleep_app):
    app, store, clock, context = sleep_app
    app.config = replace(app.config, recovery_follow_wake_at=False, recovery_max_minutes=120)
    await set_energy(app, context, 0)
    state = await app.advance_scope(context, action="night.sleep")
    target = state.wake_at
    app.config = replace(app.config, recovery_follow_wake_at=True, recovery_max_minutes=1)
    await store.close()
    reopened = SQLiteStore(store.path, config=app.config, clock=lambda: clock[0])
    await reopened.open()
    app.store = reopened
    clock[0] += 60
    assert (await app.night_snapshot(context)).wake_at == target


async def test_custom_mode_never_draws_or_writes_on_read_only_refresh(sleep_app):
    app, store, clock, context = sleep_app
    app.config = replace(app.config, recovery_follow_wake_at=False)
    await set_energy(app, context, 0)
    before = await store.get_state(context, "night")
    draws = app.draw_count
    clock[0] += 3600
    for _ in range(3):
        await app.night_display_snapshot(context)
    assert await store.get_state(context, "night") == before and app.draw_count == draws


@pytest.mark.parametrize("bad_minutes,clamped", [(0, 1), (2000, 1440)])
async def test_runtime_duration_is_bounded_even_if_validation_is_bypassed(
        sleep_app, bad_minutes, clamped):
    from types import SimpleNamespace
    from astrbot_plugin_livingemotion.contracts import to_dict
    app, _, clock, _ = sleep_app
    app.config = SimpleNamespace(**{**to_dict(app.config), "recovery_follow_wake_at": False,
                                    "recovery_max_minutes": bad_minutes})
    state = NightState(updated_at=clock[0])
    assert app._recovery_cycle(state, clock[0]).wake == clock[0] + clamped * 60


def test_daytime_recovery_partitioned_replay_matches_direct_settlement():
    initial = NightState(policy_version=2, energy=5, energy_units=50, updated_at=1000)
    policy = LifePolicy(daytime_recovery_enabled=True, recovery_units_per_minute=3)
    windows = ((2500, 5000),)
    direct, _ = advance_life(initial, now=10000, policy=policy, fatigue_windows=windows)
    stepped = initial
    for timestamp in sorted(Random(20261116).sample(range(1001, 10000), 120)) + [10000]:
        stepped, _ = advance_life(stepped, now=timestamp, policy=policy, fatigue_windows=windows)
    assert stepped == direct


def test_life_policy_uses_validated_daytime_switch():
    from astrbot_plugin_livingemotion.config import Config
    assert not life_policy(Config()).daytime_recovery_enabled
    assert life_policy(Config(energy_daytime_recovery_enabled=True)).daytime_recovery_enabled
    with pytest.raises(ValueError):
        LifePolicy(daytime_recovery_enabled=1)


@pytest.mark.parametrize("initial_units,window,expected", [
    (0, (), 1), (1000, ((1000, 1060),), 999),
])
def test_frequent_ticks_keep_fractional_energy_at_bounds(initial_units, window, expected):
    state = NightState(policy_version=2, energy=initial_units / 10,
                       energy_units=initial_units, updated_at=1000)
    policy = LifePolicy(daytime_recovery_enabled=True, recovery_units_per_minute=1,
                        fatigue_units_per_minute=1)
    for timestamp in range(1001, 1061):
        state, _ = advance_life(state, now=timestamp, policy=policy, fatigue_windows=window)
    assert state.energy_units == expected and state.energy_remainder == 0
