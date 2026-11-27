"""执行宿主真实 ToolSet/FutureTaskTool/CronMessageEvent 与两个插件的图片契约。

只替换宿主启动、Provider、HTTP 与平台发送；不连接运行中的服务。
运行需要 ASTRBOT_NATIVE_SOURCE 及 --livinghello 指向配套源码。
"""

import argparse
import asyncio
import dataclasses
import enum
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, patch
import uuid


def install_native_events(fixture):
    from astrbot.api.message_components import Plain

    class BaseEvent:
        def __init__(self, message, obj, metadata, session_id):
            self.message_obj, self.platform_meta = obj, metadata
            self._extras = {}

        @property
        def unified_msg_origin(self):
            return str(self.session)

        def get_sender_id(self):
            return str(self.message_obj.sender.user_id)

        def get_extra(self, key, default=None):
            return self._extras.get(key, default)

        def set_extra(self, key, value):
            self._extras[key] = value

        def chain_result(self, chain):
            from astrbot.api.event import MessageChain
            return MessageChain(chain=chain)

    namespace = {"Enum": enum.Enum, "dataclass": dataclasses.dataclass,
                 "field": dataclasses.field, "time": time, "Any": object,
                 "BaseMessageComponent": object, "uuid": uuid, "Plain": Plain,
                 "AstrMessageEvent": BaseEvent, "MessageChain": object}
    fixture.compile_classes("core/platform/message_type.py", {"MessageType"}, namespace)
    fixture.compile_classes("core/platform/message_session.py", {"MessageSession"}, namespace)
    fixture.compile_classes("core/platform/astrbot_message.py",
                            {"MessageMember", "Group", "AstrBotMessage"}, namespace)
    fixture.compile_classes("core/platform/platform_metadata.py", {"PlatformMetadata"}, namespace)
    fixture.compile_classes("core/cron/events.py", {"CronMessageEvent"}, namespace)
    for module_name, names in (
        ("astrbot.core.platform.message_session", ["MessageSession"]),
        ("astrbot.core.cron.events", ["CronMessageEvent"]),
    ):
        module = ModuleType(module_name)
        for name in names:
            setattr(module, name, namespace[name])
        sys.modules[module_name] = module
    return namespace


async def run(livinghello):
    sys.path.insert(0, str(livinghello))
    import run_offline_tests
    run_offline_tests.install_framework_stubs()
    from astrbot.api import logger

    sys.path.insert(0, str(livinghello / "tests"))
    import host_fixtures
    from astrbot.core.agent.tool import FunctionTool, ToolSet
    from pydantic import Field
    from pydantic.dataclasses import dataclass

    namespace = install_native_events(host_fixtures)
    namespace.update(
        FunctionTool=FunctionTool, Field=Field, dataclass=dataclass,
        AstrAgentContext=object,
        builtin_tool=lambda **_: lambda cls: cls,
        _CRON_TOOL_CONFIG={},
        CronJobSchedulingError=type("CronJobSchedulingError", (Exception,), {}),
        logger=logger, ZoneInfo=__import__("zoneinfo").ZoneInfo,
        datetime=__import__("datetime").datetime, dt_timezone=__import__("datetime").timezone,
        _parse_run_at=lambda value: __import__("datetime").datetime.fromisoformat(value),
    )
    host_fixtures.compile_classes("core/tools/cron_tools.py", {"FutureTaskTool"}, namespace)
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from astrbot_plugin_livingemotion.contracts import Context, to_dict
    from astrbot_plugin_livingemotion.runtime.promise_service import PromiseService
    from astrbot_plugin_livingemotion.runtime.promise_actions import ImagePromiseAction
    from astrbot_plugin_livingemotion.storage import SQLiteStore
    from test_image_generation import Event, ImageGenerationTests

    image_fixture = ImageGenerationTests(methodName="runTest")
    image_fixture.setUp()
    image_fixture.promise_image_plugin()
    image_fixture.service.prompt_text.complete = AsyncMock(return_value="窗边橙色猫自拍")
    folder = tempfile.TemporaryDirectory()
    store = SQLiteStore(Path(folder.name) / "test.sqlite3", clock=lambda: 1800000000.0)
    await store.open()
    context = Context("bot", "persona", "adapter", "qq", "private", "human", "human",
                      route="adapter:FriendMessage:human")

    class Manager:
        def __init__(self):
            self.jobs = []

        async def list_jobs(self, job_type=None):
            return list(self.jobs)

        async def add_active_job(self, **kwargs):
            payload = {**kwargs["payload"], "run_at": kwargs["run_at"].isoformat()}
            job = SimpleNamespace(**{**kwargs, "payload": payload},
                                  job_id="native-1", next_run_time=None)
            self.jobs.append(job)
            return job

        def get_next_run_time(self, job_id):
            return None

    mgr = Manager()
    sends = []

    async def send(route, chain):
        sends.append((route, chain))
        return True
    image_fixture.context.send_message = send

    async def ready(value):
        return value

    app = SimpleNamespace(
        host=SimpleNamespace(cron_manager=mgr, get_config=lambda **_: {"timezone": "UTC"},
                             send_message=send),
        bridge=SimpleNamespace(current=lambda _: ready(None),
                               discover=lambda _: image_fixture.plugin, sources={}),
        config=SimpleNamespace(timezone="UTC", promise_enabled=True),
        revision="native", _preparation_guard=lambda *a, **k: ready(True),
        _contexts={"native": context}, persona_style=lambda *a: ready("猫"),
        purpose_model=AsyncMock(side_effect=AssertionError("LE 不负责为图片起稿")),
        promise_actions_active=lambda: False,
    )
    service = PromiseService(store, app)
    try:
        event = Event()
        event.unified_msg_origin = context.route
        event.get_sender_id = lambda: context.account_id
        event.extra["livingemotion:context"] = to_dict(context)
        tools = ToolSet()
        tools.add_tool(namespace["FutureTaskTool"]())
        request = SimpleNamespace(func_tool=tools)
        service.ownership.wrap_tools(event, request)
        wrapped = request.func_tool.get_tool("future_task")
        assert isinstance(wrapped, FunctionTool) and wrapped.handler is None
        run_context = SimpleNamespace(context=SimpleNamespace(context=app.host, event=event))
        result = await wrapped.call(
            run_context, action="create", note="提醒我给花浇水",
            run_once=True, run_at="2027-01-15T08:02:00+00:00")
        assert "Scheduled future task native-1" in result
        outcome = await service.remember(context, [("2分钟", "到时候提醒他浇花")], event=event)
        assert outcome[0]["status"] == "delegated" and len(mgr.jobs) == 1
        mgr.jobs.clear()
        created = await service.remember(context, [("2分钟", "拍一张橙色猫自拍")])
        pid = created[0]["promise_id"]
        row = await service.promises.get(pid)
        cron_event = ImagePromiseAction(service).make_event(context, row)
        assert cron_event.unified_msg_origin == context.route
        assert cron_event.get_sender_id() == context.account_id and cron_event.role == "member"
        assert cron_event.message_obj.message_id == "promise:" + pid + ":0"
        # 图链使用宿主公开构造签名，HTTP 与平台只在最后一步替换。
        from astrbot.api.event import MessageChain
        MessageChain.__init__ = lambda self, chain=None: setattr(self, "chain", chain or [])
        store.clock = lambda: 1800000120.0
        assert await service.run_due() == 1
        assert len(sends) == 1 and image_fixture.service._request.await_count == 1
        assert (await service.promises.get(pid))["status"] == "sent"
        row = await service.promises.get(pid)
        artifact = json.loads(row["action_result_json"])
        replay = await image_fixture.plugin.deliver_deferred_image(
            cron_event, artifact, authorize=lambda: ready(True))
        assert replay["status"] == "sent" and replay["reason"] == "already_sent"
        assert len(sends) == 1

        second = await service.remember(context, [("2分钟", "画一张蓝色鲸鱼图片")])
        second_id = second[0]["promise_id"]
        store.clock = lambda: 1800000240.0
        with patch.object(service.promises, "finish_image_delivery", new=AsyncMock(return_value=False)):
            assert await service.run_due() == 0
        interrupted = await service.promises.get(second_id)
        assert (interrupted["status"], interrupted["action_state"]) == ("running", "sending")
        restored = PromiseService(store, app)
        assert await restored.heal() == 1
        assert await restored.heal() == 0
        assert (await restored.promises.get(second_id))["status"] == "sent"
        traces = await store._run(lambda db: db.execute(
            "SELECT COUNT(*) FROM promise_traces WHERE promise_id=? AND kind='delivery'", (second_id,)
        ).fetchone()[0])
        assert traces == 1 and len(sends) == 2 and image_fixture.service._request.await_count == 2
        print(json.dumps({
            "status": "passed", "checks": [
                "real_toolset_wrapper", "real_future_task_creation", "same_turn_provenance",
                "real_cron_event_route_sender_role", "public_image_contract",
                "image_delivery_and_checkpoint", "unified_delivery_receipt_replay",
                "recover_missing_le_commit_from_lh_receipt"],
            "paid_requests": 0, "platform_requests": 0,
        }, ensure_ascii=False))
    finally:
        await store.close()
        folder.cleanup()
        image_fixture.doCleanups()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--livinghello", type=Path, required=True)
    options = parser.parse_args()
    if not os.environ.get("ASTRBOT_NATIVE_SOURCE"):
        raise SystemExit("ASTRBOT_NATIVE_SOURCE is required")
    asyncio.run(run(options.livinghello))
