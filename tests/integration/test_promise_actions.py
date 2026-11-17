"""虚拟时间、真实 SQLite、隔离生图/宿主发送；绝不访问收费接口。"""

import asyncio
import json
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from types import ModuleType, SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.runtime.promise_actions import ImagePromiseAction, needs_image
from astrbot_plugin_livingemotion.runtime.promise_actions import DELIVERY_CONTRACT
from astrbot_plugin_livingemotion.livinghello_coupling import NAMES, discover
from astrbot_plugin_livingemotion.runtime.promise_ownership import same_action
from astrbot_plugin_livingemotion.runtime.promise_service import PromiseService
from astrbot_plugin_livingemotion.contracts import to_dict
from test_retro_reply import FinalMessage, at_time


class Event:
    def __init__(self, source_id="source"):
        self.extra = {}
        self.message_obj = SimpleNamespace(message_id=source_id)

    def get_extra(self, key):
        return self.extra.get(key)

    def set_extra(self, key, value):
        self.extra[key] = value


class Manager:
    def __init__(self):
        self.jobs = []
        self.creates = 0
        self.fault = False

    async def list_jobs(self, job_type=None):
        if self.fault:
            raise OSError("isolated list failure")
        return list(self.jobs)

    def add(self, context, note, due_at, **changes):
        self.creates += 1
        job = SimpleNamespace(
            job_id="host-" + str(self.creates), enabled=True, run_once=True,
            timezone="UTC", description=note,
            payload={"session": context.route, "sender_id": context.account_id, "note": note,
                     "run_at": datetime.fromtimestamp(due_at, timezone.utc).isoformat()},
        )
        job.__dict__.update(changes)
        self.jobs.append(job)
        return job


@pytest.fixture
async def scenario(le_store, le_context, tmp_path, monkeypatch):
    clock = [1_800_000_000.0]
    le_store.clock = lambda: clock[0]
    mgr = Manager()
    sends, marks = [], []
    file = tmp_path / "generated.png"
    file.write_bytes(b"\x89PNG\r\n\x1a\nisolated")

    class Peer:
        available = True
        calls = 0
        result = "generated"
        hold = None

        def get_deferred_image_contract(self):
            return {"contract": "livinghello.deferred-image.v1", "available": self.available}

        async def generate_deferred_image(self, event, prompt):
            self.calls += 1
            if getattr(self, "started", None) is not None:
                self.started.set()
            if self.hold:
                await self.hold.wait()
            return {"status": self.result, "path": str(file),
                    "request_id": "image-1", "revised": "橙色猫的自拍"}

        def complete_deferred_image(self, request_id, status):
            marks.append((request_id, status))

    peer = Peer()

    async def current(_):
        return None

    async def purpose(*args, **kwargs):
        return "窗边的橙色猫自拍"

    async def guard(*args, **kwargs):
        return app.allowed

    async def host_send(route, chain):
        sends.append((route, chain))
        if isinstance(app.send_result, BaseException):
            raise app.send_result
        return app.send_result

    async def compose(*_):
        return "到点了 给花浇水", []

    async def text_send(*args, **kwargs):
        app.text_sends += 1
        return "sent"

    app = SimpleNamespace(
        config=SimpleNamespace(timezone="UTC", promise_trace_ttl_hours=24),
        revision="revision", allowed=True, send_result=True, text_sends=0,
        host=SimpleNamespace(cron_manager=mgr, send_message=host_send,
                             get_config=lambda **_: {"timezone": "UTC"}),
        bridge=SimpleNamespace(current=current, discover=lambda _: peer, sources={}),
        _contexts={"source": le_context}, purpose_model=purpose,
        _preparation_guard=guard,
        persona_style=lambda *_: ready("猫"),
        promise_actions_active=lambda: False, compose_promise=compose, send_promise_notice=text_send,
    )
    service = PromiseService(le_store, app)
    monkeypatch.setattr(ImagePromiseAction, "make_event", lambda *args: Event("promise-fixed"))
    monkeypatch.setattr(ImagePromiseAction, "image_chain", staticmethod(lambda path: ("image", path)))
    return SimpleNamespace(service=service, app=app, peer=peer, mgr=mgr, clock=clock,
                           context=le_context, sends=sends, marks=marks, file=file)


async def ready(value):
    return value


async def add(s, description="拍一张橙色猫自拍"):
    created = await s.service.remember(s.context, [("2分钟", description)])
    pid = created[0]["promise_id"]
    s.clock[0] += 120
    return pid


@pytest.mark.parametrize("description,result", [
    ("拍一张自拍", True), ("画一张窗边的猫", True), ("生成图片给我", True),
    ("提醒我拍一张照片", False), ("提醒给花浇水", False), ("找昨晚的歌", False),
])
def test_action_routing(description, result):
    assert needs_image(description) is result


async def test_image_sent_once_and_trace_contains_actual_drawing(scenario):
    s = scenario
    pid = await add(s)
    assert await s.service.run_due() == 1
    assert await s.service.run_due() == 0
    row = await s.service.promises.get(pid)
    assert row["status"] == "sent" and row["action_state"] == "sent"
    assert row["delivered_text"] == "橙色猫的自拍"
    assert s.peer.calls == len(s.sends) == 1 and s.app.text_sends == 0
    trace = await s.service.promises.latest_trace(s.context.scope_key, s.clock[0])
    assert trace["reply_text"] == "橙色猫的自拍"


async def test_send_false_reuses_image_after_recovery(scenario):
    s = scenario
    pid = await add(s)
    s.app.send_result = False
    assert await s.service.run_due() == 0
    row = await s.service.promises.get(pid)
    assert row["status"] == "scheduled" and row["action_state"] == "generated"
    s.service = PromiseService(s.service.store, s.app)
    s.app.send_result = True
    s.clock[0] += 300
    assert await s.service.run_due() == 1
    assert s.peer.calls == 1 and len(s.sends) == 2


@pytest.mark.parametrize("cause", ["generation", "send", "missing_file"])
async def test_uncertain_side_effects_are_never_repeated(scenario, cause):
    s = scenario
    pid = await add(s)
    if cause == "generation":
        s.peer.result = "unknown"
    elif cause == "send":
        s.app.send_result = TimeoutError()
    else:
        s.file.unlink()
    assert await s.service.run_due() == 0
    assert (await s.service.promises.get(pid))["status"] == "unknown"
    for _ in range(3):
        s.clock[0] += 3600
        s.service = PromiseService(s.service.store, s.app)
        assert await s.service.run_due() == 0
    assert s.peer.calls == 1 and len(s.sends) <= 1


@pytest.mark.parametrize("phase,expected", [
    ("generating", "unknown"), ("sending", "unknown"), ("unknown", "unknown"),
    ("generated", "sent"), ("sent", "sent"),
])
async def test_restart_recovers_only_safe_phases(scenario, phase, expected):
    s = scenario
    pid = await add(s)
    await s.service.promises.move(pid, status="running", expect=("scheduled",))
    await s.service.promises.checkpoint_action(pid, phase, {
        "path": str(s.file), "request_id": "image-1", "detail": "猫自拍"})
    s.service = PromiseService(s.service.store, s.app)
    await s.service.run_due()
    assert (await s.service.promises.get(pid))["status"] == expected
    assert s.peer.calls == 0
    assert len(s.sends) == (1 if phase == "generated" else 0)


@pytest.mark.parametrize("cause", ["guard", "disabled"])
async def test_preflight_never_calls_paid_generation(scenario, cause):
    s = scenario
    pid = await add(s)
    if cause == "guard":
        s.app.allowed = False
    else:
        s.peer.available = False
    assert await s.service.run_due() == 0
    assert s.peer.calls == len(s.sends) == 0
    assert (await s.service.promises.get(pid))["status"] == "scheduled"


async def test_overlap_does_not_heal_active_image_run(scenario):
    s = scenario
    await add(s)
    s.peer.hold = asyncio.Event()
    s.peer.started = asyncio.Event()
    task = asyncio.create_task(s.service.run_due())
    try:
        # 等真实进度信号；sleep(0) 的次数不能保证SQLite线程已经完成。
        await asyncio.wait_for(s.peer.started.wait(), timeout=5)
        assert s.peer.calls == 1
        assert await s.service.run_due() == 0
    finally:
        s.peer.hold.set()
        completed = await task
    assert completed == 1 and len(s.sends) == 1


async def test_action_deadline_stops_uncertain_generation_without_retry(scenario, monkeypatch):
    import astrbot_plugin_livingemotion.runtime.promise_actions as actions
    monkeypatch.setattr(actions, "DEADLINE_SECONDS", 0.01)
    s = scenario
    pid = await add(s)
    s.peer.hold = asyncio.Event()
    assert await s.service.run_due() == 0
    assert (await s.service.promises.get(pid))["status"] == "unknown"
    s.clock[0] += 3600
    assert await s.service.run_due() == 0
    assert s.peer.calls == 1 and s.sends == []


async def test_reminder_keeps_text_delivery(scenario):
    s = scenario
    pid = await add(s, "提醒给花浇水")
    assert await s.service.run_due() == 1
    assert s.app.text_sends == 1 and s.peer.calls == 0
    assert (await s.service.promises.get(pid))["status"] == "sent"


def install_delivery_peer(s):
    original = s.peer.generate_deferred_image
    s.peer.deliveries = 0

    async def generate(event, prompt):
        artifact = await original(event, prompt)
        return {**artifact, "session": s.context.route, "delivery_contract": DELIVERY_CONTRACT}

    async def deliver(event, artifact, *, authorize):
        s.peer.deliveries += 1
        assert await authorize() is True
        assert artifact["session"] == s.context.route
        return {"contract": DELIVERY_CONTRACT, "request_id": artifact["request_id"],
                "status": "sent", "retryable": False}

    s.peer.generate_deferred_image = generate
    s.peer.deliver_deferred_image = deliver
    return deliver


async def test_new_delivery_contract_owns_transport_and_completion(scenario):
    s = scenario
    install_delivery_peer(s)
    pid = await add(s)
    assert await s.service.run_due() == 1
    assert await s.service.run_due() == 0
    assert s.peer.deliveries == 1 and s.sends == s.marks == []
    assert (await s.service.promises.get(pid))["action_state"] == "sent"


@pytest.mark.parametrize("cause", ["unknown", "wrong_contract", "wrong_id", "untyped",
                                 "exception", "invalid_artifact"])
async def test_bad_delivery_receipts_cannot_complete_or_fallback(scenario, cause):
    s = scenario
    install_delivery_peer(s)
    async def deliver(event, artifact, **kwargs):
        if cause == "exception":
            raise OSError("isolated")
        if cause == "untyped":
            return True
        return {"contract": "other" if cause == "wrong_contract" else DELIVERY_CONTRACT,
                "request_id": "other" if cause == "wrong_id" else artifact["request_id"],
                "status": "rejected" if cause == "invalid_artifact" else
                          "unknown" if cause == "unknown" else "sent",
                "retryable": False}
    s.peer.deliver_deferred_image = deliver
    pid = await add(s)
    assert await s.service.run_due() == 0
    assert (await s.service.promises.get(pid))["status"] == "unknown"
    s.clock[0] += 300
    assert await s.service.run_due() == 0
    assert s.sends == [] and s.peer.calls == 1


async def test_new_delivery_rejection_reuses_resource(scenario):
    s = scenario
    deliver = install_delivery_peer(s)
    async def reject(*args, **kwargs):
        return {"contract": DELIVERY_CONTRACT, "request_id": "image-1",
                "status": "rejected", "retryable": True}
    s.peer.deliver_deferred_image = reject
    pid = await add(s)
    assert await s.service.run_due() == 0
    assert (await s.service.promises.get(pid))["action_state"] == "generated"
    s.peer.deliver_deferred_image = deliver
    s.clock[0] += 300
    assert await s.service.run_due() == 1
    assert s.peer.calls == 1 and s.sends == []


async def test_peer_reload_before_delivery_uses_current_instance(scenario):
    s = scenario
    install_delivery_peer(s)
    current = [s.peer]
    replacement_calls = []
    async def replacement(event, artifact, **kwargs):
        replacement_calls.append(artifact["request_id"])
        return {"contract": DELIVERY_CONTRACT, "request_id": artifact["request_id"], "status": "sent"}
    new = SimpleNamespace(get_deferred_image_contract=s.peer.get_deferred_image_contract,
                          deliver_deferred_image=replacement)
    original = s.peer.generate_deferred_image
    async def generate(*args):
        result = await original(*args)
        current[0] = new
        return result
    s.peer.generate_deferred_image = generate
    s.app.bridge.discover = lambda _: current[0]
    await add(s)
    assert await s.service.run_due() == 1
    assert replacement_calls == ["image-1"] and s.peer.deliveries == 0 and s.sends == []


async def test_missing_new_delivery_api_waits_without_legacy_fallback(scenario):
    s = scenario
    deliver = install_delivery_peer(s)
    s.peer.deliver_deferred_image = None
    pid = await add(s)
    assert await s.service.run_due() == 0
    assert (await s.service.promises.get(pid))["action_state"] == "generated"
    assert s.sends == []
    s.peer.deliver_deferred_image = deliver
    s.clock[0] += 300
    assert await s.service.run_due() == 1 and s.peer.calls == 1


@pytest.mark.parametrize("name", NAMES)
def test_all_cooperation_entries_discover_historical_names(name):
    peer = object()
    assert discover(lambda key: peer if key == name else None) is peer


@pytest.mark.parametrize("changes,delegate", [
    ({}, True), ({"run_once": False}, False), ({"enabled": False}, False),
    ({"other_sender": True}, False), ({"other_route": True}, False),
    ({"other_time": True}, False), ({"other_action": True}, False),
])
async def test_host_first_dedup_scopes_schedule_and_intent(scenario, changes, delegate):
    s = scenario
    due_at = s.clock[0] + (7200 if changes.get("other_time") else 120)
    note = "提醒我出门" if changes.get("other_action") else "提醒我给花浇水"
    context = replace(s.context, account_id="other") if changes.get("other_sender") else s.context
    if changes.get("other_route"):
        context = replace(context, route="adapter:FriendMessage:other")
    s.mgr.add(context, note, due_at, **{k: v for k, v in changes.items()
                                     if k in ("run_once", "enabled")})
    result = await s.service.remember(s.context, [("2分钟", "提醒他给花浇水")])
    assert result[0]["status"] == ("delegated" if delegate else "created")
    if delegate:
        s.clock[0] += 120
        assert await s.service.run_due() == 0 and s.app.text_sends == 0


async def test_due_recheck_catches_host_created_outside_request(scenario):
    s = scenario
    pid = await add(s, "提醒给花浇水")
    s.mgr.add(s.context, "提醒我给花浇水", s.clock[0])
    assert await s.service.run_due() == 0
    assert (await s.service.promises.get(pid))["status"] == "delegated"


async def test_failed_host_lookup_blocks_duplicate_execution(scenario):
    s = scenario
    pid = await add(s, "提醒给花浇水")
    s.mgr.fault = True
    assert await s.service.run_due() == 0 and s.app.text_sends == 0
    assert (await s.service.promises.get(pid))["last_error"] == "host_task_lookup_failed"


async def test_recurring_mark_is_not_converted_to_one_time(scenario):
    result = await scenario.service.remember(scenario.context, [("每天", "提醒给花浇水")])
    assert result == [{"status": "recurring_requires_future_task"}]
    assert await scenario.service.active(scenario.context) == []


@pytest.fixture
def tool_surface(monkeypatch):
    # 普通离线矩阵的工具桩；真实宿主 ToolSet 另由 native contract runner 执行。
    @dataclass
    class FunctionTool:
        name: str
        description: str
        parameters: dict
        active: bool = True

    class ToolSet:
        def __init__(self):
            self.tools = []

        def add_tool(self, tool):
            self.tools = [t for t in self.tools if t.name != tool.name] + [tool]

        def get_tool(self, name):
            return next((t for t in self.tools if t.name == name), None)

    module = ModuleType("astrbot.core.agent.tool")
    module.FunctionTool, module.ToolSet = FunctionTool, ToolSet
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return FunctionTool, ToolSet


def future_request(s, surface, *, failure=False):
    FunctionTool, ToolSet = surface

    class FutureTool(FunctionTool):
        async def call(self, run_context, **kwargs):
            if failure:
                return "error: isolated creation failure."
            due = datetime.fromisoformat(kwargs["run_at"]).timestamp()
            job = s.mgr.add(s.context, kwargs["note"], due)
            return f"Scheduled future task {job.job_id} (task) one-time."

    event = Event()
    event.set_extra("livingemotion:context", to_dict(s.context))
    tools = ToolSet()
    tools.add_tool(FutureTool("future_task", "future", {"type": "object"}))
    request = SimpleNamespace(func_tool=tools)
    s.service.ownership.wrap_tools(event, request)
    args = {"action": "create", "run_once": True, "note": "提醒我给花浇水",
            "run_at": datetime.fromtimestamp(s.clock[0] + 120, timezone.utc).isoformat()}
    return event, request.func_tool.get_tool("future_task"), args


@pytest.mark.parametrize("failure", [False, True])
async def test_le_first_then_future_tool_handover(scenario, tool_surface, failure):
    s = scenario
    created = await s.service.remember(s.context, [("2分钟", "提醒他给花浇水")])
    pid = created[0]["promise_id"]
    _, tool, args = future_request(s, tool_surface, failure=failure)
    await tool.call(None, **args)
    assert (await s.service.promises.get(pid))["status"] == ("scheduled" if failure else "delegated")
    assert s.mgr.creates == (0 if failure else 1)


async def test_repeated_future_tool_and_marker_create_only_one_owner(scenario, tool_surface):
    s = scenario
    event, tool, args = future_request(s, tool_surface)
    first = await tool.call(None, **args)
    assert "host-1" in first
    second = await tool.call(None, **args)
    assert "already exists" in second and s.mgr.creates == 1
    result = await s.service.remember(
        s.context, [("2分钟", "提醒他给花浇水")], event=event)
    assert result[0]["status"] == "delegated"
    s.mgr.jobs.clear()  # 宿主一次性任务运行后会删除。
    again = await s.service.remember(
        s.context, [("2分钟", "提醒他给花浇水")], event=event)
    assert again[0]["promise_id"] == result[0]["promise_id"]
    assert await s.service.active(s.context) == []


async def test_same_turn_provenance_survives_paraphrase_and_random_bucket(scenario, tool_surface):
    s = scenario
    event, tool, args = future_request(s, tool_surface)
    await tool.call(None, **args)
    result = await s.service.remember(s.context, [("今晚", "到时候叫他照顾一下花")], event=event)
    assert result[0]["status"] == "delegated" and result[0]["host_job_id"] == "host-1"


async def test_many_host_jobs_do_not_create_ambiguous_marker_task(scenario):
    s = scenario
    event = Event()
    event.set_extra("livingemotion:future_tasks", [
        ("host-1", "浇水", s.clock[0] + 120), ("host-2", "出门", s.clock[0] + 3600)])
    result = await s.service.remember(s.context, [("2分钟", "到时候提醒他")], event=event)
    assert result == [{"status": "host_owned_turn"}]
    assert await s.service.active(s.context) == []


async def test_running_le_task_cannot_be_double_created(scenario, tool_surface):
    s = scenario
    created = await s.service.remember(s.context, [("2分钟", "提醒他给花浇水")])
    await s.service.promises.move(created[0]["promise_id"], status="running", expect=("scheduled",))
    _, tool, args = future_request(s, tool_surface)
    assert "already running" in await tool.call(None, **args)
    assert s.mgr.creates == 0


async def test_marker_is_created_after_send_only(tmp_path):
    app, _, _, _ = await at_time(tmp_path, 12, config={
        "night_schedule_enabled": False, "promise_enabled": True})
    try:
        message = FinalMessage(identifier="delayed-marker")
        message.send = lambda *a, **k: ready(None)
        request = SimpleNamespace(extra_user_content_parts=[])
        await app.on_llm_request(message, request)
        message.result.chain = [SimpleNamespace(text="晚点提醒你 <!--promise:2分钟:提醒给花浇水-->")]
        from astrbot_plugin_livingemotion.contracts import Context
        context = Context.from_dict(message.get_extra("livingemotion:context"))
        assert await app.on_reply_submitted(message) is True
        assert await app._promises().active(context) == []
        assert "<!--" not in message.result.chain[0].text
        await message.send(message.result)
        await app.on_reply_sent(message)
        assert len(await app._promises().active(context)) == 1
        await app.on_reply_sent(message)
        assert len(await app._promises().active(context)) == 1
    finally:
        await app.terminate()


@pytest.mark.parametrize("receipt", ["exception", "negative", "partial"])
async def test_failed_or_partial_send_hook_cannot_create_ghost_promise(tmp_path, receipt):
    app, _, _, _ = await at_time(tmp_path, 12, config={
        "night_schedule_enabled": False, "promise_enabled": True})
    try:
        message = FinalMessage(identifier="failed-" + receipt)
        async def send(*_):
            if receipt == "exception":
                raise OSError("isolated send failure")
            return False if receipt == "negative" else None
        message.send = send
        await app.on_llm_request(message, SimpleNamespace(extra_user_content_parts=[]))
        message.result.chain = [SimpleNamespace(text="晚点提醒你"),
                                SimpleNamespace(text="放心 <!--promise:2分钟:提醒给花浇水-->")]
        assert await app.on_reply_submitted(message) is True
        try:
            await message.send(SimpleNamespace(chain=message.result.chain[:1]))
        except OSError:
            pass
        await app.on_reply_sent(message)
        from astrbot_plugin_livingemotion.contracts import Context
        context = Context.from_dict(message.get_extra("livingemotion:context"))
        assert await app._promises().active(context) == []
    finally:
        await app.terminate()


def test_equivalence_does_not_drop_unrelated_tasks():
    assert same_action("提醒他给花浇水", "提醒我给花浇水")
    assert same_action("拍一张自拍照片给他", "生成一张自拍图片给我")
    assert not same_action("提醒我给花浇水", "提醒我出门")
