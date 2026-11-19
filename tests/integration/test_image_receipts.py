"""原图片事项：真实 SQLite、虚拟时间、无付费上游。"""
import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from astrbot_plugin_livingemotion.contracts import Context
from astrbot_plugin_livingemotion.storage.promise_store import PromiseStore
from test_application import application, Message
from test_promise_actions import scenario, add
from test_promise_adjustment import handoff


def binding(pid, rid="image-request-one"):
    return dict(promise_id=pid, request_id=rid, prompt="窗边的猫", use_reference=False)


def receipt(pid, status="sent", rid="image-request-one", **changes):
    return dict(binding(pid, rid), status=status, revised="橙色猫在窗边", **changes)


async def claimed(s):
    pid = await add(s)
    assert (await s.service.promises.bind_image_request(s.context, binding(pid)))["status"] == "bound"
    return pid


async def test_success_completes_only_original_and_preserves_delivery_trace(scenario):
    s = scenario
    first = await claimed(s)
    second = await add(s, "拍一张露台的猫")
    assert (await s.service.promises.settle_image_request(s.context, receipt(first)))["status"] == "sent"
    row = await s.service.promises.get(first)
    assert row["status"] == row["action_state"] == "sent"
    assert row["sent_at"] == s.clock[0]
    assert [r["promise_id"] for r in await s.service.promises.active()] == [second]
    trace = await s.service.promises.latest_trace(s.context.scope_key, s.clock[0])
    assert "图片已发送" in trace["reply_text"] and "橙色猫在窗边" in trace["reply_text"]


@pytest.mark.parametrize("status,kind", [
    ("unknown", "delivery_unknown"), ("unknown", "result_unknown"),
    ("failed", "content_rejected"), ("failed", "provider_error"),
    ("failed", "quota_exhausted"),
])
async def test_unknown_and_nonretryable_failures_preserve_original(scenario, status, kind):
    s = scenario
    pid = await claimed(s)
    assert (await s.service.promises.settle_image_request(
        s.context, receipt(pid, status, kind=kind)))["status"] == "settled"
    row = await s.service.promises.get(pid)
    assert row["status"] == "waiting" and row["sent_at"] is None
    assert [r["promise_id"] for r in await s.service.promises.active()] == [pid]
    assert await s.service.promises.latest_trace(s.context.scope_key, s.clock[0]) is None


@pytest.mark.parametrize("kind,auto", [
    ("rate_limited", False), ("content_rejected", True), ("prompt_too_long", True),
])
async def test_new_mapping_retry_reuses_original_without_external_owner(scenario, kind, auto):
    s = scenario
    pid = await claimed(s)
    await s.service.promises.settle_image_request(s.context, receipt(
        pid, "failed", kind=kind, auto_prompt_retry=auto, attempted_prompt="窗边的猫"))
    row = await s.service.promises.get(pid)
    assert row["status"] == "scheduled" and row["action_state"] == "retry_ready"
    assert not json.loads(row["action_result_json"]).get("external_image")
    assert row["due_at"] == s.clock[0] + 300
    assert [r["promise_id"] for r in await s.service.promises.active()] == [pid]


@pytest.mark.parametrize("field,value", [
    ("account_id", "other"), ("scene_id", "other"), ("persona_id", "other"),
    ("persona_revision", "other"), ("identity_revision", "other"),
    ("instance_id", "other"), ("route", "other"),
])
async def test_receipt_cannot_cross_source_boundaries(scenario, field, value):
    s = scenario
    pid = await claimed(s)
    assert (await s.service.promises.settle_image_request(
        replace(s.context, **{field: value}), receipt(pid)))["status"] == "rejected"
    assert (await s.service.promises.get(pid))["status"] == "running"


@pytest.mark.parametrize("field", ["account_id", "scene_id", "persona_id", "instance_id"])
async def test_claim_cannot_cross_sources(scenario, field):
    s = scenario
    pid = await add(s)
    assert (await s.service.promises.bind_image_request(
        replace(s.context, **{field: "other"}), binding(pid)))["status"] == "rejected"


async def test_generation_change_rejects_old_receipt(scenario):
    s = scenario
    pid = await claimed(s)
    await s.service.store._run(lambda db: db.execute(
        "UPDATE promises SET generation=generation+1 WHERE promise_id=?", (pid,)))
    assert (await s.service.promises.settle_image_request(s.context, receipt(pid)))["status"] == "rejected"


async def test_different_request_and_unclaimed_task_cannot_complete(scenario):
    s = scenario
    first = await claimed(s)
    second = await add(s, "拍一张露台的猫")
    for data in (receipt(first, rid="different-request"), receipt(second)):
        assert (await s.service.promises.settle_image_request(s.context, data))["status"] == "rejected"
    assert len(await s.service.promises.active()) == 2


async def test_parallel_claims_and_scheduler_never_generate_twice(scenario):
    s = scenario
    pid = await add(s)
    results = await asyncio.gather(*(PromiseStore(s.service.store).bind_image_request(
        s.context, binding(pid, "request-" + str(i))) for i in range(12)))
    assert sum(r["status"] == "bound" for r in results) == 1
    assert await s.service.run_due() == 0
    assert s.peer.calls == 0 and not s.sends
    assert (await s.service.promises.get(pid))["status"] == "running"


async def test_duplicate_reordered_and_restart_receipts_are_idempotent(scenario):
    s = scenario
    pid = await claimed(s)
    outcomes = await asyncio.gather(*(PromiseStore(s.service.store).settle_image_request(
        s.context, receipt(pid)) for _ in range(8)))
    assert sum(o["status"] == "sent" for o in outcomes) == 1
    before = await s.service.promises.get(pid)
    assert (await s.service.promises.settle_image_request(
        s.context, receipt(pid, "unknown", kind="delivery_unknown")))["status"] == "duplicate"
    assert await PromiseStore(s.service.store).get(pid) == before


@pytest.mark.parametrize("kind", ["content_rejected", "result_unknown", "delivery_unknown", "provider_error"])
async def test_paused_task_cannot_be_reclaimed(scenario, kind):
    s = scenario
    pid = await handoff(s, kind=kind)
    assert (await s.service.promises.bind_image_request(s.context, binding(pid)))["status"] == "rejected"


async def test_explicit_adjustment_resumes_and_completes_original(scenario):
    s = scenario
    pid = await handoff(s)
    assert (await s.service.promises.resume_image_handoff(
        s.context, pid, prompt="花园的橙色猫", source_event_id="user-adjustment"))["status"] == "resumed"
    assert (await s.service.promises.bind_image_request(s.context, binding(pid)))["status"] == "bound"
    assert (await s.service.promises.settle_image_request(s.context, receipt(pid)))["status"] == "sent"
    assert not await s.service.promises.active()


async def test_text_promise_cannot_be_claimed_as_image(scenario):
    s = scenario
    pid = await add(s, "提醒我给花浇水")
    assert (await s.service.promises.bind_image_request(s.context, binding(pid)))["status"] == "rejected"


async def test_real_api_validates_event_and_injects_completed_fact(tmp_path):
    app, _, _ = await application(tmp_path)
    try:
        event = Message("source", "请把窗边的照片给我")
        await app.on_message(event)
        scope = Context.from_dict(event.extra["livingemotion:context"])
        app.promise_actions_active = lambda: True
        store = app._promises().promises
        pid = (await store.create(scope, description="拍一张窗边的猫", note="窗边的猫",
                                  bucket="马上", due_at=app.store.clock() + 100))["promise_id"]
        event.set_extra("_livinghello_image_binding", binding(pid))
        assert (await app.api.bind_image_promise(scope, event=event))["data"]["status"] == "bound"
        event.set_extra("_livinghello_image_result", receipt(pid))
        assert (await app.api.settle_image_promise(scope, event=event))["data"]["status"] == "sent"
        next_event = Message("next", "刚刚那张发了没有")
        await app.on_message(next_event)
        request = SimpleNamespace(extra_user_content_parts=[], system_prompt="")
        await app.on_llm_request(next_event, request)
        facts = [p.text for p in request.extra_user_content_parts if "已成功交付的图片事实" in p.text]
        assert len(facts) == 1  # 两套底座合并后也只注入一次，避免重复提示词。
        fact = facts[0]
        assert "橙色猫在窗边" in json.loads(fact.rsplit("\n", 1)[1])[0]["delivered_text"]
        assert "不等于你已做视觉检查" in fact
        assert not await store.active()
        event.account = "other"
        assert (await app.api.settle_image_promise(scope, event=event))["status"] != "ok"
    finally:
        await app.terminate()


async def test_facade_shares_ownership_lock_and_configured_trace_ttl(tmp_path):
    app, _, _ = await application(tmp_path, {"promise_trace_ttl_hours": 2.5})
    try:
        event = Message("source", "请把窗边的照片给我")
        await app.on_message(event)
        scope = Context.from_dict(event.extra["livingemotion:context"])
        app.promise_actions_active = lambda: True
        service = app._promises()
        pid = (await service.promises.create(scope, description="拍一张窗边的猫",
            note="窗边的猫", bucket="马上", due_at=app.store.clock() + 100))["promise_id"]

        async def check_lock(*args):
            assert service.ownership.lock.locked()
            return ""
        service.ownership.host_match = AsyncMock(side_effect=check_lock)
        event.set_extra("_livinghello_image_binding", binding(pid))
        assert (await app.api.bind_image_promise(scope, event=event))["data"]["status"] == "bound"
        event.set_extra("_livinghello_image_result", receipt(pid))
        assert (await app.api.settle_image_promise(scope, event=event))["data"]["status"] == "sent"
        trace = await service.promises.latest_trace(scope.scope_key, app.store.clock())
        assert trace["expires_at"] - trace["created_at"] == 9000
        service.ownership.host_match.assert_awaited_once()
    finally:
        await app.terminate()


@pytest.mark.parametrize("group", [False, True])
async def test_completed_fact_never_attributes_legacy_group_to_arbitrary_member(scenario, group):
    s = scenario
    context = replace(s.context, scene_kind="group", scene_id="test-group") if group else s.context
    created = await s.service.promises.create(
        context, description="拍一张窗边的猫", note="图片", bucket="马上",
        due_at=s.clock[0] + 60)
    pid = created["promise_id"]
    # 存量群聊空归属不能冒充当前成员的图片；明确归属后才允许读取。
    await s.service.store._run(lambda db: db.execute(
        "UPDATE promises SET status='sent',sent_at=?,delivered_text='旧图片',"
        "handoff_account_key='' WHERE promise_id=?", (s.clock[0], pid)))
    rows = await s.service.promises.delivered_images(context)
    assert bool(rows) is not group
    if group:
        await s.service.store._run(lambda db: db.execute(
            "UPDATE promises SET handoff_account_key=? WHERE promise_id=?",
            (context.account_key, pid)))
        assert len(await s.service.promises.delivered_images(context)) == 1
        assert await s.service.promises.delivered_images(
            replace(context, account_id="another-member")) == []
