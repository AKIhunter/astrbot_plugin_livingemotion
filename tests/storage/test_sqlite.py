import asyncio
from dataclasses import replace
import json
import sqlite3
import threading

import pytest

from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import (
    BehaviorIntent, ContentKind, Experience, RelationshipContribution, StateWrite,
)
from astrbot_plugin_livingemotion.storage import SQLiteStore, StoreClosed
from astrbot_plugin_livingemotion.storage.schema import MIGRATIONS, migrate


async def test_atomic_event_projection_and_duplicate(le_store, le_event):
    write = StateWrite("bot", {"pleasure": 0.2})
    contribution = RelationshipContribution("source-1", "human-1", le_event.occurred_at,
                                             2, "care", "2027-01-15")
    result = await le_store.commit_event(le_event, 0, (write,), (contribution,))
    assert result.accepted
    duplicate = await le_store.commit_event(le_event, 0, (write,), (contribution,))
    assert duplicate.status == "duplicate"
    record = await le_store.get_state(le_event.context, "bot")
    assert record.version == 1
    assert record.value == {"pleasure": 0.2}
    assert len(await le_store.relationship_ledger(le_event.context)) == 1
    assert (await le_store.health())["counts"]["events"] == 1


async def test_partial_projection_failure_rolls_back_all(le_store, le_event):
    with pytest.raises(ValueError):
        await le_store.commit_event(le_event, 0, (
            StateWrite("bot", {"pleasure": 0.2}), StateWrite("invalid_kind", {}),
        ))
    assert await le_store.get_state(le_event.context, "bot") is None
    assert (await le_store.health())["counts"]["events"] == 0
    assert (await le_store.commit_event(le_event, 0)).accepted


async def test_bad_contribution_rolls_back_event_and_projection(le_store, le_event):
    bad = RelationshipContribution("source", "other-account", le_event.occurred_at,
                                   1, "care", "2027-01-15")
    with pytest.raises(ValueError):
        await le_store.commit_event(le_event, 0, (StateWrite("bot", {"stress": 0.1}),), (bad,))
    assert await le_store.get_state(le_event.context, "bot") is None
    assert (await le_store.commit_event(le_event, 0)).accepted


async def test_nonfinite_payload_is_not_committed(le_store, le_event):
    with pytest.raises(ValueError):
        await le_store.commit_event(le_event, 0, (StateWrite("bot", {"stress": float("nan")}),))
    assert (await le_store.health())["counts"]["events"] == 0


async def test_rejects_unreliable_and_future_event(le_store, le_event):
    assert (await le_store.commit_event(replace(le_event, reliable_source=False), 0)).reason_code == (
        "unreliable_source"
    )
    assert (await le_store.commit_event(replace(le_event, occurred_at=1_900_000_000), 0)).reason_code == (
        "future_event"
    )


async def test_dedupe_survives_reload(le_store, le_event):
    await le_store.commit_event(le_event, 0)
    await le_store.close()
    reopened = SQLiteStore(le_store.path, clock=le_store.clock)
    await reopened.open()
    try:
        assert (await reopened.commit_event(le_event, 0)).status == "duplicate"
        assert (await reopened.health())["journal_mode"] == "wal"
    finally:
        await reopened.close()


async def test_twenty_concurrent_cas_writers(le_store, le_event_factory, le_context):
    async def increment(number):
        for _ in range(100):
            previous = await le_store.get_state(le_context, "bot")
            version = previous.version if previous else 0
            count = previous.value["count"] if previous else 0
            result = await le_store.commit_event(
                le_event_factory(number), 0, (StateWrite("bot", {"count": count + 1}, version),),
            )
            if result.accepted:
                return
            assert result.reason_code == "version_conflict"
        pytest.fail("CAS did not converge")
    await asyncio.gather(*(increment(number) for number in range(20)))
    record = await le_store.get_state(le_context, "bot")
    assert record.value["count"] == record.version == 20
    assert (await le_store.health())["counts"]["events"] == 20


async def test_two_connections_compete_without_partial_acceptance(le_store, le_event_factory):
    other = SQLiteStore(le_store.path, clock=le_store.clock)
    await other.open()
    try:
        results = await asyncio.gather(
            le_store.commit_event(le_event_factory(1), 0, (StateWrite("bot", {"count": 1}),)),
            other.commit_event(le_event_factory(2), 0, (StateWrite("bot", {"count": 1}),)),
        )
        assert sorted(result.status for result in results) == ["accepted", "rejected"]
        assert (await other.health())["counts"]["events"] == 1
    finally:
        await other.close()


async def test_scope_isolation_and_account_keys(le_store, le_event):
    await le_store.commit_event(le_event, 0, (
        StateWrite("bot", {"pleasure": 0.4}),
        StateWrite("observation", {"labels": ["sad"]}, record_key=le_event.context.account_id),
    ))
    for field in ("bot_id", "persona_id", "adapter_id", "platform", "scene_id"):
        assert await le_store.get_state(replace(le_event.context, **{field: "other"}), "bot") is None
    with pytest.raises(ValueError):
        await le_store.get_state(replace(le_event.context, account_id="other"), "observation",
                                 le_event.context.account_id)


async def test_body_window_has_per_scope_and_global_caps(tmp_path, le_event_factory, le_context):
    config = Config(window_per_scope=2, window_global=3, body_max_chars=5)
    store = SQLiteStore(tmp_path / "window.db", config=config, clock=lambda: 1_800_000_001)
    await store.open()
    try:
        for index in range(3):
            await store.commit_event(le_event_factory(index), 0)
        window = await store.read_window(le_context, limit=2)
        assert len(window) == 2
        assert all(len(item["body"]) == 5 for item in window)
        other = replace(le_context, scene_id="another")
        for index in range(3, 5):
            await store.commit_event(le_event_factory(index, context=other), 0)
        assert (await store.health())["counts"]["body_window"] == 3
        assert len(await store.read_window(other, limit=2)) == 2
        assert len(await store.read_window(le_context, limit=2)) == 1
    finally:
        await store.close()


async def test_ttl_drops_body_not_ledger_and_retains_dedupe(le_store, le_event):
    contribution = RelationshipContribution("source-1", "human-1", le_event.occurred_at,
                                             1, "care", "2027-01-15")
    await le_store.commit_event(le_event, 0, contributions=(contribution,))
    le_store.clock = lambda: 1_800_000_001 + 8 * 86400
    assert await le_store.read_window(le_event.context) == []
    await le_store.cleanup()
    assert (await le_store.health())["counts"]["body_window"] == 0
    assert (await le_store.health())["counts"]["events"] == 1
    le_store.clock = lambda: 1_800_000_001 + 31 * 86400
    await le_store.cleanup()
    assert (await le_store.health())["counts"]["events"] == 0
    assert len(await le_store.relationship_ledger(le_event.context)) == 1
    assert (await le_store.commit_event(le_event, 0)).status == "duplicate"
    with sqlite3.connect(le_store.path) as db:
        assert not any(le_event.body in row[0] for row in db.execute(
            "SELECT metadata_json FROM events"))


async def test_cold_scope_window_not_skipped_by_hot_scope(le_store, le_event_factory, le_context):
    other = replace(le_context, scene_id="hot")
    await le_store.commit_event(le_event_factory(1), 0)
    for index in range(2, 20):
        await le_store.commit_event(le_event_factory(index, context=other), 0)
    cold = await le_store.read_window(le_context, after_seq=0)
    assert [item["event_id"] for item in cold] == ["event-1"]


async def test_clear_invalidates_inflight_and_keeps_quota(le_store, le_event):
    context = le_event.context
    await le_store.commit_event(le_event, 0, (StateWrite("bot", {"stress": 0.5}),))
    await le_store.reserve_quota("q1", context, 0, period="day", purpose="emotion", limit=1)
    assert (await le_store.clear_scope(context, 0)).generation == 1
    assert (await le_store.write_states(context, 0, (StateWrite("bot", {}),))).reason_code == (
        "stale_generation"
    )
    assert (await le_store.commit_event(replace(le_event, source_id="new"), 0)).reason_code == (
        "stale_generation"
    )
    assert await le_store.get_state(context, "bot") is None
    assert (await le_store.commit_event(le_event, 1)).status == "duplicate"
    assert await le_store.quota_usage(period="day") == 1
    assert (await le_store.reserve_quota(
        "q2", context, 1, period="day", purpose="emotion", limit=1))["reason_code"] == "quota_exhausted"


async def test_concurrent_quota_inflight_failure_and_restart(le_store, le_context):
    results = await asyncio.gather(*(le_store.reserve_quota(
        f"q{index}", le_context, 0, period="day", purpose="emotion", limit=3,
    ) for index in range(20)))
    assert sum(result["status"] == "reserved" for result in results) == 3
    await le_store.finish_quota("q0", status="failed", reason_code="synthetic_failure")
    assert await le_store.quota_usage(period="day") == 3
    await le_store.close()
    store = SQLiteStore(le_store.path)
    await store.open()
    try:
        await store.recover_inflight()
        assert await store.quota_usage(period="day") == 3
        assert (await store.reserve_quota(
            "new", le_context, 0, period="day", purpose="emotion", limit=3
        ))["status"] == "rejected"
        assert (await store.reserve_quota(
            "next-day", le_context, 0, period="next", purpose="emotion", limit=3
        ))["status"] == "reserved"
    finally:
        await store.close()


async def test_global_quota_across_purposes(le_store, le_context):
    assert (await le_store.reserve_quota(
        "diary", le_context, 0, period="day", purpose="diary", limit=2, global_limit=1,
    ))["status"] == "reserved"
    assert (await le_store.reserve_quota(
        "dream", le_context, 0, period="day", purpose="dream", limit=2, global_limit=1,
    ))["reason_code"] == "quota_exhausted"
    assert (await le_store.reserve_quota(
        "send", le_context, 0, period="day", purpose="send", pool="send", limit=2, global_limit=1,
    ))["status"] == "reserved"


async def test_intent_unknown_is_never_retried(le_store, le_context):
    now = le_store.clock()
    intent = BehaviorIntent("intent-1", le_context, "proactive", now, now + 60, 0)
    assert (await le_store.create_intent(intent))["status"] == "created"
    await le_store.reserve_quota("q1", le_context, 0, period="day", purpose="send", limit=1)
    for old, new in (("pending", "reserved"), ("reserved", "generating"), ("generating", "sending")):
        result = await le_store.transition_intent(
            le_context, intent.intent_id, 0, expected_status=old, status=new,
            reason_code="test", reservation_id="q1",
        )
        assert result["status"] == "updated"
    recovered = await le_store.recover_inflight()
    assert recovered["unknown"] == 1
    assert (await le_store.get_intent(le_context, "intent-1"))["status"] == "unknown"
    assert (await le_store.transition_intent(
        le_context, intent.intent_id, 0, expected_status="unknown", status="sending",
        reason_code="retry",
    ))["reason_code"] == "invalid_transition"
    assert (await le_store.create_intent(intent))["status"] == "duplicate"


async def test_one_reservation_cannot_back_two_intents(le_store, le_context):
    now = le_store.clock()
    for number in (1, 2):
        await le_store.create_intent(BehaviorIntent(str(number), le_context, "send", now, now + 60, 0))
    await le_store.reserve_quota("q", le_context, 0, period="day", purpose="send", limit=1)
    results = await asyncio.gather(*(le_store.transition_intent(
        le_context, str(number), 0, expected_status="pending", status="reserved",
        reason_code="reserved", reservation_id="q",
    ) for number in (1, 2)))
    assert [result["status"] for result in results].count("updated") == 1


async def test_sending_rechecks_human_and_context_tokens(le_store, le_context, le_event):
    now = le_store.clock()
    await le_store.create_intent(BehaviorIntent("i", le_context, "send", now, now + 60, 0))
    await le_store.reserve_quota("q", le_context, 0, period="day", purpose="send", limit=1)
    for old, new in (("pending", "reserved"), ("reserved", "generating")):
        await le_store.transition_intent(le_context, "i", 0, expected_status=old, status=new,
                                         reason_code="test", reservation_id="q")
    assert (await le_store.transition_intent(
        replace(le_context, identity_revision="revoked"), "i", 0,
        expected_status="generating", status="sending", reason_code="send",
    ))["reason_code"] == "context_changed"
    await le_store.commit_event(le_event, 0)
    assert (await le_store.transition_intent(
        le_context, "i", 0, expected_status="generating", status="sending", reason_code="send",
    ))["reason_code"] == "new_human_message"


async def test_wal_backup_is_consistent_and_non_destructive(le_store, le_event, tmp_path):
    await le_store.commit_event(le_event, 0, (StateWrite("bot", {"pleasure": 0.3}),))
    destination = tmp_path / "snapshot.db"
    await le_store.backup(destination)
    with sqlite3.connect(destination) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
        assert json.loads(db.execute("SELECT value_json FROM states").fetchone()[0]) == {
            "pleasure": 0.3,
        }
    with pytest.raises(ValueError):
        await le_store.backup(destination)


def test_schema_migration_failure_rolls_back(tmp_path):
    with sqlite3.connect(tmp_path / "migration.db", isolation_level=None) as db:
        migrate(db)
        with pytest.raises(sqlite3.OperationalError):
            migrate(db, (*MIGRATIONS, (
                "CREATE TABLE should_rollback(value TEXT)",
                "INSERT INTO missing_table VALUES(1)",
            )))
        assert db.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)
        assert db.execute(
            "SELECT name FROM sqlite_master WHERE name='should_rollback'").fetchone() is None


async def test_experience_unique_persona_day_and_stale_generation(le_store, le_context):
    experience = Experience("x1", le_context, ContentKind.DIARY, "2027-01-15",
                            le_store.clock(), "synthetic diary")
    assert (await le_store.save_experience(experience, 0))["status"] == "created"
    another_scene = replace(experience, experience_id="x2",
                            context=replace(le_context, scene_id="other"))
    assert (await le_store.save_experience(another_scene, 0))["status"] == "duplicate"
    await le_store.clear_scope(le_context, 0)
    assert (await le_store.save_experience(experience, 0))["reason_code"] == "stale_generation"


async def test_cancelled_thread_is_drained_before_close(le_store):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()

    def blocked(db):
        entered.set()
        release.wait(timeout=5)
        db.execute("SELECT 1").fetchone()
        finished.set()

    task = asyncio.create_task(le_store._run(blocked))
    while not entered.is_set():
        await asyncio.sleep(0.001)
    task.cancel()
    closing = asyncio.create_task(le_store.close())
    await asyncio.sleep(0.01)
    assert not closing.done()
    assert not finished.is_set()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await closing
    assert finished.is_set()
    with pytest.raises(StoreClosed):
        await le_store.health()


async def test_host_instance_changes_isolate_state_and_event_keys(le_store, le_event):
    await le_store.commit_event(le_event, 0, (StateWrite("bot", {"pleasure": 0.2}),))
    other = replace(le_event, context=replace(le_event.context, instance_id="other-host"))
    assert await le_store.get_state(other.context, "bot") is None
    assert (await le_store.commit_event(other, 0)).accepted
    assert (await le_store.health())["counts"]["events"] == 2


async def test_cooldown_persists_across_reload_and_failure(le_store, le_context):
    params = dict(period="day", purpose="emotion", limit=48, min_interval_seconds=300)
    assert (await le_store.reserve_quota("q1", le_context, 0, **params))["status"] == "reserved"
    await le_store.finish_quota("q1", status="failed", reason_code="failed")
    await le_store.close()
    store = SQLiteStore(le_store.path, clock=le_store.clock)
    await store.open()
    try:
        assert (await store.reserve_quota("q2", le_context, 0, **params))["reason_code"] == (
            "quota_cooldown"
        )
        store.clock = lambda: le_store.clock() + 300
        assert (await store.reserve_quota("q2", le_context, 0, **params))["status"] == "reserved"
    finally:
        await store.close()


async def test_bot_receipt_does_not_advance_human_watermark(le_store, le_event):
    assert await le_store.human_watermark(le_event.context) == 0
    await le_store.commit_event(replace(le_event, actor_role="bot"), 0)
    assert await le_store.human_watermark(le_event.context) == 0
    await le_store.commit_event(replace(le_event, source_id="human-source"), 0)
    assert await le_store.human_watermark(le_event.context) > 0
