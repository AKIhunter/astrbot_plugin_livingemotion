"""名额与提示词的边界：真实事务、并发入口、旧数据与配置读回，全程离线。"""
import asyncio
from dataclasses import replace
from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import Context
from astrbot_plugin_livingemotion.prompt_injection import PROMISE_CONTRACT
from astrbot_plugin_livingemotion.runtime.application import ApplicationError
from test_application import Message, application
from test_promise_actions import scenario
from test_promise_adjustment import failure
from test_promise_cancellation import seed


async def remember(s, description):
    return (await s.service.remember(s.context, [("稍后", description)]))[0]


@pytest.mark.parametrize("entrance", ["markers", "handoffs", "mixed"])
async def test_concurrent_admission_at_last_slot_is_atomic(scenario, entrance):
    s = scenario
    s.app.config.promise_max_active = 3
    await seed(s, "已有一")
    await seed(s, "已有二", kind="provider_error")

    async def attempt(i):
        if entrance == "handoffs" or (entrance == "mixed" and i % 2):
            return await s.service.promises.accept_image_handoff(
                s.context, request_id=f"request-{i}", source_event_id="",
                failure={**failure("provider_error"), "prompt": f"猫{i}"},
                max_active=s.service.max_active)
        return await remember(s, f"提醒喝水{i}")

    results = await asyncio.gather(*(attempt(i) for i in range(12)))
    assert sum(row["status"] in ("created", "accepted") for row in results) == 1
    assert sum(row["status"] == "limit_reached" for row in results) == 11
    assert await s.service.promises.count_active(s.context) == 3
    assert s.peer.calls == 0 and not s.sends


async def test_duplicate_and_paused_same_item_reuse_at_capacity(scenario):
    s = scenario
    s.app.config.promise_max_active = 1
    pid = await seed(s, "窗边", kind="provider_error")
    row = await s.service.promises.get(pid)
    result = await remember(s, row["description"])
    assert result == {"status": "duplicate", "promise_id": pid}
    data = {**failure("provider_error"), "prompt": "窗边"}
    duplicate = await s.service.promises.accept_image_handoff(
        s.context, request_id="窗边", source_event_id="", failure=data, max_active=1)
    assert duplicate["status"] == "duplicate" and duplicate["promise_id"] == pid
    assert (await remember(s, "提醒喝水"))["status"] == "limit_reached"
    assert (await s.service.promises.get(pid))["status"] == "waiting"


async def test_original_handoff_reuses_slot_and_resume_keeps_same_id(scenario):
    s = scenario
    s.app.config.promise_max_active = 1
    original = await s.service.promises.create(
        s.context, description="生图：窗边的猫", note="", bucket="稍后",
        due_at=s.clock[0] + 60, source_event_id="source", max_active=1)
    result = await s.service.promises.accept_image_handoff(
        s.context, request_id="request-one", source_event_id="source",
        failure=failure(), max_active=1)
    assert result["status"] == "accepted" and result["promise_id"] == original["promise_id"]
    resumed = await s.service.promises.resume_image_handoff(
        s.context, result["promise_id"], prompt="花园里的猫", source_event_id="new-source")
    assert resumed["status"] == "resumed"
    assert await s.service.promises.count_active(s.context) == 1


async def test_reducing_limit_preserves_legacy_rows_and_releases_only_on_cancel(scenario):
    s = scenario
    ids = [await seed(s, f"旧图{i}", kind="provider_error") for i in range(6)]
    s.app.config.promise_max_active = 2
    view = await s.service.view(s.context)
    assert view["max_active"] == 2 and view["active_count"] == len(view["items"]) == 6
    assert (await remember(s, "提醒喝水"))["status"] == "limit_reached"
    s.clock[0] += 86400
    await s.service.heal()
    assert len(await s.service.active(s.context)) == 6
    assert (await s.service.cancel(s.context, "|".join(pid[:8] for pid in ids[:5])))["count"] == 5
    assert (await remember(s, "提醒喝水"))["status"] == "created"
    assert await s.service.promises.count_active(s.context) == 2


async def test_legacy_list_and_count_are_not_truncated_at_20_or_200(scenario):
    s = scenario
    for i in range(205):
        await seed(s, f"旧提醒{i}")
    assert len(await s.service.active(s.context)) == 205
    assert await s.service.promises.count_active(s.context) == 205
    assert (await s.service.cancel(s.context, "205"))["status"] == "cancelled"
    assert await s.service.promises.count_active(s.context) == 204


async def test_separate_scope_has_separate_limit(scenario):
    s = scenario
    s.app.config.promise_max_active = 1
    await remember(s, "提醒喝水")
    other = replace(s.context, scene_id="other")
    result = await s.service.remember(other, [("稍后", "提醒喝水")])
    assert result[0]["status"] == "created"


@pytest.mark.parametrize("state", ["scheduled", "running", "waiting", "awaiting"])
async def test_each_unfinished_state_occupies_a_slot(scenario, state):
    s = scenario
    s.app.config.promise_max_active = 1
    pid = await seed(s, "窗边", kind="provider_error" if state == "waiting" else None)
    if state in ("running", "awaiting"):
        await s.service.promises.move(pid, status=state, expect=("scheduled",))
    assert (await remember(s, "提醒喝水"))["status"] == "limit_reached"


@pytest.mark.parametrize("value", [0, 11, True, "3", 1.5, None])
def test_config_rejects_invalid_active_limit(value):
    with pytest.raises(ValueError, match="promise_max_active"):
        Config.from_mapping({"promise_max_active": value})


@pytest.mark.parametrize("value,expected", [(0, 1), (99, 10), (True, 3), ("3", 3)])
def test_runtime_guard_clamps_nonstandard_host_config(scenario, value, expected):
    scenario.app.config.promise_max_active = value
    assert scenario.service.max_active == expected


async def test_console_save_schema_and_handoff_read_the_same_limit(tmp_path):
    app, host, native = await application(tmp_path, {"timezone": "UTC", "promise_max_active": 1})
    try:
        msg = Message("source", "请画窗边的猫")
        await app.on_message(msg)
        context = Context.from_dict(msg.get_extra("livingemotion:context"))
        app.promise_actions_active = lambda: True
        await app._promises().remember(context, [("稍后", "提醒喝水")])
        msg.set_extra("_livinghello_image_failure", {**failure(), "notified": True})
        full = await app.api.handoff_image_failure(context, event=msg)
        assert full["data"]["status"] == "limit_reached"
        before = dict(native)
        with pytest.raises(ApplicationError) as caught:
            await app.update_config({"promise_max_active": 11}, expected_revision=app.revision,
                                    actor_id="offline-admin", reason="offline test")
        assert caught.value.code == "validation_error"
        assert dict(native) == before
        await app.update_config({"promise_max_active": 2}, expected_revision=app.revision,
                                actor_id="offline-admin", reason="offline test")
        assert native["promise_max_active"] == app.config.promise_max_active == 2
        view = await app._promises().view(context)
        assert view["max_active"] == 2
        accepted = await app.api.handoff_image_failure(context, event=msg)
        assert accepted["data"]["status"] == "accepted"
        field = next(field for field in app.config_dto()["fields"] if field["key"] == "promise_max_active")
        assert field["min"] == 1 and field["max"] == 10 and field["value"] == 2
        assert "等待调整或核对" in field["details"]
        assert host.sends == 0
    finally:
        await app.terminate()


async def test_prompt_extra_is_bounded_with_many_long_paused_items(tmp_path, le_log):
    app, _, _ = await application(tmp_path, {"timezone": "UTC"})
    try:
        msg = Message("source", "请画猫")
        await app.on_message(msg)
        context = Context.from_dict(msg.get_extra("livingemotion:context"))
        service = app._promises()
        for i in range(6):
            await service.promises.accept_image_handoff(
                context, request_id=f"long-{i}", source_event_id="",
                failure={**failure("provider_error"), "prompt": str(i) + "长画面" * 200})
        request = SimpleNamespace(extra_user_content_parts=[])
        await app._inject_promise_contract(request, context)
        text = request.extra_user_content_parts[0].text
        assert "共6条，列出前3条" in text
        assert text.count("暂停 ID=") == 3
        assert "总数=6 展示=3" in le_log.text
        assert len(text) - len(PROMISE_CONTRACT) <= 1200
        assert len(await service.active(context)) == 6
    finally:
        await app.terminate()


async def test_legacy_awaiting_remains_visible_in_management_panel(tmp_path):
    app, _, _ = await application(tmp_path, {"timezone": "UTC"})
    try:
        msg = Message("source", "稍后提醒喝水")
        await app.on_message(msg)
        context = Context.from_dict(msg.get_extra("livingemotion:context"))
        result = (await app._promises().remember(context, [("稍后", "提醒喝水")]))[0]
        await app._promises().promises.move(
            result["promise_id"], status="awaiting", expect=("scheduled",))
        rows = await app._promises().promises.active(scope_key=context.scope_key, limit=None)
        assert [row["promise_id"] for row in rows] == [result["promise_id"]]
        assert rows[0]["status"] == "awaiting"
    finally:
        await app.terminate()
