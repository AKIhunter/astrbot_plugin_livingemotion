"""Real registry, scheduler, native events/persona and synthetic provider ports."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
import sys
import time

from retro_common import NAME, owned_tasks, plugin, product


def native_event(identifier, body="Synthetic P8 message.", *, group=False, at=None):
    from astrbot.api.message_components import At, Plain
    from astrbot.core.platform.astr_message_event import AstrMessageEvent
    from astrbot.core.platform.astrbot_message import AstrBotMessage, MessageMember
    from astrbot.core.platform.message_type import MessageType
    from astrbot.core.platform.platform_metadata import PlatformMetadata

    class SyntheticEvent(AstrMessageEvent):
        async def send(self, chain):
            self.retro_sends.append({
                "kind": "send", "hook_order": list(self.get_extra("retro:hook_order", [])),
                "result_type": str(self.get_result().result_content_type)
                if self.get_result() else None,
            })
            self._has_send_oper = True

        async def send_streaming(self, generator, *args, **kwargs):
            async for chain in generator:
                self.retro_sends.append({
                    "kind": "stream", "hook_order": list(self.get_extra("retro:hook_order", [])),
                })
            self._has_send_oper = True

        async def send_typing(self):
            return None

        async def stop_typing(self):
            return None

    msg = AstrBotMessage()
    msg.type = MessageType.GROUP_MESSAGE if group else MessageType.FRIEND_MESSAGE
    msg.self_id = "retro-bot"
    msg.group_id = "retro-group" if group else ""
    msg.message_id = identifier
    msg.message_str = body
    msg.message = ([At(qq=at)] if at is not None else []) + [Plain(text=body)]
    msg.sender = MessageMember(user_id="retro-human", nickname="Synthetic P8")
    msg.timestamp = time.time()
    event = SyntheticEvent(
        body, msg,
        PlatformMetadata(
            name="aiocqhttp", description="Synthetic only; no platform instance",
            id="retro-adapter", support_streaming_message=True,
        ),
        session_id="retro-group" if group else "retro-human",
    )
    event.retro_sends = []
    return event


async def persona_cases(core, e):
    from astrbot.core import sp
    ev = native_event("retro-persona")
    for persona_id in ("retro-config", "retro-conversation", "retro-forced"):
        await core.persona_mgr.create_persona(
            persona_id=persona_id, system_prompt=f"Synthetic persona {persona_id}.",
        )
    cfg = core.astrbot_config_mgr.get_conf(ev.unified_msg_origin)
    cfg["agent_runner"]["config"]["persona"]["persona_id"] = "retro-config"
    resolve = core.persona_mgr.resolve_selected_persona
    for label, cid, expected in (
        ("config", None, "retro-config"),
        ("conversation", "retro-conversation", "retro-conversation"),
        ("explicit_none", "[%None]", "[%None]"),
    ):
        selected = await resolve(
            umo=ev.unified_msg_origin, conversation_persona_id=cid,
            platform_name=ev.platform_meta.name,
        )
        e.check("persona." + label, selected[0] == expected,
                layer="native_persona_synthetic_storage")
    await sp.put_async(
        scope="umo", scope_id=ev.unified_msg_origin,
        key="session_service_config", value={"persona_id": "retro-forced"},
    )
    selected = await resolve(
        umo=ev.unified_msg_origin, conversation_persona_id="retro-conversation",
        platform_name=ev.platform_meta.name,
    )
    e.check("persona.forced", selected[0] == selected[2] == "retro-forced",
            layer="native_persona_synthetic_storage")
    core._retro_events = [ev]


def synthetic_provider(core):
    from astrbot.core import astrbot_config
    from astrbot.core.provider.entities import LLMResponse
    from astrbot.core.provider.provider import Provider
    from astrbot.core.provider.register import register_provider_adapter
    if hasattr(core, "_retro_provider_class"):
        provider = core._retro_provider_class()
        core.star_context.register_provider(provider)
        return provider

    @register_provider_adapter("retro_synthetic", "P8 synthetic; no model calls")
    class RetroProvider(Provider):
        def __init__(self):
            super().__init__(
                {"id": "retro-synthetic", "type": "retro_synthetic"},
                astrbot_config["provider_settings"],
            )
            self.set_model("synthetic-no-network")
            self.calls = []
            self.fail = False

        def get_current_key(self):
            return ""

        def set_key(self, key):
            pass

        async def get_models(self):
            return [self.get_model()]

        async def text_chat(self, **kwargs):
            self.calls.append({"mode": "nonstream", "kwargs": kwargs})
            if self.fail:
                raise RuntimeError("Synthetic independent P8 provider failure")
            return LLMResponse(role="assistant", completion_text="Synthetic P8 response.")

        async def text_chat_stream(self, **kwargs):
            self.calls.append({"mode": "stream", "kwargs": kwargs})
            yield LLMResponse(role="assistant", completion_text="Synthetic ", is_chunk=True)
            yield LLMResponse(role="assistant", completion_text="P8 response.", is_chunk=True)
            yield LLMResponse(role="assistant", completion_text="Synthetic P8 response.")

    core._retro_provider_class = RetroProvider
    provider = RetroProvider()
    core.star_context.register_provider(provider)
    return provider


@contextmanager
def trace_product_hook(core, e):
    from astrbot.core.star.star import star_map
    from astrbot.core.star.star_handler import EventType, star_handlers_registry

    all_handlers = star_handlers_registry.get_handlers_by_event_type(
        EventType.OnDecoratingResultEvent,
    )
    e.report["decorating_registry"] = [
        {"plugin": star_map[h.handler_module_path].name, "handler": h.handler_name,
         "priority": h.extras_configs.get("priority")}
        for h in all_handlers
    ]
    selected = [
        handler for handler in all_handlers
        if star_map[handler.handler_module_path].name == NAME
    ]
    e.check("reply.real_registered_final_hook", len(selected) == 1, fatal=True)
    target = selected[0]
    e.check(
        "reply.final_priority", target.extras_configs.get("priority") == -sys.maxsize - 1,
        detail=target.extras_configs.get("priority"),
    )
    e.check("reply.registry_last", all_handlers[-1] is target)
    original = target.handler
    calls = []

    async def observed(ev):
        order = ev.get_extra("retro:hook_order", [])
        order.append("product_enter")
        ev.set_extra("retro:hook_order", order)
        try:
            await original(ev)
        except BaseException as exc:
            calls.append({"exception": type(exc).__name__})
            raise
        calls.append({
            "id": ev.message_obj.message_id, "stopped": ev.is_stopped(),
            "result_type": str(ev.get_result().result_content_type)
            if ev.get_result() else None,
        })
        order.append("product_exit")

    target.handler = observed
    try:
        yield calls
    finally:
        target.handler = original
        e.report["decorating_dispatch"] = calls


async def pipeline_cases(core, e, *, final=False):
    provider = synthetic_provider(core)
    scheduler = next(iter(core.pipeline_scheduler_mapping.values()))
    e.report["pipeline_stages"] = [type(s).__name__ for s in scheduler.stages]
    if final:
        await product_pipeline(core, scheduler, provider, e)
        return
    try:
        ev = native_event("retro-host-default-stream")
        before = len(provider.calls)
        await asyncio.wait_for(scheduler.execute(ev), 40)
        calls = provider.calls[before:]
        e.check("stream.host_default_provider_mode",
                len(calls) == 1 and calls[0]["mode"] == "stream",
                detail=[call["mode"] for call in calls],
                layer="native_pipeline_synthetic_provider_sender")
        e.check("stream.host_default_output_before_decorating", any(
            send["kind"] == "stream" and not send["hook_order"]
            for send in ev.retro_sends
        ), detail=ev.retro_sends, layer="native_pipeline_synthetic_provider_sender")
        core._retro_events.append(ev)
        from retro_reply import output
        for clear in (False, True):
            ev = native_event("retro-sentinel-cancel-" + str(clear))
            ev.set_extra("retro:cancel", True)
            ev.set_extra("retro:clear_before_stop", clear)
            await output(scheduler, ev)
            label = "clear_stop_blocks_output" if clear else "stop_only_bypass_characterized"
            e.check("reply." + label, ev.is_stopped()
                    and (not ev.retro_sends if clear else bool(ev.retro_sends)),
                    detail={"stopped": ev.is_stopped(), "sends": ev.retro_sends,
                            "order": ev.get_extra("retro:hook_order")})
            core._retro_events.append(ev)
    finally:
        core.provider_manager.provider_insts.remove(provider)


async def product_pipeline(core, scheduler, provider, e):
    try:
        with trace_product_hook(core, e) as dispatch:
            ev = native_event("retro-product-reply")
            from astrbot.core import astrbot_config
            e.check("stream.fixture_does_not_disable_request",
                    ev.get_extra("enable_streaming") is None, fatal=True)
            await plugin(core).observe_message(ev)
            e.check("stream.product_observer_disables_request",
                    ev.get_extra("enable_streaming") is False, fatal=True)
            e.check("stream.host_global_remains_enabled",
                    astrbot_config["provider_settings"]["streaming_response"] is True)
            before = len(provider.calls)
            await asyncio.wait_for(scheduler.execute(ev), 40)
            calls = provider.calls[before:]
            e.check("reply.product_disables_streaming_before_capture",
                    len(calls) == 1 and calls[0]["mode"] == "nonstream",
                    detail=[call["mode"] for call in calls])
            e.check("reply.final_dispatch_before_output",
                    len(ev.retro_sends) == 1
                    and ev.retro_sends[0]["hook_order"] ==
                    ["sentinel", "product_enter", "product_exit"],
                    detail=ev.retro_sends)
            e.check("reply.final_hook_did_not_throw",
                    bool(dispatch) and all("exception" not in call for call in dispatch))
            raw = ev.get_extra("livingemotion:context")
            e.check("event.native_context_resolved", bool(raw), fatal=True)
            ctx = product("contracts").Context.from_dict(raw)
            e.check("persona.product_native_persona", ctx.persona_id == "retro-forced")
            core._retro_events.append(ev)
            e.report["synthetic_context"] = ctx.to_dict() if hasattr(ctx, "to_dict") else raw
        await admin_wake_cases(core, scheduler, provider, e)
        await final_request_cases(core, scheduler, provider, e)
    finally:
        core.provider_manager.provider_insts.remove(provider)


async def final_request_cases(core, scheduler, provider, e):
    from astrbot.core import astrbot_config
    from astrbot.core.star.star import star_map
    from astrbot.core.star.star_handler import EventType, star_handlers_registry
    from retro_reply import CONFIG, at, observe

    handlers = star_handlers_registry.get_handlers_by_event_type(EventType.OnLLMRequestEvent)
    e.report["request_registry"] = [
        {"plugin": star_map[h.handler_module_path].name, "handler": h.handler_name,
         "priority": h.extras_configs.get("priority")}
        for h in handlers
    ]
    selected = [h for h in handlers if star_map[h.handler_module_path].name == NAME
                and h.handler_name == "buffer_final_request"]
    e.check("request.real_final_buffer_registry", len(selected) == 1, fatal=True)
    target = selected[0]
    e.check("request.buffer_priority_and_last", handlers[-1] is target
            and target.extras_configs.get("priority") == -sys.maxsize - 1)
    app = plugin(core).application
    saved_config, saved_clock = dict(app.native_config), app.store.clock
    app.native_config.update({**CONFIG, "allow_sleep": False, "wake_reply_limit": 20})
    await app.refresh_config()
    app.store.clock = lambda: at(12)
    original = target.handler
    calls = []

    async def observed(ev, req):
        before = ev.get_extra("enable_streaming")
        await original(ev, req)
        calls.append({
            "id": ev.message_obj.message_id, "before": before,
            "after": ev.get_extra("enable_streaming"), "stopped": ev.is_stopped(),
        })

    target.handler = observed
    try:
        for mode in ("restore_streaming", "early_live", "late_live"):
            ev, ctx = await observe(core, "retro-request-" + mode,
                                    "retro-request-persona-" + mode, at(12))
            ev.set_extra("retro:restore_streaming", True)
            if mode == "early_live":
                ev.set_extra("action_type", "live")
            if mode == "late_live":
                ev.set_extra("retro:late_live", True)
            before = await app.night_snapshot(ctx)
            call_count = len(provider.calls)
            dispatch_count = len(calls)
            await asyncio.wait_for(scheduler.execute(ev), 40)
            after = await app.night_snapshot(ctx)
            energy = await app.store.energy_history(ctx, category="reply")
            modes = [c["mode"] for c in provider.calls[call_count:]]
            if mode == "restore_streaming":
                e.check("request.native_last_buffer_restores_false",
                        len(calls) == dispatch_count + 1
                        and calls[-1]["before"] is True and calls[-1]["after"] is False
                        and modes == ["nonstream"] and len(ev.retro_sends) == 1)
            else:
                e.check("request.native_" + mode + "_zero_output",
                        ev.is_stopped() and not ev.retro_sends and not modes
                        and energy["total"] == 0
                        and ev.get_extra("livingemotion:unavailable") == "live_submission_unsupported",
                        detail={"provider_modes": modes, "sends": len(ev.retro_sends),
                                "reply_energy_events": energy["total"]})
                if mode == "early_live":
                    e.check("request.early_live_never_admitted",
                            ev.get_extra("livingemotion:reply_lease") is None
                            and before.wake_replies_used == after.wake_replies_used)
                else:
                    e.check("request.late_live_last_handler_dispatched",
                            len(calls) == dispatch_count + 1 and calls[-1]["stopped"]
                            and calls[-1]["before"] is True and calls[-1]["after"] is False)
        e.check("request.global_streaming_unmodified",
                astrbot_config["provider_settings"]["streaming_response"] is True)
    finally:
        target.handler = original
        app.store.clock = saved_clock
        app.native_config.clear()
        app.native_config.update(saved_config)
        await app.refresh_config()
        e.report["final_request_dispatch"] = calls


async def admin_wake_cases(core, scheduler, provider, e):
    from astrbot.core import astrbot_config
    for admin in (False, True):
        ev = native_event("retro-admin-wake-" + str(admin), "/le_wake")
        ev.set_extra("admin", True)
        ev.set_extra("livingemotion:control_request", "admin")
        before = len(provider.calls)
        if admin:
            astrbot_config["admins_id"].append(ev.get_sender_id())
        try:
            await asyncio.wait_for(scheduler.execute(ev), 40)
        finally:
            if admin:
                astrbot_config["admins_id"].remove(ev.get_sender_id())
        if admin:
            e.check("wake.native_admin_command_accepted",
                    ev.get_extra("livingemotion:control_request") in ("wake", "admin")
                    and bool(ev.retro_sends) and len(provider.calls) == before)
        else:
            e.check("wake.forged_admin_command_denied",
                    ev.get_extra("livingemotion:control_request") not in ("wake", "admin"))
        core._retro_events.append(ev)


async def lifecycle_cases(core, e, *, final=False):
    if not final:
        before = core.star_context.get_registered_star("livingemotion_retro_probe").star_cls
        ok, _ = await core.plugin_manager.reload("livingemotion_retro_probe")
        after = core.star_context.get_registered_star("livingemotion_retro_probe").star_cls
        e.check("lifecycle.fixture_real_reload", ok and before is not after)
        return
    p = plugin(core)
    original_id = p.application.instance_id
    for iteration in range(2):
        old, tasks = p, owned_tasks()
        ok, _ = await core.plugin_manager.reload(NAME)
        e.check(f"lifecycle.real_reload_manager_{iteration}", ok, fatal=True)
        p = plugin(core)
        e.check(f"lifecycle.product_reload_{iteration}", ok and old is not p
                and old.application.closed and all(task.done() for task in tasks)
                and p.application.instance_id == original_id)
        routes = [r[0] for r in core.star_context.registered_web_apis
                  if r[0].startswith("/" + NAME + "/console/")]
        e.check(f"lifecycle.ten_unique_routes_{iteration}",
                len(routes) == len(set(routes)) == 10)
    old_api, old_page = p.api, p.page_api
    tasks = owned_tasks()
    await p.terminate()
    e.check("lifecycle.product_terminated", p.application.closed
            and all(task.done() for task in tasks))
    result = await old_api.get_health()
    e.check("lifecycle.retained_api_closed", result.get("status") != "ok")
    e.check("lifecycle.retained_page_closed", old_page._closed is True)
