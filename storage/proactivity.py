"""One durable randomized opportunity per source scene, on existing metadata.

No chat bodies are persisted here. Claim moves next_at before any model or send;
an interrupted/unknown attempt can never replay the consumed opportunity.
"""

import json

from ..contracts import canonical_json, stable_key

PREFIX = "proactivity.v1:"


def _read(db, context):
    row = db.execute("SELECT value FROM runtime_meta WHERE key=?",
                     (PREFIX + context.scope_key,)).fetchone()
    return json.loads(row[0]) if row else None


def _write(db, context, value):
    db.execute("INSERT INTO runtime_meta(key,value) VALUES(?,?) "
               "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (PREFIX + context.scope_key, canonical_json(value)))


async def read_schedule(store, context):
    return await store._run(lambda db: _read(db, context))


async def last_activity(store, context):
    """Scene-wide receipt time survives body expiry and covers every group member."""
    return await store._run(lambda db: db.execute(
        "SELECT MAX(received_at) FROM events WHERE scope_key=? "
        "AND actor_role='human' AND event_type='message' "
        "AND json_extract(metadata_json,'$.reliable_source')=1",
        (context.scope_key,),
    ).fetchone()[0])


async def claim_opportunity(store, context, *, signature, delay, lateness, deadline):
    now = store.clock()

    def claim(db):
        def mutate():
            generation = store._generation(db, context)
            old = _read(db, context)
            if (old is None or old["generation"] != generation
                    or old["signature"] != signature):
                value = {
                    "generation": generation, "signature": signature,
                    "sequence": (old or {}).get("sequence", 0),
                    "next_at": now + delay, "checked_at": now, "last_clock": now,
                    "last_outcome": "waiting", "last_reason": "random_wait",
                    "missed_count": 0, "recent_topics": [], "last_mode": "",
                }
                _write(db, context, value)
                return None
            value = dict(old)
            value.update(checked_at=now, last_clock=now)
            reason = ""
            if now < old["last_clock"]:
                reason = "clock_reversed"
            elif old.get("last_outcome") == "running":
                if now < old["deadline"]:
                    _write(db, context, value)
                    return None
                reason = "opportunity_interrupted"
            elif now < old["next_at"]:
                _write(db, context, value)
                return None
            elif now - old["next_at"] > lateness:
                reason = "missed_opportunity"
            value.update(next_at=now + delay, sequence=old["sequence"] + 1)
            if reason:
                value.update(last_outcome="skipped", last_reason=reason,
                             finished_at=now, missed_count=old["missed_count"] + 1)
                _write(db, context, value)
                return None
            run_id = "proactive:" + stable_key(
                context.scope_key, generation, signature, value["sequence"],
            )
            value.update(run_id=run_id, started_at=now, deadline=now + deadline,
                         last_outcome="running", last_reason="checking")
            _write(db, context, value)
            return dict(value)
        return store._transaction(db, mutate)
    return await store._run(claim)


async def finish_opportunity(store, context, claim, *, outcome, reason, mode="", topics=()):
    def finish(db):
        def mutate():
            value = _read(db, context)
            if (not value or value.get("run_id") != claim["run_id"]
                    or value["signature"] != claim["signature"]
                    or value["generation"] != store._generation(db, context)
                    or value["last_outcome"] != "running"):
                return False
            value.update(last_outcome=outcome, last_reason=reason,
                         finished_at=store.clock())
            if mode:
                value["last_mode"] = mode
            if topics:
                value["recent_topics"] = list(dict.fromkeys(
                    (*topics, *value.get("recent_topics", ())),
                ))[:8]
            _write(db, context, value)
            return True
        return store._transaction(db, mutate)
    return await store._run(finish)


async def record_topic_use(store, context, intent_id, *, mode, topics):
    """Remember source hashes at paid dispatch, even if its result is unknown."""
    def record(db):
        def mutate():
            value = _read(db, context)
            if (not value or value.get("run_id") != intent_id
                    or value["generation"] != store._generation(db, context)
                    or value["last_outcome"] != "running"):
                return
            value["last_mode"] = mode
            value["recent_topics"] = list(dict.fromkeys(
                (*topics, *value.get("recent_topics", ())),
            ))[:8]
            _write(db, context, value)
        return store._transaction(db, mutate)
    await store._run(record)
