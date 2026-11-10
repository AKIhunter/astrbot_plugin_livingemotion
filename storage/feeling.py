"""One durable 12-hour feeling slot per instance/persona; no raw memories."""
import json
from uuid import uuid4

from ..contracts import stable_key

INTERVAL = 12 * 3600
PREFIX = "console.feeling.v1:"


def feeling_key(instance_id, persona_id):
    return PREFIX + stable_key(instance_id, persona_id)


def _read(db, key):
    row = db.execute("SELECT value FROM runtime_meta WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else {}


def _write(db, key, value):
    db.execute("INSERT INTO runtime_meta(key,value) VALUES(?,?) "
               "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (key, json.dumps(value, ensure_ascii=False)))


async def read_feeling(store, key):
    return await store._run(lambda db: _read(db, key))


async def claim_feeling(store, key, persona_revision, *, deadline_seconds):
    now = store.clock()
    def operation(db):
        def claim():
            old = _read(db, key)
            # A restart never redispatches an ambiguous paid request in its slot.
            if old.get("status") == "running" and now >= old.get("deadline", 0):
                old.update(status="unknown", reason_code="interrupted_or_timeout", run_id="")
                _write(db, key, old)
            if now < old.get("next_due", 0) or old.get("status") == "running":
                return None
            if old.get("persona_revision") != persona_revision:
                old.update(text="", generated_at=None, sources=[])
            old.update(run_id=str(uuid4()), attempted_at=now, next_due=now + INTERVAL,
                       deadline=now + deadline_seconds, status="running", reason_code="",
                       persona_revision=persona_revision, pending_sources=[])
            _write(db, key, old)
            return old
        return store._transaction(db, claim)
    return await store._run(operation)


async def set_feeling_sources(store, key, run_id, generations):
    def operation(db):
        def update():
            current = _read(db, key)
            if current.get("run_id") != run_id or current.get("status") != "running":
                return False
            for context, generation in generations:
                if store._generation(db, context) != generation:
                    return False
            current["pending_sources"] = [c.scope_key for c, _ in generations]
            _write(db, key, current)
            return True
        return store._transaction(db, update)
    return await store._run(operation)


async def finish_feeling(store, key, run_id, *, status, text="", generations=(), reason=""):
    now = store.clock()
    def operation(db):
        def finish():
            current = _read(db, key)
            if current.get("run_id") != run_id or current.get("status") != "running":
                return False
            if status == "succeeded":
                if now >= current["deadline"] or any(
                        store._generation(db, c) != g for c, g in generations):
                    status_value, reason_value = "cancelled", "source_changed_or_deadline"
                else:
                    status_value, reason_value = status, reason
                    current.update(text=text, generated_at=now,
                                   sources=[c.scope_key for c, _ in generations])
            else:
                status_value, reason_value = status, reason
            current.update(status=status_value, reason_code=reason_value, run_id="",
                           pending_sources=[])
            _write(db, key, current)
            return status_value == "succeeded"
        return store._transaction(db, finish)
    return await store._run(operation)
