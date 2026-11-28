"""Replay peer vetoes and same-ID requests through AstrBot's real dispatcher."""
import argparse
import asyncio
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch
import zipfile

from retro_common import network_guard


def runtime_rows(prepare, plugin):
    recorder, snapshot, sources = prepare(plugin)
    bundle = recorder.export(snapshot, sources)
    try:
        with zipfile.ZipFile(bundle.path) as archive:
            content = archive.read("runtime.jsonl").decode()
        assert "private-fixture" not in content
        return [json.loads(line) for line in content.splitlines()]
    finally:
        bundle.close()


async def replay(root):
    import astrbot
    from astrbot.api.provider import ProviderRequest
    from astrbot.core import astrbot_config
    from astrbot.core.message.message_event_result import ResultContentType
    from astrbot.core.pipeline.context_utils import call_event_hook
    from astrbot.core.platform.astr_message_event import AstrMessageEvent
    from astrbot.core.platform.astrbot_message import AstrBotMessage, MessageMember
    from astrbot.core.platform.message_type import MessageType
    from astrbot.core.platform.platform_metadata import PlatformMetadata
    from astrbot.core.star.star import star_map
    from astrbot.core.star.star_handler import (
        EventType, StarHandlerMetadata, StarHandlerRegistry, star_handlers_registry,
    )
    from astrbot.core.utils.trace import trace_execution
    from astrbot.core.utils.trace_store import close_trace_store
    from astrbot_plugin_livingemotion.main import LivingEmotionPlugin
    from astrbot_plugin_livingemotion.runtime.diagnostics import prepare as le_prepare
    from astrbot_plugin_LivingHello.main import Main as LivingHello, PLUGIN_NAME as LH_NAME
    from astrbot_plugin_LivingHello.observability.guard_diagnostics import prepare as lh_prepare
    from test_application import application

    astrbot_config["trace_enable"] = True
    astrbot.logger.setLevel("INFO")
    le, host, _ = await application(root / "le", {
        "timezone": "UTC", "night_policy_version": 2, "allow_sleep": False,
        "weather_factor_enabled": False,
    })
    entry = object.__new__(LivingEmotionPlugin)
    entry.application, entry.context = le, host
    star_map[LivingHello.__module__].name = LH_NAME  # Normally populated by the plugin loader.
    lh = LivingHello(host, {"reply_early_ack_seconds": 0, "duplicate_window_seconds": 120})

    def event(identifier, *, group=False, debounce=False):
        message = AstrBotMessage()
        message.type = MessageType.GROUP_MESSAGE if group else MessageType.FRIEND_MESSAGE
        message.group_id = "synthetic-group" if group else ""
        message.self_id = "synthetic-bot"
        message.session_id = "synthetic-group" if group else "synthetic-human"
        message.sender = MessageMember(user_id="synthetic-human", nickname="synthetic")
        message.message_id = "private-fixture-" + identifier
        message.message_str, message.message = "private-fixture-body", []
        message.raw_message = {"post_type": "message", "message_type": "group" if group else "private"}
        incoming = AstrMessageEvent(message.message_str, message,
                                    PlatformMetadata("aiocqhttp", "offline", "synthetic"), message.session_id)
        incoming.is_at_or_wake_command = group  # First exercises dedup; retry bypasses classifier.
        incoming.set_extra("fixture:debounce", debounce)
        return incoming

    async def debounce_veto(incoming, request):
        if incoming.get_extra("fixture:debounce"):
            incoming.stop_event()

    registry = StarHandlerRegistry()
    selected = {
        entry: {"supplement_request", "buffer_final_request", "arbitrate_future_tasks",
                "admit_final_request", "observe_agent_begin", "observe_agent_done"},
        lh: {"guard_llm_request", "verify_image_tool"},
    }
    for plugin, names in selected.items():
        own = star_handlers_registry.get_handlers_by_module_name(type(plugin).__module__)
        for metadata in own:
            if metadata.handler_name in names:
                registry.append(replace(metadata, handler=getattr(plugin, metadata.handler_name)))
    request_hook = EventType.OnLLMRequestEvent
    registry.append(StarHandlerMetadata(
        request_hook, "fixture_debounce", "on_llm_request", "astrbot_plugin_debounce",
        debounce_veto, [], extras_configs={"priority": 100},
    ))
    request_handlers = registry.get_handlers_by_event_type(request_hook, only_activated=False)
    assert [handler.handler_name for handler in request_handlers] == [
        "supplement_request", "guard_llm_request", "on_llm_request", "buffer_final_request",
        "arbitrate_future_tasks", "verify_image_tool", "admit_final_request",
    ]

    def handlers(hook, **_):
        return registry.get_handlers_by_event_type(hook, only_activated=False)

    generated = []

    async def dispatch(incoming):
        with trace_execution(incoming.trace):
            if await call_event_hook(incoming, request_hook, ProviderRequest(prompt="fixture")):
                assert incoming.get_extra("livingemotion:reply_attempt") is None
                assert incoming.get_extra("livingemotion:reply_lease") is None
                return False
            assert incoming.get_extra("livingemotion:reply_attempt") == 1
            assert incoming.get_extra("livingemotion:reply_lease")
            generated.append(incoming.trace.trace_id)
            await call_event_hook(incoming, EventType.OnAgentBeginEvent, None)
            await call_event_hook(incoming, EventType.OnAgentDoneEvent, None, None)
            return True

    async def statuses(incoming):
        from astrbot_plugin_livingemotion.contracts import Context, stable_key
        context = Context.from_dict(incoming.get_extra("livingemotion:context"))
        reply_id = stable_key("native-reply", context.scope_key, incoming.message_obj.message_id, 0)
        return await le.store._run(lambda db: [row["status"] for row in db.execute(
            "SELECT status FROM reply_attempts WHERE reply_id=?", (reply_id,))])

    try:
        with patch.object(star_handlers_registry, "get_handlers_by_event_type", side_effect=handlers):
            first, allowed, duplicate = event("debounce", debounce=True), event("debounce"), event("debounce")
            assert not await dispatch(first) and await statuses(first) == [] and not generated
            assert await dispatch(allowed) and await statuses(allowed) == ["started"]
            # No transport receipt is produced after host submission.
            allowed.set_result(allowed.plain_result("synthetic answer").set_result_content_type(
                ResultContentType.LLM_RESULT))
            assert await le.on_reply_submitted(allowed) is True
            assert not await dispatch(duplicate) and await statuses(duplicate) == ["submitted"]
            assert generated == [allowed.trace.trace_id]

            a, b = [event("both-vetoed", debounce=True) for _ in range(2)]
            assert not await dispatch(a) and not await dispatch(b)
            assert await statuses(a) == [] and len(generated) == 1

            group_veto, group_retry = event("lh", group=True), event("lh", group=True)
            fingerprint = lh._fingerprint(group_veto.message_str)
            key = (lh._group_key(group_veto), fingerprint)
            lh.replied_fingerprints[key] = time.monotonic()
            assert not await dispatch(group_veto) and await statuses(group_veto) == []
            lh.replied_fingerprints[key] -= 121  # Advance beyond the existing LH dedup window.
            assert await dispatch(group_retry) and await statuses(group_retry) == ["started"]

            one, two = [event("parallel") for _ in range(2)]
            assert sorted(await asyncio.gather(dispatch(one), dispatch(two))) == [False, True]
            assert await statuses(one) == ["started"] and len(generated) == 3

        le_rows, lh_rows = runtime_rows(le_prepare, le), runtime_rows(lh_prepare, lh)
        duplicate_trace = duplicate.trace.trace_id
        denied, = [r for r in le_rows if r.get("stage") == "admit_final_request"
                   and r["status"] == "stopped" and r["host_trace_id"] == duplicate_trace]
        assert denied["reason_code"] == "reply_exists"
        vetoed = {ev.trace.trace_id for ev in (first, a, b, group_veto)}
        assert not any(r.get("stage") == "reply_admission" and r.get("host_trace_id") in vetoed for r in le_rows)
        agent = [r for r in le_rows if r.get("stage") in {"agent_begin", "agent_done"}]
        assert len(agent) == 2 * len(generated)
        assert {r["host_trace_id"] for r in agent} == set(generated)
        for rows in (le_rows, lh_rows):
            stopped, = [r for r in rows if r["operation"] == "host_stop"
                        and r.get("host_trace_id") == duplicate_trace]
            assert stopped["flow_id"] == denied["flow_id"] and stopped["host_trace_id"] == denied["host_trace_id"]
        stops = {r["host_trace_id"]: r["handler"] for r in le_rows if r["operation"] == "host_stop"}
        assert stops[group_veto.trace.trace_id] == "guard_llm_request"
        assert stops[first.trace.trace_id] == "on_llm_request"
        lh_receive, = [r for r in lh_rows if r.get("stage") == "receive" and r["flow_id"] == denied["flow_id"]]
        assert lh_receive["native_post_type"] == denied["native_post_type"] == "message"
    finally:
        await lh.terminate()
        await le.terminate()
        close_trace_store()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host-source", required=True, type=Path)
    parser.add_argument("--lh", required=True, type=Path)
    args = parser.parse_args()
    le_path = Path(__file__).resolve().parents[2]
    with TemporaryDirectory(prefix="lhl-evidence-") as folder:
        root = Path(folder)
        (root / "astrbot_plugin_livingemotion").symlink_to(le_path)
        (root / "astrbot_plugin_LivingHello").symlink_to(args.lh.resolve(strict=True))
        sys.path[:0] = [str(args.host_source.resolve(strict=True)), folder, str(le_path / "tests/integration")]
        os.environ.update(ASTRBOT_ROOT=str(root), ASTRBOT_TEST_MODE="true", ASTRBOT_DISABLE_METRICS="1")
        blocked = []
        network_guard(blocked)
        asyncio.run(replay(root))
        assert not blocked, blocked
        print("Native veto/replay/concurrency passed: 3 synthetic generations, 0 real model calls.")
        print("Both diagnostic ZIPs attribute the true duplicate to reply_exists.")


if __name__ == "__main__":
    main()
