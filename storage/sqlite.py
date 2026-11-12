"""Short, serialized SQLite transactions executed off the event loop."""

from __future__ import annotations

import asyncio
import contextvars
import json
import sqlite3
import time
import uuid
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any, TypeVar
from weakref import WeakValueDictionary

from ..config import Config
from ..contracts import (
    BehaviorIntent,
    CommitResult,
    Context,
    Event,
    EvidenceRef,
    Experience,
    IntentStatus,
    RelationshipContribution,
    StateRecord,
    StateWrite,
    canonical_json,
    finite,
    stable_key,
    to_dict,
)
from .schema import migrate
from .state_scope import StateScopeStore
from .night import NightStore
from .experiences import ExperienceStore

T = TypeVar("T")
STATE_KINDS = frozenset(("bot", "observation", "relationship", "night"))
_JSON_SCALARS = frozenset((str, int, float, bool, type(None)))
UNVERIFIED_EXPERIENCE = """EXISTS (
    SELECT 1 FROM json_each(experiences.value_json,'$.evidence')
    WHERE json_extract(value,'$.kind')='legacy_unknown')"""
LIVE_EXPERIENCE = f"""(pinned=1 OR expires_at IS NULL OR expires_at>?)
    AND (NOT ({UNVERIFIED_EXPERIENCE})
         OR (expires_at>? AND created_at+604800>?))"""
INTENT_TRANSITIONS = {
    "pending": {"reserved", "cancelled"},
    "reserved": {"generating", "cancelled", "failed"},
    "generating": {"sending", "cancelled", "failed"},
    "sending": {"succeeded", "failed", "unknown"},
}


class StoreClosed(RuntimeError):
    pass


class _Rejected(Exception):
    def __init__(self, reason: str):
        self.reason = reason


class _ProjectionPayload(dict):
    """Call-local native JSON produced by the built-in projector, not raw input."""


def _state_data(value: Any) -> Any:
    # Persisted guards contain thousands of plain scalars. Avoid contract/typing
    # introspection per scalar, retaining to_dict's key and custom-object semantics.
    kind = type(value)
    if kind in _JSON_SCALARS:
        return value
    if kind is dict:
        # Guard leaves already have canonical keys and scalar values. The encoder
        # still enforces finite numbers; no converted tree survives this call.
        for key, item in value.items():
            if type(key) is not str or type(item) not in _JSON_SCALARS:
                break
        else:
            return value
        return {str(key): item if type(item) in _JSON_SCALARS else _state_data(item)
                for key, item in value.items()}
    if kind is list or kind is tuple:
        return [item if type(item) in _JSON_SCALARS else _state_data(item) for item in value]
    return to_dict(value)


def _state_json(value: Any) -> str:
    native = value if type(value) is _ProjectionPayload else _state_data(value)
    return json.dumps(native, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


class _ProjectionLock(asyncio.Lock):
    def __init__(self):
        super().__init__()
        self._acquiring = 0

    @property
    def busy(self) -> bool:
        # release() wakes a waiter before that waiter owns the lock again.
        return self.locked() or self._acquiring > 0

    async def acquire(self) -> bool:
        self._acquiring += 1
        try:
            return await super().acquire()
        finally:
            self._acquiring -= 1


class SQLiteStore(StateScopeStore, NightStore, ExperienceStore):
    def __init__(self, path: str | Path, *, config: Config | None = None,
                 clock: Callable[[], float] = time.time):
        self.path = Path(path)
        self.config = config or Config()
        self.clock = clock
        self._connection: sqlite3.Connection | None = None
        self._executor: ThreadPoolExecutor | None = None
        self._lock = asyncio.Lock()
        self._projection_locks: WeakValueDictionary[str, _ProjectionLock] = WeakValueDictionary()
        self._closing = False
        self._state_modes = {}
        self._owner_generations = {}
        self._state_keys = {}

    async def _thread(self, operation: Callable[[], T]) -> T:
        # Cancelling to_thread does not stop SQLite; drain before releasing the lock.
        # Submit the context-preserving worker directly. A wrapper Task around
        # to_thread adds an extra event-loop turn to every serialized DB read/write.
        # One connection already serializes all work. Reuse one worker instead
        # of migrating the SQLite/cache working set around the host's pool.
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="livingemotion-sqlite",
            )
        context = contextvars.copy_context()
        task = asyncio.get_running_loop().run_in_executor(self._executor, context.run, operation)
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
            # Retrieve worker failures without replacing the caller's cancellation.
            if not task.cancelled():
                task.exception()
            raise

    async def open(self) -> None:
        async with self._lock:
            if self._closing:
                raise StoreClosed("store_closed")
            if self._connection is not None:
                return

            def connect() -> None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                connection = sqlite3.connect(self.path, timeout=5, isolation_level=None,
                                             check_same_thread=False)
                connection.row_factory = sqlite3.Row
                try:
                    connection.execute("PRAGMA journal_mode=WAL")
                    connection.execute("PRAGMA synchronous=FULL")
                    connection.execute("PRAGMA foreign_keys=ON")
                    connection.execute("PRAGMA busy_timeout=5000")
                    # The per-scene guard working set exceeds SQLite's 2 MiB
                    # default (legacy includes a third 192-entry guard). Bound
                    # its page cache at 16 MiB; WAL/FULL and the
                    # retained-record budgets remain unchanged.
                    connection.execute("PRAGMA cache_size=-16384")
                    migrate(connection)
                    self._state_modes = {
                        (row["instance_id"], row["persona_id"]): (row["mode"], row["revision"])
                        for row in connection.execute("SELECT * FROM state_modes")
                    }
                    self._owner_generations = {
                        row["owner_key"]: row["generation"]
                        for row in connection.execute("SELECT * FROM state_owners")
                    }
                    self._connection = connection
                except BaseException:
                    connection.close()
                    raise
            try:
                await self._thread(connect)
            except BaseException:
                try:
                    if self._connection is not None:
                        await self._thread(self._connection.close)
                        self._connection = None
                finally:
                    self._close_executor()
                raise

    async def close(self) -> None:
        self._closing = True
        async with self._lock:
            try:
                if self._connection is not None:
                    connection = self._connection
                    try:
                        await self._thread(connection.close)
                    finally:
                        self._connection = None
            finally:
                self._close_executor()

    def _close_executor(self) -> None:
        # The lock and cancellation drain guarantee no worker operation remains.
        executor, self._executor = self._executor, None
        if executor is not None:
            executor.shutdown(wait=True)

    async def _run(self, operation: Callable[[sqlite3.Connection], T]) -> T:
        if self._closing:
            raise StoreClosed("store_closed")
        async with self._lock:
            if self._closing or self._connection is None:
                raise StoreClosed("store_closed")
            connection = self._connection
            return await self._thread(lambda: operation(connection))

    def _now(self) -> float:
        now = self.clock()
        finite(now, "clock", 0)
        return now

    @staticmethod
    def _transaction(db: sqlite3.Connection, operation: Callable[[], T]) -> T:
        db.execute("BEGIN IMMEDIATE")
        try:
            result = operation()
            db.commit()
            return result
        except BaseException:
            db.rollback()
            raise

    @staticmethod
    def _generation(db: sqlite3.Connection, context: Context) -> int:
        row = db.execute("SELECT generation FROM scopes WHERE scope_key=?",
                         (context.scope_key,)).fetchone()
        return row[0] if row else 0

    @staticmethod
    def _check_generation(db: sqlite3.Connection, context: Context,
                          expected: int) -> None:
        if type(expected) is not int or expected < 0:
            raise ValueError("invalid generation")
        scope_key = context.scope_key
        row = db.execute("SELECT generation FROM scopes WHERE scope_key=?",
                         (scope_key,)).fetchone()
        if (row[0] if row else 0) != expected:
            raise _Rejected("stale_generation")
        # Callers hold BEGIN IMMEDIATE: existing scope metadata is not rewritten.
        if row is None:
            db.execute(
                "INSERT OR IGNORE INTO scopes(scope_key,context_json,generation) VALUES(?,?,?)",
                (scope_key, canonical_json(replace(context, route=None)), expected),
            )

    def _write_states(self, db, context, generation, writes, now, encoded=None):
        owner = self.state_owner(context)
        if owner is not None or any(write.owner for write in writes):
            # Source-account corrections do not change shared Bot state. Legacy
            # direct scene writes remain compatible until the first mode switch.
            account = tuple(w for w in writes if w.kind in ("relationship", "observation"))
            owned = tuple(w for w in writes if w.kind not in ("relationship", "observation"))
            if (owner and owner.mode == "scene" and owner.revision == 0
                    and (self.config.night_policy_version == 1 or not self.config.timezone)):
                owned = tuple(replace(w, owner=owner) if w.owner is None else w for w in owned)
            versions = self._write_scene_states(db, context, generation, account, now, encoded)
            versions.update(self._write_owned(db, context, generation, owned, now, encoded))
            return versions
        return self._write_scene_states(db, context, generation, writes, now, encoded)

    def _write_scene_states(self, db: sqlite3.Connection, context: Context, generation: int,
                            writes: Sequence[StateWrite], now: float, encoded=None) -> dict[str, int]:
        versions = {}
        scope_key = context.scope_key
        for write in writes:
            if write.kind not in STATE_KINDS:
                raise ValueError("invalid state kind")
            if write.kind in ("observation", "relationship") and (
                not context.account_id or write.record_key != context.account_id
            ):
                raise ValueError("account-scoped state requires source account record_key")
            if write.kind in ("bot", "night") and write.record_key:
                raise ValueError("scene-scoped state requires empty record_key")
            if type(write.expected_version) is not int or write.expected_version < 0:
                raise ValueError("invalid expected_version")
            if write.kind == "relationship" and "_relationship_override_version" in write.value:
                from .console_data import _override
                override = _override(db, context)
                if write.value["_relationship_override_version"] != (override or {}).get("version", 0):
                    raise _Rejected("version_conflict")
            loggable = write.kind == "night" and (
                write.value.get("policy_version") == 2 or write.energy_events
            )
            row = None
            version = write.expected_version
            payload = encoded[id(write.value)] if encoded is not None else None
            direct_cas = (version > 0 and not loggable and payload is not None
                          and len(payload) <= 65536)
            if not direct_cas:
                row = db.execute(
                    "SELECT version,value_json FROM states "
                    "WHERE scope_key=? AND kind=? AND record_key=?",
                    (scope_key, write.kind, write.record_key),
                ).fetchone()
                if (row[0] if row else 0) != version:
                    raise _Rejected("version_conflict")
            if payload is None:
                payload = _state_json(write.value)
            if len(payload) > 65536:
                raise ValueError("state payload too large")
            if write.kind == "bot":
                self._append_emotion(db, context.scope_key, generation, now, write.value)
            if direct_cas:
                # The CAS belongs in the UPDATE itself. Mature non-loggable
                # snapshots need no preceding SELECT or UPSERT lookup.
                cursor = db.execute(
                    """UPDATE states SET generation=?,version=?,updated_at=?,value_json=?
                       WHERE scope_key=? AND kind=? AND record_key=? AND version=?""",
                    (generation, version + 1, now, payload, scope_key,
                     write.kind, write.record_key, version),
                )
            else:
                cursor = db.execute(
                    """INSERT INTO states VALUES(?,?,?,?,?,?,?)
                       ON CONFLICT(scope_key,kind,record_key) DO UPDATE SET
                       generation=excluded.generation, version=excluded.version,
                       updated_at=excluded.updated_at,value_json=excluded.value_json
                       WHERE states.version=?""",
                    (scope_key, write.kind, write.record_key, generation,
                     version + 1, now, payload, version),
                )
            if cursor.rowcount != 1:
                raise _Rejected("version_conflict")
            versions[f"{write.kind}:{write.record_key}"] = version + 1
            if loggable and (write.energy_events or row is None or row["value_json"] != payload):
                before = self._night_value(json.loads(row["value_json"])) if row else (
                    self._night_value({})
                )
                after = self._night_value(write.value)
                self._append_energy(
                    db, context, context.scope_key,
                    stable_key("night", context.scope_key, generation, version + 1), "",
                    before, after, write.energy_events,
                )
        return versions

    async def get_generation(self, context: Context) -> int:
        return await self._run(lambda db: self._generation(db, context))

    def projection_lock(self, context: Context) -> _ProjectionLock:
        """Serialize scene projections across facades without retaining idle scopes."""
        owner = self.state_owner(context)
        key = owner.owner_key if owner and owner.mode == "shared" else context.scope_key
        lock = self._projection_locks.get(key)
        if lock is None:
            lock = _ProjectionLock()
            self._projection_locks[key] = lock
        return lock

    async def read_projection(
        self, context: Context,
    ) -> tuple[int, dict[str, StateRecord | None]]:
        """Read the generation and exact scene/account records in one SQL snapshot."""
        owner = self.state_owner(context)
        return await self._run(lambda db: self._projection_snapshot(db, context, owner))

    async def project_snapshot(self, context: Context, calculate: Callable[..., T],
                               *, relationship_override=False) -> T:
        """Run a pure local calculation with its snapshot on the same worker.

        No model or async callback belongs here. The returned projection still
        carries the read's original CAS/generation ticket; commit rechecks it.
        """
        owner = self.state_owner(context)
        def project(db):
            generation, records = self._projection_snapshot(db, context, owner)
            if relationship_override:
                from .console_data import _override
                records["_relationship_override"] = _override(db, context)
            return calculate(generation, records)
        return await self._run(project)

    def _projection_snapshot(self, db, context, owner):
        if owner is not None:
            return self._owned_projection_snapshot(db, context, owner)
        scope_key, account_id = context.scope_key, context.account_id

        rows = db.execute(
                """WITH requested(kind,record_key) AS (
                       VALUES ('bot',''),('night',''),('relationship',?),('observation',?)
                   ), current AS (
                       SELECT COALESCE((SELECT generation FROM scopes WHERE scope_key=?),0)
                           AS generation
                   )
                   SELECT r.kind,r.record_key,g.generation,s.version,s.updated_at,s.value_json
                   FROM requested r CROSS JOIN current g
                   LEFT JOIN states s ON s.scope_key=? AND s.kind=r.kind
                       AND s.record_key=r.record_key AND s.generation=g.generation
                   WHERE r.kind IN ('bot','night') OR r.record_key<>''""",
                (account_id, account_id, scope_key, scope_key),
        ).fetchall()
        return rows[0]["generation"], {
            row["kind"]: (
                StateRecord(row["kind"], json.loads(row["value_json"]), row["version"],
                            row["generation"], row["updated_at"], row["record_key"])
                if row["version"] is not None else None
            )
            for row in rows
        }

    async def get_instance_id(self) -> str:
        def identity(db: sqlite3.Connection) -> str:
            def mutate() -> str:
                db.execute("INSERT OR IGNORE INTO runtime_meta VALUES('instance_id',?)",
                           (uuid.uuid4().hex,))
                return db.execute(
                    "SELECT value FROM runtime_meta WHERE key='instance_id'").fetchone()[0]
            return self._transaction(db, mutate)
        return await self._run(identity)

    async def get_state(self, context: Context, kind: str,
                        record_key: str = "") -> StateRecord | None:
        if kind not in STATE_KINDS:
            raise ValueError("invalid state kind")
        if kind in ("observation", "relationship") and (
            not context.account_id or record_key != context.account_id
        ):
            raise ValueError("account-scoped state requires source account record_key")
        owner = self.state_owner(context)
        if owner is not None:
            return await self._run(lambda db: self._owned_record(db, context, kind, owner))

        def read(db: sqlite3.Connection) -> StateRecord | None:
            row = db.execute(
                "SELECT * FROM states WHERE scope_key=? AND kind=? AND record_key=?",
                (context.scope_key, kind, record_key),
            ).fetchone()
            if row is None:
                return None
            return StateRecord(kind, json.loads(row["value_json"]), row["version"],
                               row["generation"], row["updated_at"], record_key)
        return await self._run(read)

    async def commit_event(self, event: Event, expected_generation: int,
                           writes: Sequence[StateWrite] = (),
                           contributions: Sequence[RelationshipContribution] = (),
                           *, traces: Sequence[dict[str, Any]] = (),
                           ) -> CommitResult:
        if not event.reliable_source:
            return CommitResult("rejected", "unreliable_source")
        now = self._now()
        if event.occurred_at > now + 300:
            return CommitResult("rejected", "future_event")
        context = event.context
        scope_key, event_key = context.scope_key, event.idempotency_key
        metadata = to_dict(event)
        # Event history and dedupe outlive the body window, never duplicate its text.
        metadata.pop("body")
        metadata["context"]["route"] = None
        metadata_json = _state_json(_ProjectionPayload(metadata))
        if len(metadata_json) > 65536:
            return CommitResult("rejected", "event_too_large")
        def commit(db: sqlite3.Connection) -> CommitResult:
            # Encode bounded projections on the connection's worker, before
            # BEGIN. This avoids GIL contention with decoding/guard calculation
            # and leaves the event loop responsive; no transaction is widened.
            encoded = {id(write.value): _state_json(write.value) for write in writes}
            encoded_traces = tuple(_state_json(trace) for trace in traces)

            def mutate() -> CommitResult:
                self._check_generation(db, context, expected_generation)
                if db.execute("SELECT 1 FROM event_keys WHERE event_key=?",
                              (event_key,)).fetchone():
                    return CommitResult("duplicate", "duplicate_event", event_key,
                                        expected_generation)
                versions = self._write_states(db, context, expected_generation, writes, now, encoded)
                db.execute("INSERT INTO event_keys VALUES(?,?,?,?)",
                           (event_key, scope_key, expected_generation, now))
                cursor = db.execute(
                    """INSERT INTO events(event_key,scope_key,generation,event_id,producer,
                       event_type,actor_role,account_id,occurred_at,received_at,metadata_json)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (event_key, scope_key, expected_generation,
                     event.event_id, event.producer, event.event_type, event.actor_role.value,
                     context.account_id, event.occurred_at, now, metadata_json),
                )
                if event.actor_role.value == "human":
                    db.execute("UPDATE scopes SET human_watermark=? WHERE scope_key=?",
                               (cursor.lastrowid, scope_key))
                for trace, payload in zip(traces, encoded_traces):
                    if len(payload) > 65536 or trace.get("kind") not in (
                        "emotion", "relationship", "night",
                    ):
                        raise ValueError("invalid trace")
                    db.execute("INSERT INTO event_traces VALUES(?,?,?,?,?,?)",
                               (event_key, scope_key, expected_generation,
                                trace["kind"], now, payload))
                if event.body and event.occurred_at > now - self.config.window_days * 86400:
                    db.execute("INSERT INTO body_window VALUES(?,?,?,?)",
                               (cursor.lastrowid, scope_key, event.occurred_at,
                                event.body[:self.config.body_max_chars]))
                for contribution in contributions:
                    if contribution.account_id != context.account_id:
                        raise ValueError("contribution account mismatch")
                    db.execute(
                        """INSERT INTO relationship_ledger(scope_key,generation,event_key,
                           source_id,account_id,occurred_at,day,dimension,delta,reason_code)
                           VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (scope_key, expected_generation, event_key,
                         contribution.source_id, contribution.account_id,
                         contribution.occurred_at, contribution.day, contribution.dimension,
                         contribution.delta, contribution.reason_code),
                    )
                self._prune_window(db, now, scope_key)
                return CommitResult("accepted", "committed", event_key,
                                    expected_generation, versions)
            try:
                return self._transaction(db, mutate)
            except _Rejected as exc:
                return CommitResult("rejected", exc.reason, event_key,
                                    self._generation(db, context))
        return await self._run(commit)

    async def write_states(self, context: Context, expected_generation: int,
                           writes: Sequence[StateWrite]) -> CommitResult:
        now = self._now()

        def commit(db: sqlite3.Connection) -> CommitResult:
            def mutate() -> CommitResult:
                self._check_generation(db, context, expected_generation)
                versions = self._write_states(db, context, expected_generation, writes, now)
                return CommitResult("accepted", "committed", generation=expected_generation,
                                    versions=versions)
            try:
                return self._transaction(db, mutate)
            except _Rejected as exc:
                return CommitResult("rejected", exc.reason,
                                    generation=self._generation(db, context))
        return await self._run(commit)

    async def refine_emotion(self, event: Event, generation: int, version: int,
                             value: dict, trace: dict, *, owner=None,
                             relationship_write=None, relationship_trace=None,
                             contributions=()) -> CommitResult:
        """Replace this event's joint appraisal and ledger in one CAS transaction."""
        payload = canonical_json(trace)
        if len(payload) > 65536 or trace.get("event_key") != event.idempotency_key:
            raise ValueError("invalid refinement trace")
        context, now = event.context, self._now()
        relation_payload = canonical_json(relationship_trace) if relationship_trace else None
        if relation_payload is not None and (
                len(relation_payload) > 65536
                or relationship_trace.get("event_key") != event.idempotency_key
                or relationship_write is None
                or relationship_write.kind != "relationship"
                or relationship_write.record_key != context.account_id):
            raise ValueError("invalid relationship refinement")

        def commit(db):
            def mutate():
                self._check_generation(db, context, generation)
                row = db.execute(
                    """SELECT e.seq,s.human_watermark FROM events e JOIN scopes s USING(scope_key)
                       WHERE e.event_key=? AND e.scope_key=? AND e.generation=?""",
                    (event.idempotency_key, context.scope_key, generation),
                ).fetchone()
                if not row or row["seq"] != row["human_watermark"]:
                    raise _Rejected("new_human_message")
                versions = self._write_states(
                    db, context, generation,
                    (StateWrite("bot", value, version, owner=owner),)
                    + ((relationship_write,) if relationship_write else ()), now,
                )
                changed = db.execute(
                    """UPDATE event_traces SET value_json=? WHERE event_key=? AND scope_key=?
                       AND generation=? AND kind='emotion'""",
                    (payload, event.idempotency_key, context.scope_key, generation),
                ).rowcount
                if changed != 1:
                    raise _Rejected("trace_missing")
                if relation_payload is not None:
                    changed = db.execute(
                        """UPDATE event_traces SET value_json=? WHERE event_key=? AND scope_key=?
                           AND generation=? AND kind='relationship'""",
                        (relation_payload, event.idempotency_key, context.scope_key, generation),
                    ).rowcount
                    if changed != 1:
                        raise _Rejected("trace_missing")
                    db.execute("""DELETE FROM relationship_ledger WHERE event_key=?
                                  AND scope_key=? AND generation=? AND account_id=?""",
                               (event.idempotency_key, context.scope_key, generation, context.account_id))
                    for contribution in contributions:
                        if (contribution.source_id != event.idempotency_key
                                or contribution.account_id != context.account_id):
                            raise ValueError("contribution account mismatch")
                        db.execute(
                            """INSERT INTO relationship_ledger(scope_key,generation,event_key,
                               source_id,account_id,occurred_at,day,dimension,delta,reason_code)
                               VALUES(?,?,?,?,?,?,?,?,?,?)""",
                            (context.scope_key, generation, event.idempotency_key,
                             contribution.source_id, contribution.account_id,
                             contribution.occurred_at, contribution.day, contribution.dimension,
                             contribution.delta, contribution.reason_code),
                        )
                return CommitResult("accepted", "emotion_refined", event.idempotency_key,
                                    generation, versions)
            try:
                return self._transaction(db, mutate)
            except _Rejected as exc:
                return CommitResult("rejected", exc.reason, event.idempotency_key, generation)
        return await self._run(commit)

    def _prune_window(self, db: sqlite3.Connection, now: float,
                      scope_key: str | None = None) -> None:
        db.execute("DELETE FROM body_window WHERE occurred_at<=?",
                   (now - self.config.window_days * 86400,))
        scopes = (scope_key,) if scope_key is not None else tuple(
            row[0] for row in db.execute(
                "SELECT scope_key FROM body_window GROUP BY scope_key HAVING COUNT(*)>?",
                (self.config.window_per_scope,),
            )
        )
        for scope in scopes:
            db.execute(
                """DELETE FROM body_window WHERE scope_key=? AND seq<=
                   (SELECT seq FROM body_window WHERE scope_key=?
                    ORDER BY seq DESC LIMIT 1 OFFSET ?)""",
                (scope, scope, self.config.window_per_scope),
            )
        # Count retained rows, not event sequence distance: TTL/clear/empty bodies leave gaps.
        excess = db.execute("SELECT COUNT(*) FROM body_window").fetchone()[0] - (
            self.config.window_global
        )
        if excess > 0:
            db.execute(
                """DELETE FROM body_window WHERE seq<=
                   (SELECT seq FROM body_window ORDER BY seq LIMIT 1 OFFSET ?)""",
                (excess - 1,),
            )

    async def read_window(self, context: Context, *, after_seq: int = 0,
                          limit: int = 200) -> list[dict[str, Any]]:
        if type(limit) is not int or limit < 1 or limit > 200:
            raise ValueError("invalid window limit")
        limit = min(limit, self.config.window_per_scope)
        cutoff = self._now() - self.config.window_days * 86400

        def read(db: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = db.execute(
                """SELECT e.seq,e.event_key,e.event_id,e.actor_role,e.account_id,
                   e.occurred_at,e.metadata_json,w.body FROM body_window w
                   JOIN events e ON e.seq=w.seq WHERE w.scope_key=? AND w.seq>?
                   AND w.occurred_at>? ORDER BY w.seq LIMIT ?""",
                (context.scope_key, after_seq, cutoff, limit),
            ).fetchall()
            return [{**dict(row), "metadata_json": json.loads(row["metadata_json"])}
                    for row in rows]
        return await self._run(read)

    async def human_watermark(self, context: Context) -> int:
        return await self._run(lambda db: db.execute(
            "SELECT COALESCE(MAX(human_watermark),0) FROM scopes WHERE scope_key=?",
            (context.scope_key,),
        ).fetchone()[0])

    async def relationship_ledger(self, context: Context, *,
                                  day: str | None = None) -> list[dict[str, Any]]:
        if not context.account_id:
            raise ValueError("source account required")

        def read(db: sqlite3.Connection) -> list[dict[str, Any]]:
            sql = "SELECT * FROM relationship_ledger WHERE scope_key=? AND account_id=?"
            args: list[Any] = [context.scope_key, context.account_id]
            if day is not None:
                sql += " AND day=?"
                args.append(day)
            return [dict(row) for row in db.execute(sql + " ORDER BY id", args)]
        return await self._run(read)

    async def clear_scope(self, context: Context, expected_generation: int,
                          *, reason_code: str = "operator_clear",
                          actor_id: str = "") -> CommitResult:
        now = self._now()

        def clear(db: sqlite3.Connection) -> CommitResult:
            def mutate() -> CommitResult:
                self._check_generation(db, context, expected_generation)
                generation = expected_generation + 1
                db.execute("UPDATE scopes SET generation=? WHERE scope_key=?",
                           (generation, context.scope_key))
                owner = self.state_owner(context)
                if owner is not None:
                    self._check_owner(db, context, owner)
                    db.execute(
                        """INSERT INTO state_owners VALUES(?,?,?,1)
                           ON CONFLICT(owner_key) DO UPDATE SET generation=generation+1""",
                        (owner.owner_key, owner.persona_key, owner.mode),
                    )
                    if owner.mode == "shared":
                        # Keep shared numeric restrictions; remove source evidence
                        # and invalidate every old owner write/behavior ticket.
                        db.execute(
                            """UPDATE owner_states SET value_json=json_set(value_json,
                               '$.evidence',json('[]'),'$.reason_codes',json('[]')),
                               version=version+1 WHERE owner_key=? AND kind='bot'""",
                            (owner.owner_key,),
                        )
                    db.execute(
                        """UPDATE reply_attempts SET status='cancelled' WHERE status='started'
                           AND source_scope_key IN (
                               SELECT scope_key FROM state_members WHERE persona_key=?)""",
                        (owner.persona_key,),
                    )
                    if owner.mode == "shared":
                        db.execute(
                            """UPDATE intents SET status=CASE WHEN status='sending' THEN 'unknown'
                               WHEN status IN ('pending','reserved','generating') THEN 'cancelled'
                               ELSE status END,reason_code='source_cleared',updated_at=?
                               WHERE scope_key IN (
                                   SELECT scope_key FROM state_members WHERE persona_key=?)""",
                            (now, owner.persona_key),
                        )
                db.execute(
                    "UPDATE experience_daily SET experience_id=NULL,revision=revision+1,updated_at=? "
                    "WHERE experience_id IN (SELECT experience_id FROM experiences WHERE scope_key=?)",
                    (now, context.scope_key))
                db.execute(
                    "UPDATE experience_jobs SET status=CASE WHEN status='running' THEN 'unknown' "
                    "ELSE 'cancelled' END,reason_code='source_cleared',finished_at=? "
                    "WHERE status IN ('queued','running') AND EXISTS "
                    "(SELECT 1 FROM json_each(generation_snapshot_json,'$.sources') "
                    "WHERE json_extract(value,'$[0].instance_id')=? "
                    "AND json_extract(value,'$[0].persona_id')=? "
                    "AND json_extract(value,'$[0].scene_id')=? "
                    "AND json_extract(value,'$[0].adapter_id')=?)",
                    (now, context.instance_id, context.persona_id, context.scene_id, context.adapter_id))
                for table in ("states", "events", "body_window", "relationship_ledger",
                              "experiences", "event_traces"):
                    db.execute(f"DELETE FROM {table} WHERE scope_key=?", (context.scope_key,))
                db.execute("DELETE FROM energy_events WHERE source_scope_key=?",
                           (context.scope_key,))
                # Clear source names physically; late accepted-message callbacks cannot restore them.
                db.execute("DELETE FROM runtime_meta WHERE key LIKE 'console.qq.nickname.v1:%' "
                           "AND json_extract(value,'$.scope_key')=?", (context.scope_key,))
                # 删除来源时同步清空派生心理短句；保留周期墓碑避免重复付费生成。
                db.execute(
                    "UPDATE runtime_meta SET value=json_set(value,'$.text','',"
                    "'$.generated_at',NULL,'$.run_id','','$.status','cancelled',"
                    "'$.reason_code','source_cleared','$.sources',json('[]'),"
                    "'$.pending_sources',json('[]')) "
                    "WHERE key LIKE 'console.feeling.v1:%' AND (EXISTS "
                    "(SELECT 1 FROM json_each(runtime_meta.value,'$.sources') WHERE value=?) "
                    "OR EXISTS (SELECT 1 FROM json_each(runtime_meta.value,'$.pending_sources') WHERE value=?))",
                    (context.scope_key, context.scope_key))
                # Keep non-body intent tombstones and all quota consumption.
                db.execute(
                    """UPDATE intents SET status=CASE WHEN status='sending' THEN 'unknown'
                       WHEN status IN ('pending','reserved','generating') THEN 'cancelled'
                       ELSE status END,
                       value_json=json_object('human_watermark',
                           COALESCE(json_extract(value_json,'$.human_watermark'),-1)),
                       reason_code=?,updated_at=?
                       WHERE scope_key=?""", (reason_code, now, context.scope_key),
                )
                db.execute("INSERT INTO audit(scope_key,generation,action,reason_code,"
                           "occurred_at,actor_id) VALUES(?,?,'clear',?,?,?)",
                           (context.scope_key, generation, reason_code, now, actor_id))
                return CommitResult("accepted", "cleared", generation=generation)
            try:
                result = self._transaction(db, mutate)
                owner = self.state_owner(context)
                if owner is not None:
                    row = db.execute("SELECT generation FROM state_owners WHERE owner_key=?",
                                     (owner.owner_key,)).fetchone()
                    self._owner_generations[owner.owner_key] = row[0]
                return result
            except _Rejected as exc:
                return CommitResult("rejected", exc.reason,
                                    generation=self._generation(db, context))
        return await self._run(clear)

    async def cleanup(self) -> dict[str, int]:
        now = self._now()

        def cleanup(db: sqlite3.Connection) -> dict[str, int]:
            def mutate() -> dict[str, int]:
                self._prune_window(db, now)
                deleted = db.execute("DELETE FROM events WHERE received_at<=?",
                                     (now - self.config.event_days * 86400,)).rowcount
                db.execute("DELETE FROM event_traces WHERE event_key NOT IN "
                           "(SELECT event_key FROM events)")
                db.execute("DELETE FROM body_window WHERE seq NOT IN (SELECT seq FROM events)")
                experiences = db.execute(
                    f"DELETE FROM experiences WHERE (pinned=0 AND expires_at IS NOT NULL"
                    f" AND expires_at<=?) OR (({UNVERIFIED_EXPERIENCE}) AND "
                    "(expires_at IS NULL OR expires_at<=? OR created_at+604800<=?))",
                    (now, now, now),
                ).rowcount
                energy = db.execute("DELETE FROM energy_events WHERE occurred_at<=?",
                                    (now - 7 * 86400,)).rowcount
                db.execute("DELETE FROM wake_attempts WHERE occurred_at<=?", (now - 7 * 86400,))
                # IDs remain tombstones after cleanup; no retained route/body.
                db.execute("UPDATE reply_attempts SET context_json='{}' "
                           "WHERE started_at<=? AND status<>'started'", (now - 7 * 86400,))
                return {"events": deleted, "experiences": experiences,
                        "energy_events": energy}
            return self._transaction(db, mutate)
        return await self._run(cleanup)

    async def reserve_quota(self, reservation_id: str, context: Context,
                            expected_generation: int, *, period: str, purpose: str,
                            limit: int, units: int = 1, pool: str = "model",
                            global_limit: int | None = None,
                            scope_limit: int | None = None,
                            min_interval_seconds: float = 0) -> dict[str, Any]:
        """Reserve before a side effect. Every outcome consumes quota, without refund."""
        for value in (reservation_id, period, purpose, pool):
            if not isinstance(value, str) or not value or len(value) > 512:
                raise ValueError("invalid quota identifier")
        for value in (limit, units, global_limit, scope_limit):
            if value is not None and (type(value) is not int or value < 1):
                raise ValueError("invalid quota limit")
        finite(min_interval_seconds, "min_interval_seconds", 0)
        now = self._now()

        def reserve(db: sqlite3.Connection) -> dict[str, Any]:
            def mutate() -> dict[str, Any]:
                self._check_generation(db, context, expected_generation)
                previous = db.execute(
                    "SELECT * FROM quota_reservations WHERE reservation_id=?",
                    (reservation_id,),
                ).fetchone()
                if previous:
                    return {"status": "duplicate", "reason_code": "reservation_exists"}
                if min_interval_seconds:
                    last = db.execute(
                        """SELECT MAX(created_at) FROM quota_reservations
                           WHERE scope_key=? AND pool=? AND purpose=?""",
                        (context.scope_key, pool, purpose),
                    ).fetchone()[0]
                    if last is not None and now < last + min_interval_seconds:
                        return {"status": "rejected", "reason_code": "quota_cooldown"}
                usage = db.execute(
                    """SELECT COALESCE(SUM(units),0) FROM quota_reservations
                       WHERE period=? AND pool=? AND purpose=?""",
                    (period, pool, purpose),
                ).fetchone()[0]
                total = db.execute(
                    """SELECT COALESCE(SUM(units),0) FROM quota_reservations
                       WHERE period=? AND pool=?""", (period, pool),
                ).fetchone()[0]
                scoped = db.execute(
                    """SELECT COALESCE(SUM(units),0) FROM quota_reservations
                       WHERE period=? AND pool=? AND purpose=? AND scope_key=?""",
                    (period, pool, purpose, context.scope_key),
                ).fetchone()[0]
                if (usage + units > limit or
                        (global_limit is not None and total + units > global_limit) or
                        (scope_limit is not None and scoped + units > scope_limit)):
                    return {"status": "rejected", "reason_code": "quota_exhausted"}
                db.execute(
                    """INSERT INTO quota_reservations(reservation_id,scope_key,generation,
                       period,purpose,pool,units,status,created_at,reason_code)
                       VALUES(?,?,?,?,?,?,?,'reserved',?,'reserved')""",
                    (reservation_id, context.scope_key, expected_generation, period, purpose,
                     pool, units, now),
                )
                return {"status": "reserved", "reason_code": "quota_reserved",
                        "reservation_id": reservation_id, "used": usage + units}
            try:
                return self._transaction(db, mutate)
            except _Rejected as exc:
                return {"status": "rejected", "reason_code": exc.reason}
        return await self._run(reserve)

    async def finish_quota(self, reservation_id: str, *, status: str,
                           reason_code: str) -> bool:
        if status not in ("succeeded", "failed", "cancelled", "unknown"):
            raise ValueError("invalid quota status")
        now = self._now()
        return await self._run(lambda db: db.execute(
            """UPDATE quota_reservations SET status=?,finished_at=?,reason_code=?
               WHERE reservation_id=? AND status='reserved'""",
            (status, now, reason_code, reservation_id),
        ).rowcount == 1)

    async def quota_usage(self, *, period: str, pool: str = "model",
                          purpose: str | None = None) -> int:
        def read(db: sqlite3.Connection) -> int:
            sql = "SELECT COALESCE(SUM(units),0) FROM quota_reservations WHERE period=? AND pool=?"
            args = [period, pool]
            if purpose is not None:
                sql += " AND purpose=?"
                args.append(purpose)
            return db.execute(sql, args).fetchone()[0]
        return await self._run(read)

    async def create_intent(self, intent: BehaviorIntent) -> dict[str, Any]:
        if intent.status != IntentStatus.PENDING:
            raise ValueError("new intent must be pending")
        if not intent.context.route:
            return {"status": "rejected", "reason_code": "missing_route"}
        if intent.expires_at <= self._now():
            return {"status": "rejected", "reason_code": "expired_intent"}

        def create(db: sqlite3.Connection) -> dict[str, Any]:
            def mutate() -> dict[str, Any]:
                self._check_generation(db, intent.context, intent.generation)
                owner = self.state_owner(intent.context)
                self._check_owner(db, intent.context, owner)
                cursor = db.execute(
                    """INSERT OR IGNORE INTO intents(intent_id,scope_key,generation,status,
                       created_at,expires_at,updated_at,reason_code,value_json,
                       state_persona_key,state_revision)
                       VALUES(?,?,?,'pending',?,?,?,'created',?,?,?)""",
                    (intent.intent_id, intent.context.scope_key, intent.generation,
                     intent.created_at, intent.expires_at, self._now(), canonical_json(intent),
                     owner.persona_key if owner else None, owner.revision if owner else None),
                )
                return {"status": "created" if cursor.rowcount else "duplicate",
                        "reason_code": "intent_created" if cursor.rowcount else "intent_exists"}
            try:
                return self._transaction(db, mutate)
            except _Rejected as exc:
                return {"status": "rejected", "reason_code": exc.reason}
        return await self._run(create)

    async def get_intent(self, context: Context, intent_id: str) -> dict[str, Any] | None:
        def read(db: sqlite3.Connection) -> dict[str, Any] | None:
            row = db.execute("SELECT * FROM intents WHERE scope_key=? AND intent_id=?",
                             (context.scope_key, intent_id)).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["value"] = json.loads(result.pop("value_json"))
            return result
        return await self._run(read)

    async def transition_intent(self, context: Context, intent_id: str,
                                expected_generation: int, *, expected_status: str,
                                status: str, reason_code: str,
                                reservation_id: str | None = None,
                                transport_receipt: dict | None = None,
                                content: str | None = None,
                                emotion_snapshot: str | None = None) -> dict[str, Any]:
        if content is not None and (not isinstance(content, str) or len(content) > 2000):
            raise ValueError("invalid intent content")
        if emotion_snapshot is not None and (
                not isinstance(emotion_snapshot, str) or len(emotion_snapshot) > 512):
            raise ValueError("invalid intent emotion snapshot")
        if status not in INTENT_TRANSITIONS.get(expected_status, set()):
            return {"status": "rejected", "reason_code": "invalid_transition"}
        if transport_receipt is not None and (
                set(transport_receipt) != {"status", "receipt_id"}
                or transport_receipt["status"] not in ("confirmed", "rejected", "unknown")
                or (transport_receipt["receipt_id"] is not None and (
                    not isinstance(transport_receipt["receipt_id"], str)
                    or not 1 <= len(transport_receipt["receipt_id"]) <= 512))):
            raise ValueError("invalid transport receipt")
        now = self._now()

        def transition(db: sqlite3.Connection) -> dict[str, Any]:
            def mutate() -> dict[str, Any]:
                self._check_generation(db, context, expected_generation)
                row = db.execute(
                    "SELECT * FROM intents WHERE intent_id=? AND scope_key=?",
                    (intent_id, context.scope_key),
                ).fetchone()
                if row is None or row["generation"] != expected_generation:
                    return {"status": "rejected", "reason_code": "intent_missing"}
                if row["status"] != expected_status:
                    return {"status": "rejected", "reason_code": "intent_conflict"}
                if row["state_persona_key"] is not None:
                    mode = db.execute("SELECT revision FROM state_modes WHERE persona_key=?",
                                      (row["state_persona_key"],)).fetchone()
                    if mode is None or mode[0] != row["state_revision"]:
                        return {"status": "rejected", "reason_code": "stale_state_mode"}
                if status == "reserved":
                    quota = db.execute(
                        """SELECT 1 FROM quota_reservations WHERE reservation_id=?
                           AND scope_key=? AND generation=? AND status='reserved'""",
                        (reservation_id, context.scope_key, expected_generation),
                    ).fetchone()
                    if not quota:
                        return {"status": "rejected", "reason_code": "quota_not_reserved"}
                    if db.execute("SELECT 1 FROM intents WHERE reservation_id=?",
                                  (reservation_id,)).fetchone():
                        return {"status": "rejected", "reason_code": "reservation_in_use"}
                if status in ("generating", "sending") and row["expires_at"] <= now:
                    return {"status": "rejected", "reason_code": "expired_intent"}
                if status == "sending":
                    value = json.loads(row["value_json"])
                    previous_context = value["context"]
                    if any(previous_context[name] != getattr(context, name) for name in
                           ("identity_revision", "persona_revision", "route")):
                        return {"status": "rejected", "reason_code": "context_changed"}
                    watermark = db.execute(
                        "SELECT human_watermark FROM scopes WHERE scope_key=?",
                        (context.scope_key,),
                    ).fetchone()[0]
                    if watermark > value["human_watermark"]:
                        return {"status": "rejected", "reason_code": "new_human_message"}
                db.execute(
                    """UPDATE intents SET status=?,updated_at=?,reason_code=?,
                       reservation_id=COALESCE(reservation_id,?),
                       attempted_at=CASE WHEN ?='sending' THEN ? ELSE attempted_at END
                       WHERE intent_id=?""",
                    (status, now, reason_code, reservation_id, status, now, intent_id),
                )
                if transport_receipt is not None or content is not None or emotion_snapshot is not None:
                    value = json.loads(row["value_json"])
                    if transport_receipt is not None:
                        value["transport_receipt"] = transport_receipt
                    if content is not None:
                        value["content"] = content
                    if emotion_snapshot is not None:
                        value["emotion_snapshot"] = emotion_snapshot
                    db.execute("UPDATE intents SET value_json=? WHERE intent_id=?",
                               (canonical_json(value), intent_id))
                return {"status": "updated", "reason_code": reason_code}
            try:
                return self._transaction(db, mutate)
            except _Rejected as exc:
                return {"status": "rejected", "reason_code": exc.reason}
        return await self._run(transition)

    async def recover_inflight(self) -> dict[str, int]:
        """Use on startup after exclusive ownership; never resume an old send."""
        now = self._now()

        def recover(db: sqlite3.Connection) -> dict[str, int]:
            def mutate() -> dict[str, int]:
                unknown = db.execute(
                    """UPDATE intents SET status='unknown',reason_code='interrupted_send',
                       updated_at=? WHERE status='sending'""", (now,),
                ).rowcount
                cancelled = db.execute(
                    """UPDATE intents SET status='cancelled',reason_code='runtime_restarted',
                       updated_at=? WHERE status IN ('pending','reserved','generating')""", (now,),
                ).rowcount
                db.execute(
                    """UPDATE quota_reservations SET status='unknown',reason_code='interrupted',
                       finished_at=? WHERE status='reserved'""", (now,),
                )
                db.execute("UPDATE reply_attempts SET status='cancelled' WHERE status='started'")
                return {"unknown": unknown, "cancelled": cancelled}
            return self._transaction(db, mutate)
        return await self._run(recover)

    async def save_experience(self, experience: Experience,
                              expected_generation: int, *, replace_existing: bool = False,
                              ) -> dict[str, Any]:
        """Private content persistence only; callers own generation/authorization.

        replace_existing=True：手动重写同一天时覆盖旧内容（默认仍保留第一份）。
        """
        context = experience.context
        owner = stable_key(context.instance_id, context.bot_id, context.persona_id,
                           context.adapter_id, context.platform)
        payload = canonical_json(experience)
        if len(payload) > 131072:
            raise ValueError("experience too large")

        def save(db: sqlite3.Connection) -> dict[str, Any]:
            def mutate() -> dict[str, Any]:
                self._check_generation(db, context, expected_generation)
                verb = "INSERT OR REPLACE" if replace_existing else "INSERT OR IGNORE"
                cursor = db.execute(
                    verb + " INTO experiences VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (experience.experience_id, context.scope_key, owner, expected_generation,
                     experience.kind.value, experience.period, experience.created_at,
                     experience.expires_at, int(experience.pinned), payload),
                )
                return {"status": "created" if cursor.rowcount else "duplicate",
                        "reason_code": "experience_saved" if cursor.rowcount else "experience_exists"}
            try:
                return self._transaction(db, mutate)
            except _Rejected as exc:
                return {"status": "rejected", "reason_code": exc.reason}
        return await self._run(save)

    async def backup(self, destination: str | Path) -> None:
        target = Path(destination)
        if target.resolve() == self.path.resolve() or target.exists():
            raise ValueError("backup destination must be new")

        def copy(db: sqlite3.Connection) -> None:
            target.parent.mkdir(parents=True, exist_ok=True)
            backup = sqlite3.connect(target)
            try:
                db.backup(backup)
            finally:
                backup.close()
        await self._run(copy)

    async def register_context(self, context: Context) -> str:
        """Remember a trusted source, not permission to reuse its route after restart."""
        now, identifier = self._now(), context.account_key
        await self._run(lambda db: db.execute(
            """INSERT INTO source_contexts VALUES(?,?,?,?)
               ON CONFLICT(context_id) DO UPDATE SET
               context_json=excluded.context_json,updated_at=excluded.updated_at""",
            (identifier, context.scope_key, canonical_json(replace(context, route=None)), now),
        ))
        return identifier

    async def list_contexts(self, *, limit: int = 512) -> list[Context]:
        if type(limit) is not int or not 1 <= limit <= 512:
            raise ValueError("invalid context limit")
        return await self._run(lambda db: [
            Context.from_dict(json.loads(row[0]))
            for row in db.execute(
                "SELECT context_json FROM source_contexts ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            )
        ])

    async def correct_relationship(self, context: Context, expected_generation: int, *,
                                   expected_version: int, actor_id: str, reason: str,
                                   score: float | None = None,
                                   frozen: bool | None = None) -> CommitResult:
        """Apply the pure correction with its source ledger and audit in one transaction."""
        from ..contracts import Relationship
        from ..domain.relationship import correct_relationship

        now = self._now()

        def commit(db):
            def mutate():
                self._check_generation(db, context, expected_generation)
                row = db.execute(
                    "SELECT version,value_json FROM states WHERE scope_key=? "
                    "AND kind='relationship' AND record_key=?",
                    (context.scope_key, context.account_id),
                ).fetchone()
                version = row["version"] if row else 0
                if version != expected_version:
                    raise _Rejected("version_conflict")
                value = json.loads(row["value_json"]) if row else {}
                state = Relationship(**{k: v for k, v in value.items() if not k.startswith("_")})
                result = correct_relationship(
                    state, context, now=now, actor_id=actor_id, reason=reason,
                    expected_version=expected_version, current_version=version,
                    score=score, frozen=frozen,
                )
                versions = self._write_states(db, context, expected_generation, (
                    StateWrite("relationship", {
                        **to_dict(result["relationship"]), "_runtime": value.get("_runtime", {}),
                        **({"_account_affect": value["_account_affect"]}
                           if "_account_affect" in value else {}),
                    }, version, context.account_id),
                ), now)
                event_key = stable_key("management", context.account_key,
                                       expected_generation, version + 1)
                for item in result["contributions"]:
                    db.execute(
                        """INSERT INTO relationship_ledger(scope_key,generation,event_key,
                           source_id,account_id,occurred_at,day,dimension,delta,reason_code)
                           VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (context.scope_key, expected_generation, event_key, item.source_id,
                         item.account_id, item.occurred_at, item.day, item.dimension,
                         item.delta, item.reason_code),
                    )
                db.execute(
                    """INSERT INTO audit(scope_key,generation,action,reason_code,occurred_at,
                       actor_id,value_json) VALUES(?,?,'relationship.correct',?,?,?,?)""",
                    (context.scope_key, expected_generation, reason, now, actor_id,
                     canonical_json(result["audit"])),
                )
                return CommitResult("accepted", "relationship_corrected",
                                    generation=expected_generation, versions=versions)
            try:
                return self._transaction(db, mutate)
            except _Rejected as exc:
                return CommitResult("rejected", exc.reason)
        return await self._run(commit)

    async def append_audit(self, *, action: str, actor_id: str, reason: str,
                           value: dict[str, Any], context: Context | None = None) -> None:
        payload = canonical_json(value)
        if not actor_id or not reason.strip() or len(reason) > 1000 or len(payload) > 65536:
            raise ValueError("invalid audit")
        await self._run(lambda db: db.execute(
            """INSERT INTO audit(scope_key,generation,action,reason_code,occurred_at,
               actor_id,value_json) VALUES(?,?,?,?,?,?,?)""",
            (context.scope_key if context else "", self._generation(db, context) if context else 0,
             action, reason, self._now(), actor_id, payload),
        ))

    async def audit_records(self, context: Context | None = None, *,
                            limit: int = 100) -> list[dict[str, Any]]:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("invalid audit limit")
        def read(db):
            where = " WHERE scope_key=?" if context else ""
            args = (context.scope_key, limit) if context else (limit,)
            return [{**dict(row), "value": json.loads(row["value_json"])}
                    for row in db.execute(
                        f"SELECT * FROM audit{where} ORDER BY seq DESC LIMIT ?", args)]
        return await self._run(read)

    async def query_records(self, context: Context, kind: str, *, page: int = 1,
                            page_size: int = 10, query: str = "") -> dict[str, Any]:
        if (kind not in ("emotion", "behavior", "diary", "dream")
                or type(page) is not int or not 1 <= page <= 100000
                or page_size != 10 or type(page_size) is not int
                or not isinstance(query, str) or len(query) > 200):
            raise ValueError("invalid record query")
        tables = {"emotion": ("event_traces", "occurred_at", "event_key"),
                  "behavior": ("intents", "created_at", "intent_id"),
                  "diary": ("experiences", "created_at", "experience_id"),
                  "dream": ("experiences", "created_at", "experience_id")}
        table, time_col, id_col = tables[kind]
        def read(db):
            filters, args = ["scope_key=?"], [context.scope_key]
            if kind != "behavior":
                filters.append("kind=?")
                args.append(kind)
            if kind in ("diary", "dream"):
                filters.append(LIVE_EXPERIENCE)
                args.extend([self._now()] * 3)
            if query:
                filters.append("instr(lower(value_json),lower(?))>0")
                args.append(query)
            where = " AND ".join(filters)
            total = db.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", args).fetchone()[0]
            rows = db.execute(
                f"SELECT * FROM {table} WHERE {where} ORDER BY {time_col} DESC,{id_col} DESC "
                "LIMIT ? OFFSET ?", [*args, page_size, (page - 1) * page_size],
            ).fetchall()
            return {"items": [
                {**{k: row[k] for k in row.keys() if k != "value_json"},
                 "id": row[id_col], "created_at": row[time_col],
                 # 正文只由鉴权控制台的专用日志查询读取；通用诊断仍不带正文。
                 "value": {k: v for k, v in json.loads(row["value_json"]).items()
                           if kind != "behavior" or k != "content"}} for row in rows
            ], "page": page, "page_size": page_size, "total": total}
        return await self._run(read)

    async def behavior_history(self, context: Context, period: str,
                               exclude_intent_id: str | None = None) -> dict[str, Any]:
        def read(db):
            exclude = db.execute(
                "SELECT reservation_id FROM intents WHERE intent_id=? AND scope_key=?",
                (exclude_intent_id, context.scope_key),
            ).fetchone()
            reservation = exclude[0] if exclude else ""
            usage = db.execute(
                """SELECT COALESCE(SUM(units),0),
                   COALESCE(SUM(CASE WHEN scope_key=? AND purpose='behavior'
                   THEN units ELSE 0 END),0)
                   FROM quota_reservations WHERE pool='send'
                   AND period=? AND reservation_id<>?""",
                (context.scope_key, period, reservation or ""),
            ).fetchone()
            watermark = db.execute(
                "SELECT COALESCE(MAX(human_watermark),0) FROM scopes WHERE scope_key=?",
                (context.scope_key,),
            ).fetchone()[0]
            attempts = db.execute(
                """SELECT attempted_at,status,value_json FROM intents WHERE scope_key=?
                   AND intent_id<>? AND attempted_at IS NOT NULL""",
                (context.scope_key, exclude_intent_id or ""),
            ).fetchall()
            history = {
                "global_used": usage[0], "scope_used": usage[1],
                "last_attempt_at": max((r["attempted_at"] for r in attempts), default=None),
                "unanswered_count": sum(
                    r["status"] in ("succeeded", "unknown")
                    and json.loads(r["value_json"]).get("human_watermark", -1) >= watermark
                    for r in attempts
                ),
                "cooldown_until": None,
                "reason_codes": (),
            }
            return history
        return await self._run(read)

    async def load_experience(self, entry_id: str) -> tuple[Experience, int] | None:
        def read(db):
            row = db.execute(f"SELECT value_json,generation FROM experiences WHERE "
                             f"experience_id=? AND {LIVE_EXPERIENCE}",
                             (entry_id, *([self._now()] * 3))).fetchone()
            if row is None:
                return None
            value = json.loads(row[0])
            value["context"] = Context.from_dict(value["context"])
            value["evidence"] = tuple(EvidenceRef(**{
                **ref, "context": Context.from_dict(ref["context"]),
            }) for ref in value["evidence"])
            return Experience(**value), row[1]
        return await self._run(read)

    async def save_experience_guarded(self, experience: Experience,
                                     generations: Sequence[tuple[Context, int]], *,
                                     watermarks: Sequence[tuple[Context, int]] = (),
                                     replace_existing: bool = False) -> dict[str, Any]:
        """All source clear-generations and the entry are checked in one transaction."""
        context = experience.context
        payload = canonical_json(experience)
        if len(payload) > 131072:
            raise ValueError("experience too large")
        owner = stable_key(context.instance_id, context.bot_id, context.persona_id,
                           context.adapter_id, context.platform)
        def save(db):
            def mutate():
                for source, generation in generations:
                    self._check_generation(db, source, generation)
                for source, expected in watermarks:
                    row = db.execute("SELECT human_watermark FROM scopes WHERE scope_key=?",
                                     (source.scope_key,)).fetchone()
                    if (row[0] if row else 0) != expected:
                        raise _Rejected("new_human_message")
                if not any(source.scope_key == context.scope_key for source, _ in generations):
                    raise ValueError("missing target generation")
                generation = self._generation(db, context)
                verb = "INSERT OR REPLACE" if replace_existing else "INSERT OR IGNORE"
                cursor = db.execute(
                    verb + " INTO experiences VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (experience.experience_id, context.scope_key, owner, generation,
                     experience.kind.value, experience.period, experience.created_at,
                     experience.expires_at, int(experience.pinned), payload),
                )
                return {"status": "created" if cursor.rowcount else "duplicate",
                        "reason_code": "experience_saved" if cursor.rowcount else "experience_exists"}
            try:
                return self._transaction(db, mutate)
            except _Rejected as exc:
                return {"status": "rejected", "reason_code": exc.reason}
        return await self._run(save)

    async def pin_experience(self, old: Experience, new: Experience,
                             expected_generation: int, *, actor_id: str,
                             reason: str) -> dict[str, Any]:
        """Compare the entire old record and audit the bounded pin change atomically."""
        if (not actor_id or not reason.strip() or len(reason) > 1000
                or replace(new, pinned=old.pinned, clarity=old.clarity) != old):
            raise ValueError("invalid pin update")
        now, context = self._now(), old.context

        def commit(db):
            def mutate():
                self._check_generation(db, context, expected_generation)
                row = db.execute(
                    "SELECT value_json,generation,expires_at,pinned FROM experiences "
                    "WHERE experience_id=?", (old.experience_id,),
                ).fetchone()
                if (not row or row["generation"] != expected_generation
                        or row["value_json"] != canonical_json(old)
                        or not row["pinned"] and row["expires_at"] is not None
                        and row["expires_at"] <= now):
                    raise _Rejected("experience_changed")
                # 来源不明的体验仍遵守七天硬期限，置顶不能绕过隐私边界。
                if any(ref.kind.value == "legacy_unknown" for ref in old.evidence):
                    if old.expires_at is None or now >= min(old.expires_at, old.created_at + 604800):
                        raise _Rejected("experience_expired")
                db.execute("UPDATE experiences SET pinned=?,value_json=? WHERE experience_id=?",
                           (int(new.pinned), canonical_json(new), old.experience_id))
                db.execute(
                    """INSERT INTO audit(scope_key,generation,action,reason_code,occurred_at,
                       actor_id,value_json) VALUES(?,?,?,?,?,?,?)""",
                    (context.scope_key, expected_generation, "experience.pin", reason, now,
                     actor_id, canonical_json({"id": old.experience_id, "pinned": new.pinned})),
                )
                return {"status": "updated", "reason_code": "pin_updated"}
            try:
                return self._transaction(db, mutate)
            except _Rejected as exc:
                return {"status": "rejected", "reason_code": exc.reason}
        return await self._run(commit)

    async def replace_external_memories(self, persona_id: str, provider: str,
                                        rows: Sequence[dict], *, synced_at: float,
                                        truncated: bool = False) -> dict[str, Any]:
        """Replace the local mirror of one persona's external memories atomically.

        The mirror is a read-only copy for the admin page; LivingMemory remains
        the source of truth. Replacing (not merging) keeps deletions visible.
        """
        if not isinstance(persona_id, str) or not persona_id or len(persona_id) > 512:
            raise ValueError("invalid persona id")
        if not isinstance(provider, str) or not provider or len(provider) > 128:
            raise ValueError("invalid provider")
        finite(synced_at, "synced_at", 0)
        prepared = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("invalid memory row")
            memory_id = row.get("memory_id")
            if type(memory_id) is not int or memory_id <= 0:
                raise ValueError("invalid memory id")
            body = row.get("text")
            if not isinstance(body, str):
                raise ValueError("invalid memory body")
            created = row.get("created_at")
            if created is not None:
                finite(created, "created_at", 0)
            prepared.append((memory_id, persona_id, body[:4000],
                             created, str(row.get("session_id") or "")[:512],
                             canonical_json(row.get("metadata") or {}), synced_at))

        def write(db: sqlite3.Connection) -> dict[str, Any]:
            def mutate():
                db.execute("DELETE FROM external_memories WHERE persona_id=?", (persona_id,))
                db.executemany(
                    "INSERT OR REPLACE INTO external_memories"
                    "(memory_id,persona_id,body,created_at,session_id,metadata_json,synced_at)"
                    " VALUES(?,?,?,?,?,?,?)", prepared)
                db.execute(
                    "INSERT OR REPLACE INTO external_memory_sync"
                    "(persona_id,provider,synced_at,stored,truncated) VALUES(?,?,?,?,?)",
                    (persona_id, provider, synced_at, len(prepared), int(bool(truncated))))
                return {"stored": len(prepared), "truncated": bool(truncated)}
            return self._transaction(db, mutate)
        return await self._run(write)

    async def external_memory_mirror(self, persona_id: str, *,
                                     limit: int = 5) -> dict[str, Any]:
        """Mirror summary for the console; body text is never logged."""
        if not isinstance(persona_id, str) or len(persona_id) > 512:
            raise ValueError("invalid persona id")
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("invalid mirror limit")

        def read(db: sqlite3.Connection) -> dict[str, Any]:
            meta = db.execute(
                "SELECT provider,synced_at,stored,truncated FROM external_memory_sync "
                "WHERE persona_id=?", (persona_id,)).fetchone()
            total = db.execute("SELECT COUNT(*) FROM external_memories WHERE persona_id=?",
                               (persona_id,)).fetchone()[0]
            items = []
            if persona_id:
                items = [{"memory_id": row["memory_id"], "text": row["body"],
                          "created_at": row["created_at"], "session_id": row["session_id"]}
                         for row in db.execute(
                             "SELECT memory_id,body,created_at,session_id FROM external_memories "
                             "WHERE persona_id=? ORDER BY memory_id DESC LIMIT ?",
                             (persona_id, limit))]
            return {"total": total, "provider": meta["provider"] if meta else "",
                    "synced_at": meta["synced_at"] if meta else None,
                    "truncated": bool(meta["truncated"]) if meta else False,
                    "items": items}
        return await self._run(read)

    async def health(self) -> dict[str, Any]:
        def read(db: sqlite3.Connection) -> dict[str, Any]:
            counts = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                      for table in ("events", "body_window", "states", "intents",
                                    "quota_reservations")}
            return {"status": "ready", "schema_version": db.execute(
                "PRAGMA user_version").fetchone()[0],
                "journal_mode": db.execute("PRAGMA journal_mode").fetchone()[0],
                "counts": counts}
        return await self._run(read)
