"""Bounded, offline legacy import. No runtime/store, network or model calls.

Only a reviewed, explicit snapshot is read. The target must be stopped. This
module deliberately pins the entire SQL schema, not just PRAGMA user_version.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..contracts import (
    ContentKind,
    Context,
    EvidenceRef,
    Experience,
    HumanObservation,
    NightState,
    canonical_json,
    stable_key,
    to_dict,
)

FORMAT = 1
SCHEMA_VERSION = 2
# Full sqlite_master (non-internal tables/indexes), inspected on 2026-11-05.
SCHEMA_HASH = "6a884b7faa9b138fce265e4dbcb18c109ded743e73a8bc97bb65003eb04b1ab6"
MAX_ROWS = 500
MAX_WINDOW = 200
MAX_PAYLOAD = 131072
MAX_FILE = 512 * 1024 * 1024
HISTORY_TTL = 7 * 86400
KEYS = {
    "persona_state": ("persona_id", "scope", "subject_id"),
    "emotion_event": ("id",),
    "affinity": ("persona_id", "subject_key"),
    "mem_diary": ("id",),
    "proactive_log": ("id",),
    "night_dream_plan": ("id",),
    "kv": ("k",),
    "msg_archive": ("id",),
}
FIELDS = {
    "persona_state": (
        "persona_id", "scope", "subject_id", "intimacy", "mood", "energy", "busy",
        "agenda_json", "last_active", "emotion_intensity", "emotion_reason",
        "source_event_id", "emotion_updated_at", "emotion_expires_at", "emotion_confidence",
    ),
    "emotion_event": (
        "id", "persona_id", "person_id", "source_account", "scene", "label", "intensity",
        "summary", "source_msg_id", "audience", "shareable", "occurred_at", "created_at",
        "expires_at", "confidence",
    ),
    "affinity": (
        "persona_id", "subject_key", "score", "stage", "delta_today", "floor", "last_talk_at",
        "talk_days_30", "evidence_atom_ids", "manual", "updated_at",
    ),
    "mem_diary": (
        "id", "persona_id", "day_key", "created_at", "title", "text", "mood", "tags", "refs",
        "affinity_subject", "affinity_score", "pinned", "hidden", "expires_at", "classification",
    ),
    "proactive_log": (
        "id", "persona_id", "session_id", "umo", "at", "reason", "text", "kind",
        "replied_at", "replied_delta", "status",
    ),
    "night_dream_plan": (
        "id", "persona_id", "night_key", "plan_key", "stage_index", "status", "scheduled_at",
        "dream_id", "generated_at",
    ),
    "msg_archive": ("id", "msg_id", "session_id", "session_kind", "sender_id", "ts", "text"),
    "kv": ("k", "v", "updated_at"),
}
KV_FIELDS = {
    "night.state": (
        "mode", "energy", "sleep_at", "wake_at", "reason", "last_tick", "dream_count_today",
        "dream_skip", "version", "sleep_kind", "enter_waking_at", "last_wake_at",
        "last_wake_reason", "pending_crawl", "transition_deadline",
    ),
    "night.dreams": (
        "dream_id", "session_id", "created_at", "level", "tags", "text", "importance",
        "decay_per_day", "strength", "expired", "night_key", "pinned", "planned_at",
        "stage_key", "cycle", "backfilled", "decay_at", "refs", "expires_at", "classification",
    ),
    "proactive.sessions": ("last_at", "unanswered", "next_ok_at", "day", "sent_today"),
    "proactive.global": ("day", "sent_today"),
    "proactive.state": ("status", "pending", "updated_at"),
}


class MigrationError(Exception):
    """Fixed public error code, never source text or a raw SQL exception."""


def _require(condition: Any, code: str) -> None:
    if not condition:
        raise MigrationError(code)


def _number(value: Any, code: str, low: float = 0, high: float = 1e15) -> float:
    _require(
        type(value) in (int, float) and math.isfinite(value) and low <= value <= high, code
    )
    return value


def _pairs(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def parse_json(text: str) -> Any:
    _require(len(text) <= 4 * 1024 * 1024, "json_too_large")
    try:
        return json.loads(text, object_pairs_hook=_pairs,
                          parse_constant=lambda _: _require(False, "nonfinite_json"))
    except (ValueError, TypeError) as exc:
        raise MigrationError("invalid_json") from exc


def read_json(path: str | Path) -> dict:
    path = Path(path)
    _require(path.is_file() and path.stat().st_size <= 4 * 1024 * 1024, "invalid_json_file")
    value = parse_json(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "json_object_required")
    return value


def write_json(path: str | Path, value: dict) -> None:
    """Exclusive creation: never overwrite an existing report, database or config."""
    data = (canonical_json(value) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _path(value: str | Path) -> Path:
    path = Path(value)
    _require(path.is_absolute(), "absolute_path_required")
    _require(not path.is_symlink() and path.is_file(), "regular_file_required")
    _require(0 < path.stat().st_size <= MAX_FILE, "database_size_limit")
    return path.resolve()


def _no_sidecars(path: Path) -> None:
    _require(not any(Path(str(path) + suffix).exists()
                     for suffix in ("-wal", "-shm", "-journal")), "sqlite_sidecar_present")


@contextmanager
def _readonly(path: Path):
    _no_sidecars(path)
    before = file_hash(path)
    db = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA trusted_schema=OFF")
        db.execute("PRAGMA query_only=ON")
        _require(db.execute("PRAGMA quick_check").fetchone()[0] == "ok", "sqlite_corrupt")
        yield db, before
    finally:
        db.close()
        _no_sidecars(path)
        _require(file_hash(path) == before, "readonly_file_changed")


def schema_hash(db: sqlite3.Connection) -> str:
    rows = db.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE ? "
        "ORDER BY type,name", ("sqlite_%",),
    ).fetchall()
    return stable_key([tuple(row) for row in rows])


def _target_info(db: sqlite3.Connection) -> dict:
    version = db.execute("PRAGMA user_version").fetchone()[0]
    fingerprint = schema_hash(db)
    _require(version == SCHEMA_VERSION and fingerprint == SCHEMA_HASH,
             "target_schema_incompatible")
    row = db.execute("SELECT value FROM runtime_meta WHERE key='instance_id'").fetchone()
    _require(row and isinstance(row[0], str) and row[0].strip() and row[0] != "local",
             "target_instance_missing")
    return {"schema_version": version, "schema_hash": fingerprint, "instance_id": row[0]}


def _columns(db: sqlite3.Connection, table: str) -> tuple[str, ...]:
    _require(table in KEYS, "unsupported_source_table")
    row = db.execute("SELECT type,sql FROM sqlite_master WHERE name=?", (table,)).fetchone()
    _require(row and row[0] == "table" and "VIRTUAL" not in row[1].upper(),
             "source_table_missing_or_virtual")
    return tuple(row[1] for row in db.execute(f'PRAGMA table_info("{table}")'))


def _inventory(db: sqlite3.Connection) -> dict:
    result = {}
    for table, key_columns in KEYS.items():
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name=?", (table,)).fetchone():
            continue
        columns = _columns(db, table)
        result[table] = {
            "columns": list(columns), "key_columns": list(key_columns),
            "count": db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0],
            "unmapped_columns": sorted(set(columns) - set(FIELDS[table])),
        }
    return result


def _select(db: sqlite3.Connection, item: dict) -> tuple[dict, list[str]]:
    table, key = item["table"], item["key"]
    _require(table in KEYS and isinstance(key, dict) and set(key) == set(KEYS[table]),
             "invalid_source_key")
    columns = _columns(db, table)
    _require(set(KEYS[table]) <= set(columns), "source_key_columns_missing")
    allowed = [column for column in FIELDS[table] if column in columns]
    names = ",".join(f'"{column}"' for column in allowed)
    where = " AND ".join(f'"{column}"=?' for column in KEYS[table])
    rows = db.execute(f'SELECT {names} FROM "{table}" WHERE {where} LIMIT 2',
                      tuple(key[column] for column in KEYS[table])).fetchall()
    _require(len(rows) == 1, "source_key_not_unique_or_missing")
    row = dict(rows[0])
    _require(len(canonical_json(row)) <= MAX_PAYLOAD, "source_row_too_large")
    ignored = sorted(set(columns) - set(allowed))
    if table == "kv":
        name = row["k"]
        _require(name in KV_FIELDS, "unsupported_kv_key")
        value = parse_json(row["v"])
        if name == "proactive.sessions":
            _require(isinstance(value, dict) and item.get("member") in value,
                     "explicit_session_member_required")
            value = value[item["member"]]
        elif name == "night.dreams":
            _require(isinstance(value, list) and isinstance(item.get("member"), str),
                     "explicit_dream_member_required")
            matches = [v for v in value if isinstance(v, dict)
                       and v.get("dream_id") == item["member"]]
            _require(len(matches) == 1, "dream_key_not_unique_or_missing")
            value = matches[0]
        else:
            _require("member" not in item, "unexpected_member")
        _require(isinstance(value, dict), "invalid_kv_value")
        ignored.extend("v." + k for k in value if k not in KV_FIELDS[name])
        row["v"] = {k: v for k, v in value.items() if k in KV_FIELDS[name]}
    else:
        _require("member" not in item, "unexpected_member")
    return row, ignored


def _context(db: sqlite3.Connection, item: dict, instance: str,
             source_id: str, identity: str) -> tuple[Context, int, bool]:
    context_id = item.get("context_id")
    if context_id:
        row = db.execute(
            "SELECT c.context_json,COALESCE(s.generation,0),c.scope_key "
            "FROM source_contexts c LEFT JOIN scopes s "
            "ON c.scope_key=s.scope_key WHERE c.context_id=?", (context_id,),
        ).fetchone()
        _require(row is not None, "target_context_missing")
        context = Context.from_dict(parse_json(row[0]))
        _require(context.instance_id == instance, "target_context_instance_mismatch")
        _require(context.scope_key == row[2] and context.account_key == context_id,
                 "target_context_key_mismatch")
        return replace(context, route=None), row[1], True
    # Unresolved identities are isolated per original row, never guessed from a bare ID.
    context = Context(
        bot_id="legacy:" + stable_key(source_id),
        persona_id="legacy:" + identity, adapter_id="legacy_snapshot",
        platform="legacy_unknown", scene_kind="private", scene_id=identity,
        account_id="legacy:" + identity, instance_id=instance,
    )
    row = db.execute("SELECT generation FROM scopes WHERE scope_key=?",
                     (context.scope_key,)).fetchone()
    return context, row[0] if row else 0, False


@dataclass
class Write:
    table: str
    key: dict
    values: dict


@dataclass
class Entry:
    identity: str
    digest: str
    context: Context
    generation: int
    writes: list[Write]
    report: dict


def _state(context: Context, generation: int, kind: str, key: str,
           value: dict, at: float) -> Write:
    _require(len(canonical_json(value)) <= MAX_PAYLOAD, "target_payload_too_large")
    identity = {"scope_key": context.scope_key, "kind": kind, "record_key": key}
    return Write("states", identity, {
        **identity, "generation": generation, "version": 1, "updated_at": at,
        "value_json": canonical_json(value),
    })


def _proved_human(db: sqlite3.Connection, event: dict, context: Context, item: dict) -> bool:
    if not item.get("context_id") or not context.account_id or not event.get("source_msg_id"):
        return False
    if event.get("source_account") != context.account_id or not item.get("source_session_id"):
        return False
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='msg_archive'").fetchone():
        return False
    columns = _columns(db, "msg_archive")
    if not {"msg_id", "session_id", "sender_id"} <= set(columns):
        return False
    rows = db.execute(
        "SELECT sender_id FROM msg_archive WHERE msg_id=? AND session_id=? LIMIT 2",
        (event["source_msg_id"], item["source_session_id"]),
    ).fetchall()
    return len(rows) == 1 and rows[0][0] == context.account_id


def _reference(context: Context, identity: str, at: float, expires: float | None,
               raw_refs: Any) -> EvidenceRef:
    # Missing original reference metadata is not invented or authorized.
    sources = _source_refs(raw_refs)
    _require(len(sources) <= 100 and all(len(x) <= 2048 for x in sources),
             "reference_limit")
    return EvidenceRef(
        provider="congling.snapshot", source_id=identity, context=context,
        subject_id="legacy_unknown", holder_id="legacy_unknown",
        kind=ContentKind.LEGACY_UNKNOWN, occurred_at=at, expires_at=expires,
        sensitive=True, exportable=False, source_ids=sources,
    )


def _source_refs(raw: Any) -> tuple[str, ...]:
    """Keep reference IDs, not arbitrary nested objects that may contain bodies."""
    if isinstance(raw, str):
        raw = parse_json(raw)
    if not isinstance(raw, list):
        return ()
    result = []
    for ref in raw:
        if isinstance(ref, dict):
            ref = ref.get("id", ref.get("source_id", ref.get("msg_id")))
        if type(ref) in (str, int):
            result.append(str(ref))
    _require(len(result) <= 100 and all(len(ref) <= 2048 for ref in result), "reference_limit")
    return tuple(result)


def _history_times(table: str, row: dict, ttl: int) -> tuple[float, float]:
    value = row["v"] if table == "kv" else row
    names = {
        "persona_state": ("emotion_updated_at", "last_active"),
        "emotion_event": ("occurred_at", "created_at"),
        "msg_archive": ("ts",),
        "mem_diary": ("created_at",),
        "proactive_log": ("at",),
        "night_dream_plan": ("generated_at",),
    }.get(table, ("updated_at",))
    if table == "kv":
        names = {
            "night.dreams": ("created_at",),
            "night.state": ("last_tick",),
            "proactive.sessions": ("last_at",),
        }.get(row["k"], ("updated_at",))
    times = [_number(value[name], "invalid_history_time")
             for name in names if value.get(name) is not None]
    # Never fall back to the import clock, future scheduled time, reference
    # access time, or a KV container update that refreshed an old dream body.
    origin = min(times) if times else 0
    expires = origin + ttl if origin else 0
    for name in ("expires_at", "emotion_expires_at"):
        if value.get(name) is not None:
            expires = min(expires, _number(value[name], "invalid_history_expiry"))
    if value.get("expired"):
        expires = min(expires, origin)
    return origin, expires


def _redact_original(row: dict) -> dict:
    # Retain only typed non-body facts. IDs/references also live in the envelope.
    result = {key: value for key, value in row.items()
              if value is None or type(value) in (int, float, bool)}
    if isinstance(row.get("v"), dict):
        result["v"] = _redact_original(row["v"])
    return result


def _binding(item: dict, table: str, row: dict) -> dict:
    binding = item.get("constraint_binding", {})
    _require(isinstance(binding, dict) and set(binding) <= {"timezone", "quota_scope"},
             "invalid_constraint_binding")
    if binding:
        _require(table == "kv" and row["k"] in ("proactive.sessions", "proactive.global")
                 and item.get("context_id"), "constraint_binding_requires_mapped_behavior")
        _require(set(binding) == {"timezone", "quota_scope"}, "incomplete_constraint_binding")
        _require(binding["quota_scope"] == (
            "instance" if row["k"] == "proactive.global" else "scope"
        ), "invalid_quota_scope")
        _require(isinstance(binding["timezone"], str) and 0 < len(binding["timezone"]) <= 128,
                 "invalid_legacy_timezone")
        try:
            ZoneInfo(binding["timezone"])
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise MigrationError("invalid_legacy_timezone") from exc
    return {"version": 1, **binding}


def _experience(context: Context, generation: int, identity: str,
                data: dict, kind: str, history_expires: float) -> Write:
    at = _number(data.get("created_at"), "invalid_experience_time")
    expires = data.get("expires_at")
    if expires is not None:
        _number(expires, "invalid_experience_expiry", at)
    expires = min(expires, history_expires) if expires is not None else history_expires
    refs = data.get("refs", [])
    if isinstance(refs, str):
        refs = parse_json(refs)
    _require(isinstance(refs, list), "invalid_references")
    period = data.get("day_key") if kind == "diary" else (
        str(data.get("night_key") or "legacy") + ":" + str(data["dream_id"])
    )
    _require(isinstance(period, str) and 0 < len(period) <= 512, "invalid_experience_period")
    body = data.get("text", "")
    _require(isinstance(body, str) and len(body) <= 32000, "invalid_experience_body")
    value = Experience(
        experience_id="legacy:" + identity, context=context, kind=ContentKind(kind),
        period=period, created_at=at, body=body,
        evidence=(_reference(context, identity, at, expires, refs),),
        expires_at=expires, pinned=False,
        clarity=_number(data.get("strength", 1), "invalid_clarity", 0, 1),
    )
    payload = canonical_json(value)
    _require(len(payload) <= MAX_PAYLOAD, "target_payload_too_large")
    return Write("experiences", {"experience_id": value.experience_id}, {
        "experience_id": value.experience_id, "scope_key": context.scope_key,
        "owner_key": stable_key(context.instance_id, context.bot_id, context.persona_id,
                               context.adapter_id, context.platform),
        "generation": generation, "kind": kind, "period": period, "created_at": at,
        "expires_at": expires, "pinned": int(value.pinned), "value_json": payload,
    })


def _map(db: sqlite3.Connection, target: sqlite3.Connection, item: dict, selection: dict,
         source_hash: str, instance: str) -> Entry:
    _require(isinstance(item, dict) and set(item) <= {
        "table", "key", "member", "context_id", "source_session_id", "constraint_binding",
    } and {"table", "key"} <= set(item), "invalid_selection_item")
    row, ignored = _select(db, item)
    table = item["table"]
    runtime_constraints = _binding(item, table, row)
    history_at, history_expires = _history_times(
        table, row, selection.get("history_retention_seconds", HISTORY_TTL),
    )
    identity = stable_key(selection["source_id"], table, item["key"], item.get("member"))
    context, generation, resolved = _context(
        target, item, instance, selection["source_id"], identity
    )
    writes: list[Write] = []
    blockers: list[str] = []
    baseline: dict = {}
    classification = "legacy_unknown"
    field_map = {name: "private_history" for name in row}
    at = row.get("updated_at") or row.get("created_at") or row.get("at") or 0
    at = _number(at, "invalid_source_time")
    if table in ("persona_state", "emotion_event"):
        event = row
        if table == "persona_state":
            event = {}
            if row.get("source_event_id"):
                try:
                    event, _ = _select(db, {
                        "table": "emotion_event", "key": {"id": row["source_event_id"]},
                    })
                except MigrationError:
                    pass
            occurred = row.get("emotion_updated_at")
            expires = row.get("emotion_expires_at")
            label = row.get("mood")
            confidence = row.get("emotion_confidence")
            field_map.update({
                "persona_id": "native_persona_reference_only",
                "intimacy": "legacy_intimacy_not_trust",
                "energy": "human_or_unknown_energy_not_bot",
                "busy": "human_or_unknown_busy",
                "agenda_json": "private_legacy_agenda",
                "mood": "observation_label_or_unknown",
                "emotion_expires_at": "original_expires_at",
                "source_event_id": "original_source_reference",
            })
        else:
            occurred, expires = row.get("occurred_at"), row.get("expires_at")
            label, confidence = row.get("label"), row.get("confidence")
        human = resolved and _proved_human(db, event, context, item)
        if table == "persona_state":
            human = human and row.get("persona_id") == event.get("persona_id") and (
                row.get("subject_id") in (event.get("person_id"), event.get("source_account"))
            )
        classification = "human_observation" if human else "legacy_unknown"
        if human and occurred is not None and expires is not None and confidence is not None:
            _require(isinstance(label, str) and 0 < len(label) <= 512, "invalid_label")
            observation = HumanObservation(
                subject_id=context.account_id, labels=(label,), confidence=confidence,
                occurred_at=occurred, expires_at=expires,
                evidence=(_reference(context, identity, occurred, expires,
                                     [event.get("source_msg_id")]),),
            )
            writes.append(_state(context, generation, "observation", context.account_id,
                                 to_dict(observation), occurred))
        elif human:
            blockers.append("observation_missing_original_ttl_or_confidence")
    elif table == "affinity":
        score = _number(row.get("score"), "invalid_legacy_score", -1000, 1000)
        classification = "relationship_baseline"
        field_map.update({
            "subject_key": "original_source_key", "score": "baseline_raw_score",
            "stage": "baseline_original_stage", "manual": "baseline_manual_status",
            "evidence_atom_ids": "unresolved_original_references",
        })
        row = {**row, "trust": None, "familiarity": None, "boundary": None,
               "evidence_complete": False, "auto_aggregate": False}
        baseline = {
            "score": score, "stage": row.get("stage"), "manual": row.get("manual"),
            "source_key": row["subject_key"], "trust": None, "familiarity": None,
            "boundary": None, "auto_aggregate": False,
        }
        ledger_key = {
            "event_key": "legacy:" + identity, "source_id": str(item["key"]["subject_key"]),
            "account_id": context.account_id, "dimension": "legacy_score",
        }
        writes.append(Write("relationship_ledger", ledger_key, {
            **ledger_key, "scope_key": context.scope_key, "generation": generation,
            "occurred_at": at, "day": "legacy_unknown", "delta": score,
            "reason_code": "legacy_baseline_not_aggregatable",
        }))
        blockers.append("relationship_baseline_requires_explicit_adoption")
    elif table == "mem_diary":
        classification = "diary_subjective_private"
        field_map.update({"refs": "unresolved_original_references", "text": "private_diary"})
        writes.append(_experience(context, generation, identity, row, "diary", history_expires))
    elif table in ("proactive_log", "night_dream_plan"):
        classification = "task_history_never_resume"
        field_map = {name: "history_only_never_send" for name in row}
    elif table == "msg_archive":
        window = selection.get("window")
        _require(isinstance(window, dict) and set(window) == {"since", "until"},
                 "explicit_bounded_window_required")
        start = _number(window["since"], "invalid_window_start")
        end = _number(window["until"], "invalid_window_end", start, start + 7 * 86400)
        _require(start <= _number(row.get("ts"), "invalid_message_time") <= end,
                 "message_outside_selected_window")
        classification = "legacy_window_reference_only"
        blockers.append("legacy_window_not_live_event")
    elif table == "kv":
        name, value = row["k"], row["v"]
        field_map = {"v." + key: "private_history" for key in value}
        if name == "night.state":
            classification = "night_baseline"
            mode = value.get("mode")
            if resolved and mode in ("awake", "asleep"):
                night = NightState(
                    phase=mode, energy=value["energy"], updated_at=value["last_tick"],
                    sleep_started_at=value.get("sleep_at") or None,
                    wake_at=value.get("wake_at") or None,
                    reason_codes=("legacy_snapshot_no_task_replay",),
                )
                _require(mode != "asleep" or (
                    night.sleep_started_at is not None and night.wake_at is not None
                    and night.wake_at > night.sleep_started_at
                ), "incomplete_sleep_window")
                writes.append(_state(context, generation, "night", "", to_dict(night),
                                     night.updated_at))
                field_map.update({
                    "v.mode": "night.phase", "v.energy": "night.energy",
                    "v.sleep_at": "night.sleep_started_at", "v.wake_at": "night.wake_at",
                    "v.last_tick": "night.updated_at",
                })
            else:
                blockers.append("night_unresolved_or_transition_requires_review")
            baseline = {
                "phase": mode, "energy": value.get("energy"),
                "sleep_started_at": value.get("sleep_at"), "wake_at": value.get("wake_at"),
                "updated_at": value.get("last_tick"),
                "dream_quota_used": value.get("dream_count_today"),
                "pending_crawl": value.get("pending_crawl", []), "resume_tasks": False,
            }
            if value.get("dream_count_today"):
                blockers.append("legacy_dream_quota_period_requires_review")
        elif name == "night.dreams":
            classification = "dream_imagined_private"
            if value.get("expired") or value.get("expires_at") is None:
                blockers.append("legacy_dream_decay_kept_history_only")
            else:
                writes.append(_experience(
                    context, generation, identity, value, "dream", history_expires,
                ))
            field_map.update({"v.refs": "unresolved_original_references",
                              "v.text": "private_dream_imagined",
                              "v.expires_at": "original_expires_at",
                              "v.expired": "original_expired_no_revival"})
        elif name in ("proactive.sessions", "proactive.global"):
            classification = "cooldown_quota_baseline"
            field_map.update({
                "v.next_ok_at": "original_cooldown_until",
                "v.last_at": "original_last_attempt_at",
                "v.unanswered": "original_unanswered_count",
                "v.sent_today": "original_quota_used",
                "v.day": "original_quota_period",
            })
            for key in ("next_ok_at", "last_at", "unanswered", "sent_today"):
                if key in value:
                    _number(value[key], "invalid_behavior_baseline")
            baseline = {
                "level": "global" if name == "proactive.global" else "session",
                "source_session_id": item.get("member"),
                "cooldown_until": value.get("next_ok_at"),
                "last_attempt_at": value.get("last_at"),
                "unanswered_count": value.get("unanswered"),
                "quota_period": value.get("day"), "quota_used": value.get("sent_today"),
                "runtime_adopted": False,
            }
            # Global and per-session counters may overlap; never double-charge or
            # reset them by guessing their old timezone/period or source ownership.
            blockers.append("legacy_behavior_counters_not_consumed_by_runtime")
        else:
            classification = "task_history_never_resume"
    ref_data = row["v"] if table == "kv" else row
    raw_refs = ref_data.get("refs", ref_data.get("evidence_atom_ids", []))
    source_refs = list(_source_refs(raw_refs))
    source_refs.extend(str(ref_data[key]) for key in ("msg_id", "source_msg_id", "source_event_id")
                       if type(ref_data.get(key)) in (str, int))
    archive = {
        "format": FORMAT, "source_id": selection["source_id"], "source_hash": source_hash,
        "table": table, "key": item["key"], "member": item.get("member"),
        "original": row, "classification": classification, "private": True,
        "exportable": False, "history_only": True, "field_map": field_map,
        "unmapped_columns": ignored, "activation_blockers": blockers,
        "baseline": baseline,
        "runtime_constraints": runtime_constraints,
        "history_expires_at": history_expires, "history_origin_at": history_at,
        "history_redacted": False,
        "source_refs": list(dict.fromkeys(source_refs)),
        "target_context": to_dict(context), "identity_resolved": resolved,
        "original_persona_reference": row.get("persona_id"),
    }
    writes.insert(0, _state(context, generation, "legacy_import", identity, archive, history_at))
    digest = stable_key(item, row, [write.values for write in writes])
    report = {
        "identity": identity, "table": table, "key": item["key"], "member": item.get("member"),
        "classification": classification, "identity_resolved": resolved,
        "scope_key": context.scope_key, "generation": generation,
        "field_map": field_map, "unmapped_columns": ignored, "activation_blockers": blockers,
        "history_origin_at": history_at, "history_expires_at": history_expires,
        "digest": digest, "destinations": [
            {"table": write.table, "key": write.key} for write in writes
        ],
    }
    return Entry(identity, digest, context, generation, writes, report)


def _selection(value: dict) -> None:
    _require(set(value) <= {"format", "source_id", "rows", "window", "history_retention_seconds"}
             and value.get("format") == FORMAT, "selection_format")
    ttl = value.get("history_retention_seconds", HISTORY_TTL)
    _require(type(ttl) is int and 0 < ttl <= HISTORY_TTL, "invalid_history_retention")
    _require(isinstance(value.get("source_id"), str)
             and 0 < len(value["source_id"]) <= 128, "stable_source_id_required")
    _require(isinstance(value.get("rows"), list) and len(value["rows"]) <= MAX_ROWS,
             "selection_row_limit")
    count = sum(isinstance(row, dict) and row.get("table") == "msg_archive"
                for row in value["rows"])
    _require(count <= MAX_WINDOW, "window_row_limit")


def _entries(source: sqlite3.Connection, target: sqlite3.Connection,
             selection: dict, source_hash: str, instance: str) -> list[Entry]:
    _selection(selection)
    entries = [_map(source, target, item, selection, source_hash, instance)
               for item in selection["rows"]]
    _require(len({entry.identity for entry in entries}) == len(entries),
             "duplicate_selection")
    destinations = [(write.table, canonical_json(write.key))
                    for entry in entries for write in entry.writes]
    _require(len(set(destinations)) == len(destinations), "multiple_writes_same_target")
    _require(sum(len(canonical_json(write.values)) for entry in entries
                 for write in entry.writes) <= 16 * 1024 * 1024, "batch_payload_limit")
    return entries


def _receipt_key(identity: str) -> str:
    return "legacy_import:entry:" + identity


def _existing(db: sqlite3.Connection, write: Write) -> sqlite3.Row | None:
    where = " AND ".join(f'"{column}"=?' for column in write.key)
    return db.execute(f'SELECT * FROM "{write.table}" WHERE {where}',
                      tuple(write.key.values())).fetchone()


def _status(db: sqlite3.Connection, entry: Entry) -> str:
    row = db.execute("SELECT value FROM runtime_meta WHERE key=?",
                     (_receipt_key(entry.identity),)).fetchone()
    if row:
        return "duplicate" if parse_json(row[0])["digest"] == entry.digest else "conflict"
    for write in entry.writes:
        if _existing(db, write):
            return "conflict"
        if write.table == "experiences" and db.execute(
            "SELECT 1 FROM experiences WHERE owner_key=? AND kind=? AND period=?",
            tuple(write.values[k] for k in ("owner_key", "kind", "period")),
        ).fetchone():
            return "conflict"
    return "new"


def _paths(snapshot: str | Path, target: str | Path, confirmed: bool,
           stopped: bool) -> tuple[Path, Path]:
    _require(confirmed is True, "snapshot_confirmation_required")
    _require(stopped is True, "target_must_be_stopped")
    source, destination = _path(snapshot), _path(target)
    _require(not os.path.samefile(source, destination), "source_target_same_file")
    return source, destination


def preview(snapshot: str | Path, target: str | Path, selection: dict, *,
            snapshot_confirmed: bool = False, target_stopped: bool = False) -> dict:
    source_path, target_path = _paths(snapshot, target, snapshot_confirmed, target_stopped)
    with _readonly(source_path) as (source, digest), _readonly(target_path) as (db, _):
        info = _target_info(db)
        entries = _entries(source, db, selection, digest, info["instance_id"])
        manifest = {
            "format": FORMAT, "tool": "livingemotion-offline-import-1",
            "source": {
                "path": str(source_path), "sha256": digest,
                "user_version": source.execute("PRAGMA user_version").fetchone()[0],
                "schema_hash": schema_hash(source),
                "journal_mode": source.execute("PRAGMA journal_mode").fetchone()[0],
                "tables": _inventory(source),
            },
            "target": {"path": str(target_path), **info},
            "selection": selection,
            "entries": [entry.report for entry in entries],
            "conflicts": [entry.identity for entry in entries if _status(db, entry) == "conflict"],
            "activation_blockers": sorted({
                reason for entry in entries for reason in entry.report["activation_blockers"]
            }),
            "excluded": ["mem_atom", "vectors", "mem_subject", "mem_profile", "fixed_persona_text"],
        }
        manifest["manifest_hash"] = stable_key(manifest)
        return manifest


def _check_manifest(manifest: dict, source_path: Path, target_path: Path) -> None:
    _require(manifest.get("format") == FORMAT, "manifest_format")
    _require(manifest.get("manifest_hash") == stable_key({
        key: value for key, value in manifest.items() if key != "manifest_hash"
    }), "manifest_hash_mismatch")
    _require(manifest["source"]["path"] == str(source_path)
             and manifest["target"]["path"] == str(target_path), "manifest_path_mismatch")


def _prepare(source: sqlite3.Connection, db: sqlite3.Connection, digest: str,
             manifest: dict) -> list[Entry]:
    _require(digest == manifest["source"]["sha256"], "source_hash_mismatch")
    info = _target_info(db)
    _require(info == {key: manifest["target"][key] for key in info}, "target_identity_changed")
    _require(schema_hash(source) == manifest["source"]["schema_hash"], "source_schema_changed")
    entries = _entries(source, db, manifest["selection"], digest, info["instance_id"])
    _require([entry.report for entry in entries] == manifest["entries"], "mapping_changed")
    return entries


def _insert(db: sqlite3.Connection, write: Write) -> None:
    columns = ",".join(f'"{column}"' for column in write.values)
    placeholders = ",".join("?" for _ in write.values)
    db.execute(f'INSERT INTO "{write.table}" ({columns}) VALUES ({placeholders})',
               tuple(write.values.values()))


def _retained_write(write: Write, *, now: float, human_watermark: int) -> Write | None:
    if write.table == "experiences" and write.values["expires_at"] <= now:
        return None
    if write.table != "states" or write.key["kind"] != "legacy_import":
        return write
    value = parse_json(write.values["value_json"])
    value["runtime_constraints"]["import_human_watermark"] = human_watermark
    if value["history_expires_at"] <= now:
        value["original"] = _redact_original(value["original"])
        value["baseline"].pop("pending_crawl", None)
        value["history_redacted"] = True
    return replace(write, values={**write.values, "value_json": canonical_json(value)})


def import_manifest(snapshot: str | Path, target: str | Path, manifest: dict, *,
                    snapshot_confirmed: bool = False, target_stopped: bool = False,
                    now: float | None = None) -> dict:
    checked_at = _number(time.time() if now is None else now, "invalid_import_time")
    source_path, target_path = _paths(snapshot, target, snapshot_confirmed, target_stopped)
    _check_manifest(manifest, source_path, target_path)
    _no_sidecars(target_path)
    # timeout=0 refuses competing writers immediately. Stopping the plugin is an
    # operational prerequisite: no advisory lock can make an uncooperative runtime stop.
    with _readonly(source_path) as (source, digest):
        db = sqlite3.connect(target_path.as_uri() + "?mode=rw", uri=True,
                             timeout=0, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA trusted_schema=OFF")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN EXCLUSIVE")
            entries = _prepare(source, db, digest, manifest)
            _require(entries, "empty_selection")
            states = [_status(db, entry) for entry in entries]
            _require("conflict" not in states, "target_conflict")
            inserted = 0
            for entry, status in zip(entries, states):
                if status == "duplicate":
                    continue
                row = db.execute("SELECT generation,human_watermark FROM scopes WHERE scope_key=?",
                                 (entry.context.scope_key,)).fetchone()
                _require(row is None or row[0] == entry.generation, "target_generation_changed")
                watermark = row[1] if row else 0
                db.execute(
                    "INSERT OR IGNORE INTO scopes(scope_key,context_json,generation) VALUES(?,?,?)",
                    (entry.context.scope_key, canonical_json(entry.context), entry.generation),
                )
                for write in entry.writes:
                    retained = _retained_write(write, now=checked_at, human_watermark=watermark)
                    if retained is not None:
                        _insert(db, retained)
                db.execute("INSERT INTO runtime_meta(key,value) VALUES(?,?)", (
                    _receipt_key(entry.identity), canonical_json({
                        "digest": entry.digest, "manifest_hash": manifest["manifest_hash"],
                        "source_hash": digest, "destinations": entry.report["destinations"],
                        "retention_checked_at": checked_at, "import_human_watermark": watermark,
                    }),
                ))
                inserted += 1
            _no_sidecars(source_path)
            _require(file_hash(source_path) == digest, "source_hash_mismatch")
            db.commit()
            return {
                "status": "imported", "inserted": inserted,
                "duplicates": len(entries) - inserted, "manifest_hash": manifest["manifest_hash"],
                "source_hash": digest, "activation_blockers": manifest["activation_blockers"],
                "sends": 0, "model_calls": 0,
            }
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()


def _matches_retained(row: sqlite3.Row | None, write: Write, now: float) -> bool:
    if row is None:
        return write.table == "experiences" and write.values["expires_at"] <= now
    if all(row[k] == value for k, value in write.values.items()):
        return True
    if write.table != "states" or write.key["kind"] != "legacy_import":
        return False
    value = parse_json(write.values["value_json"])
    if value["history_expires_at"] > now:
        return False
    actual = parse_json(row["value_json"])
    # Legitimate core cleanup may remove the whole original after import has
    # already retained only numeric/boolean history. No other drift is ignored.
    for key in ("original",):
        value.pop(key, None)
    value["baseline"].pop("pending_crawl", None)
    value["history_redacted"] = True
    return (actual == value and row["version"] >= write.values["version"]
            and all(row[k] == v for k, v in write.values.items()
                    if k not in ("value_json", "version")))


def verify(snapshot: str | Path, target: str | Path, manifest: dict, *,
           snapshot_confirmed: bool = False, target_stopped: bool = False,
           now: float | None = None) -> dict:
    checked_at = _number(time.time() if now is None else now, "invalid_verify_time")
    source_path, target_path = _paths(snapshot, target, snapshot_confirmed, target_stopped)
    _check_manifest(manifest, source_path, target_path)
    with _readonly(source_path) as (source, digest), _readonly(target_path) as (db, _):
        entries = _prepare(source, db, digest, manifest)
        mismatches = []
        for entry in entries:
            if _status(db, entry) != "duplicate":
                mismatches.append({"identity": entry.identity, "reason": "receipt_missing_or_changed"})
                continue
            receipt = parse_json(db.execute("SELECT value FROM runtime_meta WHERE key=?",
                                           (_receipt_key(entry.identity),)).fetchone()[0])
            for write in entry.writes:
                expected = _retained_write(
                    write, now=receipt["retention_checked_at"],
                    human_watermark=receipt["import_human_watermark"],
                )
                row = _existing(db, write)
                matches = row is None if expected is None else _matches_retained(
                    row, expected, checked_at,
                )
                if not matches:
                    mismatches.append({"identity": entry.identity, "table": write.table,
                                       "reason": "target_missing_or_changed"})
        return {"status": "verified" if not mismatches else "mismatch",
                "checked": len(entries), "mismatches": mismatches,
                "source_hash": digest, "manifest_hash": manifest["manifest_hash"],
                "sends": 0, "model_calls": 0}


def rollback_plan(target: str | Path, consumer_selection: dict, *,
                  target_stopped: bool = False) -> dict:
    _require(target_stopped is True, "target_must_be_stopped")
    path = _path(target)
    _require(set(consumer_selection) == {"format", "consumers"}
             and consumer_selection["format"] == FORMAT
             and isinstance(consumer_selection["consumers"], dict)
             and consumer_selection["consumers"], "explicit_consumer_selection_required")
    for name, value in consumer_selection["consumers"].items():
        _require(isinstance(name, str) and 0 < len(name) <= 128 and isinstance(value, dict)
                 and set(value) == {"current", "restore"}
                 and value["current"] == "livingemotion"
                 and value["restore"] in ("congling", "none"),
                 "invalid_consumer_selection")
    with _readonly(path) as (db, digest):
        info = _target_info(db)
        counts = {table: db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                  for table in ("states", "events", "experiences", "intents")}
        plan = {
            "format": FORMAT, "status": "plan_only_no_changes", "target": str(path),
            "target_hash": digest, "target_info": info, "preserved_counts": counts,
            "consumer_selection": consumer_selection, "destructive_operations": [],
            "steps": [
                {"order": 1, "action": "stop_new_executor_and_consumers",
                 "required": "Confirm plugin tasks drained; stop model/send/export and injection."},
                {"order": 2, "action": "preserve_new_database",
                 "required": "Keep original target; make a separate SQLite backup if needed."},
                {"order": 3, "action": "restore_explicit_consumer_selection",
                 "required": "Apply recorded restore choices; do not restore pending send queues."},
                {"order": 4, "action": "verify_single_owner_before_restart",
                 "required": "New executor remains stopped; validate old provider offline first."},
                {"order": 5, "action": "retain_new_records_readonly",
                 "required": "Never replace target with old backup or write new records into old DB."},
            ],
            "sends": 0, "model_calls": 0,
        }
        plan["plan_hash"] = stable_key(plan)
        return plan
