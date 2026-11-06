"""Frozen-only sleep/wake acceptance on native events, persistence and reload."""

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import patch

from retro_common import NAME, owned_tasks, plugin, product
from retro_native import native_event, synthetic_provider
from retro_reply import CONFIG, observe, select_persona


def at(value):
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp()


async def set_energy(app, ctx, value):
    record = await app.store.get_state(ctx, "night")
    state = replace(app.store._night_value(record.value), energy=value,
                    energy_units=int(round(value * 10)))
    payload = {**product("contracts").to_dict(state),
               "_runtime": record.value.get("_runtime", {})}
    result = await app.store.write_states(
        ctx, await app.store.get_generation(ctx),
        (product("contracts").StateWrite(
            "night", payload, record.version, owner=record.owner,
        ),),
    )
    if not result.accepted:
        raise AssertionError("Synthetic energy fixture was not persisted")


async def reload_at_clock(core, e, clock, draw):
    old = plugin(core)
    tasks = owned_tasks()
    old.application.native_config.save_config()
    # Reload reimports the real SQLiteStore, capturing this synthetic clock.
    # No state-machine, storage operation, permission or hook is replaced.
    with patch("time.time", side_effect=lambda: clock[0]), patch("random.randint", side_effect=draw):
        ok, _ = await core.plugin_manager.reload(NAME)
    current = plugin(core)
    e.check("sleep.real_manager_reload", ok and current is not old
            and old.application.closed and all(t.done() for t in tasks), fatal=True)
    e.check("sleep.reload_initialization_used_synthetic_clock",
            current.application.store.clock() == clock[0], fatal=True)
    current.application.store.clock = lambda: clock[0]
    current.application.night_random = draw
    return current.application


async def final_sleep_cases(core, e):
    app = plugin(core).application
    saved_config, saved_clock = dict(app.native_config), app.store.clock
    clock = [at("2026-11-05T23:29:00")]
    draws, dice = [], [0, 0]

    def draw(low, high):
        value = dice.pop(0) if (low, high) == (0, 9) and dice else (
            60 if high == 90 else low
        )
        draws.append({"low": low, "high": high, "value": value})
        return value

    app.native_config.update({
        **CONFIG, "night_enabled": True, "nap_enabled": True,
        "fatigue_start": "23:30", "fatigue_end": "07:00",
        "deep_sleep_at": "02:30", "wake_at": "08:00",
        "nap_start": "13:00", "nap_end": "14:30",
        "lie_in_max_minutes": 90, "wake_reply_limit": 3, "wake_mode": "chat",
    })
    await app.refresh_config()
    app.store.clock, app.night_random = lambda: clock[0], draw
    observations = []
    try:
        for value, expected in (
            ("2026-11-05T23:29:00", "awake"),
            ("2026-11-05T23:30:00", "groggy"),
            ("2026-11-06T01:00:00", "drowsy"),
        ):
            clock[0] = at(value)
            ev, ctx = await observe(
                core, "retro-timeline-" + expected, "retro-timeline-persona", clock[0], group=True,
            )
            night = await app.night_snapshot(ctx)
            observations.append({"at": value, "display": night.display_state.value})
            e.check("sleep.native_timeline_" + expected, night.display_state.value == expected)
            e.check("sleep.native_timeline_" + expected + "_chat_gate",
                    ev.is_stopped() is (expected == "drowsy") and not ev.retro_sends)
        e.check("sleep.cross_midnight_targets", night.drowsy_at == at("2026-11-06T01:00:00")
                and night.deep_sleep_at == at("2026-11-06T02:30:00")
                and night.wake_at == at("2026-11-06T09:00:00"))
        e.check("sleep.lie_in_draw_once", len(draws) == 1 and night.lie_in_minutes == 60)

        clock[0] = at("2026-11-06T01:30:00")
        _, low_ctx = await observe(
            core, "retro-low-seed", "retro-low-persona", clock[0], group=True,
        )
        await set_energy(app, low_ctx, 9.9)
        first, low_ctx = await observe(
            core, "retro-low-0", "retro-low-persona", clock[0],
        )
        low = await app.night_snapshot(low_ctx)
        e.check("wake.low_first_two_dice_fail", low.wake_score == 0
                and low.wake_failures == 1 and low.energy == 9.9 and first.is_stopped())
        before = len(draws)
        duplicate, low_ctx = await observe(
            core, "retro-low-0", "retro-low-persona", clock[0],
        )
        low = await app.night_snapshot(low_ctx)
        e.check("wake.low_duplicate_does_not_roll_or_increment",
                low.wake_score == 0 and low.wake_failures == 1 and len(draws) == before)

        def different_draw(low, high):
            value = 9 if high == 9 else min(high, max(low, 17))
            draws.append({"low": low, "high": high, "value": value})
            return value

        app = await reload_at_clock(core, e, clock, different_draw)
        before = len(draws)
        _, ctx = await observe(
            core, "retro-timeline-after-reload", "retro-timeline-persona", clock[0], group=True,
        )
        night = await app.night_snapshot(ctx)
        duplicate, low_ctx = await observe(core, "retro-low-0", "retro-low-persona", clock[0])
        low = await app.night_snapshot(low_ctx)
        e.check("sleep.lie_in_persisted_across_real_reload",
                night.lie_in_minutes == 60 and night.wake_at == at("2026-11-06T09:00:00")
                and len(draws) == before)
        e.check("wake.low_score_and_duplicate_persisted_across_real_reload",
                low.wake_score == 0 and low.wake_failures == 1 and duplicate.is_stopped())
        for score in range(1, 10):
            ev, low_ctx = await observe(
                core, "retro-low-" + str(score), "retro-low-persona", clock[0],
            )
            low = await app.night_snapshot(low_ctx)
            e.check("wake.low_accumulate_" + str(score),
                    (low.wake_score == score and low.wake_failures == score + 1
                     and ev.is_stopped()) if score <= 8 else (
                         low.wake_score is None and low.wake_failures == 0
                         and low.display_state.value == "groggy"
                         and not ev.is_stopped() and low.energy == 9.9
                     ))
        e.check("wake.low_success_never_redraws_or_refills", len(draws) == before
                and low.energy == 9.9)
        for value, expected in (
            ("2026-11-06T02:30:00", "deep_sleep"),
            ("2026-11-06T07:30:00", "deep_sleep"),
            ("2026-11-06T08:59:59", "deep_sleep"),
            ("2026-11-06T09:00:00", "awake"),
            ("2026-11-06T13:00:00", "nap"),
            ("2026-11-06T14:30:00", "awake"),
        ):
            clock[0] = at(value)
            ev, ctx = await observe(
                core, "retro-timeline-" + value, "retro-timeline-persona", clock[0], group=True,
            )
            night = await app.night_snapshot(ctx)
            observations.append({"at": value, "display": night.display_state.value})
            e.check("sleep.timeline_" + value, night.display_state.value == expected)
            e.check("sleep.gate_" + value, ev.is_stopped() is (
                expected in ("deep_sleep", "nap")
            ) and not ev.retro_sends)
            if expected == "deep_sleep":
                e.check("sleep.full_energy_cannot_exit_" + value, night.energy == 100)
        e.report["native_sleep_timeline"] = observations
        e.report["synthetic_sleep_draws"] = draws
        await native_controls(core, e, app, clock)
    finally:
        current = plugin(core).application
        current.store.clock = saved_clock
        current.native_config.clear()
        current.native_config.update(saved_config)
        current.native_config.save_config()
        await current.refresh_config()
        await select_persona(core, native_event("retro-sleep-restore"), "retro-forced")


async def native_controls(core, e, app, clock):
    from astrbot.core import astrbot_config
    scheduler = next(iter(core.pipeline_scheduler_mapping.values()))
    provider = synthetic_provider(core)
    saved_admins = list(astrbot_config["admins_id"])
    astrbot_config["admins_id"] = []
    try:
        clock[0] = at("2026-11-06T03:00:00")
        for authenticated in (False, True):
            persona = "retro-deep-admin-" + str(authenticated)
            _, ctx = await observe(core, persona + "-seed", persona, clock[0])
            await set_energy(app, ctx, 2)
            initial = await app.night_snapshot(ctx)
            ev = native_event(persona + "-command", "/le_wake")
            ev.message_obj.timestamp = clock[0]
            await select_persona(core, ev, persona)
            ev.set_extra("admin", True)
            ev.set_extra("livingemotion:control_request", "admin")
            before, draw_count = len(provider.calls), len(e.report["synthetic_sleep_draws"])
            if authenticated:
                astrbot_config["admins_id"].append(ev.get_sender_id())
            await asyncio.wait_for(scheduler.execute(ev), 40)
            astrbot_config["admins_id"] = []
            core._retro_events.append(ev)
            after = await app.night_snapshot(ctx)
            e.check("wake.deep_native_admin_" + str(authenticated),
                    initial.display_state.value == "deep_sleep"
                    and after.display_state.value == ("awake" if authenticated else "deep_sleep")
                    and bool(ev.retro_sends) is authenticated
                    and len(provider.calls) == before)
            e.check("wake.deep_never_accumulates_or_rolls_" + str(authenticated),
                    after.wake_score is None and after.wake_failures == 0
                    and len(e.report["synthetic_sleep_draws"]) == draw_count)
            e.check("wake.deep_admin_claim_is_native_" + str(authenticated),
                    ev.is_admin() is authenticated
                    and (authenticated or ev.get_extra("livingemotion:control_request") != "admin"))

        clock[0] = at("2026-11-06T01:30:00")
        for mode, group, mention in (
            ("never", False, None), ("never", True, "retro-bot"),
            ("chat", True, "retro-bot"), ("both", True, "retro-bot"),
        ):
            app.native_config["wake_mode"] = mode
            await app.refresh_config()
            label = mode + ("-group" if group else "-private")
            ev, ctx = await observe(core, "retro-mode-" + label, "retro-mode-" + label,
                                    clock[0], group=group, at=mention)
            night = await app.night_snapshot(ctx)
            accepted = mode == "both"
            e.check("wake.native_mode_" + label,
                    night.display_state.value == ("awake" if accepted else "drowsy")
                    and ev.is_stopped() is not accepted)
        clock[0] = at("2026-11-06T03:30:00")
        for key in ("allow_sleep", "night_enabled"):
            app.native_config.update(allow_sleep=True, night_enabled=True, wake_mode="never")
            app.native_config[key] = False
            await app.refresh_config()
            ev, ctx = await observe(core, "retro-disable-" + key, "retro-disable-" + key, clock[0])
            before = len(provider.calls)
            await asyncio.wait_for(scheduler.execute(ev), 40)
            available = await app.availability(ctx)
            e.check("sleep.disabled_" + key + "_native_reply",
                    available.available and not available.block_chat
                    and len(ev.retro_sends) == 1 and len(provider.calls) == before + 1)
    finally:
        astrbot_config["admins_id"] = saved_admins
        core.provider_manager.provider_insts.remove(provider)
