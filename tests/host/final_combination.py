"""Native pipelines/registries with explicit synthetic provider and sender ports."""

import asyncio
from contextlib import nullcontext
import importlib
from types import SimpleNamespace
from unittest.mock import patch

from final_checks import NAME, SUFFIX, event, plugin, product, setup_persona


def synthetic_event(identifier, body="A short synthetic message."):
    ev = event(identifier, body)
    ev.synthetic_sends = []

    async def send(chain):
        ev.synthetic_sends.append(chain)
        # The adapter port deliberately has no delivery or telemetry network.
        ev._has_send_oper = True

    ev.send = send
    return ev


async def pipelines(core, e):
    from astrbot.core import astrbot_config
    from astrbot.core.provider.provider import Provider
    from astrbot.core.provider.entities import LLMResponse
    from astrbot.core.provider.register import register_provider_adapter

    @register_provider_adapter("final_synthetic", "Acceptance-only, never calls a model")
    class SyntheticProvider(Provider):
        def __init__(self):
            super().__init__({"type": "final_synthetic", "id": "final-synthetic"},
                             astrbot_config["provider_settings"])
            self.set_model("synthetic-no-network")
            self.calls = []

        def get_current_key(self):
            return ""

        def set_key(self, key):
            pass

        async def get_models(self):
            return [self.get_model()]

        async def text_chat(self, **kwargs):
            self.calls.append(kwargs)
            return LLMResponse(role="assistant", completion_text="Synthetic ordinary reply.")

    provider = SyntheticProvider()
    core.star_context.register_provider(provider)
    scheduler = next(iter(core.pipeline_scheduler_mapping.values()))
    e.report["pipeline_stages"] = [type(stage).__name__ for stage in scheduler.stages]
    try:
        for fault in (False, True):
            ev = synthetic_event(f"synthetic-pipeline-{fault}")
            await setup_persona(core, ev)
            ev.set_extra("enable_streaming", False)
            before = len(provider.calls)

            async def failed_read(*args, **kwargs):
                raise OSError("synthetic storage read failure")

            injector = patch.object(plugin(core).application.store, "get_state", failed_read)
            with injector if fault else nullcontext():
                await asyncio.wait_for(scheduler.execute(ev), 35)
            calls = provider.calls[before:]
            prefix = "C52.read_fault" if fault else "C42.ordinary_pipeline"
            e.check(prefix + ".one_provider_call", len(calls) == 1,
                    layer="native_pipeline_synthetic_provider_sender", detail=len(calls))
            e.check(prefix + ".one_reply", len(ev.synthetic_sends) == 1,
                    layer="native_pipeline_synthetic_provider_sender",
                    detail=len(ev.synthetic_sends))
            count = sum(getattr(part, "text", "").startswith(SUFFIX)
                        for call in calls for part in call.get("extra_user_content_parts", []))
            e.check(prefix + ".suffix_count", count == (0 if fault else 1),
                    layer="native_pipeline_synthetic_provider_sender", detail=count)
            if calls and not fault:
                prompt = calls[0].get("system_prompt", "") or ""
                for message in calls[0].get("contexts", []):
                    data = message.model_dump() if hasattr(message, "model_dump") else message
                    if data.get("role") == "system":
                        prompt += str(data.get("content", ""))
                e.check("C05.pipeline_native_persona_once",
                        prompt.count("Synthetic native persona synthetic-persona-a.") == 1,
                        layer="native_pipeline_synthetic_provider_sender")
            core._final_synthetic_events.append(ev)

        p = plugin(core)
        p.application.native_config.update(night_enabled=True, night_block_chat=True)
        await p.application.refresh_config()
        scope_event = synthetic_event("synthetic-sleep")
        await setup_persona(core, scope_event)
        await p.observe_message(scope_event)
        ctx = product("contracts").Context.from_dict(scope_event.get_extra("livingemotion:context"))
        await p.application.advance_scope(ctx, action="night.sleep")
        for kind in ("ordinary", "admin", "wake"):
            ev = synthetic_event("synthetic-control-" + kind,
                                 "/le_wake" if kind == "wake" else "Synthetic control check.")
            ev.set_extra("enable_streaming", False)
            if kind == "admin":
                astrbot_config["admins_id"].append(ev.get_sender_id())
            before = len(provider.calls)
            try:
                await asyncio.wait_for(scheduler.execute(ev), 35)
            finally:
                if kind == "admin":
                    astrbot_config["admins_id"].remove(ev.get_sender_id())
            if kind == "ordinary":
                e.check("C31.pipeline_sleep_blocks_ordinary",
                        ev.is_stopped() and len(provider.calls) == before
                        and not ev.synthetic_sends)
            elif kind == "admin":
                e.check("C31.native_admin_exempt", ev.is_admin()
                        and len(provider.calls) == before + 1 and len(ev.synthetic_sends) == 1,
                        detail={"native_admin": ev.is_admin(), "stopped": ev.is_stopped(),
                                "provider_calls": len(provider.calls) - before,
                                "sends": len(ev.synthetic_sends),
                                "trusted_extra": ev.get_extra("livingemotion:control_request")})
            else:
                e.check("C31.registered_wake_pipeline",
                        ev.get_extra("livingemotion:control_request") == "wake"
                        and len(provider.calls) == before and len(ev.synthetic_sends) == 1)
            core._final_synthetic_events.append(ev)
        p.application.native_config["night_block_chat"] = False
        await p.application.refresh_config()
        await p.application.advance_scope(ctx, action="night.wake")
    finally:
        core.provider_manager.provider_insts.remove(provider)


async def behavior_persona(core, e):
    from astrbot.core import sp

    p = plugin(core)
    ev = event("synthetic-generated-persona")
    await setup_persona(core, ev)
    await p.observe_message(ev)
    ctx = product("contracts").Context.from_dict(ev.get_extra("livingemotion:context"))
    original = dict(p.application.native_config)
    calls, sends = [], []
    from astrbot.core.platform.platform_metadata import PlatformMetadata

    async def send_by_session(session, chain):
        sends.append((str(session), len(chain.chain)))

    adapter = SimpleNamespace(
        meta=lambda: PlatformMetadata(id="synthetic-adapter", name="aiocqhttp",
                                      description="Synthetic sender port"),
        send_by_session=send_by_session)
    core.platform_manager.platform_insts.append(adapter)
    original_binding = p.application.model_binding
    change_persona = True

    class Binding:
        fingerprint = "acceptance-only-synthetic"

        def count(self, system, data):
            return len((system + data).encode()) + 256

        async def generate(self, system, data, output_tokens, timeout):
            calls.append(True)
            output = "Synthetic generated message."
            if change_persona:
                await sp.put_async(scope="umo", scope_id=ev.unified_msg_origin,
                                   key="session_service_config",
                                   value={"persona_id": "synthetic-persona-b"})
            return output

    async def binding(context):
        if not await p.application.validate_context(context):
            raise ValueError("context_changed")
        return Binding()

    try:
        p.application.native_config.update(
            autonomy_enabled=True, autonomy_scopes=ctx.scope_key, timezone="UTC",
            model_input_tokens=16384, memory_mode="none")
        await p.application.refresh_config()
        p.application.model_binding = binding
        relation = await p.application.store.get_state(ctx, "relationship", ctx.account_id)
        await p.application.correct_relationship(
            ctx.account_key, expected_version=relation.version, score=900,
            reason="synthetic acceptance", actor_id="synthetic-admin")
        result = await asyncio.wait_for(
            p.application.behavior.execute(ctx, intent_id="synthetic-persona-switch"), 10)
        e.check("C06.generated_then_native_persona_switch_cancels",
                len(calls) == 1 and not sends and result.status == "cancelled",
                layer="real_behavior_native_persona_synthetic_model_sender",
                detail={"model_calls": len(calls), "sender_calls": len(sends),
                        "status": result.status, "reason": result.reason_codes})
        e.check("C06.old_scope_state_retained_after_cancel",
                (await p.api.get_bot_state(ctx)).get("status") == "ok")
        core._final_synthetic_events.append(ev)
        ev = event("synthetic-bool-material", "Fresh synthetic evidence after persona restoration.")
        await setup_persona(core, ev)
        await p.observe_message(ev)
        ctx = product("contracts").Context.from_dict(ev.get_extra("livingemotion:context"))
        change_persona = False
        result = await asyncio.wait_for(
            p.application.behavior.execute(ctx, intent_id="synthetic-bool"), 10)
        e.check("C04.native_send_message_bool_unknown",
                len(sends) == 1 and result.status == "unknown" and not result.receipt_recorded,
                layer="real_host_send_message_synthetic_platform",
                detail={"sends": len(sends), "status": result.status, "reason": result.reason_codes})
        before = len(sends)
        again = await p.application.behavior.execute(ctx, intent_id="synthetic-bool")
        e.check("C04.unknown_not_retried", again.status == "unknown" and len(sends) == before)
    finally:
        p.application.model_binding = original_binding
        p.application.native_config.clear()
        p.application.native_config.update(original)
        await p.application.refresh_config()
        core.platform_manager.platform_insts.remove(adapter)
        core._final_synthetic_events.append(ev)


async def consumers(core, e):
    bridge = importlib.import_module("data.plugins.BiliBot.core.emotion_bridge")
    bili_name = "astrbot_plugin_bilibili_ai_bot"
    bili = core.star_context.get_registered_star(bili_name).star_cls
    expected = {NAME, "astrbot_plugin_at_guard", "astrbot_plugin_livingmemory", bili_name}
    actual = {m.name for m in core.star_context.get_all_stars() if m.activated}
    e.check("C42.four_real_instances", expected <= actual, detail=sorted(actual))
    chosen, api, _ = await bridge._provider(bili, "ingest_event")
    e.check("C40.actual_bili_prefers_livingemotion", chosen == "livingemotion" and api is plugin(core).api)
    result = await bridge._report(
        bili, "synthetic-author", "Synthetic", 5, "comment",
        source_id="synthetic-comment-1", occurred_at=__import__("time").time(),
        bot_account="synthetic-bili-bot",
        source_scene={"comment_type": "1", "oid": "synthetic-video", "thread_id": "synthetic-thread"})
    e.check("C40.actual_bili_neutral_public_ingest",
            isinstance(result, dict) and result.get("status") in ("accepted", "duplicate"),
            detail=result)
    for target in ("astrbot_plugin_at_guard", NAME, bili_name):
        old = plugin(core).api
        ok, _ = await core.plugin_manager.reload(target)
        bili = core.star_context.get_registered_star(bili_name).star_cls
        chosen, api, _ = await bridge._provider(bili, "ingest_event")
        e.check("C43.rediscover_after_reload_" + target, ok and chosen == "livingemotion"
                and api is plugin(core).api and (target != NAME or api is not old))
