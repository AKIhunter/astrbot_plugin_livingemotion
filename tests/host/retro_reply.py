"""Frozen-only reply tickets/window checks through actual registered host hooks."""

import asyncio
from datetime import datetime, timezone
from retro_common import plugin, product
from retro_native import native_event, trace_product_hook


CONFIG = {
    "timezone": "UTC", "night_policy_version": 2, "night_schedule_enabled": True,
    "persona_shared_state": True, "allow_sleep": True,
    "lie_in_min_minutes": 0, "lie_in_max_minutes": 0,
    "catchup_enabled": False, "catchup_reply_enabled": False,
    "memory_read": False, "memory_write": False, "livingmemory_enabled": False,
    "autonomy_enabled": False, "closing_enabled": False,
    "wake_reply_limit": 1, "wake_window_minutes": 10,
    "energy_fatigue_per_minute": 0, "energy_recovery_per_minute": 0,
}


def at(hour, minute=0):
    return datetime(2026, 11, 6, hour, minute, tzinfo=timezone.utc).timestamp()


async def select_persona(core, event, persona_id):
    from astrbot.core import sp
    try:
        await core.persona_mgr.get_persona(persona_id)
    except ValueError:
        await core.persona_mgr.create_persona(
            persona_id=persona_id, system_prompt="Synthetic independent P8 persona.",
        )
    await sp.put_async(
        scope="umo", scope_id=event.unified_msg_origin,
        key="session_service_config", value={"persona_id": persona_id},
    )


async def observe(core, identifier, persona_id, now, **kwargs):
    ev = native_event(identifier, **kwargs)
    ev.message_obj.timestamp = now
    await select_persona(core, ev, persona_id)
    await plugin(core).observe_message(ev)
    core._retro_events.append(ev)
    raw = ev.get_extra("livingemotion:context")
    if not raw:
        raise AssertionError("Native observer did not resolve a real source")
    return ev, product("contracts").Context.from_dict(raw)


async def request(core, identifier, persona_id, now):
    from astrbot.api.provider import ProviderRequest
    from astrbot.core.pipeline.context import call_event_hook
    from astrbot.core.star.star_handler import EventType
    ev, ctx = await observe(core, identifier, persona_id, now)
    await call_event_hook(
        ev, EventType.OnLLMRequestEvent,
        ProviderRequest(prompt="Synthetic request.", extra_user_content_parts=[]),
    )
    return ev, ctx


async def output(scheduler, event, *, finish=False):
    from astrbot.core.message.message_event_result import MessageEventResult, ResultContentType
    result_type = ResultContentType.STREAMING_FINISH if finish else ResultContentType.LLM_RESULT
    event.set_result(MessageEventResult().message("Synthetic final reply.").set_result_content_type(
        result_type,
    ))
    index = next(
        i for i, stage in enumerate(scheduler.stages)
        if type(stage).__name__ == "ResultDecorateStage"
    )
    await asyncio.wait_for(scheduler._process_stages(event, index), 15)


async def final_reply_cases(core, e):
    from astrbot.core.pipeline.context import call_event_hook
    from astrbot.core.star.star_handler import EventType
    app = plugin(core).application
    native = app.native_config
    saved_config, saved_clock = dict(native), app.store.clock
    clock = [at(1, 30)]
    native.update(CONFIG)
    await app.refresh_config()
    app.store.clock = lambda: clock[0]
    scheduler = next(iter(core.pipeline_scheduler_mapping.values()))
    try:
        with trace_product_hook(core, e):
            ev, ctx = await request(core, "retro-window", "retro-window-persona", clock[0])
            before = await app.night_snapshot(ctx)
            lease = ev.get_extra("livingemotion:reply_lease")
            e.check("ticket.real_request_admitted", bool(lease)
                    and lease["attempt_id"] in app._reply_tickets, fatal=True)
            e.check("window.not_started_at_generation",
                    before.first_reply_submitted_at is None
                    and before.wake_window_deadline is None
                    and before.wake_replies_used == 1)
            clock[0] += 5
            await output(scheduler, ev)
            submitted = await app.night_snapshot(ctx)
            e.check("window.first_final_submission_time",
                    submitted.first_reply_submitted_at == clock[0]
                    and submitted.wake_window_deadline == clock[0] + 600)
            e.check("window.last_admitted_reply_can_finish", len(ev.retro_sends) == 1)
            energy = await app.store.energy_history(ctx, category="reply")
            e.check("energy.one_actual_submission_charge", energy["total"] == 1
                    and abs(submitted.energy - (before.energy - 4)) < 0.1)
            clock[0] += 1
            await call_event_hook(ev, EventType.OnDecoratingResultEvent)
            repeated = await app.night_snapshot(ctx)
            energy = await app.store.energy_history(ctx, category="reply")
            e.check("window.repeated_hook_never_renews",
                    repeated.first_reply_submitted_at == submitted.first_reply_submitted_at
                    and repeated.wake_window_deadline == submitted.wake_window_deadline)
            e.check("energy.repeated_hook_does_not_charge", energy["total"] == 1)
            e.report["reply_window_observation"] = {
                "started": before.first_reply_submitted_at,
                "submitted": submitted.first_reply_submitted_at,
                "deadline": submitted.wake_window_deadline,
                "energy_reply_events": energy["total"],
            }

            clock[0] = at(1, 30)
            ev, ctx = await request(core, "retro-deep", "retro-deep-persona", clock[0])
            e.check("ticket.deep_case_started", bool(ev.get_extra("livingemotion:reply_lease")),
                    fatal=True)
            clock[0] = at(3)
            await output(scheduler, ev)
            night = await app.night_snapshot(ctx)
            energy = await app.store.energy_history(ctx, category="reply")
            e.check("reply.deep_sleep_preempts_final_stage",
                    ev.is_stopped() and not ev.retro_sends
                    and night.display_state.value == "deep_sleep" and energy["total"] == 0)

            clock[0] = at(1, 30)
            ev, ctx = await request(core, "retro-stale", "retro-stale-persona", clock[0])
            clock[0] += 1
            newer = native_event("retro-new-human")
            newer.message_obj.timestamp = clock[0]
            await plugin(core).observe_message(newer)
            core._retro_events.append(newer)
            await output(scheduler, ev)
            e.check("reply.new_human_invalidates_old_result",
                    ev.is_stopped() and not ev.retro_sends)

            clock[0] = at(1, 30)
            ev, ctx = await request(core, "retro-forged-ticket", "retro-forged-persona", clock[0])
            forged = dict(ev.get_extra("livingemotion:reply_lease") or {})
            forged["attempt_id"] = "synthetic-unadmitted-ticket"
            ev.set_extra("livingemotion:reply_lease", forged)
            await output(scheduler, ev)
            e.check("ticket.forged_attempt_cannot_submit",
                    ev.is_stopped() and not ev.retro_sends)

            clock[0] = at(1, 30)
            ev, ctx = await request(core, "retro-finish", "retro-finish-persona", clock[0])
            clock[0] += 5
            await output(scheduler, ev, finish=True)
            night = await app.night_snapshot(ctx)
            energy = await app.store.energy_history(ctx, category="reply")
            e.check("window.finish_hook_is_not_first_submission",
                    night.first_reply_submitted_at is None and energy["total"] == 0)
            await deadline_cases(core, e, app, clock, scheduler)
            await provider_failure_cases(core, e, app, clock, scheduler)
            await native_at_cases(core, e, app, clock)
    finally:
        app.store.clock = saved_clock
        native.clear()
        native.update(saved_config)
        await app.refresh_config()
        await select_persona(core, native_event("retro-restore"), "retro-forced")


async def deadline_cases(core, e, app, clock, scheduler):
    app.native_config["wake_reply_limit"] = 3
    await app.refresh_config()
    clock[0] = at(1, 30)
    first, ctx = await request(core, "retro-deadline-first", "retro-deadline-persona", clock[0])
    await output(scheduler, first)
    initial = await app.night_snapshot(ctx)
    e.check("window.deadline_case_first_submitted",
            initial.wake_window_deadline == clock[0] + 600 and len(first.retro_sends) == 1,
            fatal=True)
    for label, admitted, submitted, expected in (
        ("before", 598, 599, True), ("at", 599, 600, False),
    ):
        # A new human message at 600 may legitimately open another wake
        # session. Check expiry of a result admitted in the existing session.
        clock[0] = at(1, 30) + admitted
        pending, ctx = await request(
            core, "retro-deadline-" + label, "retro-deadline-persona", clock[0],
        )
        clock[0] = at(1, 30) + submitted
        await output(scheduler, pending)
        night = await app.night_snapshot(ctx)
        energy = await app.store.energy_history(ctx, category="reply")
        e.check("window." + label + "_absolute_deadline",
                bool(pending.retro_sends) is expected
                and (expected or pending.is_stopped())
                and night.wake_window_deadline == initial.wake_window_deadline
                and energy["total"] == 2,
                detail={"admitted_delta": admitted, "submitted_delta": submitted,
                        "sends": len(pending.retro_sends), "stopped": pending.is_stopped(),
                        "deadline": night.wake_window_deadline,
                        "reply_energy_events": energy["total"]})
    clock[0] = at(1, 30)
    first, ctx = await request(core, "retro-expire-first", "retro-expire-persona", clock[0])
    await output(scheduler, first)
    pending, ctx = await request(core, "retro-expire-pending", "retro-expire-persona", clock[0])
    e.check("window.pending_admitted_before_expiry",
            bool(pending.get_extra("livingemotion:reply_lease")), fatal=True)
    clock[0] += 600
    await output(scheduler, pending)
    energy = await app.store.energy_history(ctx, category="reply")
    e.check("window.admitted_result_revoked_at_deadline",
            pending.is_stopped() and not pending.retro_sends and energy["total"] == 1)


async def provider_failure_cases(core, e, app, clock, scheduler):
    from retro_native import synthetic_provider
    app.native_config["wake_reply_limit"] = 2
    await app.refresh_config()
    clock[0] = at(1, 30)
    provider = synthetic_provider(core)
    provider.fail = True
    try:
        for number in range(2):
            ev, ctx = await observe(
                core, "retro-provider-failure-" + str(number), "retro-failure-persona", clock[0],
            )
            await asyncio.wait_for(scheduler.execute(ev), 40)
            night = await app.night_snapshot(ctx)
            energy = await app.store.energy_history(ctx, category="reply")
            e.check("failure.generation_" + str(number) + "_counts_one_round",
                    night.wake_replies_used == number + 1,
                    detail={"rounds": night.wake_replies_used,
                            "provider_calls": len(provider.calls)})
            e.check("failure.generation_" + str(number) + "_no_reply_charge_or_window",
                    energy["total"] == 0 and night.first_reply_submitted_at is None
                    and night.wake_window_deadline is None,
                    detail={"reply_events": energy["total"],
                            "first_submission": night.first_reply_submitted_at,
                            "deadline": night.wake_window_deadline,
                            "result_type": str(ev.get_result().result_content_type)
                            if ev.get_result() else None})
        e.check("failure.exhausted_rounds_rest", night.display_state.value == "drowsy")
        e.check("failure.actual_native_provider_fault_injected",
                len(provider.calls) == 2 and all(c["mode"] == "nonstream" for c in provider.calls))
    finally:
        core.provider_manager.provider_insts.remove(provider)


async def native_at_cases(core, e, app, clock):
    app.native_config["wake_mode"] = "both"
    await app.refresh_config()
    clock[0] = at(1, 30)
    for label, target, expected in (
        ("ordinary_group", None, "drowsy"),
        ("native_at_other", "retro-other", "drowsy"),
        ("native_at_bot", "retro-bot", "awake"),
    ):
        ev = native_event("retro-at-" + label, group=True, at=target)
        ev.message_obj.timestamp = clock[0]
        await select_persona(core, ev, "retro-at-persona")
        ev.set_extra("at_bot", True)
        await plugin(core).observe_message(ev)
        raw = ev.get_extra("livingemotion:context")
        e.check("wake." + label + ".native_source", bool(raw), fatal=True)
        ctx = product("contracts").Context.from_dict(raw)
        night = await app.night_snapshot(ctx)
        e.check("wake." + label + ".actual_state",
                night.display_state.value == expected,
                detail={"display_state": night.display_state.value})
        core._retro_events.append(ev)
    clock[0] = at(3)
    ev = native_event("retro-at-deep", group=True, at="retro-bot")
    ev.message_obj.timestamp = clock[0]
    await plugin(core).observe_message(ev)
    ctx = product("contracts").Context.from_dict(ev.get_extra("livingemotion:context"))
    night = await app.night_snapshot(ctx)
    e.check("wake.native_at_cannot_bypass_deep_sleep",
            night.display_state.value == "deep_sleep" and not ev.retro_sends)
    core._retro_events.append(ev)
