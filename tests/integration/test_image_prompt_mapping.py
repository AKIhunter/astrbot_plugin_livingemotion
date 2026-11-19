"""真实承诺SQLite + LH真实映射器 + 全打桩模型/生图/投递，零付费请求。"""
import importlib.util
import json
import os
from pathlib import Path
import sys
from unittest.mock import AsyncMock

import pytest

from astrbot_plugin_livingemotion.runtime.promise_service import PromiseService
from test_promise_actions import scenario, add
from test_application import application, Message
from astrbot_plugin_livingemotion.contracts import Context


@pytest.fixture
def mapping(scenario, monkeypatch, tmp_path):
    s = scenario
    configured = os.environ.get("LIVINGHELLO_SOURCE")
    lh = Path(configured) if configured else Path(__file__).resolve().parents[3] / "LivingHello"
    if not configured and not lh.exists():
        # 部署后的相邻插件使用宿主标准包名。
        lh = Path(__file__).resolve().parents[3] / "astrbot_plugin_LivingHello"
    assert (lh / "images/guard_image_prompt.py").is_file(), (
        "此显式矩阵需要 LH 2.8.0 源码，请设置 LIVINGHELLO_SOURCE")
    monkeypatch.syspath_prepend(str(lh))
    spec = importlib.util.spec_from_file_location("_lh_prompt_mapping_fixture", lh / "images/guard_image_prompt.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    guard = module.ImagePromptMapping(tmp_path)
    values = {"provider_id": "images", "protocol": "images", "prompt_guard_enabled": True,
              "prompt_guard_retry_limit": 2, "prompt_guard_learn_enabled": True}
    connection = ("https://example.invalid/v1", "fixture-only", "image-one")
    s.guard, s.image_values, s.connection = guard, values, connection
    s.peer.get_image_prompt_mapping_contract = lambda: guard.policy(values, connection)
    s.peer.prepare_image_prompt_repair = lambda prompt, proposal, **_: guard.prepare_repair(values, connection, prompt, proposal)
    s.generated = []

    async def generate(event, prompt):
        s.peer.calls += 1
        prepared = guard.apply(values, connection, prompt, event.get_extra("_livinghello_image_prompt_repair"))
        s.generated.append((event.message_obj.message_id, prompt, prepared))
        request_id = f"image-{s.peer.calls}"
        if s.reject:
            return {"status": "failed", "failure": {
                "kind": s.reject, "reason": "受控失败", "prompt": prompt,
                "attempted_prompt": prepared["prompt"], "request_id": request_id}}
        guard.observe(request_id, prepared, "success")
        return {"status": "generated", "path": str(s.file), "request_id": request_id,
                "effective_prompt": prepared["prompt"], "prompt": prompt}

    s.peer.generate_deferred_image = AsyncMock(side_effect=generate)
    s.reject = "content_rejected"
    s.app.send_promise_notice = AsyncMock(return_value="sent")
    s.app.purpose_model = AsyncMock(return_value="blue blouse")
    return s


def proposal(source="blouse", target="shirt", **changes):
    return json.dumps({"changes_scene": False, "substitutions": [{"from": source, "to": target}], **changes})


@pytest.mark.parametrize("le_limit,lh_limit,expected", [
    (0, 10, 0), (10, 0, 0), (3, 10, 3), (10, 2, 2), (10, 10, 10)])
async def test_prompt_retry_budget_is_actual_configured_minimum(mapping, le_limit, lh_limit, expected):
    s = mapping
    s.app.config.promise_retry_limit = le_limit
    s.image_values["prompt_guard_retry_limit"] = lh_limit
    words = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta",
             "eta", "theta", "iota", "kappa", "lambda"]
    s.app.purpose_model.side_effect = [words[0]] + [
        proposal(words[i], words[i+1]) for i in range(expected)]
    pid = await add(s)
    await s.service.run_due()
    row = await s.service.promises.get(pid)
    assert row["status"] == "waiting"
    assert s.peer.calls == expected + 1
    assert json.loads(row["action_result_json"])["prompt_retry_count"] == expected
    s.service = PromiseService(s.service.store, s.app)
    s.clock[0] += 301
    await s.service.run_due()
    assert s.peer.calls == expected + 1


async def test_delay_retry_and_prompt_retry_share_le_budget(mapping):
    s = mapping
    s.app.config.promise_retry_limit = 3
    s.image_values["prompt_guard_retry_limit"] = 10
    pid = await add(s)
    await s.service.store._run(lambda db: db.execute(
        "UPDATE promises SET retry_count=2 WHERE promise_id=?", (pid,)))
    s.app.purpose_model.side_effect = ["alpha", proposal("alpha", "beta")]
    await s.service.run_due()
    row = await s.service.promises.get(pid)
    assert row["retry_count"] == 2
    assert json.loads(row["action_result_json"])["prompt_retry_count"] == 1
    assert s.peer.calls == 2


async def test_explicit_rejection_retries_same_scene_then_learns(mapping):
    s = mapping
    initial = s.peer.generate_deferred_image.side_effect

    async def accept_repair(event, prompt):
        s.reject = "content_rejected" if s.peer.calls == 0 else ""
        return await initial(event, prompt)

    s.peer.generate_deferred_image.side_effect = accept_repair
    s.app.purpose_model.side_effect = ["blue blouse", proposal()]
    pid = await add(s)
    assert await s.service.run_due() == 1
    row = await s.service.promises.get(pid)
    artifact = json.loads(row["action_result_json"])
    assert artifact["original_prompt"] == "blue blouse"
    assert artifact["prompt_retry_count"] == 1
    assert s.generated[1][2]["prompt"] == "blue shirt"
    assert s.generated[0][0] != s.generated[1][0]
    assert s.peer.calls == 2 and len(s.sends) == 1
    assert s.guard.apply(s.image_values, s.connection, "red blouse")["prompt"] == "red shirt"
    assert s.app.purpose_model.call_args.args[1] == "closing"


async def test_retries_are_bounded_and_exhaustion_waits_for_user(mapping):
    s = mapping
    s.app.purpose_model.side_effect = ["blue blouse", proposal(), proposal("blue", "azure")]
    pid = await add(s)
    assert await s.service.run_due() == 0
    row = await s.service.promises.get(pid)
    artifact = json.loads(row["action_result_json"])
    assert (row["status"], row["action_state"]) == ("waiting", "held")
    assert artifact["prompt_retry_count"] == 2 and artifact["original_prompt"] == "blue blouse"
    assert s.peer.calls == 3 and len({r[0] for r in s.generated}) == 3
    s.app.send_promise_notice.assert_awaited_once()
    assert s.guard.learned(s.guard.scope(s.image_values, s.connection)) == []
    s.clock[0] += 3600
    s.service = PromiseService(s.service.store, s.app)
    assert await s.service.run_due() == 0 and s.peer.calls == 3


@pytest.mark.parametrize("kind", ["result_unknown", "delivery_unknown", "provider_error", "quota_exhausted"])
async def test_non_repairable_failures_do_not_request_rewrite(mapping, kind):
    s = mapping
    s.reject = kind
    pid = await add(s)
    await s.service.run_due()
    assert s.app.purpose_model.await_count == 1 and s.peer.calls == 1
    row = await s.service.promises.get(pid)
    assert row["status"] == ("unknown" if "unknown" in kind else "waiting")
    s.clock[0] += 3600
    await s.service.run_due()
    assert s.peer.calls == 1


@pytest.mark.parametrize("cause", ["disabled", "zero", "noop", "invalid", "pose"])
async def test_disabled_noop_or_scene_change_waits_without_second_image(mapping, cause):
    s = mapping
    if cause == "disabled":
        s.image_values["prompt_guard_enabled"] = False
    elif cause == "zero":
        s.image_values["prompt_guard_retry_limit"] = 0
    answer = {"noop": json.dumps({"changes_scene": False, "substitutions": []}),
              "invalid": "invalid",
              "pose": proposal(changes_scene=True, notice="建议改站姿，需要你确认。")}.get(cause, proposal())
    s.app.purpose_model.side_effect = ["blue blouse", answer]
    pid = await add(s)
    await s.service.run_due()
    assert s.peer.calls == 1 and (await s.service.promises.get(pid))["status"] == "waiting"
    if cause == "pose":
        assert "站姿" in s.app.send_promise_notice.call_args.args[1]


async def test_cancel_during_rewrite_prevents_paid_retry(mapping):
    s = mapping
    pid = await add(s)

    # running准备阶段通过事务直接模拟“整会话取消”，取消代次也会被实时检查。
    async def cancel_midway(*args, **kwargs):
        if "整理提示词" in args[2]:
            await s.service.store._run(lambda db: db.execute(
                "UPDATE promises SET status='cancelled' WHERE promise_id=?", (pid,)))
            return proposal()
        return "blue blouse"
    s.app.purpose_model.side_effect = cancel_midway
    await s.service.run_due()
    assert s.peer.calls == 1 and (await s.service.promises.get(pid))["status"] == "cancelled"


async def test_handoff_schedules_only_authorized_content_retry(mapping):
    s = mapping
    failure = {"kind": "content_rejected", "prompt": "blue blouse", "reason": "受控失败",
               "request_id": "handoff-image", "use_reference": False, "auto_prompt_retry": True}
    result = await s.service.promises.accept_image_handoff(
        s.context, request_id="handoff-image", source_event_id="source", failure=failure)
    assert result["task_status"] == "scheduled"
    s.app.purpose_model.return_value = proposal()
    s.reject = ""
    s.clock[0] += 301
    assert await s.service.run_due() == 1 and s.peer.calls == 1
    assert s.generated[0][2]["prompt"] == "blue shirt"


async def test_restart_with_prepared_repair_reuses_it_without_model_call(mapping):
    s = mapping
    pid = await add(s)
    recipe = s.guard.prepare_repair(s.image_values, s.connection, "blue blouse", json.loads(proposal()))
    await s.service.promises.move(pid, status="running", expect=("scheduled",))
    await s.service.promises.checkpoint_action(pid, "retry_ready", {
        "kind": "adjusted_prompt", "prompt": "blue blouse", "original_prompt": "blue blouse",
        "prompt_retry_count": 1, "prompt_repair": recipe})
    s.service = PromiseService(s.service.store, s.app)
    s.reject = ""
    s.app.purpose_model.side_effect = AssertionError("恢复准备结果不能重新调用模型")
    assert await s.service.run_due() == 1
    assert s.peer.calls == 1 and s.generated[0][2]["prompt"] == "blue shirt"


async def test_user_adjustment_resets_budget_and_clears_old_candidate(mapping):
    s = mapping
    pid = await add(s)
    await s.service.promises.move(pid, status="running", expect=("scheduled",))
    await s.service.promises.hold_image_request(s.context, pid, {
        "kind": "prompt_adjustment_required", "prompt": "blue blouse", "request_id": "failed",
        "prompt_retry_count": 2, "prompt_repair": {}, "notice": "确认站姿"})
    resumed = await s.service.promises.resume_image_handoff(
        s.context, pid, prompt="花园里的橙色猫", source_event_id="new-user")
    assert resumed["status"] == "resumed"
    artifact = json.loads((await s.service.promises.get(pid))["action_result_json"])
    assert artifact["prompt_retry_count"] == 0 and artifact["original_prompt"] == "花园里的橙色猫"
    assert "prompt_repair" not in artifact and "notice" not in artifact


async def test_rate_limit_after_repair_preserves_recipe_and_does_not_rewrite_again(mapping):
    s = mapping
    generate = s.peer.generate_deferred_image.side_effect
    kinds = iter(["content_rejected", "rate_limited", ""])

    async def successive(event, prompt):
        s.reject = next(kinds)
        return await generate(event, prompt)
    s.peer.generate_deferred_image.side_effect = successive
    s.app.purpose_model.side_effect = ["blue blouse", proposal()]
    pid = await add(s)
    assert await s.service.run_due() == 0
    assert (await s.service.promises.get(pid))["status"] == "scheduled"
    s.clock[0] += 301
    assert await s.service.run_due() == 1
    assert s.app.purpose_model.await_count == 2 and s.peer.calls == 3
    assert s.generated[-1][2]["prompt"] == "blue shirt"


async def test_facade_readiness_and_authorized_handoff_preserve_original(mapping, tmp_path):
    s = mapping
    app, _, _ = await application(tmp_path, {"timezone": "UTC"})
    try:
        app.promise_actions_active = lambda: True
        msg = Message("source", "请画窗边的猫")
        await app.on_message(msg)
        scope = Context.from_dict(msg.get_extra("livingemotion:context"))
        ready = await app.api.get_image_prompt_retry_policy(scope, event=msg)
        assert ready["data"]["allowed"] is True
        app.bridge.discover = lambda _: s.peer
        msg.set_extra("_livinghello_image_failure", {
            "kind": "content_rejected", "reason": "受控失败", "prompt": "blue blouse",
            "original_prompt": "blue blouse", "attempted_prompt": "blue blouse",
            "request_id": "facade-image", "notified": True, "use_reference": False})
        receipt = await app.api.handoff_image_failure(scope, event=msg)
        assert receipt["data"]["task_status"] == "scheduled"
        row = await app._promises().promises.get(receipt["data"]["promise_id"])
        assert json.loads(row["action_result_json"])["original_prompt"] == "blue blouse"
        app.promise_actions_active = lambda: False
        assert (await app.api.get_image_prompt_retry_policy(scope, event=msg))["data"]["allowed"] is False
    finally:
        await app.terminate()
