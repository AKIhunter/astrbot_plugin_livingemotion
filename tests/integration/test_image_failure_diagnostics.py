"""Issue #9: truthful receipts, isolated failures and replay-safe model budgets."""
import json
from unittest.mock import AsyncMock

import pytest

from test_promise_actions import scenario, add
from astrbot_plugin_livingemotion.runtime.promise_service import PromiseService


@pytest.mark.parametrize("reason", [
    "relationship_unavailable", "action_policy_unavailable", "reply_cancelled",
    "invalid_parameters", "reply_or_config_changed",
])
async def test_unrequested_failure_preserves_permission_reason(scenario, reason):
    s = scenario
    s.app.send_promise_notice = AsyncMock(return_value="sent")
    s.peer.generate_deferred_image = AsyncMock(return_value={
        "status": "failed", "failure": {
            "kind": "provider_error", "reason": "这次未能开始生图。",
            "reason_code": reason, "requested": False, "prompt": "猫",
        }})
    pid = await add(s)
    assert await s.service.run_due() == 0
    row = await s.service.promises.get(pid)
    artifact = json.loads(row["action_result_json"])
    assert row["status"] == "waiting"
    assert artifact["reason_code"] == reason and artifact["requested"] is False
    s.clock[0] += 301
    await s.service.run_due()
    s.peer.generate_deferred_image.assert_awaited_once()


@pytest.mark.parametrize("receipt", [None, [], {"status": "unknown", "reason": "duplicate_image_call"}])
async def test_invalid_or_duplicate_receipt_does_not_repeat_image(scenario, receipt):
    s = scenario
    s.app.send_promise_notice = AsyncMock(return_value="sent")
    s.peer.generate_deferred_image = AsyncMock(return_value=receipt)
    pid = await add(s)
    await s.service.run_due()
    row = await s.service.promises.get(pid)
    assert row["status"] == "unknown"
    artifact = json.loads(row["action_result_json"])
    assert artifact["reason_code"] == (
        "duplicate_image_call" if isinstance(receipt, dict) else "invalid_peer_receipt")
    s.service = PromiseService(s.service.store, s.app)
    s.clock[0] += 301
    await s.service.run_due()
    s.peer.generate_deferred_image.assert_awaited_once()


async def test_exception_type_is_retained_without_private_body(scenario, le_log):
    s = scenario
    s.app.send_promise_notice = AsyncMock(return_value="sent")
    s.peer.generate_deferred_image = AsyncMock(side_effect=RuntimeError("sk-private-fixture"))
    pid = await add(s)
    await s.service.run_due()
    row = await s.service.promises.get(pid)
    assert row["status"] == "unknown"
    assert json.loads(row["action_result_json"])["exception_type"] == "RuntimeError"
    assert "RuntimeError" in le_log.text
    assert "sk-private-fixture" not in le_log.text + row["action_result_json"]
