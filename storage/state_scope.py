"""State-mode transactions and body-free energy history."""

from dataclasses import fields
import json

from ..contracts import (
    BotAffect, NightState, StateOwner, StateRecord, canonical_json, stable_key, to_dict,
    state_owner_key as owner_key, state_persona_key as persona_key,
)


class OwnedRecords(dict):
    def __init__(self, values, owner):
        super().__init__(values)
        self.owner = owner


class StateScopeStore:
    @staticmethod
    def _source_value(value, context):
        refs = value.get("evidence", [])
        own = [ref for ref in refs if all(
            ref.get("context", {}).get(name) == getattr(context, name) for name in (
                "instance_id", "bot_id", "persona_id", "adapter_id",
                "platform", "scene_kind", "scene_id",
            )
        )]
        if own != refs:
            value["evidence"], value["reason_codes"] = own, []
        return value

    def _state_identity(self, context):
        identity = (context.instance_id, context.persona_id)
        keys = self._state_keys.get(identity)
        if keys is None:
            keys = persona_key(context), owner_key(context, True)
            self._state_keys[identity] = keys
        return keys

    def state_owner(self, context):
        item = self._state_modes.get((context.instance_id, context.persona_id))
        if item is None:
            return None
        mode, revision = item
        person, shared = self._state_identity(context)
        key = shared if mode == "shared" else context.scope_key
        return StateOwner(key, person, mode, revision,
                          self._owner_generations.get(key, 0))

    def _check_owner(self, db, context, owner):
        from .sqlite import _Rejected
        person, shared = self._state_identity(context)
        row = db.execute("SELECT mode,revision FROM state_modes WHERE persona_key=?",
                         (person,)).fetchone()
        if row is None:
            if owner is not None:
                raise _Rejected("stale_state_mode")
            return
        if owner is None:
            raise _Rejected("state_owner_required")
        expected_key = shared if row["mode"] == "shared" else context.scope_key
        generation = db.execute("SELECT generation FROM state_owners WHERE owner_key=?",
                                (expected_key,)).fetchone()
        if (owner.persona_key != person or owner.mode != row["mode"]
                or owner.revision != row["revision"] or owner.owner_key != expected_key):
            raise _Rejected("stale_state_mode")
        if owner.generation != (generation[0] if generation else 0):
            raise _Rejected("stale_owner_generation")

    def _add_state_member(self, db, context):
        key = persona_key(context)
        db.execute("INSERT OR IGNORE INTO state_members VALUES(?,?)", (context.scope_key, key))
        # Initial migration includes all old scenes of the selected instance/persona.
        db.execute(
            """INSERT OR IGNORE INTO state_members
               SELECT scope_key,? FROM scopes
               WHERE json_extract(context_json,'$.instance_id')=?
               AND json_extract(context_json,'$.persona_id')=?""",
            (key, context.instance_id, context.persona_id),
        )

    async def initialize_state_mode(self, context, *, shared=None):
        """Composition-root bootstrap; never silently switches an existing mode."""
        if shared is None:
            shared = self.config.persona_shared_state
        if type(shared) is not bool:
            raise ValueError("invalid shared state setting")
        key = persona_key(context)

        def initialize(db):
            def mutate():
                self._add_state_member(db, context)
                row = db.execute("SELECT mode,revision FROM state_modes WHERE persona_key=?",
                                 (key,)).fetchone()
                if row is None:
                    db.execute("INSERT INTO state_modes VALUES(?,?,?,?,0)",
                               (key, context.instance_id, context.persona_id,
                                "shared" if shared else "scene"))
                    self._seed_owner(db, context, shared, self._now())
                    row = db.execute("SELECT mode,revision FROM state_modes WHERE persona_key=?",
                                     (key,)).fetchone()
                return tuple(row)
            item = self._transaction(db, mutate)
            self._state_modes[(context.instance_id, context.persona_id)] = item
            return self.state_owner(context)
        return await self._run(initialize)

    @staticmethod
    def _night_value(value):
        names = {f.name for f in fields(NightState)}
        return NightState(**{k: v for k, v in value.items() if k in names})

    def _seed_owner(self, db, context, shared, now):
        from ..runtime.state_scope import conservative_night
        key, person = owner_key(context, shared), persona_key(context)
        db.execute("INSERT OR IGNORE INTO state_owners VALUES(?,?,?,0)",
                   (key, person, "shared" if shared else "scene"))
        values = []
        for row in db.execute(
            """SELECT kind,value_json FROM states WHERE scope_key IN (
               SELECT scope_key FROM state_members WHERE persona_key=?)
               AND kind='night' UNION ALL SELECT kind,value_json FROM owner_states
               WHERE owner_key IN (SELECT owner_key FROM state_owners WHERE persona_key=?)
               AND kind='night'""", (person, person),
        ):
            values.append(self._night_value(json.loads(row["value_json"])))
        night = conservative_night(values, now=now)
        table, column = ("owner_states", "owner_key") if shared else ("states", "scope_key")
        target = db.execute(f"SELECT value_json,version FROM {table} WHERE {column}=? "
                            "AND kind='night'", (key,)).fetchone()
        bot = db.execute("SELECT value_json FROM states WHERE scope_key=? AND kind='bot'",
                         (context.scope_key,)).fetchone()
        if bot is None:
            bot = db.execute(
                """SELECT value_json FROM owner_states WHERE kind='bot' AND owner_key IN (
                   SELECT owner_key FROM state_owners WHERE persona_key=?)""", (person,),
            ).fetchone()
        affect = json.loads(bot[0]) if bot else to_dict(BotAffect())
        affect["evidence"], affect["reason_codes"] = [], []
        version = (target["version"] if target else 0) + 1
        if shared:
            db.execute(
                """INSERT INTO owner_states VALUES(?,'night',?,?,?)
                   ON CONFLICT(owner_key,kind) DO UPDATE SET version=excluded.version,
                   updated_at=excluded.updated_at,value_json=excluded.value_json""",
                (key, version, now, canonical_json(night)),
            )
            db.execute("INSERT OR IGNORE INTO owner_states VALUES(?,'bot',1,?,?)",
                       (key, now, canonical_json(affect)))
        else:
            generation = self._generation(db, context)
            db.execute(
                """INSERT INTO states VALUES(?,'night','',?,?,?,?)
                   ON CONFLICT(scope_key,kind,record_key) DO UPDATE SET version=excluded.version,
                   generation=excluded.generation,updated_at=excluded.updated_at,
                   value_json=excluded.value_json""",
                (key, generation, version, now, canonical_json(night)),
            )
            db.execute("INSERT OR IGNORE INTO states VALUES(?,'bot','',?,1,?,?)",
                       (key, generation, now, canonical_json(affect)))
        before = self._night_value(json.loads(target["value_json"])) if target else night
        self._append_energy(db, context, key, stable_key("mode", person, key, now, version), "", before,
                            night, ({"occurred_at": now, "category": "config",
                                     "before_units": int(round(before.energy * 10)),
                                     "after_units": int(round(night.energy * 10)),
                                     "reason_code": "state_mode"},))

    async def switch_state_mode(self, context, *, shared, expected_revision,
                                actor_id, reason="state_mode_changed"):
        from .sqlite import _Rejected
        if type(shared) is not bool or not actor_id or not reason.strip():
            raise ValueError("invalid state switch")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("invalid mode revision")
        now, key = self._now(), persona_key(context)

        def switch(db):
            def mutate():
                self._add_state_member(db, context)
                row = db.execute("SELECT mode,revision FROM state_modes WHERE persona_key=?",
                                 (key,)).fetchone()
                if row is None or row["revision"] != expected_revision:
                    raise _Rejected("state_revision_conflict")
                mode = "shared" if shared else "scene"
                if row["mode"] == mode:
                    return {"status": "accepted", "reason_code": "state_mode_unchanged",
                            "revision": expected_revision}
                self._seed_owner(db, context, shared, now)
                revision = expected_revision + 1
                db.execute("UPDATE state_modes SET mode=?,revision=? WHERE persona_key=?",
                           (mode, revision, key))
                # Preserve quotas and unknown-send blockers, cancelling only work
                # which has not reached submission.
                db.execute(
                    """UPDATE intents SET status=CASE WHEN status='sending' THEN 'unknown'
                       WHEN status IN ('pending','reserved','generating') THEN 'cancelled'
                       ELSE status END,reason_code='state_mode_changed',updated_at=?
                       WHERE scope_key IN (SELECT scope_key FROM state_members WHERE persona_key=?)""",
                    (now, key),
                )
                db.execute(
                    """UPDATE reply_attempts SET status='cancelled' WHERE status='started'
                       AND source_scope_key IN (
                         SELECT scope_key FROM state_members WHERE persona_key=?)""", (key,),
                )
                db.execute(
                    """INSERT INTO audit(scope_key,generation,action,reason_code,occurred_at,
                       actor_id,value_json) VALUES(?,?,'state.mode',?,?,?,?)""",
                    (context.scope_key, self._generation(db, context), reason, now, actor_id,
                     canonical_json({"mode": mode, "revision": revision})),
                )
                return {"status": "accepted", "reason_code": "state_mode_changed",
                        "revision": revision}
            try:
                result = self._transaction(db, mutate)
                if result["status"] == "accepted":
                    self._state_modes[(context.instance_id, context.persona_id)] = (
                        "shared" if shared else "scene", result["revision"],
                    )
                return result
            except _Rejected as exc:
                return {"status": "rejected", "reason_code": exc.reason}
        return await self._run(switch)

    def _owned_record(self, db, context, kind, owner):
        if owner.mode == "shared" and kind in ("bot", "night"):
            row = db.execute("SELECT * FROM owner_states WHERE owner_key=? AND kind=?",
                             (owner.owner_key, kind)).fetchone()
            if row is None:
                return None
            value = json.loads(row["value_json"])
            if kind == "bot":
                value = self._source_value(value, context)
            return StateRecord(kind, value, row["version"],
                               self._generation(db, context), row["updated_at"], "", owner)
        record_key = context.account_id if kind in ("relationship", "observation") else ""
        row = db.execute("SELECT * FROM states WHERE scope_key=? AND kind=? AND record_key=?",
                         (context.scope_key, kind, record_key)).fetchone()
        return StateRecord(kind, json.loads(row["value_json"]), row["version"], row["generation"],
                           row["updated_at"], record_key, owner) if row else None

    async def _read_owned_projection(self, context, owner):
        return await self._run(lambda db: self._owned_projection_snapshot(db, context, owner))

    def _owned_projection_snapshot(self, db, context, owner):
        from .sqlite import _Rejected
        rows = db.execute(
                """WITH requested(kind,record_key) AS (
                       VALUES ('bot',''),('night',''),('relationship',?),('observation',?)
                   ), current AS (
                       SELECT COALESCE((SELECT generation FROM scopes WHERE scope_key=?),0)
                           AS generation
                   )
                   SELECT r.kind,r.record_key,g.generation,m.mode,m.revision,
                       COALESCE(own.generation,0) AS owner_generation,
                       CASE WHEN ?='shared' AND r.kind IN ('bot','night')
                            THEN o.version ELSE s.version END AS version,
                       CASE WHEN ?='shared' AND r.kind IN ('bot','night')
                            THEN o.updated_at ELSE s.updated_at END AS updated_at,
                       CASE WHEN ?='shared' AND r.kind IN ('bot','night')
                            THEN o.value_json ELSE s.value_json END AS value_json
                   FROM requested r CROSS JOIN current g
                   LEFT JOIN state_modes m ON m.persona_key=?
                   LEFT JOIN state_owners own ON own.owner_key=?
                   LEFT JOIN owner_states o ON o.owner_key=? AND o.kind=r.kind
                   LEFT JOIN states s ON s.scope_key=? AND s.kind=r.kind
                       AND s.record_key=r.record_key AND s.generation=g.generation
                   WHERE r.kind IN ('bot','night') OR r.record_key<>''""",
                (context.account_id, context.account_id, context.scope_key,
                 owner.mode, owner.mode, owner.mode, self._state_identity(context)[0],
                 owner.owner_key, owner.owner_key, context.scope_key),
        ).fetchall()
        current = rows[0]
        if current["mode"] != owner.mode or current["revision"] != owner.revision:
            raise _Rejected("stale_state_mode")
        if current["owner_generation"] != owner.generation:
            raise _Rejected("stale_owner_generation")
        records = {}
        for row in rows:
            value = json.loads(row["value_json"]) if row["version"] is not None else None
            if owner.mode == "shared" and row["kind"] == "bot" and value is not None:
                value = self._source_value(value, context)
            records[row["kind"]] = StateRecord(
                row["kind"], value, row["version"], row["generation"],
                row["updated_at"], row["record_key"], owner,
            ) if value is not None else None
        return current["generation"], OwnedRecords(records, owner)

    def _write_owned(self, db, context, generation, writes, now, encoded=None):
        from .sqlite import _Rejected, _state_json
        versions = {}
        checked = set()
        for write in writes:
            if write.owner not in checked:
                self._check_owner(db, context, write.owner)
                checked.add(write.owner)
            if write.kind not in ("bot", "night") or write.owner.mode == "scene":
                versions.update(self._write_scene_states(
                    db, context, generation, (write,), now, encoded,
                ))
                continue
            if write.record_key or type(write.expected_version) is not int:
                raise ValueError("invalid owner state write")
            row = db.execute("SELECT version,value_json FROM owner_states "
                             "WHERE owner_key=? AND kind=?",
                             (write.owner.owner_key, write.kind)).fetchone()
            if (row["version"] if row else 0) != write.expected_version:
                raise _Rejected("version_conflict")
            payload = encoded[id(write.value)] if encoded is not None else _state_json(write.value)
            if len(payload) > 65536:
                raise ValueError("state payload too large")
            version = write.expected_version + 1
            db.execute(
                """INSERT INTO owner_states VALUES(?,?,?,?,?)
                   ON CONFLICT(owner_key,kind) DO UPDATE SET version=excluded.version,
                   updated_at=excluded.updated_at,value_json=excluded.value_json""",
                (write.owner.owner_key, write.kind, version, now, payload),
            )
            versions[f"{write.kind}:"] = version
            if write.kind == "bot":
                self._append_emotion(db, write.owner.owner_key, write.owner.generation, now, write.value)
            if write.kind == "night" and (
                write.energy_events or row is None or row["value_json"] != payload
            ):
                before = self._night_value(json.loads(row["value_json"])) if row else (
                    NightState(updated_at=now)
                )
                after = self._night_value(write.value)
                self._append_energy(db, context, write.owner.owner_key,
                                    stable_key("state", write.owner, version), "", before, after,
                                    write.energy_events)
        return versions

    def _append_emotion(self, db, key, generation, now, value):
        import math
        dims = [value.get(k) for k in ("pleasure", "arousal", "stress", "social_need")]
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in dims):
            return
        db.execute("INSERT OR REPLACE INTO emotion_samples VALUES(?,?,?,?,?,?,?)",
                   (key, generation, now, *dims))
        db.execute("DELETE FROM emotion_samples WHERE at<?", (now - 172800,))

    async def emotion_history(self, context, *, since, until):
        """Reconstruct 5 minute values from recorded state and its known decay."""
        from ..domain.emotion import decay_affect
        from ..domain.dreaming import six_emotions
        owner = self.state_owner(context)
        key = owner.owner_key if owner else context.scope_key
        generation = owner.generation if owner and owner.mode == "shared" else await self.get_generation(context)
        def read(db):
            self._check_owner(db, context, owner)
            rows = db.execute(
                """SELECT * FROM emotion_samples WHERE owner_key=? AND generation=? AND at<=?
                   AND (at>=? OR at=(SELECT MAX(at) FROM emotion_samples
                       WHERE owner_key=? AND generation=? AND at<?)) ORDER BY at""",
                (key, generation, until, since, key, generation, since)).fetchall()
            points, index, current = [], 0, None
            # Right edge is a completed 5-minute slot; exactly 288 slots for 24h.
            end = int(until // 300) * 300
            for at in range(end - 86100, end + 1, 300):
                if at < since:
                    continue
                while index < len(rows) and rows[index]["at"] <= at:
                    current = rows[index]; index += 1
                emotions = None
                if current is not None:
                    affect = BotAffect(**{k: current[k] for k in
                        ("pleasure", "arousal", "stress", "social_need")}, updated_at=current["at"])
                    emotions = six_emotions(decay_affect(affect, now=at))
                points.append({"at": at, "emotions": emotions,
                               "basis": "recorded_decay" if current is not None else "uncollected"})
            return points
        return await self._run(read)

    def _append_energy(self, db, context, key, event_id, source_id, before, after, changes):
        if not changes and (before.energy != after.energy or before.phase != after.phase
                            or before.display_state != after.display_state):
            changes = ({"occurred_at": after.updated_at, "category": "manual",
                        "before_units": int(round(before.energy * 10)),
                        "after_units": int(round(after.energy * 10)),
                        "reason_code": after.reason_codes[0] if after.reason_codes else "state"},)
        for index, change in enumerate(changes):
            left, right = change["before_units"], change["after_units"]
            if (type(left) is not int or type(right) is not int
                    or not 0 <= left <= 1000 or not 0 <= right <= 1000):
                raise ValueError("invalid energy delta")
            category = change["category"]
            if category not in ("reply", "fatigue", "recovery", "sleep", "wake", "manual", "config"):
                raise ValueError("invalid energy category")
            db.execute(
                """INSERT INTO energy_events VALUES(NULL,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (stable_key(event_id, index), change["occurred_at"], key, context.scope_key,
                 change.get("source_id", source_id), category, left, right, right - left,
                 (before.display_state or before.phase).value,
                 (after.display_state or after.phase).value, change["reason_code"]),
            )
        if changes:
            # This bounded delete is normally a no-op; maintenance handles time TTL.
            db.execute("DELETE FROM energy_events WHERE seq<=("
                       "SELECT seq FROM energy_events ORDER BY seq DESC LIMIT 1 OFFSET 20000)")

    async def energy_history(self, context=None, *, owner=None, since=None, until=None,
                             category=None, page=1, page_size=10, buckets=1440):
        """Authenticated callers may supply an owner; source callers use Context."""
        if context is None and owner is None:
            raise ValueError("energy owner required")
        if (type(page) is not int or not 1 <= page <= 100000 or page_size != 10
                or type(buckets) is not int or not 1 <= buckets <= 1440):
            raise ValueError("invalid energy query")
        now = self._now()
        since = max(now - 7 * 86400, now - 86400 if since is None else since)
        until = now if until is None else until
        if not since < until <= now:
            raise ValueError("invalid energy time range")
        owner = owner or self.state_owner(context)
        key = owner.owner_key if owner else context.scope_key
        if category is not None and category not in (
            "reply", "fatigue", "recovery", "sleep", "wake", "manual", "config",
        ):
            raise ValueError("invalid energy category")

        def read(db):
            args = [key, since, until]
            where = "owner_key=? AND occurred_at>=? AND occurred_at<=?"
            if category:
                where += " AND category=?"
                args.append(category)
            rows = [dict(row) for row in db.execute(
                f"SELECT * FROM energy_events WHERE {where} ORDER BY occurred_at,seq", args)]
            curve = {}
            for row in rows:
                row.update(before=row["before_units"] / 10, after=row["after_units"] / 10,
                           delta=row["delta_units"] / 10)
                index = min(buckets - 1, int((row["occurred_at"] - since) * buckets
                                            / (until - since)))
                point = curve.setdefault(index, {
                    "occurred_at": row["occurred_at"], "first": row["before"],
                    "last": row["after"], "min": row["before"], "max": row["before"],
                })
                point["last"] = row["after"]
                point["min"] = min(point["min"], row["before"], row["after"])
                point["max"] = max(point["max"], row["before"], row["after"])
            offset = (page - 1) * page_size
            return {"items": list(reversed(rows))[offset:offset + page_size],
                    "curve": list(curve.values()), "total": len(rows), "page": page,
                    "page_size": page_size, "collected": bool(rows), "since": since,
                    "until": until, "owner_key": key}
        return await self._run(read)
