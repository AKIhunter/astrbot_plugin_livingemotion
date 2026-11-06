"""Native response stage against an installed product; synthetic transport only."""

import copy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from final_checks import event, plugin, product, setup_persona


async def native_after_sent(core, e):
    from astrbot.api.provider import ProviderRequest
    from astrbot.core import astrbot_config
    from astrbot.core.pipeline.context_utils import call_event_hook
    from astrbot.core.pipeline.respond.stage import RespondStage
    from astrbot.core.platform.platform_metadata import PlatformMetadata
    from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
        AiocqhttpMessageEvent,
    )

    p = plugin(core)
    saved = dict(p.application.native_config)
    now = datetime.now(timezone.utc)
    p.application.native_config.update(
        night_enabled=True, night_schedule_enabled=True, timezone="UTC",
        sleep_at=(now - timedelta(minutes=2)).strftime("%H:%M"),
        wake_at=(now + timedelta(hours=2)).strftime("%H:%M"))
    active_sends = []

    async def send_by_session(session, chain):
        active_sends.append(str(session))

    adapter = SimpleNamespace(
        meta=lambda: PlatformMetadata(id="synthetic-adapter", name="aiocqhttp",
                                      description="Synthetic C30 transport"),
        send_by_session=send_by_session)
    core.platform_manager.platform_insts.append(adapter)

    def check(name, value, detail=None):
        e.check("C30.native_response." + name, value,
                layer="real_product_native_respond_synthetic_aiocqhttp_transport_clock",
                detail=detail)

    try:
        await p.application.refresh_config()
        for i, (label, outcome) in enumerate((
            ("none", None), ("false", False),
            ("exception", RuntimeError("synthetic platform failure")),
            ("ack_discarded", {"message_id": 200003}),
        )):
            attempts = []

            async def send_private_msg(**kwargs):
                attempts.append(True)
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome

            base = event("synthetic-native-receipt-" + label)
            base.message_obj.sender.user_id = str(200100 + i)
            ev = AiocqhttpMessageEvent(
                base.message_obj.message_str, base.message_obj, base.platform_meta,
                session_id=str(200100 + i),
                bot=SimpleNamespace(send_private_msg=send_private_msg))
            await setup_persona(core, ev)
            await p.supplement_request(ev, ProviderRequest(prompt="synthetic"))
            ctx = product("contracts").Context.from_dict(ev.get_extra("livingemotion:context"))
            state = await p.application.advance_scope(ctx)
            check(label + ".pending", state.phase.value == "settling")
            check(label + ".deadline_120_seconds",
                  state.transition_deadline - state.updated_at == 120)
            cfg = copy.deepcopy(dict(astrbot_config))
            cfg["platform_settings"]["segmented_reply"]["enable"] = False
            stage = RespondStage()
            await stage.initialize(SimpleNamespace(astrbot_config=cfg))
            ev.set_result(ev.plain_result("Synthetic response."))
            # Spy delegates to the original host dispatcher and all real handlers.
            with patch("astrbot.core.pipeline.respond.stage.call_event_hook",
                       wraps=call_event_hook) as hook:
                await stage.process(ev)
            check(label + ".after_sent_actually_called", hook.await_count == 1)
            check(label + ".retains_settling",
                  (await p.application.night_snapshot(ctx)).phase.value == "settling")
            with patch.object(p.application.store, "clock", lambda: state.transition_deadline + 1):
                expired = await p.application.advance_scope(ctx)
                check(label + ".timeout_cancels",
                      expired.phase.value in ("awake", "drowsy")
                      and "settling_timeout" in expired.reason_codes
                      and expired.awaiting_reply_id is None)
                same_window = await p.application.advance_scope(ctx)
                check(label + ".no_reentry_or_retry",
                      same_window.phase.value in ("awake", "drowsy")
                      and len(attempts) == 1 and not active_sends,
                      {"reply_attempts": len(attempts), "active_send_attempts": len(active_sends)})
            core._final_synthetic_events.append(ev)

        # No pending response is a separate path, never a forged success receipt.
        ev = event("synthetic-no-pending")
        ev.message_obj.sender.user_id = "synthetic-no-pending-human"
        ev = type(ev)(ev.message_obj.message_str, ev.message_obj, ev.platform_meta,
                      session_id="synthetic-no-pending-human")
        await setup_persona(core, ev)
        await p.observe_message(ev)
        ctx = product("contracts").Context.from_dict(ev.get_extra("livingemotion:context"))
        scheduled = await p.application.advance_scope(ctx)
        check("no_pending_direct_schedule_sleeps",
              scheduled.phase.value == "asleep"
              and "scheduled_sleep" in scheduled.reason_codes)
        await p.application.advance_scope(ctx, action="night.wake")
        manual = await p.application.advance_scope(ctx, action="night.sleep")
        check("manual_sleep_still_works",
              manual.phase.value == "asleep" and "manual_sleep" in manual.reason_codes)
        core._final_synthetic_events.append(ev)
    finally:
        core.platform_manager.platform_insts.remove(adapter)
        p.application.native_config.clear()
        p.application.native_config.update(saved)
        await p.application.refresh_config()
