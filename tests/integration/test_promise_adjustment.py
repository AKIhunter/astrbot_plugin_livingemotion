"""主动调整追问：真实 SQLite、虚拟时间，模型和消息发送全部打桩。"""
import asyncio
import json
from dataclasses import replace
from unittest.mock import AsyncMock

import pytest

from astrbot_plugin_livingemotion.contracts import Context, SceneKind
from astrbot_plugin_livingemotion.runtime.promise_service import PromiseService
from astrbot_plugin_livingemotion.storage.promise_store import PromiseStore
from test_application import application, Message
from test_promise_actions import scenario, add


def failure(kind="content_rejected", *, request_id="request-one", asked=False):
    return dict(kind=kind, prompt="窗边的猫", reason="受控原因", use_reference=False,
                request_id=request_id, adjustment_asked=asked)


async def handoff(s, **changes):
    data = failure(**changes)
    result = await s.service.promises.accept_image_handoff(
        s.context, request_id=data["request_id"], source_event_id="source", failure=data)
    return result["promise_id"]


def isolate_notice(s, result="sent"):
    s.app.send_promise_notice = AsyncMock(return_value=result)
    s.app.purpose_model = AsyncMock(side_effect=AssertionError("追问不能请求模型"))
    return s.app.send_promise_notice


async def test_legacy_waiting_is_asked_once_across_restart(scenario):
    s = scenario
    notice = isolate_notice(s)
    pid = await handoff(s)
    assert await s.service.run_due() == 0
    assert await s.service.run_due() == 0
    s.service = PromiseService(s.service.store, s.app)
    assert await s.service.run_due() == 0
    notice.assert_awaited_once()
    text = notice.call_args.args[1]
    assert "暂时还没弄好" in text and "保留" in text
    assert not any(word in text for word in ("任务", "接口", "待办", "服务", pid[:8]))
    assert (await s.service.promises.get(pid))["adjustment_notice_state"] == "sent"
    assert s.peer.calls == 0 and not s.sends


async def test_lh_already_asked_never_gets_second_question(scenario):
    s = scenario
    notice = isolate_notice(s)
    await handoff(s, asked=True)
    await s.service.run_due()
    notice.assert_not_awaited()


async def test_duplicate_receipt_can_confirm_lh_question(scenario):
    s = scenario
    notice = isolate_notice(s)
    pid = await handoff(s)
    assert await handoff(s, asked=True) == pid
    await s.service.run_due()
    notice.assert_not_awaited()


@pytest.mark.parametrize("kind", [
    "provider_error", "result_unknown", "delivery_unknown", "quota_exhausted",
])
async def test_non_content_failures_receive_one_followup_without_image_retry(scenario, kind):
    s = scenario
    notice = isolate_notice(s)
    await handoff(s, kind=kind)
    await s.service.run_due()
    notice.assert_awaited_once()
    text = notice.call_args.args[1]
    if "unknown" in kind:
        assert "核对" in text or "收到" in text
        s.app.purpose_model.assert_not_awaited()
    else:
        assert "暂时还没弄好" in text
    await s.service.run_due()
    notice.assert_awaited_once()
    assert s.peer.calls == 0


async def test_rate_limit_remains_scheduled_without_question(scenario):
    s = scenario
    notice = isolate_notice(s)
    pid = await handoff(s, kind="rate_limited")
    await s.service.run_due()
    assert (await s.service.promises.get(pid))["status"] == "scheduled"
    notice.assert_not_awaited()
    assert s.peer.calls == 0


async def test_due_rejection_asks_and_keeps_original_resume_entry(scenario):
    s = scenario
    pid = await add(s)
    notice = isolate_notice(s)
    s.app.purpose_model = AsyncMock(return_value="窗边的猫")
    s.peer.generate_deferred_image = AsyncMock(return_value={
        "status": "failed", "failure": failure()})
    assert await s.service.run_due() == 0
    row = await s.service.promises.get(pid)
    assert (row["status"], row["action_state"], row["handoff_key"]) == (
        "waiting", "held", "request-one")
    notice.assert_awaited_once()
    result = await s.service.promises.resume_image_handoff(
        s.context, pid, prompt="花园里的橙色猫", source_event_id="new-source")
    assert result == {"status": "resumed", "promise_id": pid}
    assert len(await s.service.active(s.context)) == 1
    s.app.purpose_model = AsyncMock(side_effect=AssertionError("沿用用户调整后的画面"))
    s.peer.generate_deferred_image = AsyncMock(return_value={
        "status": "generated", "path": str(s.file), "request_id": "request-two"})
    s.clock[0] += 21
    assert await s.service.run_due() == 1
    assert s.peer.generate_deferred_image.call_args.args[1] == "花园里的橙色猫"
    assert (await s.service.promises.get(pid))["status"] == "sent"
    assert len(s.sends) == 1 and notice.await_count == 1


async def test_crash_after_failure_checkpoint_cannot_restart_image(scenario):
    s = scenario
    pid = await add(s)
    await s.service.promises.move(pid, status="running", expect=("scheduled",))
    assert await s.service.promises.hold_image_request(s.context, pid, failure())
    notice = isolate_notice(s)
    s.service = PromiseService(s.service.store, s.app)
    await s.service.run_due()
    assert (await s.service.promises.get(pid))["status"] == "waiting"
    notice.assert_awaited_once()
    assert s.peer.calls == 0


@pytest.mark.parametrize("result", ["unknown", "failed", RuntimeError("uncertain")])
async def test_unknown_notice_never_resends_or_regenerates(scenario, result):
    s = scenario
    notice = isolate_notice(s, result)
    if isinstance(result, Exception):
        notice.side_effect = result
    pid = await handoff(s)
    await s.service.run_due()
    s.clock[0] += 86400
    s.service = PromiseService(s.service.store, s.app)
    await s.service.run_due()
    notice.assert_awaited_once()
    assert (await s.service.promises.get(pid))["adjustment_notice_state"] == "unknown"
    assert s.peer.calls == 0


async def test_rejected_notice_retries_with_new_intent_then_stops(scenario):
    s = scenario
    notice = isolate_notice(s, "rejected")
    pid = await handoff(s)
    await s.service.run_due()
    await s.service.run_due()
    assert notice.await_count == 1
    s.clock[0] += 301
    notice.return_value = "sent"
    await s.service.run_due()
    assert notice.await_count == 2
    assert notice.call_args_list[0].args[2] != notice.call_args_list[1].args[2]
    assert (await s.service.promises.get(pid))["status"] == "waiting"
    assert s.peer.calls == 0


async def test_rejected_notice_is_bounded_but_task_stays_waiting(scenario):
    s = scenario
    notice = isolate_notice(s, "rejected")
    pid = await handoff(s)
    for _ in range(5):
        await s.service.run_due()
        s.clock[0] += 301
    assert notice.await_count == 3
    row = await s.service.promises.get(pid)
    assert row["status"] == "waiting" and row["adjustment_notice_state"] == "rejected"


async def test_crashed_sending_claim_is_not_repeated(scenario):
    s = scenario
    notice = isolate_notice(s)
    pid = await handoff(s)
    assert await s.service.promises.claim_adjustment_notice(s.context, pid)
    s.service = PromiseService(s.service.store, s.app)
    await s.service.run_due()
    notice.assert_not_awaited()


async def test_parallel_claims_only_allow_one_sender(scenario):
    s = scenario
    pid = await handoff(s)
    stores = [PromiseStore(s.service.store) for _ in range(8)]
    claims = await asyncio.gather(*(p.claim_adjustment_notice(s.context, pid) for p in stores))
    assert sum(c is not None for c in claims) == 1


async def test_existing_database_migrates_without_changing_waiting_request(scenario):
    s = scenario
    pid = await handoff(s)
    before = await s.service.promises.get(pid)
    for name in ("adjustment_notice_state", "adjustment_notice_attempt", "adjustment_notice_retry_at"):
        await s.service.store._run(lambda db, name=name: db.execute(
            "ALTER TABLE promises DROP COLUMN " + name))
    s.service = PromiseService(s.service.store, s.app)
    notice = isolate_notice(s)
    await s.service.run_due()
    after = await s.service.promises.get(pid)
    assert after["action_result_json"] == before["action_result_json"]
    assert after["status"] == "waiting" and after["adjustment_notice_state"] == "sent"
    notice.assert_awaited_once()


async def test_other_account_and_same_source_cannot_resume(scenario):
    s = scenario
    pid = await handoff(s)
    resume = s.service.promises.resume_image_handoff
    assert (await resume(replace(s.context, account_id="other"), pid,
                         prompt="花园里的猫", source_event_id="new"))["status"] == "missing"
    assert (await resume(s.context, pid, prompt="花园里的猫",
                         source_event_id="source"))["status"] == "rejected"
    assert (await s.service.promises.get(pid))["status"] == "waiting"


async def test_blocked_context_does_not_spend_notification_attempt(scenario):
    s = scenario
    notice = isolate_notice(s)
    pid = await handoff(s)
    s.app.allowed = False
    await s.service.run_due()
    assert (await s.service.promises.get(pid))["adjustment_notice_attempt"] == 0
    s.app.allowed = True
    s.clock[0] += 61
    await s.service.run_due()
    notice.assert_awaited_once()


async def test_unavailable_notice_yields_scan_slot_to_next_task(scenario):
    s = scenario
    notice = isolate_notice(s)
    await handoff(s)
    await handoff(s, request_id="request-two")
    original = s.service._live_context
    s.service._live_context = AsyncMock(return_value=None)
    await s.service.run_due(limit=1)
    s.service._live_context = original
    await s.service.run_due(limit=1)
    notice.assert_awaited_once()


async def test_changed_generation_never_sends_old_notice(scenario):
    s = scenario
    notice = isolate_notice(s)
    pid = await handoff(s)
    await s.service.store._run(lambda db: db.execute(
        "UPDATE promises SET generation=generation+1 WHERE promise_id=?", (pid,)))
    await s.service.run_due()
    notice.assert_not_awaited()


async def test_group_question_uses_original_account_and_group(scenario):
    s = scenario
    group = replace(s.context, scene_kind=SceneKind.GROUP, scene_id="group-one",
                    route="adapter-1:GroupMessage:group-one")
    s.context = group
    s.app._contexts = {
        "original": group, "other": replace(group, account_id="other"),
    }
    notice = isolate_notice(s)
    await handoff(s)
    await s.service.run_due()
    assert notice.call_args.args[0] == group
    assert notice.call_args.args[1].startswith("@" + group.account_id)


async def test_resume_invalidates_pending_send_authorization(scenario):
    s = scenario
    pid = await handoff(s)
    async def raced_send(*args, **kwargs):
        assert await kwargs["authorize"]()
        await s.service.promises.resume_image_handoff(
            s.context, pid, prompt="花园里的猫", source_event_id="new-source")
        assert not await kwargs["authorize"]()
        return "rejected"
    s.app.send_promise_notice = AsyncMock(side_effect=raced_send)
    await s.service.run_due()
    row = await s.service.promises.get(pid)
    assert row["status"] == "scheduled" and row["adjustment_notice_state"] == ""


async def test_old_receipt_cannot_confirm_new_blocking_round(scenario):
    s = scenario
    pid = await handoff(s)
    first = await s.service.promises.claim_adjustment_notice(s.context, pid)
    await s.service.promises.resume_image_handoff(
        s.context, pid, prompt="花园里的猫", source_event_id="new-source")
    await s.service.promises.move(pid, status="running", expect=("scheduled",))
    await s.service.promises.hold_image_request(
        s.context, pid, {**failure(request_id="request-two"), "prompt": "花园里的猫"})
    assert await s.service.promises.claim_adjustment_notice(s.context, pid)
    assert not await s.service.promises.finish_adjustment_notice(
        pid, 1, payload=first["action_result_json"], state="sent")
    assert (await s.service.promises.get(pid))["adjustment_notice_state"] == "sending"


async def test_adjusted_request_can_ask_again_after_new_rejection(scenario):
    s = scenario
    notice = isolate_notice(s)
    pid = await handoff(s)
    await s.service.run_due()
    await s.service.promises.resume_image_handoff(
        s.context, pid, prompt="花园里的猫", source_event_id="new-source")
    s.peer.generate_deferred_image = AsyncMock(return_value={"status": "failed", "failure": {
        **failure(request_id="request-two"), "prompt": "花园里的猫"}})
    s.clock[0] += 21
    await s.service.run_due()
    await s.service.run_due()
    assert notice.await_count == 2
    assert notice.call_args_list[0].args[2] != notice.call_args_list[1].args[2]
    assert s.peer.generate_deferred_image.await_count == 1
    text = notice.call_args.args[1]
    assert "暂时还没弄好" in text and "保留" in text
    assert not any(word in text for word in ("任务", "接口", "待办", "服务", pid[:8]))
    row = await s.service.promises.get(pid)
    assert json.loads(row["action_result_json"])["adjustment_round"] == 1
    assert row["status"] == "waiting"


@pytest.mark.parametrize("text", [
    "嗯", "好的", "再试一次", "嗯，再试一次", "继续", "", "算了", "这张就不画了", "取消",
])
async def test_store_rejects_acknowledgment_as_new_prompt(scenario, text):
    s = scenario
    pid = await handoff(s)
    result = await s.service.promises.resume_image_handoff(
        s.context, pid, prompt=text, source_event_id="new-source")
    assert result["status"] == "rejected"
    assert (await s.service.promises.get(pid))["status"] == "waiting"


async def test_user_can_cancel_picture_after_adjustment_fails(scenario):
    s = scenario
    notice = isolate_notice(s)
    pid = await handoff(s)
    await s.service.promises.resume_image_handoff(
        s.context, pid, prompt="花园里的猫", source_event_id="new-source")
    s.peer.generate_deferred_image = AsyncMock(return_value={"status": "failed", "failure": {
        **failure(request_id="request-two"), "prompt": "花园里的猫"}})
    s.clock[0] += 21
    await s.service.run_due()
    assert (await s.service.cancel(s.context))["status"] == "cancelled"
    assert (await s.service.promises.get(pid))["status"] == "cancelled"
    assert await s.service.active(s.context) == []
    await s.service.run_due()
    s.peer.generate_deferred_image.assert_awaited_once()
    notice.assert_awaited_once()


@pytest.mark.parametrize("description", [
    "拍一张自拍", "拍一张照片", "画一张图", "晚点拍照给你看", "拍给你看",
])
async def test_photo_selfie_and_drawing_share_adjustment_choice(scenario, description):
    s = scenario
    pid = await add(s, description)
    notice = isolate_notice(s)
    s.app.purpose_model = AsyncMock(side_effect=[
        "这张暂时还没弄好，晚点再给你。",
        "这张暂时还没弄好，晚点再给你。"])
    s.peer.generate_deferred_image = AsyncMock(return_value={
        "status": "failed", "failure": {**failure(), "prompt": "窗边的自拍"}})
    await s.service.run_due()
    await s.service.promises.resume_image_handoff(
        s.context, pid, prompt="花园里的自拍", source_event_id="new-source")
    s.peer.generate_deferred_image.return_value = {
        "status": "failed", "failure": {**failure(request_id="request-two"), "prompt": "花园里的自拍"}}
    s.clock[0] += 21
    await s.service.run_due()
    assert notice.await_count == 2
    text = notice.call_args.args[1]
    assert text == "这张暂时还没弄好，晚点再给你。"
    assert "画" not in text
    assert (await s.service.cancel(s.context))["status"] == "cancelled"
    await s.service.run_due()
    assert s.peer.generate_deferred_image.await_count == 2


async def test_cancel_multiple_waiting_pictures_needs_selection(scenario):
    s = scenario
    ids = [await handoff(s), await handoff(s, request_id="request-two")]
    assert (await s.service.cancel(s.context))["status"] == "ambiguous"
    rows = [await s.service.promises.get(pid) for pid in ids]
    assert all(row["status"] == "waiting" for row in rows)


async def test_cancel_invalidates_pending_notice_authorization(scenario):
    s = scenario
    pid = await handoff(s)
    async def raced_send(*args, **kwargs):
        assert await kwargs["authorize"]()
        assert (await s.service.cancel(s.context))["status"] == "cancelled"
        assert not await kwargs["authorize"]()
        return "rejected"
    s.app.send_promise_notice = AsyncMock(side_effect=raced_send)
    await s.service.run_due()
    assert (await s.service.promises.get(pid))["status"] == "cancelled"


async def api_app(tmp_path):
    app, host, _ = await application(tmp_path, {"timezone": "UTC"})
    app.promise_actions_active = lambda: True
    msg = Message("source", "请画窗边的猫")
    await app.on_message(msg)
    scope = Context.from_dict(msg.get_extra("livingemotion:context"))
    data = {**failure(), "notified": True}
    msg.set_extra("_livinghello_image_failure", data)
    receipt = await app.api.handoff_image_failure(scope, event=msg)
    return app, host, scope, receipt["data"]["promise_id"]


async def test_facade_preserves_lh_question_receipt(tmp_path):
    app, host, scope, pid = await api_app(tmp_path)
    try:
        msg = Message("source", "请画窗边的猫")
        await app.on_message(msg)
        msg.set_extra("_livinghello_image_failure", {**failure(asked=True), "notified": True})
        await app.api.handoff_image_failure(scope, event=msg)
        assert (await app._promises().promises.get(pid))["adjustment_notice_state"] == "sent"
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.parametrize("text", ["嗯", "好的", "再试一次", "继续", "第一张再试一次"])
async def test_facade_cannot_invent_adjustment_from_acknowledgment(tmp_path, text):
    app, host, scope, pid = await api_app(tmp_path)
    try:
        msg = Message("new-source", text)
        await app.on_message(msg)
        receipt = await app.api.resume_image_followup(
            scope, event=msg, promise_id=pid, prompt="模型擅自改写成花园里的猫")
        assert receipt["reason_code"] == "user_adjustment_required"
        assert host.sends == 0
    finally:
        await app.terminate()


@pytest.mark.parametrize("text", [
    "算了", "这张就不画了", "取消", "不用画了", "不拍了", "这张照片不要了", "不用拍了",
])
async def test_facade_never_interprets_cancel_as_adjustment(tmp_path, text):
    app, host, scope, pid = await api_app(tmp_path)
    try:
        msg = Message("cancel-source", text)
        await app.on_message(msg)
        receipt = await app.api.resume_image_followup(
            scope, event=msg, promise_id=pid, prompt="模型擅自改写的画面")
        assert receipt["reason_code"] == "user_adjustment_required"
        assert host.sends == 0
    finally:
        await app.terminate()


async def test_actual_notice_executor_falls_back_once_when_closing_unavailable(tmp_path):
    app, host, scope, pid = await api_app(tmp_path)
    try:
        app._preparation_guard = AsyncMock(return_value=True)
        app.purpose_model = AsyncMock(side_effect=AssertionError("追问不调用模型"))
        assert await app._promises().run_due() == 0
        assert await app._promises().run_due() == 0
        assert host.sends == 1
        row = await app._promises().promises.get(pid)
        assert row["status"] == "waiting" and row["adjustment_notice_state"] == "sent"
        app.purpose_model.assert_awaited_once()
    finally:
        await app.terminate()


async def test_multiple_pictures_can_be_selected_without_technical_prefix(tmp_path):
    app, host, scope, pid = await api_app(tmp_path)
    try:
        msg = Message("other-source", "请画一只小狗")
        await app.on_message(msg)
        msg.set_extra("_livinghello_image_failure", {
            **failure(request_id="request-two"), "prompt": "公园里的小狗", "notified": True})
        await app.api.handoff_image_failure(scope, event=msg)
        msg = Message("adjust-source", "窗边的猫换成黑猫")
        await app.on_message(msg)
        receipt = await app.api.resume_image_followup(
            scope, event=msg, promise_id=pid, prompt="窗边的黑猫")
        assert receipt["data"]["status"] == "resumed"
        assert host.sends == 0
    finally:
        await app.terminate()
@pytest.mark.parametrize("text,allowed", [
    ("改成花园里的猫", False), ("第一张改成花园里的猫", True),
])
async def test_multiple_tasks_need_explicit_user_selection(tmp_path, text, allowed):
    app, host, scope, pid = await api_app(tmp_path)
    try:
        msg = Message("other-source", "另一张猫")
        await app.on_message(msg)
        msg.set_extra("_livinghello_image_failure", {
            **failure(request_id="request-two"), "notified": True})
        await app.api.handoff_image_failure(scope, event=msg)
        msg = Message("adjust-source", text)
        await app.on_message(msg)
        receipt = await app.api.resume_image_followup(
            scope, event=msg, promise_id=pid, prompt="花园里的猫")
        if allowed:
            assert receipt["data"]["status"] == "resumed"
        else:
            assert receipt["reason_code"] == "ambiguous_image_adjustment"
        assert host.sends == 0
    finally:
        await app.terminate()
