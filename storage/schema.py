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
