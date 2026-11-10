"""Authenticated console queries and account overrides on existing store tables.

No schema ownership here. All database work uses the store's serialized _run.
Persisted contexts describe provenance, never authority to send.
"""

from dataclasses import replace
from decimal import Decimal
import json
import math

from ..contracts import ActorRole, ContentKind, Context, Event, Relationship, canonical_json, stable_key, to_dict
from ..domain.relationship import initial_relationship, relationship_stage, relationship_stage_dto
from ..domain.relationship_inference import RelationshipStatement, infer_relationships

OVERRIDE_PREFIX = "console.relationship.override.v1:"
NICKNAME_PREFIX = "console.qq.nickname.v1:"


async def remember_qq_nickname(store, context, nickname, generation, *, occurred_at):
    """Cache a native QQ sender name only after accepted ingestion, with clear fencing."""
    if (context.platform != "qq" or context.scene_kind.value not in ("private", "group")
            or not isinstance(nickname, str) or not nickname.strip()):
        return
    nickname = "".join(char for char in nickname.strip() if ord(char) >= 32)[:80]
    if not nickname:
        return
    def write(db):
        row = db.execute("SELECT generation FROM scopes WHERE scope_key=?",
                         (context.scope_key,)).fetchone()
        if not row or row[0] != generation:
            return
        key = NICKNAME_PREFIX + context.account_key
        old = db.execute("SELECT value FROM runtime_meta WHERE key=?", (key,)).fetchone()
        if old and json.loads(old[0])["occurred_at"] > occurred_at:
            return
        value = {"scope_key": context.scope_key, "account_key": context.account_key,
                 "nickname": nickname, "generation": generation, "occurred_at": occurred_at,
                 "qq_name_verified": True}
        db.execute("INSERT INTO runtime_meta(key,value) VALUES(?,?) "
                   "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                   (key, canonical_json(value)))
    await store._run(write)


def _qq_nickname(db, sources):
    candidates = []
    for context in sources:
        if context.platform != "qq":
            continue
        row = db.execute(
            "SELECT r.value FROM runtime_meta r JOIN scopes s "
            "ON s.scope_key=json_extract(r.value,'$.scope_key') "
            "AND s.generation=json_extract(r.value,'$.generation') WHERE r.key=?",
            (NICKNAME_PREFIX + context.account_key,),
        ).fetchone()
        if row:
            value = json.loads(row[0])
            # Older group caches used the adapter's card-first display name.
            if context.scene_kind.value != "group" or value.get("qq_name_verified") is True:
                candidates.append(value)
    latest = max(candidates, key=lambda n: n["occurred_at"], default=None)
    return latest["nickname"] if latest else ""


class ConsoleDataConflict(ValueError):
    code = "version_conflict"
    status_code = 409


def relationship_account_key(context):
    return stable_key(context.instance_id, context.persona_id,
                      context.platform, context.account_id)


def _override(db, context):
    row = db.execute("SELECT value FROM runtime_meta WHERE key=?",
                     (OVERRIDE_PREFIX + relationship_account_key(context),)).fetchone()
    return json.loads(row[0]) if row else None


async def read_relationship_override(store, context):
    """Return the persisted account override, or None; does not authorize reads."""
    return await store._run(lambda db: _override(db, context))


def _apply_override(context, relationship, override, *, applied_version=0):
    if relationship is None or override is None:
        return relationship
    score = (relationship.score if applied_version == override["version"]
             else override.get("score", relationship.score))
    return replace(relationship, score=score, stage=relationship_stage(score),
                   frozen=override.get("frozen", relationship.frozen),
                   updated_at=max(relationship.updated_at, override["updated_at"]),
                   identity_revision=context.identity_revision,
                   reason_codes=tuple(dict.fromkeys(
                       (*relationship.reason_codes, "platform_account_override"))))


async def apply_relationship_override(store, context, relationship):
    """Call after a live authorized projection; None remains fail-closed."""
    if relationship is None:
        return None
    record = await store.get_state(context, "relationship", context.account_id)
    return _apply_override(context, relationship,
                           await read_relationship_override(store, context),
                           applied_version=(record.value.get("_relationship_override_version", 0)
                                            if record else 0))


def _score(value):
    if type(value) not in (int, float) or not 0 <= value <= 100 or not math.isfinite(value):
        raise ValueError("invalid display score")
    scaled = Decimal(str(value)) * 10
    if scaled != scaled.to_integral_value():
        raise ValueError("score requires 0.1 display units")
    return int(scaled)


async def write_relationship_override(store, context, *, expected_version,
                                      actor_id, reason, score=None, frozen=None, note=None):
    """CAS override and audit together; never edit external/local plugin state."""
    if (not context.account_id or type(expected_version) is not int
            or not 0 <= expected_version <= 2**63 - 1
            or not isinstance(actor_id, str) or not actor_id.strip() or len(actor_id) > 512
            or not isinstance(reason, str) or not reason.strip() or len(reason) > 1000
            or (score is None and frozen is None and note is None)
            or (frozen is not None and type(frozen) is not bool)):
        raise ValueError("invalid relationship override")
    if note is not None:
        validate_relationship_note(note)
    raw_score = _score(score) if score is not None else None
    now = store.clock()

    def commit(db):
        def mutate():
            old = _override(db, context)
            version = old["version"] if old else 0
            if version != expected_version:
                raise ConsoleDataConflict("relationship override changed")
            value = {
                **(old or {}), "version": version + 1, "updated_at": now,
                "instance_id": context.instance_id, "persona_id": context.persona_id,
                "platform": context.platform, "account_id": context.account_id,
            }
            if raw_score is not None:
                value["score"] = raw_score
            if frozen is not None:
                value["frozen"] = frozen
            if note is not None:
                value["note"] = note
            db.execute(
                "INSERT INTO runtime_meta(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (OVERRIDE_PREFIX + relationship_account_key(context), canonical_json(value)),
            )
            generation = db.execute("SELECT generation FROM scopes WHERE scope_key=?",
                                    (context.scope_key,)).fetchone()
            db.execute(
                "INSERT INTO audit(scope_key,generation,action,reason_code,occurred_at,"
                "actor_id,value_json) VALUES(?,?,'relationship.override',?,?,?,?)",
                (context.scope_key, generation[0] if generation else 0, reason.strip(), now,
                 actor_id, canonical_json({"account_key": relationship_account_key(context),
                                          "expected_version": version, "version": version + 1,
                                          "before": old, "after": value})),
            )
            sources = [c for c in _contexts(db, context.instance_id)
                       if relationship_account_key(c) == relationship_account_key(context)]
            return {**value, "node": _relationship_node(
                db, sources or [context], getattr(store, "config", None))}
        return store._transaction(db, mutate)
    return await store._run(commit)


def validate_relationship_note(note):
    if (not isinstance(note, str) or len(note) > 1000
            or any((ord(c) < 32 and c not in "\n\r\t") or 127 <= ord(c) < 160 for c in note)):
        raise ValueError("invalid relationship note")
    return note


def context_dto(context):
    return {"id": context.account_key, "scope_key": context.scope_key,
            "persona_id": context.persona_id,
            "platform": context.platform, "view_scope": context.scene_kind.value,
            "scene_id": context.scene_id, "account_id": context.account_id,
            "label": f"{context.platform} / {context.scene_id} / {context.account_id}"}


def _contexts(db, instance_id):
    result = []
    for row in db.execute(
            "SELECT context_json FROM source_contexts ORDER BY updated_at DESC,context_id DESC"):
        context = Context.from_dict(json.loads(row[0]))
        if context.instance_id == instance_id and context.scene_kind.value in ("private", "group"):
            result.append(context)
    return result


def _selected(contexts, selection):
    persona = selection.get("persona_id", "")
    platform = selection.get("platform", "")
    view = selection.get("view_scope", "global")
    identifier = selection.get("context_id", "")
    if view not in ("global", "private", "group"):
        raise ValueError("invalid view scope")
    selected = [c for c in contexts if (not persona or c.persona_id == persona)
                and (not platform or c.platform == platform)
                and (view == "global" or c.scene_kind.value == view)
                and (not identifier or c.account_key == identifier)]
    if identifier and not selected:
        raise ValueError("unknown or mismatched context")
    return selected


async def selected_contexts(store, instance_id, selection):
    return await store._run(lambda db: _selected(_contexts(db, instance_id), selection))


async def query_scopes(store, instance_id, selection):
    def read(db):
        contexts = _contexts(db, instance_id)
        selected = _selected(contexts, selection)
        return {
            "personas": [{"id": p, "name": p} for p in sorted({c.persona_id for c in contexts})],
            "platforms": sorted({c.platform for c in contexts
                                 if not selection.get("persona_id")
                                 or c.persona_id == selection["persona_id"]}),
            "contexts": [{**context_dto(c), "nickname": _qq_nickname(db, [c])} for c in selected],
            "counts": {"global": len(selected),
                       **{kind: sum(c.scene_kind.value == kind for c in selected)
                          for kind in ("private", "group")}},
        }
    return await store._run(read)


def _relationship_node(db, sources, config=None):
    context = sources[0]
    records = []
    for source in sources:
        row = db.execute(
            "SELECT s.value_json,s.updated_at FROM states s JOIN scopes g "
            "ON s.scope_key=g.scope_key AND s.generation=g.generation "
            "WHERE s.scope_key=? AND s.kind='relationship' AND s.record_key=?",
            (source.scope_key, source.account_id),
        ).fetchone()
        if row:
            records.append(row)
    row = max(records, key=lambda r: r["updated_at"], default=None)
    raw = json.loads(row["value_json"]) if row else {}
    relation = (Relationship(**{key: raw[key] for key in Relationship.__dataclass_fields__
                                if key in raw}) if row else
                initial_relationship())
    override = _override(db, context)
    relation = _apply_override(context, relation, override,
                              applied_version=raw.get("_relationship_override_version", 0))
    stage = relationship_stage_dto(relation.score, config)
    return {
        "id": relationship_account_key(context), "persona_id": context.persona_id,
        "platform": context.platform, "account_id": context.account_id,
        "label": _qq_nickname(db, sources) or context.account_id,
        "raw": relation.score, "score": relation.score / 10,
        "normalized": relation.normalized, **stage,
        **{name: getattr(relation, name) for name in ("trust", "familiarity", "boundary", "frozen")},
        "source_completeness": "complete" if row and relation.evidence_complete else "partial",
        "sources": [{"context_id": c.account_key, "platform": c.platform,
                     "view_scope": c.scene_kind.value, "scene_id": c.scene_id} for c in sources],
        "version": override["version"] if override else 0, "updated_at": relation.updated_at,
        "note": (override or {}).get("note", ""),
    }


async def query_relationships(store, instance_id, selection, *, page=1, page_size=10,
                              query="", limit=200, config=None, graph_scope="matched",
                              extra=(), memory_generation=None):
    if (type(page) is not int or not 1 <= page <= 1000000 or type(page_size) is not int
            or page_size != 10 or type(limit) is not int or not 1 <= limit <= 200
            or not isinstance(query, str) or len(query) > 200
            or graph_scope not in ("matched", "neighbors")):
            raise ValueError("invalid relationship query")
    config = config or getattr(store, "config", None)
    def read(db):
        groups = {}
        contexts = _selected(_contexts(db, instance_id), selection)
        for context in contexts:
            if context.account_id:
                groups.setdefault(relationship_account_key(context), []).append(context)
        nodes = [_relationship_node(db, sources, config) for sources in groups.values()]
        nodes.sort(key=lambda n: (n["updated_at"], n["id"]), reverse=True)
        term = query.strip()
        exact = [n for n in nodes if n["account_id"] == term] if term else []
        matched = exact or [n for n in nodes if term.casefold() in
                           (n["account_id"] + " " + n["label"]).casefold()]
        center = {"id": stable_key(instance_id, selection["persona_id"]),
                  "persona_id": selection["persona_id"]}
        statements = _relationship_statements(db, store, contexts)
        known = {c.account_key: c for c in contexts}
        generation = (db.execute("SELECT generation FROM scopes WHERE scope_key=?",
                                (memory_generation[0],)).fetchone() if memory_generation else None)
        valid = not memory_generation or generation and generation[0] == memory_generation[1]
        statements.extend(s for s in extra if valid and known.get(s.context.account_key) == s.context)
        # Infer before search/cap: a reliable neighbor may be outside the first 200.
        peers = infer_relationships(nodes, statements)
        focus = {n["id"] for n in matched}
        graph = matched
        if graph_scope == "neighbors" and term:
            neighbors = {end for edge in peers if edge["source"] in focus or edge["target"] in focus
                         for end in (edge["source"], edge["target"])} - focus
            graph = [*matched, *(n for n in nodes if n["id"] in neighbors)]
        visible = graph[:limit]
        visible_ids = {n["id"] for n in visible}
        return {"center": center, "nodes": visible,
                "edges": [{"source": center["id"], "target": n["id"], "score": n["score"]}
                          for n in visible],
                "items": matched[(page - 1) * page_size:page * page_size],
                "total": len(matched), "displayed": len(visible), "page": page,
                "page_size": page_size,
                "graph_scope": graph_scope, "focus_ids": list(n["id"] for n in matched) if term else [],
                "graph_total": len(graph), "graph_truncated": len(graph) > limit,
                "peer_edges": [e for e in peers if e["source"] in visible_ids
                               and e["target"] in visible_ids]}
    return await store._run(read)


def _relationship_statements(db, store, contexts):
    """One bounded snapshot: current generations, exact identities and live bodies."""
    known = {c.account_key: c for c in contexts}
    if not known:
        return []
    now = store.clock()
    rows = db.execute(
        "SELECT e.*,w.body FROM body_window w JOIN events e "
        "ON e.seq=w.seq AND e.scope_key=w.scope_key AND e.occurred_at=w.occurred_at "
        "JOIN scopes s ON e.scope_key=s.scope_key AND e.generation=s.generation "
        "WHERE e.scope_key IN (SELECT value FROM json_each(?)) "
        "AND e.actor_role='human' AND e.event_type='message' "
        "AND e.occurred_at>? AND e.occurred_at<=? "
        "ORDER BY e.occurred_at DESC,e.seq DESC LIMIT 400",
        (canonical_json(list({c.scope_key for c in contexts})),
         now - store.config.window_days * 86400, now),
    )
    statements = []
    for row in rows:
        try:
            event = Event.from_dict(json.loads(row["metadata_json"]))
        except (ValueError, TypeError, KeyError):
            continue
        if (known.get(event.context.account_key) != event.context
                or event.actor_role != ActorRole.HUMAN or not event.reliable_source
                or event.actor_id != event.context.account_id
                or event.context.account_id != row["account_id"]
                or event.event_type != "message" or event.idempotency_key != row["event_key"]
                or event.occurred_at != row["occurred_at"]
                or any(ref.kind != ContentKind.INTERACTION or replace(ref.context, route=None) != event.context
                       or ref.occurred_at > now or ref.expires_at is not None and ref.expires_at <= now
                       for ref in event.evidence)):
            continue
        statements.append(RelationshipStatement(
            event.context, event.source_id, "聊天记录", event.occurred_at, row["body"],
            event.actor_id,
        ))
    return statements


async def project_relationship_clues(store, instance_id, selection, nodes, extra=(), *,
                                     memory_generation=None):
    """Re-read records after optional I/O so deletion/denial remains authoritative."""
    def read(db):
        contexts = _selected(_contexts(db, instance_id), selection)
        known = {c.account_key: c for c in contexts}
        current = [n for n in nodes if any(relationship_account_key(c) == n["id"] for c in contexts)]
        current_generation = (db.execute("SELECT generation FROM scopes WHERE scope_key=?",
                                        (memory_generation[0],)).fetchone()
                              if memory_generation else None)
        valid = not memory_generation or current_generation and current_generation[0] == memory_generation[1]
        allowed = [s for s in extra if valid and known.get(s.context.account_key) == s.context]
        return infer_relationships(current, [*_relationship_statements(db, store, contexts), *allowed])
    return await store._run(read)

async def query_console_records(store, instance_id, selection, kind, *,
                                page=1, page_size=10, query=""):
    """Global management reads still filter real provenance and record kind."""
    tables = {"emotion": ("event_traces", "occurred_at", "event_key"),
              "behavior": ("intents", "created_at", "intent_id"),
              "diary": ("experiences", "created_at", "experience_id"),
              "dream": ("experiences", "created_at", "experience_id")}
    if (kind not in tables or type(page) is not int or not 1 <= page <= 1000000
            or type(page_size) is not int or page_size != 10
            or not isinstance(query, str) or len(query) > 200):
        raise ValueError("invalid record query")
    def read(db):
        contexts = _selected(_contexts(db, instance_id), selection)
        scopes = {c.scope_key: c for c in contexts}
        if not scopes:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        table, time_col, id_col = tables[kind]
        # json_each avoids SQLite's host-parameter limit for a global selection.
        filters = ["scope_key IN (SELECT value FROM json_each(?))"]
        args = [canonical_json(list(scopes))]
        if kind != "behavior":
            filters.append("kind=?")
            args.append(kind)
        if kind in ("diary", "dream"):
            from .sqlite import LIVE_EXPERIENCE
            filters.append(LIVE_EXPERIENCE)
            args.extend([store.clock()] * 3)
        if query:
            filters.append("instr(lower(value_json),lower(?))>0")
            args.append(query)
        where = " AND ".join(filters)
        total = db.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", args).fetchone()[0]
        rows = db.execute(f"SELECT * FROM {table} WHERE {where} "
                          f"ORDER BY {time_col} DESC,{id_col} DESC LIMIT ? OFFSET ?",
                          [*args, page_size, (page - 1) * page_size])
        return {"items": [
            {**{key: row[key] for key in row.keys() if key != "value_json"},
             "id": row[id_col], "created_at": row[time_col],
             "context": to_dict(scopes[row["scope_key"]]),
             "value": json.loads(row["value_json"])} for row in rows
        ], "total": total, "page": page, "page_size": page_size}
    return await store._run(read)
