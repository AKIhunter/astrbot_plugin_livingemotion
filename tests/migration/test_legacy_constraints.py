"""F3: synthetic import -> real SQLite reopen -> pure constraints and cleanup."""

import asyncio
import copy
import json
from dataclasses import replace
from datetime import datetime, timezone

import pytest
from astrbot_plugin_livingemotion.contracts import Event, canonical_json
from astrbot_plugin_livingemotion.runtime.legacy import (
    evaluate_legacy,
    evaluate_legacy_constraints,
)
from astrbot_plugin_livingemotion.storage import SQLiteStore
from astrbot_plugin_livingemotion.storage import legacy_import as migration
from astrbot_plugin_livingemotion.tests.migration import test_legacy_import as fixtures

sample = fixtures.sample
NOW, YES, execute = fixtures.NOW, fixtures.YES, fixtures.execute
DAY = datetime.fromtimestamp(NOW, timezone.utc).date().isoformat()


def behavior_selection(sample, *, binding=True, cooldown=NOW - 1, unanswered=2):
    source, _, selection, context = sample
    values = {
        "proactive.sessions": {"old-session": {
            "last_at": NOW - 200, "next_ok_at": cooldown,
            "unanswered": unanswered, "sent_today": 2, "day": DAY,
        }},
        "proactive.global": {"sent_today": 3, "day": DAY},
    }
    for key, value in values.items():
        execute(source, "UPDATE kv SET v=? WHERE k=?", (canonical_json(value), key))
    selection = copy.deepcopy(selection)
    selection["rows"] = [row for row in selection["rows"] if row["key"].get("k") in values]
    if binding:
        for row in selection["rows"]:
            row["context_id"] = context.account_key
            row["constraint_binding"] = {
                "timezone": "UTC", "quota_scope": (
                    "instance" if row["key"]["k"] == "proactive.global" else "scope"
                ),
            }
    return selection


def import_selection(sample, selection, *, now=NOW):
    source, target = sample[:2]
    manifest = migration.preview(source, target, selection, **YES)
    assert migration.import_manifest(source, target, manifest, now=now, **YES)["inserted"]
    return manifest


async def rows_from_store(target, *, now=NOW):
    store = SQLiteStore(target, clock=lambda: now)
    await store.open()
    try:
        return await store.legacy_baselines()
    finally:
        await store.close()


def evaluate(rows, context, *, now=NOW, purpose="behavior", watermark=0, zone="UTC"):
    return evaluate_legacy(
        rows, context, purpose=purpose, timezone=zone, now=now, human_watermark=watermark,
    )


def test_real_import_restart_known_floors_do_not_double_add(sample):
    selection = behavior_selection(sample)
    manifest = import_selection(sample, selection)
    rows = asyncio.run(rows_from_store(sample[1]))
    before = copy.deepcopy(rows)
    result = evaluate(rows, sample[3])
    assert result["allowed"], result
    assert result["global_used_floor"] == 3  # Not global 3 + session 2.
    assert result["scope_used_floor"] == result["unanswered_floor"] == 2
    assert result["cooldown_until"] == NOW - 1
    assert result["last_attempt_at"] is None  # Never restart TTL from last_at.
    assert len(result["sources"]) == 2
    assert rows == before
    assert evaluate(rows + rows, sample[3]) == result
    assert migration.import_manifest(*sample[:2], manifest, now=NOW + 10, **YES)["inserted"] == 0
    assert asyncio.run(rows_from_store(sample[1])) == rows
    for table in ("intents", "quota_reservations", "events"):
        assert not execute(sample[1], f"SELECT * FROM {table}")


def test_known_cooldown_uses_original_absolute_deadline(sample):
    import_selection(sample, behavior_selection(sample, cooldown=NOW + 800))
    rows = asyncio.run(rows_from_store(sample[1]))
    for at in (NOW, NOW + 799):
        result = evaluate(rows, sample[3], now=at)
        assert not result["allowed"] and "legacy_cooldown_active" in result["reason_codes"]
        assert result["cooldown_until"] == NOW + 800
    assert evaluate(rows, sample[3], now=NOW + 800)["allowed"]
    assert evaluate(rows, sample[3], now=NOW + 801)["cooldown_until"] == NOW + 800


def test_unknown_scope_timezone_cannot_be_resolved_by_flags_or_next_day(sample):
    import_selection(sample, behavior_selection(sample, binding=False))
    rows = asyncio.run(rows_from_store(sample[1]))
    for row in rows:
        row["value"]["activation_blockers"] = []
        row["value"]["baseline"]["runtime_adopted"] = True
    for at in (NOW, NOW + 8 * 86400):
        result = evaluate(rows, sample[3], now=at)
        assert not result["allowed"]
        assert {"legacy_scope_unresolved", "legacy_timezone_unresolved",
                "legacy_quota_scope_unresolved"} <= set(result["reason_codes"])
        assert result["global_used_floor"] == 3


def test_explicit_original_day_and_timezone_end_quota_only(sample):
    import_selection(sample, behavior_selection(sample))
    rows = asyncio.run(rows_from_store(sample[1]))
    assert evaluate(rows, sample[3], zone="Asia/Shanghai")["allowed"] is False
    tomorrow = evaluate(rows, sample[3], now=NOW + 86400)
    assert tomorrow["allowed"]
    assert tomorrow["global_used_floor"] == tomorrow["scope_used_floor"] == 0
    assert tomorrow["unanswered_floor"] == 2  # Not a daily counter.
    assert not evaluate(rows, sample[3], now=NOW - 86400)["allowed"]


def test_scope_isolation_preserves_instance_quota_without_relationship_projection(sample):
    import_selection(sample, behavior_selection(sample, cooldown=NOW + 800))
    rows = asyncio.run(rows_from_store(sample[1]))
    other = replace(sample[3], scene_id="other", account_id="other", bot_id="other-bot")
    result = evaluate(rows, other)
    assert result["allowed"]
    assert result["global_used_floor"] == 3
    assert result["scope_used_floor"] == result["unanswered_floor"] == 0
    assert result["cooldown_until"] is None
    assert "relationship" not in result


def test_distinct_sessions_sum_but_global_overlaps(sample):
    selection = behavior_selection(sample)
    source, target, _, context = sample
    original = json.loads(execute(source, "SELECT v FROM kv WHERE k='proactive.sessions'")[0][0])
    original["another"] = {**original["old-session"], "sent_today": 2}
    execute(source, "UPDATE kv SET v=? WHERE k='proactive.sessions'", (canonical_json(original),))

    async def register():
        store = SQLiteStore(target)
        await store.open()
        try:
            return await store.register_context(replace(context, scene_id="another"))
        finally:
            await store.close()

    identifier = asyncio.run(register())
    selected = copy.deepcopy(selection["rows"][0])
    selected.update(member="another", context_id=identifier)
    selection["rows"].append(selected)
    import_selection(sample, selection)
    result = evaluate(asyncio.run(rows_from_store(target)), context)
    assert result["global_used_floor"] == 4  # max(global 3, sessions 2 + 2).
    assert result["scope_used_floor"] == 2


def test_preimport_human_or_bot_does_not_clear_old_unanswered(sample):
    context, target = sample[3], sample[1]

    async def message(number, role, *, now=NOW):
        store = SQLiteStore(target, clock=lambda: now)
        await store.open()
        try:
            event = Event(str(number), "test", "message", context, role, now, str(number),
                          actor_id=context.account_id if role == "human" else context.bot_id)
            assert (await store.commit_event(event, 0)).accepted
            return await store.human_watermark(context)
        finally:
            await store.close()

    old = asyncio.run(message(1, "human"))
    manifest = import_selection(sample, behavior_selection(sample))
    rows = asyncio.run(rows_from_store(target))
    assert all(r["value"]["runtime_constraints"]["import_human_watermark"] == old for r in rows)
    assert evaluate(rows, context, watermark=old)["unanswered_floor"] == 2
    bot = asyncio.run(message(2, "bot"))
    assert evaluate(rows, context, watermark=bot)["unanswered_floor"] == 2
    new = asyncio.run(message(3, "human", now=NOW + 1))
    result = evaluate(rows, context, watermark=new)
    assert result["unanswered_floor"] == 0
    assert result["global_used_floor"] == 3
    assert migration.import_manifest(*sample[:2], manifest, now=NOW + 2, **YES)["inserted"] == 0
    assert evaluate(asyncio.run(rows_from_store(target)), context, watermark=new) == result


@pytest.mark.parametrize("quota", [None, 1, 2])
def test_dream_unknown_night_period_denied_after_restart(sample, quota):
    selection = copy.deepcopy(sample[2])
    selection["rows"] = [row for row in selection["rows"] if row["key"].get("k") == "night.state"]
    value = json.loads(execute(sample[0], "SELECT v FROM kv WHERE k='night.state'")[0][0])
    value["dream_count_today"] = quota
    execute(sample[0], "UPDATE kv SET v=? WHERE k='night.state'", (canonical_json(value),))
    import_selection(sample, selection)
    rows = asyncio.run(rows_from_store(sample[1]))
    for at in (NOW, NOW + 864000):
        result = evaluate(rows, sample[3], now=at, purpose="dream")
        assert result["reason_codes"] == ("legacy_dream_period_unresolved",)
        assert not result["allowed"]
    assert not execute(sample[1], "SELECT * FROM quota_reservations")


@pytest.mark.parametrize("mutation", [
    lambda row: row["value"]["baseline"].update(quota_used=True),
    lambda row: row["value"]["baseline"].update(quota_used=-1),
    lambda row: row["value"]["baseline"].update(quota_used=1.5),
    lambda row: row["value"]["baseline"].update(cooldown_until=float("inf")),
    lambda row: row["value"]["runtime_constraints"].update(version=99),
    lambda row: row.update(scope_key="forged"),
])
def test_malformed_restricted_payload_fails_closed(sample, mutation):
    import_selection(sample, behavior_selection(sample))
    rows = list(asyncio.run(rows_from_store(sample[1])))
    session = next(r for r in rows if r["value"]["baseline"]["level"] == "session")
    mutation(session)
    assert evaluate(rows, sample[3])["reason_codes"] == ("legacy_constraints_invalid",)


def test_pure_port_is_bounded_and_does_not_treat_no_history_as_blocked(sample):
    context = sample[3]
    for purpose in ("behavior", "emotion", "diary", "dream", "export"):
        assert evaluate([], context, purpose=purpose)["allowed"]
    assert not evaluate([{}] * 2001, context)["allowed"]
    assert not evaluate({}, context)["allowed"]
    assert not evaluate([], context, now=float("nan"))["allowed"]
    assert not evaluate([], context, purpose="unknown")["allowed"]
    assert evaluate_legacy_constraints([], context, NOW)["allowed"]


def test_same_owner_other_scene_cannot_evade_unknown_night_or_export(sample):
    selection = copy.deepcopy(sample[2])
    selection["rows"] = [row for row in selection["rows"] if row["key"].get("k") == "night.state"]
    import_selection(sample, selection)
    rows = asyncio.run(rows_from_store(sample[1]))
    other_scene = replace(sample[3], scene_id="another-scene")
    other_bot = replace(other_scene, bot_id="another-bot")
    assert not evaluate(rows, other_scene, purpose="dream")["allowed"]
    assert not evaluate(rows, other_scene, purpose="export")["allowed"]
    assert evaluate(rows, other_bot, purpose="dream")["allowed"]
    assert evaluate(rows, other_bot, purpose="export")["allowed"]


def test_conflicting_or_multiple_source_snapshots_are_not_guessed_disjoint(sample):
    import_selection(sample, behavior_selection(sample))
    rows = list(asyncio.run(rows_from_store(sample[1])))
    changed = copy.deepcopy(rows[0])
    changed["value"]["baseline"]["quota_used"] += 1
    assert not evaluate([*rows, changed], sample[3])["allowed"]
    changed["value"]["source_id"] = "another-source-with-unproven-overlap"
    assert "legacy_multiple_sources_unreconciled" in evaluate(
        [*rows, changed], sample[3],
    )["reason_codes"]


def test_invalid_binding_is_not_accepted_as_source_proof(sample):
    selection = behavior_selection(sample)
    selection["rows"][0]["constraint_binding"]["timezone"] = "not/a-timezone"
    with pytest.raises(migration.MigrationError, match="invalid_legacy_timezone"):
        migration.preview(*sample[:2], selection, **YES)
    selection["rows"][0]["constraint_binding"]["timezone"] = "UTC"
    selection["rows"][0].pop("context_id")
    with pytest.raises(migration.MigrationError, match="constraint_binding_requires_mapped"):
        migration.preview(*sample[:2], selection, **YES)


def test_expired_originals_and_native_experiences_not_saved_at_import(sample):
    source, target, selection, _ = sample
    selection = copy.deepcopy(selection)
    selection["rows"] = [row for row in selection["rows"] if row["table"] == "mem_diary"
                         or row["key"].get("k") == "night.dreams"]
    selection["rows"].append({"table": "msg_archive", "key": {"id": 2}})
    selection["window"] = {"since": NOW - 9 * 86400, "until": NOW - 7 * 86400}
    execute(source, "UPDATE mem_diary SET created_at=?, pinned=1", (NOW - 8 * 86400,))
    execute(source, "UPDATE msg_archive SET ts=? WHERE id=2", (NOW - 8 * 86400,))
    dreams = json.loads(execute(source, "SELECT v FROM kv WHERE k='night.dreams'")[0][0])
    for dream in dreams:
        dream["created_at"] = NOW - 8 * 86400
        dream["pinned"] = True
        dream["refs"] = [{"id": 9, "text": "BODY MUST NOT SURVIVE AS A REFERENCE"}]
    execute(source, "UPDATE kv SET v=?,updated_at=? WHERE k='night.dreams'",
            (canonical_json(dreams), NOW + 100000))
    manifest = import_selection(sample, selection)
    values = fixtures.archive_values(target)
    assert all(value["history_redacted"] for value in values)
    assert all(value["history_expires_at"] <= NOW for value in values)
    assert "SYNTHETIC" not in canonical_json(values)
    assert "BODY MUST NOT SURVIVE" not in canonical_json(values)
    assert all(value["source_hash"] and value["key"] for value in values)
    assert all(value["source_refs"] == ["9"] for value in values if value["table"] == "kv")
    assert not execute(target, "SELECT * FROM experiences")
    assert migration.verify(source, target, manifest, now=NOW, **YES)["status"] == "verified"
    assert migration.import_manifest(source, target, manifest, now=NOW + 86400, **YES)[
        "inserted"] == 0


def test_expiry_during_preview_import_gap_and_new_source_id_cannot_extend_body(sample):
    selection = copy.deepcopy(sample[2])
    selection["rows"] = [{"table": "msg_archive", "key": {"id": 2}}]
    selection["window"] = {"since": NOW - 100, "until": NOW}
    selection["history_retention_seconds"] = 100
    manifest = migration.preview(*sample[:2], selection, **YES)
    assert migration.import_manifest(*sample[:2], manifest, now=NOW + 50, **YES)["inserted"] == 1
    value = fixtures.archive_values(sample[1])[0]
    assert value["history_expires_at"] == NOW + 50
    assert value["history_redacted"] and "text" not in value["original"]
    selection["source_id"] = "second-import-of-same-old-body"
    import_selection(sample, selection, now=NOW + 51)
    assert all("text" not in v["original"] for v in fixtures.archive_values(sample[1]))


def test_cleanup_retains_constraints_receipts_and_refs_without_rehydrating(sample):
    selection = behavior_selection(sample, binding=False)
    diary = next(row for row in sample[2]["rows"] if row["table"] == "mem_diary")
    selection["rows"].append(diary)
    manifest = import_selection(sample, selection)
    before = asyncio.run(rows_from_store(sample[1]))

    async def cleanup():
        store = SQLiteStore(sample[1], clock=lambda: NOW + 8 * 86400)
        await store.open()
        try:
            await store.cleanup()
            return await store.legacy_baselines()
        finally:
            await store.close()

    after = asyncio.run(cleanup())
    assert evaluate(after, sample[3], now=NOW + 8 * 86400)["reason_codes"] == evaluate(
        before, sample[3], now=NOW + 8 * 86400,
    )["reason_codes"]
    assert not evaluate(after, sample[3], purpose="export")["allowed"]
    values = fixtures.archive_values(sample[1])
    assert "SYNTHETIC PRIVATE DIARY" not in canonical_json(values)
    assert next(v for v in values if v["table"] == "mem_diary")["source_refs"] == ["9", "10"]
    assert migration.verify(*sample[:2], manifest, now=NOW + 8 * 86400, **YES)[
        "status"] == "verified"
    assert migration.import_manifest(*sample[:2], manifest, now=NOW + 8 * 86400, **YES)[
        "inserted"] == 0
    assert "SYNTHETIC PRIVATE DIARY" not in canonical_json(fixtures.archive_values(sample[1]))
    assert len(execute(sample[1], "SELECT * FROM runtime_meta WHERE key LIKE 'legacy_import:%'")) == 3


def test_retained_native_copy_expires_even_if_pinned_later(sample):
    source, target, selection, _ = sample
    selection = copy.deepcopy(selection)
    selection["rows"] = [row for row in selection["rows"] if row["table"] == "mem_diary"]
    execute(source, "UPDATE mem_diary SET pinned=1")
    import_selection(sample, selection)
    record = execute(target, "SELECT experience_id,expires_at,pinned FROM experiences")[0]
    assert record[1:] == (NOW - 200 + 7 * 86400, 0)
    # Synthetic legacy/old-version pinned row: privacy expiry must still win.
    execute(target, "UPDATE experiences SET pinned=1,"
                    "value_json=json_set(value_json,'$.pinned',json('true'))")

    async def expired_read():
        store = SQLiteStore(target, clock=lambda: NOW + 7 * 86400)
        await store.open()
        try:
            assert await store.load_experience(record[0]) is None
            await store.cleanup()
        finally:
            await store.close()

    asyncio.run(expired_read())
    assert not execute(target, "SELECT * FROM experiences")


@pytest.mark.parametrize("patch", [
    {"history_retention_seconds": 604801},
    {"history_retention_seconds": True},
    {"history_retention_seconds": 0},
])
def test_retention_can_only_shorten_seven_day_bound(sample, patch):
    with pytest.raises(migration.MigrationError, match="invalid_history_retention"):
        migration.preview(*sample[:2], {**sample[2], **patch}, **YES)


def test_read_port_does_not_return_original_or_pending_bodies(sample):
    import_selection(sample, sample[2])
    rows = asyncio.run(rows_from_store(sample[1]))
    encoded = canonical_json(rows)
    assert "SYNTHETIC PRIVATE" not in encoded
    assert "original" not in encoded and "pending_crawl" not in encoded
    assert all("runtime_constraints" in row["value"] for row in rows)
