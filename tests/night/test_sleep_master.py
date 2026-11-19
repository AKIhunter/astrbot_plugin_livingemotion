"""Sleep permission matrix: virtual time, real SQLite, no network or providers."""
from dataclasses import replace

import pytest

from astrbot_plugin_livingemotion.config import Config, LEGACY_FIELDS
from astrbot_plugin_livingemotion.contracts import (
    NightPhase, NightState, SleepState, StateWrite, to_dict,
)
from astrbot_plugin_livingemotion.domain.night import (
    advance_life, advance_night, sleepless_state, submit_life_reply,
)
from astrbot_plugin_livingemotion.runtime.application import Application
from astrbot_plugin_livingemotion.runtime.projector import Projector
from astrbot_plugin_livingemotion.tests.experience.test_manual_daily import make_app
from test_life_state import Harness, at, human
from test_sleep_energy_rules import sleep_app, set_energy


@pytest.mark.parametrize("old_enabled", [False, True])
@pytest.mark.parametrize("old_schedule", [False, True])
@pytest.mark.parametrize("permission", [False, True])
def test_explicit_permission_wins_over_legacy_schedule(old_enabled, old_schedule, permission):
    config = Config.from_mapping({
        "night_schedule_enabled": old_schedule, "allow_sleep": permission,
        "night_enabled": old_enabled, "timezone": "UTC",
    })
    assert config.allow_sleep is permission
    assert "night_schedule_enabled" in LEGACY_FIELDS


@pytest.mark.parametrize("old_schedule", [False, True])
def test_old_config_without_permission_migrates_once(old_schedule):
    migrated = Config.from_mapping({"night_schedule_enabled": old_schedule})
    assert migrated.allow_sleep is old_schedule
    saved = {**to_dict(migrated), "allow_sleep": not old_schedule}
    assert Config.from_mapping(saved).allow_sleep is not old_schedule


@pytest.mark.parametrize("energy", [0, 0.1, 15, 20, 99, 100])
@pytest.mark.parametrize("now", [900, 1000, 100000])
def test_disabled_time_and_replies_always_full_even_on_rollback(energy, now):
    state = NightState(
        policy_version=2, energy=energy, energy_units=round(energy * 10),
        updated_at=1000, phase=NightPhase.ASLEEP, display_state=SleepState.DEEP_SLEEP,
        sleep_started_at=900, wake_at=2000, cycle_id="old", cycle_kind="night",
        deep_sleep_at=900, energy_remainder=17, energy_direction="fatigue",
        wake_session="old-wake", wake_reply_limit=3, wake_replies_used=2,
    )
    result, changes = advance_life(
        state, now=now, allow_sleep=False, fatigue_windows=((0, 200000),))
    assert result.energy == 100 and result.energy_units == 1000
    assert result.phase == NightPhase.AWAKE and result.display_state == SleepState.AWAKE
    assert result.updated_at == max(now, 1000)
    assert result.cycle_id is result.wake_at is result.wake_session is None
    assert result.energy_remainder == 0 and result.energy_direction == ""
    if changes:
        assert changes[0]["category"] == "config"
    for _ in range(20):
        result, charge = submit_life_reply(result, now=now, allow_sleep=False)
        assert result.energy == 100 and charge == ()


def test_legacy_disabled_restores_full_energy():
    state = NightState(energy=0, updated_at=1000, phase=NightPhase.ASLEEP,
                       sleep_started_at=900, wake_at=2000)
    result = advance_night(state, now=100000, enabled=False)
    assert result.energy == 100 and result.phase == NightPhase.AWAKE
    assert result.sleep_started_at is result.wake_at is None


async def test_partial_v2_record_without_units_can_be_closed(sleep_app):
    app, store, _, context = sleep_app
    record = await store.get_state(context, "night")
    partial = NightState(policy_version=2, energy=15, energy_units=None,
                         updated_at=store.clock())
    assert (await store.write_states(context, await store.get_generation(context), (
        StateWrite("night", to_dict(partial), record.version, owner=record.owner),
    ))).accepted
    app.config = replace(app.config, allow_sleep=False)
    assert (await app.night_snapshot(context)).energy == 100


async def test_disabled_read_projection_is_pure_and_needs_no_timezone(sleep_app):
    app, store, clock, context = sleep_app
    await set_energy(app, context, 0)
    before = await store.get_state(context, "night")
    app.config = replace(app.config, allow_sleep=False, timezone="")
    draws = app.draw_count
    clock[0] += 86400
    for _ in range(4):
        result = await app.night_display_snapshot(context)
        assert result.energy == 100 and result.display_state == SleepState.AWAKE
    assert await store.get_state(context, "night") == before
    assert app.draw_count == draws
    assert (await app.night_snapshot(context)).energy == 100
    assert await app.advance_scope(context, action="night.sleep") is None
    assert (await app.advance_scope(context)).energy == 100


async def test_disabled_runtime_replies_and_human_projection_cannot_drain(sleep_app):
    app, store, clock, context = sleep_app
    await set_energy(app, context, 0)
    app.config = replace(app.config, allow_sleep=False)
    draws = app.draw_count
    projector = Projector(store, lambda: app.config)
    for index in range(5):
        clock[0] += 3600
        projection = await projector(human(context, clock[0], str(index)))
        assert (await store.commit_event(human(context, clock[0], str(index)),
                                         projection.generation, projection.writes,
                                         projection.contributions, traces=projection.traces)).accepted
        started = await app.reply_started(context, f"reply-{index}")
        assert started["allowed"]
        sent = await app.reply_submitted(context, f"reply-{index}", ticket=started["ticket"])
        assert sent["allowed"] and sent["night"].energy == 100
    assert app.draw_count == draws
    assert await app.advance_scope(context, action="night.sleep") is None
    assert (await app.advance_scope(context, action="night.wake")).energy == 100
    app._participation = {context.scope_key: clock[0]}
    app.config = replace(app.config, closing_enabled=True)
    assert await Application._closing_due(app, context, active_reply=True) is None


@pytest.mark.parametrize("shared", [False, True])
async def test_instance_reset_covers_idle_scenes_and_preserves_other_data(le_store, le_context, shared):
    contexts = [
        le_context, replace(le_context, scene_id="idle", account_id="other"),
        replace(le_context, instance_id="other-instance"),
    ]
    for context in contexts:
        await le_store.register_context(context)
        await le_store.initialize_state_mode(context, shared=shared)
        record = await le_store.get_state(context, "night")
        state = NightState(
            policy_version=2, energy=0, energy_units=0, updated_at=le_store.clock(),
            phase=NightPhase.ASLEEP, display_state=SleepState.DEEP_SLEEP,
            sleep_started_at=le_store.clock(), wake_at=le_store.clock() + 1000,
            cycle_id="old", cycle_kind="manual",
        )
        assert (await le_store.write_states(context, await le_store.get_generation(context), (
            StateWrite("night", {**to_dict(state), "_runtime": {
                "manual_wake_until": le_store.clock() + 1000, "keep": "preserved",
            }}, record.version if record else 0, owner=le_store.state_owner(context)),
        ))).accepted
    foreign = await le_store.get_state(contexts[-1], "night")
    await le_store.reset_sleep_permission(le_context.instance_id)
    for context in contexts[:2]:
        row = await le_store.get_state(context, "night")
        assert row.value["energy"] == 100
        assert row.value["_runtime"] == {"keep": "preserved"}
    assert await le_store.get_state(contexts[-1], "night") == foreign
    version = (await le_store.get_state(le_context, "night")).version
    await le_store.reset_sleep_permission(le_context.instance_id)
    assert (await le_store.get_state(le_context, "night")).version == version


async def test_native_save_close_reopen_idle_state_never_charges_closed_interval(tmp_path, le_context):
    app, _, _, _ = await make_app(tmp_path, {"allow_sleep": True})
    context = replace(le_context, instance_id=app.instance_id)
    try:
        await app.store.register_context(context)
        await app.initialize_state_scope(context)
        record = await app.store.get_state(context, "night")
        state = NightState(policy_version=2, energy=0, energy_units=0,
                           updated_at=app.store.clock())
        assert (await app.store.write_states(context, 0, (
            StateWrite("night", to_dict(state), record.version, owner=record.owner),
        ))).accepted
        result = await app.update_config(
            {"allow_sleep": False}, expected_revision=app.config_revision,
            reason="", actor_id="synthetic-admin", receipt="config")
        assert result["config"]["values"]["allow_sleep"] is False
        assert (await app.store.get_state(context, "night")).value["energy"] == 100
        later = at("2026-11-12T16:00:00")
        app.store.clock = lambda: later
        await app.update_config(
            {"allow_sleep": True}, expected_revision=app.config_revision,
            reason="", actor_id="synthetic-admin", receipt="config")
        row = await app.store.get_state(context, "night")
        assert row.value["updated_at"] == later and row.value["energy"] == 100
        runtime = Harness(app.store, app.config)
        result = await runtime.night_snapshot(context)
        assert result.energy == 100
        assert app.native_config["allow_sleep"] is True
    finally:
        await app.terminate()
