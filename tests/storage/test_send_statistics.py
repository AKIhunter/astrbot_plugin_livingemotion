"""Read counters must not conflate quota consumption with delivery."""
from astrbot_plugin_livingemotion.contracts import BehaviorIntent


async def test_send_quota_counts_all_outcomes_and_orphan_success_is_unknown(le_store, le_context):
    now = le_store.clock()
    period = "2026-11-14"
    for terminal in ("succeeded", "unknown", "cancelled", "failed", "reserved"):
        key = "statistics:" + terminal
        await le_store.create_intent(BehaviorIntent(key, le_context, "closing", now, now + 300, 0))
        assert (await le_store.reserve_quota(
            key + ":send", le_context, 0, period=period, purpose="closing", pool="send",
            limit=6, global_limit=6))["status"] == "reserved"
        previous = "pending"
        for status in ("reserved", "generating", "sending"):
            if terminal == "reserved" and status != "reserved":
                break
            if terminal == "cancelled" and status == "sending":
                break
            assert (await le_store.transition_intent(
                le_context, key, 0, expected_status=previous, status=status, reason_code="test",
                reservation_id=key + ":send" if status == "reserved" else None))["status"] == "updated"
            previous = status
        if terminal != "reserved":
            receipt = {"status": "confirmed" if terminal == "succeeded" else "unknown",
                       "receipt_id": "123" if terminal == "succeeded" else None}
            assert (await le_store.transition_intent(
                le_context, key, 0, expected_status=previous, status=terminal, reason_code="test",
                transport_receipt=receipt))["status"] == "updated"
            await le_store.finish_quota(key + ":send", status=terminal, reason_code="test")
    await le_store.reserve_quota("orphan", le_context, 0, period=period,
        purpose="closing", pool="send", limit=6, global_limit=6)
    await le_store.finish_quota("orphan", status="succeeded", reason_code="old")
    expected = dict(consumed=6, confirmed=1, unknown=2, cancelled=1, failed=1, in_progress=1)
    result = await le_store.send_statistics(le_context, period)
    assert result["global"] == result["scope"] == expected
    assert (await le_store.behavior_history(le_context, period))["global_used"] == 6
    assert (await le_store.reserve_quota("seventh", le_context, 0, period=period,
        purpose="closing", pool="send", limit=6, global_limit=6))["status"] == "rejected"
