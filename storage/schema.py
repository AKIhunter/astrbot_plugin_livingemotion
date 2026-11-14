"""Transactional schema migrations. Do not use executescript (implicit COMMIT)."""

import sqlite3
from collections.abc import Sequence

MIGRATIONS: tuple[tuple[str, ...], ...] = ((
    "CREATE TABLE runtime_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    """CREATE TABLE scopes (
        scope_key TEXT PRIMARY KEY, context_json TEXT NOT NULL,
        generation INTEGER NOT NULL DEFAULT 0)""",
    """CREATE TABLE event_keys (
        event_key TEXT PRIMARY KEY, scope_key TEXT NOT NULL,
        generation INTEGER NOT NULL, received_at REAL NOT NULL)""",
    """CREATE TABLE events (
        seq INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT NOT NULL UNIQUE,
        scope_key TEXT NOT NULL, generation INTEGER NOT NULL,
        event_id TEXT NOT NULL, producer TEXT NOT NULL, event_type TEXT NOT NULL,
        actor_role TEXT NOT NULL, account_id TEXT NOT NULL,
        occurred_at REAL NOT NULL, received_at REAL NOT NULL,
        metadata_json TEXT NOT NULL)""",
    "CREATE INDEX events_scope_seq ON events(scope_key, seq)",
    "CREATE INDEX events_retention ON events(received_at)",
    """CREATE TABLE body_window (
        seq INTEGER PRIMARY KEY, scope_key TEXT NOT NULL,
        occurred_at REAL NOT NULL, body TEXT NOT NULL)""",
    "CREATE INDEX body_scope_seq ON body_window(scope_key, seq)",
    "CREATE INDEX body_retention ON body_window(occurred_at)",
    """CREATE TABLE states (
        scope_key TEXT NOT NULL, kind TEXT NOT NULL, record_key TEXT NOT NULL,
        generation INTEGER NOT NULL, version INTEGER NOT NULL,
        updated_at REAL NOT NULL, value_json TEXT NOT NULL,
        PRIMARY KEY (scope_key, kind, record_key))""",
    """CREATE TABLE relationship_ledger (
        id INTEGER PRIMARY KEY, scope_key TEXT NOT NULL, generation INTEGER NOT NULL,
        event_key TEXT NOT NULL, source_id TEXT NOT NULL, account_id TEXT NOT NULL,
        occurred_at REAL NOT NULL, day TEXT NOT NULL, dimension TEXT NOT NULL,
        delta REAL NOT NULL, reason_code TEXT NOT NULL,
        UNIQUE (event_key, source_id, account_id, dimension))""",
    "CREATE INDEX ledger_source ON relationship_ledger(scope_key, account_id, day)",
    """CREATE TABLE intents (
        intent_id TEXT PRIMARY KEY, scope_key TEXT NOT NULL, generation INTEGER NOT NULL,
        status TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL,
        updated_at REAL NOT NULL, reason_code TEXT NOT NULL,
        value_json TEXT NOT NULL, reservation_id TEXT)""",
    "CREATE INDEX intents_scope ON intents(scope_key, status)",
    """CREATE TABLE quota_reservations (
        reservation_id TEXT PRIMARY KEY, scope_key TEXT NOT NULL, generation INTEGER NOT NULL,
        period TEXT NOT NULL, purpose TEXT NOT NULL, pool TEXT NOT NULL, units INTEGER NOT NULL,
        status TEXT NOT NULL, created_at REAL NOT NULL,
        finished_at REAL, reason_code TEXT NOT NULL)""",
    """CREATE INDEX quota_usage
       ON quota_reservations(period, pool, purpose, scope_key)""",
    """CREATE TABLE experiences (
        experience_id TEXT PRIMARY KEY, scope_key TEXT NOT NULL,
        owner_key TEXT NOT NULL, generation INTEGER NOT NULL,
        kind TEXT NOT NULL, period TEXT NOT NULL, created_at REAL NOT NULL,
        expires_at REAL, pinned INTEGER NOT NULL, value_json TEXT NOT NULL,
        UNIQUE (owner_key, kind, period))""",
    """CREATE TABLE audit (
        seq INTEGER PRIMARY KEY, scope_key TEXT NOT NULL, generation INTEGER NOT NULL,
        action TEXT NOT NULL, reason_code TEXT NOT NULL, occurred_at REAL NOT NULL)""",
), (
    "ALTER TABLE audit ADD COLUMN actor_id TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE audit ADD COLUMN value_json TEXT NOT NULL DEFAULT '{}'",
    "ALTER TABLE scopes ADD COLUMN human_watermark INTEGER NOT NULL DEFAULT 0",
    """UPDATE scopes SET human_watermark=COALESCE(
        (SELECT MAX(seq) FROM events WHERE events.scope_key=scopes.scope_key
         AND actor_role='human'),0)""",
    "ALTER TABLE intents ADD COLUMN attempted_at REAL",
    """UPDATE intents SET attempted_at=updated_at
        WHERE status IN ('sending','succeeded','unknown')""",
    """CREATE TABLE event_traces (
        event_key TEXT NOT NULL, scope_key TEXT NOT NULL, generation INTEGER NOT NULL,
        kind TEXT NOT NULL, occurred_at REAL NOT NULL, value_json TEXT NOT NULL,
        PRIMARY KEY(event_key,kind))""",
    "CREATE INDEX traces_scope ON event_traces(scope_key,occurred_at)",
    """CREATE TABLE source_contexts (
        context_id TEXT PRIMARY KEY, scope_key TEXT NOT NULL, context_json TEXT NOT NULL,
        updated_at REAL NOT NULL)""",
), (
    """CREATE TABLE state_modes (
        persona_key TEXT PRIMARY KEY, instance_id TEXT NOT NULL, persona_id TEXT NOT NULL,
        mode TEXT NOT NULL, revision INTEGER NOT NULL)""",
    """CREATE TABLE state_members (
        scope_key TEXT PRIMARY KEY, persona_key TEXT NOT NULL)""",
    "CREATE INDEX state_members_persona ON state_members(persona_key)",
    """CREATE TABLE state_owners (
        owner_key TEXT PRIMARY KEY, persona_key TEXT NOT NULL, mode TEXT NOT NULL,
        generation INTEGER NOT NULL DEFAULT 0)""",
    """CREATE TABLE owner_states (
        owner_key TEXT NOT NULL, kind TEXT NOT NULL, version INTEGER NOT NULL,
        updated_at REAL NOT NULL, value_json TEXT NOT NULL,
        PRIMARY KEY(owner_key,kind))""",
    """CREATE TABLE energy_events (
        seq INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE, occurred_at REAL NOT NULL,
        owner_key TEXT NOT NULL, source_scope_key TEXT NOT NULL, source_id TEXT NOT NULL,
        category TEXT NOT NULL, before_units INTEGER NOT NULL, after_units INTEGER NOT NULL,
        delta_units INTEGER NOT NULL, before_state TEXT NOT NULL, after_state TEXT NOT NULL,
        reason_code TEXT NOT NULL)""",
    "CREATE INDEX energy_owner_time ON energy_events(owner_key,occurred_at,seq)",
    "CREATE INDEX energy_retention ON energy_events(occurred_at)",
    """CREATE TABLE reply_attempts (
        reply_key TEXT PRIMARY KEY, source_scope_key TEXT NOT NULL, reply_id TEXT NOT NULL,
        source_generation INTEGER NOT NULL, owner_json TEXT, cycle_id TEXT,
        wake_session TEXT, started_at REAL NOT NULL, submitted_at REAL,
        status TEXT NOT NULL, context_json TEXT NOT NULL)""",
    """CREATE TABLE wake_attempts (
        event_key TEXT PRIMARY KEY, owner_key TEXT NOT NULL, cycle_id TEXT,
        occurred_at REAL NOT NULL, accepted INTEGER NOT NULL, reason_code TEXT NOT NULL)""",
    "ALTER TABLE intents ADD COLUMN state_persona_key TEXT",
    "ALTER TABLE intents ADD COLUMN state_revision INTEGER",
), (
    # External memory mirror: a read-only copy pulled from LivingMemory (or any
    # other provider wired in integrations/*). Never the source of truth.
    """CREATE TABLE external_memories (
        memory_id INTEGER NOT NULL, persona_id TEXT NOT NULL, body TEXT NOT NULL,
        created_at REAL, session_id TEXT NOT NULL DEFAULT '',
        metadata_json TEXT NOT NULL DEFAULT '{}', synced_at REAL NOT NULL,
        PRIMARY KEY(persona_id, memory_id))""",
    "CREATE INDEX external_memories_persona ON external_memories(persona_id, memory_id)",
    """CREATE TABLE external_memory_sync (
        persona_id TEXT PRIMARY KEY, provider TEXT NOT NULL,
        synced_at REAL NOT NULL, stored INTEGER NOT NULL,
        truncated INTEGER NOT NULL DEFAULT 0)""",
), (
    """CREATE TABLE experience_daily (
        owner_key TEXT NOT NULL, kind TEXT NOT NULL, day TEXT NOT NULL,
        timezone TEXT NOT NULL, experience_id TEXT, revision INTEGER NOT NULL,
        origin TEXT NOT NULL, updated_at REAL NOT NULL,
        PRIMARY KEY(owner_key,kind,day))""",
    """CREATE TABLE experience_jobs (
        request_id TEXT PRIMARY KEY, owner_key TEXT NOT NULL, persona_id TEXT NOT NULL,
        kind TEXT NOT NULL, day TEXT NOT NULL, timezone TEXT NOT NULL,
        status TEXT NOT NULL, reason_code TEXT NOT NULL, experience_id TEXT,
        expected_entry_revision INTEGER NOT NULL, attempted_at REAL NOT NULL,
        finished_at REAL, generation_snapshot_json TEXT NOT NULL)""",
    """CREATE UNIQUE INDEX experience_active_day ON experience_jobs(owner_key,kind,day)
        WHERE status IN ('queued','running')""",
    "CREATE INDEX experience_jobs_owner ON experience_jobs(owner_key,attempted_at)",
), (
    # Numeric history only; never retain message text, evidence or account labels.
    """CREATE TABLE emotion_samples (
        owner_key TEXT NOT NULL, generation INTEGER NOT NULL, at REAL NOT NULL,
        pleasure REAL NOT NULL, arousal REAL NOT NULL, stress REAL NOT NULL,
        social_need REAL NOT NULL, PRIMARY KEY(owner_key,generation,at))""",
    "CREATE INDEX emotion_retention ON emotion_samples(at)",
    """INSERT OR IGNORE INTO emotion_samples
        SELECT s.owner_key,COALESCE(o.generation,0),s.updated_at,
        json_extract(s.value_json,'$.pleasure'),COALESCE(json_extract(s.value_json,'$.arousal'),0.3),
        COALESCE(json_extract(s.value_json,'$.stress'),0),COALESCE(json_extract(s.value_json,'$.social_need'),0.3)
        FROM owner_states s LEFT JOIN state_owners o ON o.owner_key=s.owner_key
        WHERE s.kind='bot' AND json_type(s.value_json,'$.pleasure') IN ('integer','real')""",
    """INSERT OR IGNORE INTO emotion_samples
        SELECT scope_key,generation,updated_at,
        json_extract(value_json,'$.pleasure'),COALESCE(json_extract(value_json,'$.arousal'),0.3),
        COALESCE(json_extract(value_json,'$.stress'),0),COALESCE(json_extract(value_json,'$.social_need'),0.3)
        FROM states WHERE kind='bot' AND record_key=''
        AND json_type(value_json,'$.pleasure') IN ('integer','real')""",
), (
    # 每人格/类型仅保留最新自动结果，不保存正文；与手动任务表独立。
    """CREATE TABLE experience_auto_status (
        owner_key TEXT NOT NULL, kind TEXT NOT NULL,
        attempted_at REAL NOT NULL, value_json TEXT NOT NULL,
        PRIMARY KEY(owner_key,kind))""",
), (
    # Older samples never recorded their baseline; NULL explicitly preserves that gap.
    "ALTER TABLE emotion_samples ADD COLUMN baseline_pleasure REAL",
    "ALTER TABLE emotion_samples ADD COLUMN baseline_arousal REAL",
    "ALTER TABLE emotion_samples ADD COLUMN baseline_stress REAL",
    "ALTER TABLE emotion_samples ADD COLUMN baseline_social_need REAL",
    "ALTER TABLE emotion_samples ADD COLUMN baseline_refined INTEGER",
))


def migrate(connection: sqlite3.Connection,
            migrations: Sequence[Sequence[str]] = MIGRATIONS) -> None:
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version > len(migrations):
        raise RuntimeError("schema_newer_than_code")
    for index in range(version, len(migrations)):
        connection.execute("BEGIN IMMEDIATE")
        try:
            for statement in migrations[index]:
                connection.execute(statement)
            connection.execute(f"PRAGMA user_version={index + 1}")
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
