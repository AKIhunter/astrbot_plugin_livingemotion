"""Additional host acceptance boundaries, using only synthetic local records."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
from unittest.mock import patch

from final_checks import NAME, event, plugin, product, setup_persona, tasks


async def reply_receipts(core, e):
    from astrbot.api.provider import ProviderRequest, LLMResponse
    from astrbot.core.pipeline.context_utils import call_event_hook
    from astrbot.core.star.star_handler import EventType, star_handlers_registry

    p = plugin(core)
    saved = dict(p.application.native_config)
    now = datetime.now(timezone.utc)
    p.application.native_config.update(
        night_enabled=True, night_schedule_enabled=True, timezone="UTC",
        sleep_at=(now - timedelta(minutes=2)).strftime("%H:%M"),
        wake_at=(now + timedelta(hours=2)).strftime("%H:%M"))
    try:
        await p.application.refresh_config()
        ev = event("synthetic-receipt")
        await setup_persona(core, ev)
        await p.supplement_request(ev, ProviderRequest(prompt="synthetic"))
        ctx = product("contracts").Context.from_dict(ev.get_extra("livingemotion:context"))
        state = await p.application.advance_scope(ctx)
        e.check("C30.native_pending_enters_settling", state.phase.value == "settling")
        await call_event_hook(ev, EventType.OnLLMResponseEvent,
                              LLMResponse(role="assistant", completion_text="Synthetic generated reply."))
        e.check("C30.llm_response_not_delivery", (await p.application.night_snapshot(ctx)).phase.value == "settling")
        for value in (None, True, False):
            async def send(chain):
                ev._has_send_oper = True
                return value
            ev.send = send
            await ev.send(ev.plain_result("Synthetic adapter operation."))
            await call_event_hook(ev, EventType.OnAfterMessageSentEvent)
            e.check(f"C30.native_after_sent_{value}_not_confirmation",
                    (await p.application.night_snapshot(ctx)).phase.value == "settling",
                    layer="real_host_hooks_synthetic_sender")
        receipt_cls = product("domain.night").ReplyReceipt
        clock = p.application.store.clock()
        for label, receipt in (
            ("wrong_message", receipt_cls(ctx, "succeeded", clock, message_id="wrong")),
            ("other_scope", receipt_cls(replace(ctx, scene_id="synthetic-other"), "succeeded",
                                       clock, message_id="synthetic-receipt")),
            ("unknown", receipt_cls(ctx, "unknown", clock, message_id="synthetic-receipt")),
            ("failed", receipt_cls(ctx, "failed", clock, message_id="synthetic-receipt")),
            ("cancelled", receipt_cls(ctx, "cancelled", clock, message_id="synthetic-receipt")),
        ):
            await p.application.confirm_reply(receipt)
            e.check("C30.direct_port_" + label + "_retains_settling",
                    (await p.application.night_snapshot(ctx)).phase.value == "settling",
                    layer="real_application_synthetic_typed_receipt")
        await p.application.confirm_reply(receipt_cls(
            ctx, "succeeded", clock, message_id="synthetic-receipt"))
        e.check("C30.direct_port_matched_success_sleeps",
                (await p.application.night_snapshot(ctx)).phase.value == "asleep",
                layer="real_application_synthetic_typed_receipt")
        e.report["C30_native_receipt_hook_boundary"] = {
            "after_sent_handlers": [
                h.handler_full_name
                for h in star_handlers_registry.get_handlers_by_event_type(EventType.OnAfterMessageSentEvent)
                if NAME in h.handler_module_path
            ],
            "real_platform_confirmed_success": "not_verified",
            "direct_typed_receipt_is_not_native_transport_confirmation": True,
        }
        await p.application.advance_scope(ctx, action="night.wake")
        core._final_synthetic_events.append(ev)
        # New native event scope; clock injection advances only the product store.
        base = event("synthetic-receipt-timeout")
        base.message_obj.sender.user_id = "synthetic-timeout-human"
        timeout_ev = type(base)(
            base.message_obj.message_str, base.message_obj, base.platform_meta,
            session_id="synthetic-timeout-human")
        await setup_persona(core, timeout_ev)
        await p.supplement_request(timeout_ev, ProviderRequest(prompt="synthetic timeout"))
        timeout_ctx = product("contracts").Context.from_dict(
            timeout_ev.get_extra("livingemotion:context"))
        started = p.application.store.clock()
        pending = await p.application.advance_scope(timeout_ctx)
        e.check("C30.pending_has_bounded_deadline",
                pending.phase.value == "settling"
                and 0 < pending.transition_deadline - started <= 121,
                layer="real_application_synthetic_event_clock",
                detail={"deadline_seconds": pending.transition_deadline - started})
        with patch.object(p.application.store, "clock", lambda: pending.transition_deadline + 1):
            expired = await p.application.advance_scope(timeout_ctx)
            e.check("C30.timeout_does_not_fake_success",
                    expired.phase.value in ("awake", "drowsy")
                    and "settling_timeout" in expired.reason_codes
                    and expired.awaiting_reply_id is None,
                    layer="real_application_synthetic_event_clock",
                    detail={"phase": expired.phase.value, "reasons": expired.reason_codes})
            await p.application.confirm_reply(receipt_cls(
                timeout_ctx, "succeeded", p.application.store.clock(),
                message_id="synthetic-receipt-timeout"))
            late = await p.application.night_snapshot(timeout_ctx)
            e.check("C30.late_success_does_not_sleep_after_timeout",
                    late.phase.value in ("awake", "drowsy"),
                    layer="real_application_synthetic_typed_receipt")
            again = await p.application.advance_scope(timeout_ctx)
            e.check("C30.same_window_does_not_reenter_settling",
                    again.phase.value in ("awake", "drowsy"),
                    layer="real_application_synthetic_event_clock")
        core._final_synthetic_events.append(timeout_ev)
    finally:
        p.application.native_config.clear()
        p.application.native_config.update(saved)
        await p.application.refresh_config()


async def bili_fault(core, e):
    bridge = importlib.import_module("data.plugins.BiliBot.core.emotion_bridge")
    config = importlib.import_module("data.plugins.BiliBot.core.config")
    bili = core.star_context.get_registered_star("astrbot_plugin_bilibili_ai_bot").star_cls
    for kind in ("comment", "private"):
        mid = "synthetic-bili-" + kind
        sent = []

        async def send(*args, **kwargs):
            sent.append(True)
            return True

        def failed_bridge(*args, **kwargs):
            raise RuntimeError("synthetic bridge unavailable")

        result = {"_protocol_validated": True, "decision": "reply",
                  "reply": "Synthetic Bili response.", "score_delta": 2}
        with patch.object(bili, "_send_reply", send), patch.object(
                bili, "_send_bili_private_message", send), patch.object(
                bridge, "report_relationship_event", failed_bridge):
            if kind == "comment":
                outcome = await bili._apply_reply_result(
                    mid=mid, username="Synthetic", content="Synthetic public input.",
                    oid="synthetic-object", rpid="synthetic-comment-write", comment_type=2,
                    thread_id="synthetic-comment-thread", result=result)
            else:
                outcome = await bili._apply_private_reply_result({
                    "sender_uid": mid, "username": "Synthetic", "content": "Synthetic private input.",
                    "msg_key": "synthetic-private-write", "timestamp": __import__("time").time(),
                }, result, thread_id="synthetic-private-thread")
        stored = bili._load_json(config.AFFECTION_FILE, {})
        profile = bili._load_json(config.USER_PROFILE_FILE, {}).get(mid, {})
        e.check("C41.real_" + kind + "_survives_bridge_failure",
                outcome is True and len(sent) == 1 and bili._affection.get(mid) == 2
                and stored.get(mid) == 2
                and profile.get("relationship", {}).get("positive_interactions") == 1,
                layer="real_bilibot_flow_synthetic_transport_fault_injection",
                detail={"result": outcome, "sends": len(sent),
                        "persisted_score": stored.get(mid),
                        "positive_interactions": profile.get("relationship", {}).get("positive_interactions")})


async def rollback(core, e, root):
    bridge = importlib.import_module("data.plugins.BiliBot.core.emotion_bridge")
    bili = core.star_context.get_registered_star("astrbot_plugin_bilibili_ai_bot").star_cls
    p = plugin(core)
    ev = event("synthetic-new-before-rollback")
    await setup_persona(core, ev)
    await p.observe_message(ev)
    ctx = product("contracts").Context.from_dict(ev.get_extra("livingemotion:context"))
    records = await p.application.console_records(ctx.account_key, "emotion")
    e.check("C58.new_records_exist_before_stop", records["total"] > 0)
    data_dir = root / "data/plugin_data" / NAME
    await core.plugin_manager.turn_off_plugin(NAME)
    files = {str(f.relative_to(data_dir)): hashlib.sha256(f.read_bytes()).hexdigest()
             for f in data_dir.rglob("*") if f.is_file()}
    e.check("C58.native_stop_no_tasks", p.application.closed and not tasks())
    await p.observe_message(event("synthetic-late-after-rollback"))
    after = {str(f.relative_to(data_dir)): hashlib.sha256(f.read_bytes()).hexdigest()
             for f in data_dir.rglob("*") if f.is_file()}
    e.check("C58.stopped_target_data_unchanged", files == after and bool(files))
    # Reopen with the actual store reader; no import, restore, or destructive plan.
    store = type(p.application.store)(p.application.store.path)
    await store.open()
    try:
        retained = await store.query_records(ctx, "emotion", page=1, page_size=10)
        e.check("C58.new_records_retained", retained["total"] == records["total"],
                detail={"before": records["total"], "after": retained["total"]})
    finally:
        await store.close()
