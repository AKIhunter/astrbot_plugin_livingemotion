"""Only synthetic databases in pytest tmp_path; never discover a legacy data path."""

import asyncio
import copy
import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from astrbot_plugin_livingemotion.api import LivingEmotionAPI
from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import (
    ActorRole,
    Context,
    Event,
    SceneKind,
    canonical_json,
    stable_key,
    to_dict,
)
from astrbot_plugin_livingemotion.storage import SQLiteStore
from astrbot_plugin_livingemotion.storage import legacy_import as migration

NOW = 1_800_000_000
CLI = Path(__file__).resolve().parents[2] / "tools" / "migrate_legacy.py"
YES = {"snapshot_confirmed": True, "target_stopped": True}


def execute(path, sql, values=()):
    with sqlite3.connect(path) as db:
        result = db.execute(sql, values).fetchall()
    db.close()
    return result


def dumps(value):
    return canonical_json(value)


@pytest.fixture
def sample(tmp_path):
    source = tmp_path / "synthetic-old-snapshot.sqlite3"
    target = tmp_path / "synthetic-new.sqlite3"
    with sqlite3.connect(source) as db:
        db.executescript("""
            PRAGMA user_version=7;
            CREATE TABLE persona_state(
                persona_id TEXT, scope TEXT, subject_id TEXT, intimacy REAL, mood TEXT,
                energy REAL, busy INTEGER, agenda_json TEXT, last_active INTEGER,
                emotion_intensity REAL, emotion_reason TEXT, source_event_id INTEGER,
                emotion_updated_at INTEGER, emotion_expires_at INTEGER, emotion_confidence REAL,
                PRIMARY KEY(persona_id,scope,subject_id));
            CREATE TABLE emotion_event(
                id INTEGER PRIMARY KEY, persona_id TEXT, person_id TEXT, source_account TEXT,
                scene TEXT, label TEXT, intensity REAL, summary TEXT, source_msg_id TEXT,
                audience TEXT, shareable INTEGER, occurred_at INTEGER, created_at INTEGER);
            CREATE TABLE affinity(
                persona_id TEXT, subject_key TEXT, score REAL, stage INTEGER, delta_today REAL,
                floor REAL, evidence_atom_ids TEXT, manual INTEGER, updated_at INTEGER,
                PRIMARY KEY(persona_id,subject_key));
            CREATE TABLE mem_diary(
                id INTEGER PRIMARY KEY, persona_id TEXT, day_key TEXT, created_at INTEGER,
                title TEXT, text TEXT, refs TEXT, pinned INTEGER, hidden INTEGER);
            CREATE TABLE kv(k TEXT PRIMARY KEY,v TEXT,updated_at INTEGER);
            CREATE TABLE proactive_log(
                id INTEGER PRIMARY KEY, persona_id TEXT, session_id TEXT, at INTEGER,
                text TEXT, status TEXT);
            CREATE TABLE night_dream_plan(
                id INTEGER PRIMARY KEY, persona_id TEXT, night_key TEXT,
                status TEXT, scheduled_at INTEGER);
            CREATE TABLE msg_archive(
                id INTEGER PRIMARY KEY,msg_id TEXT,session_id TEXT,session_kind TEXT,
                sender_id TEXT,ts INTEGER,text TEXT);
            CREATE TABLE mem_atom(id INTEGER PRIMARY KEY,content TEXT,vector BLOB);
        """)
        db.execute("INSERT INTO persona_state VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            "old-persona", "user", "human", .8, "sadness", .7, 1, "[]", NOW - 200,
            .9, "synthetic reason", 1, NOW - 100, NOW - 1, .9,
        ))
        db.execute("INSERT INTO emotion_event VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            1, "old-persona", "human", "human", "old-session", "sadness", .9,
            "synthetic observation", "message-1", "self_private", 0, NOW - 100, NOW - 100,
        ))
        db.execute("INSERT INTO emotion_event VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            2, "old-persona", "human", "", "ambiguous", "happy", .7,
            "unknown-role synthetic", "unproved", "unknown", 0, NOW - 90, NOW - 90,
        ))
        db.execute("INSERT INTO affinity VALUES(?,?,?,?,?,?,?,?,?)", (
            "old-persona", "123", 750, 4, 12, 50, "[9,10]", 1, NOW - 10,
        ))
        db.execute("INSERT INTO mem_diary VALUES(?,?,?,?,?,?,?,?,?)", (
            1, "old-persona", "2026-11-04", NOW - 200,
            "synthetic title", "SYNTHETIC PRIVATE DIARY", '[9,{"scene":"other","id":10}]', 0, 1,
        ))
        db.execute("INSERT INTO msg_archive VALUES(?,?,?,?,?,?,?)", (
            1, "message-1", "old-session", "private", "human", NOW - 100,
            "SYNTHETIC PRIVATE MESSAGE",
        ))
        db.execute("INSERT INTO msg_archive VALUES(?,?,?,?,?,?,?)", (
            2, "message-2", "old-session", "private", "human", NOW - 50, "SYNTHETIC WINDOW",
        ))
        values = {
            "night.state": {
                "mode": "asleep", "energy": 42, "sleep_at": NOW - 3600,
                "wake_at": NOW + 3600, "last_tick": NOW - 10,
                "dream_count_today": 2, "pending_crawl": ["old-session"],
            },
            "night.dreams": [
                {"dream_id": "dream-1", "created_at": NOW - 500, "night_key": "old-night",
                 "text": "SYNTHETIC PRIVATE DREAM", "strength": .8, "expired": False,
                 "expires_at": NOW + 500, "refs": [9], "classification": "imagined"},
                {"dream_id": "dream-2", "created_at": NOW - 500, "night_key": "old-night",
                 "text": "SYNTHETIC EXPIRED DREAM", "strength": .1, "expired": True,
                 "pinned": True},
            ],
            "proactive.sessions": {
                "old-session": {"last_at": NOW - 200, "next_ok_at": NOW + 800,
                                "unanswered": 2, "sent_today": 2, "day": "2026-11-05"},
            },
            "proactive.global": {"sent_today": 3, "day": "2026-11-05"},
            "proactive.state": {"status": "pending", "pending": ["old-task"]},
        }
        for key, value in values.items():
            db.execute("INSERT INTO kv VALUES(?,?,?)", (key, dumps(value), NOW - 10))
        db.execute("INSERT INTO proactive_log VALUES(?,?,?,?,?,?)", (
            1, "old-persona", "old-session", NOW - 10, "OLD PENDING TEXT", "pending",
        ))
        db.execute("INSERT INTO night_dream_plan VALUES(?,?,?,?,?)", (
            1, "old-persona", "old-night", "pending", NOW + 100,
        ))
        db.execute("INSERT INTO mem_atom VALUES(?,?,?)", (9, "DO NOT COPY FACT", b"vector"))
    db.close()

    async def create_target():
        store = SQLiteStore(target, clock=lambda: NOW)
        await store.open()
        instance = await store.get_instance_id()
        context = Context(
            "bot", "native-persona", "adapter", "qq", SceneKind.PRIVATE, "human", "human",
            instance_id=instance, audience=("human",), route="synthetic:verified",
        )
        await store.get_generation(context)
        identifier = await store.register_context(context)
        await store.close()
        return context, identifier

    context, identifier = asyncio.run(create_target())
    rows = [
        {"table": "persona_state",
         "key": {"persona_id": "old-persona", "scope": "user", "subject_id": "human"},
         "context_id": identifier, "source_session_id": "old-session"},
        {"table": "emotion_event", "key": {"id": 2}},
        {"table": "affinity", "key": {"persona_id": "old-persona", "subject_key": "123"}},
        {"table": "mem_diary", "key": {"id": 1}, "context_id": identifier},
        {"table": "kv", "key": {"k": "night.state"}, "context_id": identifier},
        {"table": "kv", "key": {"k": "night.dreams"}, "member": "dream-1",
         "context_id": identifier},
        {"table": "kv", "key": {"k": "night.dreams"}, "member": "dream-2"},
        {"table": "kv", "key": {"k": "proactive.sessions"}, "member": "old-session",
         "context_id": identifier},
        {"table": "kv", "key": {"k": "proactive.global"}},
        {"table": "kv", "key": {"k": "proactive.state"}},
        {"table": "proactive_log", "key": {"id": 1}, "context_id": identifier},
        {"table": "night_dream_plan", "key": {"id": 1}},
    ]
    selection = {"format": 1, "source_id": "synthetic-installation", "rows": rows}
    return source, target, selection, context


def plan(sample):
    return migration.preview(*sample[:3], **YES)


def archive_values(target):
    return [json.loads(row[0]) for row in execute(
        target, "SELECT value_json FROM states WHERE kind='legacy_import'",
    )]


def test_preview_readonly_hash_privacy_and_actual_instance(sample):
    source, target, _, context = sample
    before = [migration.file_hash(p) for p in (source, target)]
    manifest = plan(sample)
    assert [migration.file_hash(p) for p in (source, target)] == before
    assert manifest["target"]["instance_id"] == context.instance_id != "local"
    assert manifest["target"]["schema_version"] == migration.SCHEMA_VERSION
    assert manifest["source"]["user_version"] == 7
    assert manifest["source"]["tables"]["persona_state"]["count"] == 1
    assert manifest["manifest_hash"] == stable_key({
        k: v for k, v in manifest.items() if k != "manifest_hash"
    })
    assert "SYNTHETIC PRIVATE" not in dumps(manifest)
    assert "synthetic reason" not in dumps(manifest)
    assert not execute(target, "SELECT * FROM states")


@pytest.mark.parametrize("version", [2, 3, 4, 5, 6])
def test_retained_v2_profile_import_verify_and_runtime_upgrade(sample, tmp_path, version):
    from astrbot_plugin_livingemotion.storage.schema import MIGRATIONS, migrate

    source, _, selection, context = sample
    target = tmp_path / f"retained-v{version}.sqlite"
    db = sqlite3.connect(target)
    try:
        migrate(db, MIGRATIONS[:version])
        db.execute("INSERT INTO runtime_meta VALUES('instance_id',?)", (context.instance_id,))
        db.execute("INSERT INTO source_contexts VALUES(?,?,?,?)",
                   (context.account_key, context.scope_key,
                    dumps(to_dict(replace(context, route=None))), NOW))
        db.commit()
    finally:
        db.close()
    manifest = migration.preview(source, target, selection, **YES)
    assert manifest["target"]["schema_version"] == version
    assert migration.import_manifest(source, target, manifest, **YES)["inserted"] == len(
        selection["rows"]
    )
    assert migration.verify(source, target, manifest, **YES)["status"] == "verified"

    async def upgrade():
        store = SQLiteStore(target, clock=lambda: NOW)
        await store.open()
        try:
            assert (await store.health())["schema_version"] == len(MIGRATIONS)
            assert await store.legacy_baselines()
        finally:
            await store.close()
    asyncio.run(upgrade())


def test_import_repeat_zero_and_full_reconciliation(sample):
    source, target, _, _ = sample
    manifest = plan(sample)
    result = migration.import_manifest(source, target, manifest, **YES)
    assert result["inserted"] == 12 and result["duplicates"] == 0
    first_hash = migration.file_hash(target)
    repeat = migration.import_manifest(source, target, manifest, **YES)
    assert repeat["inserted"] == 0 and repeat["duplicates"] == 12
    assert migration.file_hash(target) == first_hash
    assert migration.file_hash(source) == manifest["source"]["sha256"]
    assert migration.verify(source, target, manifest, **YES)["status"] == "verified"
    assert not execute(target, "SELECT * FROM intents")
    assert not execute(target, "SELECT * FROM events")
    assert not execute(target, "SELECT * FROM body_window")
    assert not execute(target, "SELECT * FROM states WHERE kind='bot'")


def test_field_semantics_original_ttl_and_api_instance(sample):
    source, target, _, context = sample
    migration.import_manifest(source, target, plan(sample), **YES)
    archives = archive_values(target)
    persona = next(v for v in archives if v["table"] == "persona_state")
    assert persona["classification"] == "human_observation"
    assert persona["original"]["energy"] == .7
    assert persona["field_map"]["energy"] == "human_or_unknown_energy_not_bot"
    assert persona["original_persona_reference"] == "old-persona"
    observation = json.loads(execute(target, "SELECT value_json FROM states "
                                           "WHERE kind='observation'")[0][0])
    assert observation["expires_at"] == NOW - 1
    assert observation["occurred_at"] == NOW - 100
    assert observation["evidence"][0]["source_ids"] == ["message-1"]
    unknown = next(v for v in archives if v["table"] == "emotion_event")
    assert unknown["classification"] == "legacy_unknown"
    assert not unknown["identity_resolved"]

    async def check():
        store = SQLiteStore(target, clock=lambda: NOW)
        await store.open()
        api = LivingEmotionAPI(store, Config(), None, instance_id=context.instance_id)
        response = await api.get_observation(context)
        assert response["status"] == "ok" and response["data"] is None
        assert (await api.get_bot_state(context))["data"]["pleasure"] == 0
        await store.close()

    asyncio.run(check())


def test_relationship_not_aggregate_or_invent_trust(sample):
    source, target, selection, _ = sample
    migration.import_manifest(source, target, plan(sample), **YES)
    relation = next(v for v in archive_values(target) if v["table"] == "affinity")
    assert relation["original"]["score"] == 750
    assert relation["original"]["stage"] == 4
    assert relation["original"]["manual"] == 1
    assert relation["original"]["trust"] is None
    assert relation["original"]["auto_aggregate"] is False
    assert relation["target_context"]["platform"] == "legacy_unknown"
    assert execute(target, "SELECT source_id,dimension,delta FROM relationship_ledger") == [
        ("123", "legacy_score", 750),
    ]
    assert not execute(target, "SELECT * FROM states WHERE kind='relationship'")
    other = copy.deepcopy(selection)
    other["source_id"] = "different-synthetic-installation"
    other["rows"] = [other["rows"][2]]
    second = migration.preview(source, target, other, **YES)
    migration.import_manifest(source, target, second, **YES)
    assert len(execute(target, "SELECT DISTINCT scope_key FROM relationship_ledger")) == 2


def test_private_experience_references_night_and_history(sample):
    source, target, _, _ = sample
    manifest = plan(sample)
    migration.import_manifest(source, target, manifest, **YES)
    experiences = execute(target, "SELECT kind,value_json FROM experiences")
    assert {v[0] for v in experiences} == {"diary", "dream"}
    for _, payload in experiences:
        value = json.loads(payload)
        ref = value["evidence"][0]
        assert ref["kind"] == "legacy_unknown"
        assert ref["sensitive"] and not ref["exportable"] and ref["authorization"] is None
        assert value["context"]["route"] is None
    archives = archive_values(target)
    diary = next(v for v in archives if v["table"] == "mem_diary")
    assert diary["private"] and diary["original"]["hidden"] == 1
    assert json.loads(diary["original"]["refs"]) == [9, {"scene": "other", "id": 10}]
    expired = next(v for v in archives if v["member"] == "dream-2")
    assert expired["original"]["v"]["expired"]
    night = json.loads(execute(target, "SELECT value_json FROM states WHERE kind='night'")[0][0])
    assert night["energy"] == 42 and night["sleep_started_at"] == NOW - 3600
    assert night["wake_at"] == NOW + 3600 and night["unread_watermark"] == 0
    cooldown = next(v for v in archives if v["member"] == "old-session")
    assert cooldown["original"]["v"]["next_ok_at"] == NOW + 800
    assert cooldown["original"]["v"]["unanswered"] == 2
    assert cooldown["original"]["v"]["sent_today"] == 2
    assert cooldown["baseline"]["cooldown_until"] == NOW + 800
    assert cooldown["baseline"]["quota_used"] == 2
    assert cooldown["baseline"]["quota_period"] == "2026-11-05"
    assert not cooldown["baseline"]["runtime_adopted"]
    assert "legacy_behavior_counters_not_consumed_by_runtime" in manifest["activation_blockers"]
    assert not execute(target, "SELECT * FROM intents")


@pytest.mark.parametrize("operation", ["preview", "import", "verify"])
@pytest.mark.parametrize("flag,code", [
    ("snapshot_confirmed", "snapshot_confirmation_required"),
    ("target_stopped", "target_must_be_stopped"),
])
def test_requires_explicit_snapshot_and_stop(sample, operation, flag, code):
    source, target, selection, _ = sample
    data = selection if operation == "preview" else plan(sample)
    options = {**YES, flag: False}
    function = {"preview": migration.preview, "import": migration.import_manifest,
                "verify": migration.verify}[operation]
    with pytest.raises(migration.MigrationError, match=code):
        function(source, target, data, **options)


@pytest.mark.parametrize("sidecar", ["-wal", "-shm", "-journal"])
@pytest.mark.parametrize("which", [0, 1])
def test_rejects_even_empty_sidecars(sample, sidecar, which):
    Path(str(sample[which]) + sidecar).touch()
    with pytest.raises(migration.MigrationError, match="sqlite_sidecar_present"):
        plan(sample)


def test_live_wal_refused_backup_snapshot_accepted(sample, tmp_path):
    source, target, selection, _ = sample
    writer = sqlite3.connect(source)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("UPDATE affinity SET score=751")
    writer.commit()
    before = migration.file_hash(source)
    with pytest.raises(migration.MigrationError, match="sqlite_sidecar_present"):
        plan(sample)
    assert migration.file_hash(source) == before
    snapshot = tmp_path / "synthetic-consistent-backup.sqlite3"
    backup = sqlite3.connect(snapshot)
    writer.backup(backup)
    backup.close()
    writer.close()
    manifest = migration.preview(snapshot, target, selection, **YES)
    migration.import_manifest(snapshot, target, manifest, **YES)
    assert next(v for v in archive_values(target) if v["table"] == "affinity")[
        "original"]["score"] == 751


@pytest.mark.parametrize("sql", [
    "PRAGMA user_version=999",
    "PRAGMA user_version=2",
    "ALTER TABLE states ADD COLUMN unexpected TEXT",
    "CREATE TRIGGER surprise AFTER INSERT ON states BEGIN DELETE FROM states; END",
    "DROP INDEX ledger_source",
    "CREATE TABLE unexpected(id INTEGER)",
])
def test_unknown_target_schema_refused_before_data_write(sample, sql):
    source, target, _, _ = sample
    manifest = plan(sample)
    execute(target, sql)
    before = migration.file_hash(target)
    with pytest.raises(migration.MigrationError, match="target_schema_incompatible"):
        migration.import_manifest(source, target, manifest, **YES)
    assert migration.file_hash(target) == before
    assert not execute(target, "SELECT * FROM states")


@pytest.mark.parametrize("value", ["local", ""])
def test_missing_real_persistent_instance_rejected(sample, value):
    execute(sample[1], "UPDATE runtime_meta SET value=? WHERE key='instance_id'", (value,))
    with pytest.raises(migration.MigrationError, match="target_instance_missing"):
        plan(sample)


def test_same_file_and_hardlink_refused(sample, tmp_path):
    source, _, selection, _ = sample
    for path in (source, tmp_path / "hardlink.sqlite3"):
        if path != source:
            os.link(source, path)
        with pytest.raises(migration.MigrationError, match="source_target_same_file"):
            migration.preview(source, path, selection, **YES)


def test_tampered_manifest_and_source_refused(sample):
    source, target, _, _ = sample
    manifest = plan(sample)
    changed = copy.deepcopy(manifest)
    changed["selection"]["source_id"] = "tampered"
    with pytest.raises(migration.MigrationError, match="manifest_hash_mismatch"):
        migration.import_manifest(source, target, changed, **YES)
    execute(source, "UPDATE affinity SET score=749")
    with pytest.raises(migration.MigrationError, match="source_hash_mismatch"):
        migration.import_manifest(source, target, manifest, **YES)
    assert not execute(target, "SELECT * FROM states")


def test_whole_transaction_rollback_after_partial_writes(sample, monkeypatch):
    source, target, _, _ = sample
    manifest = plan(sample)
    original = migration._insert
    calls = []

    def fail(db, write):
        original(db, write)
        calls.append(write)
        if len(calls) == 4:
            raise RuntimeError("synthetic-interruption")

    monkeypatch.setattr(migration, "_insert", fail)
    with pytest.raises(RuntimeError, match="synthetic-interruption"):
        migration.import_manifest(source, target, manifest, **YES)
    assert len(calls) == 4
    for table in ("states", "relationship_ledger", "experiences", "intents"):
        assert not execute(target, f"SELECT * FROM {table}")
    assert not execute(target, "SELECT * FROM runtime_meta WHERE key LIKE 'legacy_import:%'")
    assert migration.file_hash(source) == manifest["source"]["sha256"]
    monkeypatch.setattr(migration, "_insert", original)
    assert migration.import_manifest(source, target, manifest, **YES)["inserted"] == 12


def test_target_lock_refused_without_partial_write(sample):
    source, target, _, _ = sample
    manifest = plan(sample)
    writer = sqlite3.connect(target)
    writer.execute("PRAGMA journal_mode=DELETE")
    writer.execute("BEGIN EXCLUSIVE")
    try:
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            migration.import_manifest(source, target, manifest, **YES)
    finally:
        writer.rollback()
        writer.close()
    assert not execute(target, "SELECT * FROM states")


def test_new_runtime_state_not_overwritten_and_verify_reports_drift(sample):
    source, target, _, _ = sample
    manifest = plan(sample)
    migration.import_manifest(source, target, manifest, **YES)
    execute(target, "UPDATE states SET version=2 WHERE kind='night'")
    assert migration.import_manifest(source, target, manifest, **YES)["inserted"] == 0
    result = migration.verify(source, target, manifest, **YES)
    assert result["status"] == "mismatch"
    assert any(v["reason"] == "target_missing_or_changed" for v in result["mismatches"])
    assert execute(target, "SELECT version FROM states WHERE kind='night'") == [(2,)]


def test_conflict_rolls_back_entire_new_batch(sample):
    source, target, selection, _ = sample
    partial = {**selection, "rows": [selection["rows"][0]]}
    first = migration.preview(source, target, partial, **YES)
    migration.import_manifest(source, target, first, **YES)
    changed = copy.deepcopy(selection)
    changed["source_id"] = "other-original-source"
    manifest = migration.preview(source, target, changed, **YES)
    assert manifest["conflicts"]
    before = migration.file_hash(target)
    with pytest.raises(migration.MigrationError, match="target_conflict"):
        migration.import_manifest(source, target, manifest, **YES)
    assert migration.file_hash(target) == before
    assert len(archive_values(target)) == 1


@pytest.mark.parametrize("table", ["mem_atom", "vector", "mem_subject", "sqlite_master"])
def test_no_facts_vectors_or_arbitrary_tables(sample, table):
    source, target, selection, _ = sample
    selection["rows"] = [{"table": table, "key": {"id": 9}}]
    with pytest.raises(migration.MigrationError, match="invalid_source_key"):
        migration.preview(source, target, selection, **YES)


def test_window_explicit_bounded_and_not_live_events(sample):
    source, target, selection, _ = sample
    selection["rows"] = [{"table": "msg_archive", "key": {"id": 2}}]
    with pytest.raises(migration.MigrationError, match="explicit_bounded_window_required"):
        plan(sample)
    selection["window"] = {"since": NOW - 60, "until": NOW}
    manifest = plan(sample)
    migration.import_manifest(source, target, manifest, **YES)
    archive = archive_values(target)[0]
    assert archive["classification"] == "legacy_window_reference_only"
    assert archive["original"]["text"] == "SYNTHETIC WINDOW"
    assert not execute(target, "SELECT * FROM events")
    assert not execute(target, "SELECT * FROM body_window")
    selection["window"]["since"] = NOW - 10
    with pytest.raises(migration.MigrationError, match="message_outside_selected_window"):
        plan(sample)


@pytest.mark.parametrize("bad", [
    '{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{"a":', "null",
])
def test_strict_json_manifest_input(tmp_path, bad):
    path = tmp_path / "synthetic.json"
    path.write_text(bad)
    with pytest.raises(migration.MigrationError):
        migration.read_json(path)


def test_bare_account_or_broken_source_never_human(sample):
    source, target, _, _ = sample
    execute(source, "UPDATE emotion_event SET source_account='' WHERE id=1")
    manifest = plan(sample)
    assert manifest["entries"][0]["classification"] == "legacy_unknown"
    migration.import_manifest(source, target, manifest, **YES)
    assert not execute(target, "SELECT * FROM states WHERE kind='observation'")


def test_deleted_scope_does_not_resurrect(sample):
    source, target, _, context = sample
    manifest = plan(sample)
    migration.import_manifest(source, target, manifest, **YES)

    async def clear():
        store = SQLiteStore(target)
        await store.open()
        await store.clear_scope(context, 0)
        await store.close()

    asyncio.run(clear())
    with pytest.raises(migration.MigrationError, match="mapping_changed"):
        migration.import_manifest(source, target, manifest, **YES)
    assert not execute(target, "SELECT * FROM states WHERE scope_key=?", (context.scope_key,))


def test_rollback_dry_run_preserves_new_records_and_consumer_choices(sample):
    source, target, _, context = sample
    migration.import_manifest(source, target, plan(sample), **YES)

    async def new_record():
        store = SQLiteStore(target, clock=lambda: NOW)
        await store.open()
        event = Event("new", "synthetic", "message", context, ActorRole.HUMAN, NOW,
                      "new-source", actor_id="human", body="NEW SYNTHETIC RECORD")
        assert (await store.commit_event(event, 0)).accepted
        await store.close()

    asyncio.run(new_record())
    before = migration.file_hash(target)
    consumers = {"format": 1, "consumers": {
        "BiliBot": {"current": "livingemotion", "restore": "congling"},
        "LivingHello": {"current": "livingemotion", "restore": "none"},
    }}
    plan_result = migration.rollback_plan(target, consumers, target_stopped=True)
    assert plan_result["destructive_operations"] == []
    assert [s["action"] for s in plan_result["steps"]][:3] == [
        "stop_new_executor_and_consumers", "preserve_new_database",
        "restore_explicit_consumer_selection",
    ]
    # Synthetic consumer simulator only; no runtime, plugin or production config.
    executor_running = False
    restored = {}
    for name, choice in plan_result["consumer_selection"]["consumers"].items():
        assert not executor_running
        restored[name] = choice["restore"]
    assert restored == {"BiliBot": "congling", "LivingHello": "none"}
    assert migration.file_hash(target) == before
    assert execute(target, "SELECT body FROM body_window") == [("NEW SYNTHETIC RECORD",)]


def test_cli_all_four_commands_and_exclusive_report(sample, tmp_path):
    source, target, selection, _ = sample
    selection_path = tmp_path / "selection.json"
    manifest_path = tmp_path / "manifest.json"
    consumers_path = tmp_path / "consumers.json"
    migration.write_json(selection_path, selection)
    migration.write_json(consumers_path, {"format": 1, "consumers": {
        "synthetic": {"current": "livingemotion", "restore": "congling"},
    }})
    common = ["--snapshot", str(source), "--target", str(target),
              "--snapshot-confirmed", "--target-stopped"]

    def run(args, code=0):
        result = subprocess.run([sys.executable, str(CLI), *args], cwd=tmp_path, check=False,
                                capture_output=True, text=True, timeout=20)
        assert result.returncode == code, result.stderr
        return json.loads(result.stdout if code == 0 else result.stderr)

    preview_result = run(["preview", *common, "--selection", str(selection_path),
                          "--output", str(manifest_path)])
    assert preview_result["manifest_hash"]
    assert manifest_path.stat().st_mode & 0o777 == 0o600
    result = run(["import", *common, "--manifest", str(manifest_path)])
    assert result["inserted"] == 12
    assert run(["import", *common, "--manifest", str(manifest_path)])["inserted"] == 0
    assert run(["verify", *common, "--manifest", str(manifest_path)])["status"] == "verified"
    rollback = run(["rollback-plan", "--target", str(target), "--target-stopped",
                    "--consumers", str(consumers_path)])
    assert rollback["status"] == "plan_only_no_changes"
    rejected = run(["preview", *common, "--selection", str(selection_path),
                    "--output", str(source)], code=2)
    assert rejected["reason_code"] == "output_must_be_new_file"


def test_hard_process_exit_recovers_without_partial_rows(sample, tmp_path):
    source, target, _, _ = sample
    manifest_path = tmp_path / "crash-manifest.json"
    manifest = plan(sample)
    migration.write_json(manifest_path, manifest)
    script = """
import os, sys
sys.path.insert(0, sys.argv[1])
from astrbot_plugin_livingemotion.storage import legacy_import as m
original = m._insert
def crash(db, write):
    original(db, write)
    os._exit(73)
m._insert = crash
m.import_manifest(sys.argv[2], sys.argv[3], m.read_json(sys.argv[4]),
                  snapshot_confirmed=True, target_stopped=True)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(CLI.parents[2]), str(source),
         str(target), str(manifest_path)], timeout=20, capture_output=True, check=False,
    )
    assert result.returncode == 73, result.stderr
    # SQLite recovery is performed only on this disposable synthetic target.
    assert not execute(target, "SELECT * FROM states")
    assert not execute(target, "SELECT * FROM runtime_meta WHERE key LIKE 'legacy_import:%'")
    assert migration.file_hash(source) == manifest["source"]["sha256"]
