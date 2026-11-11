"""Private simulation logs and real sends share a query, never a sending ledger."""
import json

from ..contracts import canonical_json, to_dict
from .console_data import _contexts, _selected

PREFIX = "console.behavior.simulation.v1:"


async def simulation_record(store, request_id, value=None):
    def access(db):
        key = PREFIX + request_id
        old = db.execute("SELECT value FROM runtime_meta WHERE key=?", (key,)).fetchone()
        if value is not None:
            db.execute("INSERT INTO runtime_meta(key,value) VALUES(?,?) "
                       "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (key, canonical_json(value)))
        return json.loads(old[0]) if old else None
    return await store._run(access)


async def query_behavior_logs(store, instance_id, selection, *, page=1, page_size=10, query=""):
    if (type(page) is not int or not 1 <= page <= 1000000 or page_size != 10
            or not isinstance(query, str) or len(query) > 200):
        raise ValueError("invalid record query")

    def read(db):
        scopes = {c.scope_key: c for c in _selected(_contexts(db, instance_id), selection)}
        # Recover old bodies only by the exact confirmed receipt in the same scope.
        real = """SELECT i.intent_id id,i.created_at,COALESCE(i.attempted_at,i.created_at) timestamp,
            i.status,i.reason_code,i.value_json,
            i.scope_key,COALESCE(json_extract(i.value_json,'$.content'),(
                SELECT b.body FROM events e JOIN body_window b ON e.seq=b.seq
                WHERE e.scope_key=i.scope_key AND e.generation=i.generation
                  AND e.event_type='bot_action_succeeded' AND e.actor_role='bot'
                  AND json_extract(e.metadata_json,'$.source_id')=
                      json_extract(i.value_json,'$.transport_receipt.receipt_id')
                ORDER BY e.seq DESC LIMIT 1),'') content,
            EXISTS(SELECT 1 FROM events e WHERE e.scope_key=i.scope_key
                AND e.generation=i.generation AND e.actor_role='human'
                AND e.seq>json_extract(i.value_json,'$.human_watermark')
                AND e.received_at>COALESCE(i.attempted_at,i.created_at)
                AND i.attempted_at IS NOT NULL) replied
            FROM intents i WHERE i.scope_key IN (SELECT value FROM json_each(?))"""
        sim = """SELECT json_extract(value,'$.request_id') id,
            json_extract(value,'$.created_at') created_at,
            json_extract(value,'$.created_at') timestamp,
            CASE WHEN json_extract(value,'$.status')='running'
                AND json_extract(value,'$.created_at')<? THEN 'failed'
                ELSE json_extract(value,'$.status') END status,
            json_extract(value,'$.reason_code') reason_code,value value_json,'' scope_key,
            json_extract(value,'$.text') content,0 replied FROM runtime_meta
            WHERE key LIKE ? AND json_extract(value,'$.instance_id')=?
            AND json_extract(value,'$.persona_id')=?"""
        allow_sim = (selection.get("view_scope", "global") == "global"
                     and not selection.get("context_id") and not selection.get("platform"))
        args = [canonical_json(list(scopes)),
                store.clock() - getattr(getattr(store, "config", None), "model_timeout_seconds", 90) - 5,
                PREFIX + "%", instance_id,
                selection.get("persona_id", "") if allow_sim else "\x00"]
        merged = f"SELECT * FROM ({real} UNION ALL {sim})"
        # Search includes the compact fields, the unique ID and historical recovered body.
        merged += " WHERE instr(lower(id || value_json || content),lower(?))>0"
        args.append(query)
        total = db.execute(f"SELECT COUNT(*) FROM ({merged})", args).fetchone()[0]
        rows = db.execute(merged + " ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
                          [*args, page_size, (page - 1) * page_size])
        items = []
        for row in rows:
            value = json.loads(row["value_json"])
            context = to_dict(scopes[row["scope_key"]]) if row["scope_key"] else value["context"]
            items.append({**dict(row), "value": value, "context": context,
                          "replied": bool(row["replied"]), "simulated": not bool(row["scope_key"])})
        return {"items": items, "total": total, "page": page, "page_size": page_size}
    return await store._run(read)
