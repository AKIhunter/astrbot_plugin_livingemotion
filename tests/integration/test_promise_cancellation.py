"""取消标记 → 组件清洗 → 发送确认 → SQLite 原子取消，全程离线。"""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.runtime.application import Application
from astrbot_plugin_livingemotion.runtime.promise_service import strip_marks
from test_promise_actions import Event, scenario
from test_promise_adjustment import failure


@pytest.mark.parametrize("marker", [
    "<!--promise-cancel:窗边-->",
    "<!--promise-cancel：窗边-->",
    "<!--promise-cancel 窗边-->",
    "<  --promise-cancel 窗边-->",
    "<!--promise-cancel:窗边|花园-->",
])
def test_known_marker_variants_are_extracted_and_hidden(marker):
    body, creates, cancels = strip_marks("好的" + marker)
    assert body == "好的" and not creates
    assert cancels == ["窗边|花园" if "|" in marker else "窗边"]


async def seed(s, description, *, kind=None, context=None):
    context = context or s.context
    if kind:
        data = {**failure(kind, request_id=description), "prompt": description}
        result = await s.service.promises.accept_image_handoff(
            context, request_id=description, source_event_id="", failure=data)
    else:
        result = await s.service.promises.create(
            context, description=description, note="", bucket="稍后", due_at=s.clock[0] + 60)
    return result["promise_id"]


@pytest.mark.parametrize("kind", [
    "content_rejected", "provider_error", "quota_exhausted", "rate_limited",
])
async def test_known_failed_pictures_can_be_cancelled(scenario, kind):
    s = scenario
    pid = await seed(s, "窗边", kind=kind)
    result = await s.service.cancel(s.context, pid[:8])
    assert result["status"] == "cancelled"
    assert (await s.service.promises.get(pid))["status"] == "cancelled"
    s.clock[0] += 86400
    await s.service.run_due()
    assert s.peer.calls == 0 and not s.sends


@pytest.mark.parametrize("separator", ["|", "、", ",", "，"])
async def test_multiple_tokens_cancel_all_unique_targets(scenario, separator):
    s = scenario
    ids = [await seed(s, "窗边", kind="provider_error"), await seed(s, "花园")]
    assert (await s.service.cancel(s.context, separator.join(["窗边", "花园"])))["count"] == 2
    assert [row["status"] for row in [await s.service.promises.get(pid) for pid in ids]] == [
        "cancelled", "cancelled"]


@pytest.mark.parametrize("other,token,status", [
    ("花园", "窗边|找不到", "unmatched"),
    ("窗边另一张", "窗边|花园", "ambiguous"),
])
async def test_bad_selection_never_cancels_partial_group(scenario, other, token, status):
    s = scenario
    ids = [await seed(s, "窗边"), await seed(s, other)]
    assert (await s.service.cancel(s.context, token))["status"] == status
    assert all(row["status"] == "scheduled"
               for row in [await s.service.promises.get(pid) for pid in ids])


@pytest.mark.parametrize("kind", ["result_unknown", "delivery_unknown"])
async def test_unknown_result_can_cancel_followup_without_erasing_request(scenario, kind):
    s = scenario
    first = await seed(s, "窗边")
    second = await seed(s, "花园", kind=kind)
    before = (await s.service.promises.get(second))["action_result_json"]
    assert (await s.service.cancel_tokens(s.context, ["窗边", "花园"]))["status"] == "cancelled"
    assert (await s.service.promises.get(first))["status"] == "cancelled"
    assert (await s.service.promises.get(second))["status"] == "cancelled"
    assert (await s.service.promises.get(second))["action_result_json"] == before


async def test_cancellation_rechecks_status_after_selection(scenario):
    s = scenario
    ids = [await seed(s, "窗边"), await seed(s, "花园")]
    original = s.service.promises.cancel_many

    async def race(targets, **kwargs):
        await s.service.promises.move(ids[1], status="running", expect=("scheduled",))
        return await original(targets, **kwargs)

    s.service.promises.cancel_many = race
    assert (await s.service.cancel(s.context, "窗边|花园"))["status"] == "conflict"
    assert (await s.service.promises.get(ids[0]))["status"] == "scheduled"


async def test_other_conversation_is_never_cancelled(scenario):
    s = scenario
    other = replace(s.context, scene_id="other-chat")
    pid = await seed(s, "窗边", context=other)
    assert (await s.service.cancel(s.context, "窗边"))["status"] == "empty"
    assert (await s.service.promises.cancel_many([pid], context=s.context))["status"] == "conflict"
    assert (await s.service.promises.get(pid))["status"] == "scheduled"


async def test_split_component_marker_is_hidden_and_cancelled_only_on_flush(scenario, caplog):
    s = scenario
    pid = await seed(s, "窗边", kind="provider_error")
    event = Event()
    image = SimpleNamespace(file="kept-image")
    result = SimpleNamespace(chain=[
        SimpleNamespace(text="好，我取消这张。<  --promise-"), image,
        SimpleNamespace(text="cancel 窗边-->继续聊吧。"),
    ])
    app = SimpleNamespace(config=SimpleNamespace(promise_enabled=True),
                          _promises=lambda: s.service,
                          _track_promise_send=lambda event: None)
    raw = "".join(getattr(part, "text", "") for part in result.chain)
    cleaned = Application._strip_promise_marks(app, event, result, raw)
    assert cleaned == "好，我取消这张。继续聊吧。"
    assert [result.chain[0].text, result.chain[2].text] == ["好，我取消这张。", "继续聊吧。"]
    assert result.chain[1] is image
    assert (await s.service.promises.get(pid))["status"] == "waiting"
    await Application.flush_promises(app, s.context, event, cleaned)
    assert (await s.service.promises.get(pid))["status"] == "cancelled"
    assert "承诺取消 状态=cancelled 数量=1" in caplog.text


async def test_blocked_reply_does_not_cancel(scenario):
    s = scenario
    pid = await seed(s, "窗边")
    event = Event()
    event.set_extra("livingemotion:promise_cancels", ["窗边"])
    event.set_extra("_at_guard_superseded", True)
    app = SimpleNamespace(config=SimpleNamespace(promise_enabled=True), _promises=lambda: s.service)
    await Application.flush_promises(app, s.context, event)
    assert (await s.service.promises.get(pid))["status"] == "scheduled"
