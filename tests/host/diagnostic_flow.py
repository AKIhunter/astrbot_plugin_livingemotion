"""Replay one native request and its duplicate through AstrBot's real dispatcher."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
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
    from astrbot.core import astrbot_config
    from astrbot.core.pipeline.context_utils import call_event_hook
    from astrbot.core.platform.astr_message_event import AstrMessageEvent
    from astrbot.core.platform.astrbot_message import AstrBotMessage, MessageMember
    from astrbot.core.platform.message_type import MessageType
    from astrbot.core.platform.platform_metadata import PlatformMetadata
    from astrbot.core.star.star_handler import EventType, star_handlers_registry
    from astrbot.core.utils.trace import trace_execution
    from astrbot.core.utils.trace_store import close_trace_store
    from astrbot_plugin_livingemotion.main import LivingEmotionPlugin
    from astrbot_plugin_livingemotion.runtime.diagnostics import prepare as le_prepare
    from astrbot_plugin_LivingHello.observability.guard_diagnostics import prepare as lh_prepare, start
    from astrbot_plugin_LivingHello.observability.guard_request_trace import RequestTrace
    from test_application import application

    astrbot_config["trace_enable"] = True
    astrbot.logger.setLevel("INFO")
    le, host, _ = await application(root / "le", {
        "timezone": "UTC", "night_policy_version": 2, "allow_sleep": False,
        "weather_factor_enabled": False,
    })
    entry = object.__new__(LivingEmotionPlugin)
    entry.application = le
    lh = SimpleNamespace(context=host, data_dir=root / "lh", config={},
                         engine=SimpleNamespace(log=SimpleNamespace(),
                                                min_length=lambda: 2, threshold=lambda: 65))
    lh.diagnostics = start(lh)
    lh.request_trace = RequestTrace(lh, lh.data_dir)

    def event():
        message = AstrBotMessage()
        message.type = MessageType.FRIEND_MESSAGE
        message.self_id, message.session_id = "synthetic-bot", "synthetic-session"
        message.sender = MessageMember(user_id="synthetic-human", nickname="synthetic")
        message.message_id = "private-fixture-message-id"
        message.message_str, message.message = "private-fixture-body", []
        message.raw_message = {"post_type": "message", "message_type": "private"}
        return AstrMessageEvent(message.message_str, message,
                                PlatformMetadata("aiocqhttp", "offline", "synthetic"), message.session_id)

    async def dispatch(incoming, hook, callback, *args):
        handler = SimpleNamespace(
            handler=callback, event_type=hook, handler_name=callback.__name__,
            handler_full_name="fixture_" + callback.__name__,
            handler_module_path="astrbot_plugin_livingemotion",
        )
        with patch.object(star_handlers_registry, "get_handlers_by_event_type", return_value=[handler]):
            return await call_event_hook(incoming, hook, *args)

    try:
        events = [event(), event()]
        for index, incoming in enumerate(events):
            with trace_execution(incoming.trace):
                lh.request_trace.begin(incoming)
                stopped = await dispatch(incoming, EventType.OnLLMRequestEvent, entry.supplement_request,
                                         SimpleNamespace(extra_user_content_parts=[]))
                assert stopped is (index == 1)
                if not stopped:
                    await dispatch(incoming, EventType.OnAgentBeginEvent, entry.observe_agent_begin, None)
                    await dispatch(incoming, EventType.OnAgentDoneEvent, entry.observe_agent_done, None, None)

        le_rows, lh_rows = runtime_rows(le_prepare, le), runtime_rows(lh_prepare, lh)
        denied, = [r for r in le_rows if r.get("stage") == "supplement_request" and r["status"] == "stopped"]
        assert denied["reason_code"] == "reply_exists"
        assert denied["host_trace_id"] == events[1].trace.trace_id
        agent = [r for r in le_rows if r.get("stage") in {"agent_begin", "agent_done"}]
        assert [r["stage"] for r in agent] == ["agent_begin", "agent_done"]
        assert {r["host_trace_id"] for r in agent} == {events[0].trace.trace_id}
        for rows in (le_rows, lh_rows):
            stopped, = [r for r in rows if r["operation"] == "host_stop"]
            assert stopped["flow_id"] == denied["flow_id"] and stopped["host_trace_id"] == denied["host_trace_id"]
        lh_receive, = [r for r in lh_rows if r.get("stage") == "receive" and r["flow_id"] == denied["flow_id"]]
        assert lh_receive["native_post_type"] == denied["native_post_type"] == "message"
    finally:
        await lh.request_trace.close()
        lh.diagnostics.close()
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
        print("Two ZIPs joined by flow_id and native host_trace_id; duplicate stopped by reply_exists.")


if __name__ == "__main__":
    main()
