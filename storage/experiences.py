"""Daily private archives and durable single-dispatch identities.

All revision, source-clear, old-body and job checks share the write transaction.
No production bodies or prompt text are stored in task metadata.
"""
from dataclasses import replace
from datetime import date, datetime
import json
from zoneinfo import ZoneInfo

from ..contracts import Context, canonical_json, stable_key, to_dict


def owner_key(instance_id, persona_id):
    return stable_key("experience-persona", instance_id, persona_id)


def entry_day(value, kind, timezone):
    if kind == "diary":
        try:
            return date.fromisoformat(value["period"]).isoformat()
        except (ValueError, KeyError, TypeError):
            return ""
    return datetime.fromtimestamp(value["created_at"], ZoneInfo(timezone)).date().isoformat()


def public_job(row):
    if row is None:
        return None
    return {"api_version": 1, **{key: row[key] for key in (
        "request_id", "persona_id", "kind", "day", "timezone", "status",
        "reason_code", "experience_id", "attempted_at", "finished_at")},
        "entry_revision": row["expected_entry_revision"] + int(row["status"] == "succeeded"),
        "memory_sync": "skipped_private_archive"}


class DailyConflict(ValueError):
    pass


class ExperienceStore:
    async def record_manual_dispatch(self, request_id, context, day, kind):
        """Count a real dispatch in the shared usage pool without quota admission."""
        await self._run(lambda db: db.execute(
            "INSERT INTO quota_reservations(reservation_id,scope_key,generation,period,purpose,"
            "pool,units,status,created_at,reason_code) VALUES(?,?,?,?,?,'model',1,'reserved',?,'manual_dispatch')",
            ("manual:" + request_id, context.scope_key, self._generation(db, context),
             day, kind, self.clock())))

    def _daily_rows(self, db, instance_id, persona_id, kind, day, timezone):
        from .sqlite import LIVE_EXPERIENCE
        rows = db.execute(
            f"SELECT * FROM experiences WHERE kind=? AND "
            f"json_extract(value_json,'$.context.instance_id')=? AND "
            f"json_extract(value_json,'$.context.persona_id')=? AND {LIVE_EXPERIENCE}",
            (kind, instance_id, persona_id, self.clock(), self.clock(), self.clock()))
        return [row for row in rows
                if entry_day(json.loads(row["value_json"]), kind, timezone) == day]

    async def daily_revision(self, owner, kind, day):
        return await self._run(lambda db: (
            dict(row) if (row := db.execute(
                "SELECT * FROM experience_daily WHERE owner_key=? AND kind=? AND day=?",
                (owner, kind, day)).fetchone()) else None))

    async def experience_job(self, request_id, owner):
        return await self._run(lambda db: public_job(db.execute(
            "SELECT * FROM experience_jobs WHERE request_id=? AND owner_key=?",
            (request_id, owner)).fetchone()))

    async def latest_experience_job(self, owner, kind):
        return await self._run(lambda db: public_job(db.execute(
            "SELECT * FROM experience_jobs WHERE owner_key=? AND kind=? "
            "ORDER BY attempted_at DESC,rowid DESC LIMIT 1", (owner, kind)).fetchone()))

    async def accept_experience_job(self, request_id, context, kind, day, timezone,
                                    generations, fingerprint):
        owner = owner_key(context.instance_id, context.persona_id)
        def accept(db):
            def mutate():
                previous = db.execute("SELECT * FROM experience_jobs WHERE request_id=?",
                                      (request_id,)).fetchone()
                if previous:
                    if previous["owner_key"] != owner or previous["kind"] != kind:
                        raise DailyConflict("request_identity_conflict")
                    return public_job(previous), False
                active = db.execute(
                    "SELECT * FROM experience_jobs WHERE owner_key=? AND kind=? AND day=? "
                    "AND status IN ('queued','running')", (owner, kind, day)).fetchone()
                if active:
                    return public_job(active), False
                if db.execute("SELECT COUNT(*) FROM experience_jobs WHERE status='queued'").fetchone()[0] >= 16:
                    raise DailyConflict("queue_full")
                for source, generation in generations:
                    self._check_generation(db, source, generation)
                daily = db.execute(
                    "SELECT * FROM experience_daily WHERE owner_key=? AND kind=? AND day=?",
                    (owner, kind, day)).fetchone()
                revision = daily["revision"] if daily else 0
                old = self._daily_rows(db, context.instance_id, context.persona_id, kind, day, timezone)
                snapshot = {"sources": [(to_dict(c), g) for c, g in generations],
                            "fingerprint": fingerprint,
                            "old": {r["experience_id"]: stable_key(r["value_json"]) for r in old}}
                db.execute(
                    "INSERT INTO experience_jobs VALUES(?,?,?,?,?,?,'queued','queued',?,?,?,NULL,?)",
                    (request_id, owner, context.persona_id, kind, day, timezone,
                     daily["experience_id"] if daily else None, revision, self.clock(),
                     canonical_json(snapshot)))
                return public_job(db.execute("SELECT * FROM experience_jobs WHERE request_id=?",
                                             (request_id,)).fetchone()), True
            return self._transaction(db, mutate)
        return await self._run(accept)

    async def mark_experience_job(self, request_id, status, reason):
        if status not in ("running", "failed", "cancelled", "unknown"):
            raise ValueError("invalid_job_status")
        expected = "('queued')" if status == "running" else "('queued','running')"
        return await self._run(lambda db: db.execute(
            f"UPDATE experience_jobs SET status=?,reason_code=?,finished_at=? "
            f"WHERE request_id=? AND status IN {expected}",
            (status, reason, None if status == "running" else self.clock(), request_id)).rowcount == 1)

    async def recover_experience_jobs(self):
        def recover(db):
            def mutate():
                db.execute("UPDATE experience_jobs SET status='cancelled',reason_code='reload_before_dispatch',"
                           "finished_at=? WHERE status='queued'", (self.clock(),))
                db.execute("UPDATE experience_jobs SET status='unknown',reason_code='reload_after_dispatch',"
                           "finished_at=? WHERE status='running'", (self.clock(),))
            return self._transaction(db, mutate)
        await self._run(recover)

    async def commit_manual_experience(self, request_id, entry):
        def commit(db):
            def mutate():
                job = db.execute("SELECT * FROM experience_jobs WHERE request_id=?",
                                 (request_id,)).fetchone()
                if not job or job["status"] != "running":
                    raise DailyConflict("job_changed")
                snapshot = json.loads(job["generation_snapshot_json"])
                for source, generation in snapshot["sources"]:
                    self._check_generation(db, Context.from_dict(source), generation)
                daily = db.execute(
                    "SELECT * FROM experience_daily WHERE owner_key=? AND kind=? AND day=?",
                    (job["owner_key"], job["kind"], job["day"])).fetchone()
                if (daily["revision"] if daily else 0) != job["expected_entry_revision"]:
                    raise DailyConflict("entry_changed")
                old = self._daily_rows(db, entry.context.instance_id, entry.context.persona_id,
                                       job["kind"], job["day"], job["timezone"])
                if {r["experience_id"]: stable_key(r["value_json"]) for r in old} != snapshot["old"]:
                    raise DailyConflict("entry_changed")
                # Keep a proven original diary ID; otherwise this is a stable daily ID.
                identifier = (daily["experience_id"] if daily and daily["experience_id"] else
                              old[0]["experience_id"] if old and job["kind"] == "diary" else
                              stable_key("daily", job["owner_key"], job["kind"], job["day"]))
                new = replace(entry, experience_id=identifier, pinned=any(r["pinned"] for r in old))
                self._write_daily_body(db, new, job["owner_key"])
                db.execute(
                    "INSERT INTO experience_daily VALUES(?,?,?,?,?,?,'manual',?) "
                    "ON CONFLICT(owner_key,kind,day) DO UPDATE SET experience_id=excluded.experience_id,"
                    "revision=excluded.revision,origin='manual',timezone=excluded.timezone,updated_at=excluded.updated_at",
                    (job["owner_key"], job["kind"], job["day"], job["timezone"], identifier,
                     job["expected_entry_revision"] + 1, self.clock()))
                db.execute("UPDATE experience_jobs SET status='succeeded',reason_code='private_archive_updated',"
                           "experience_id=?,finished_at=? WHERE request_id=?",
                           (identifier, self.clock(), request_id))
                db.execute("INSERT INTO audit(scope_key,generation,action,reason_code,occurred_at,actor_id,value_json)"
                           " VALUES(?,?,?,?,?,'console',?)",
                           (entry.context.scope_key, self._generation(db, entry.context), "experience.generate",
                            "private_archive_updated", self.clock(),
                            canonical_json({"id": identifier, "kind": job["kind"], "day": job["day"],
                                            "revision": job["expected_entry_revision"] + 1})))
                for row in old:
                    if row["experience_id"] != identifier:
                        db.execute("DELETE FROM experiences WHERE experience_id=?", (row["experience_id"],))
                return identifier
            return self._transaction(db, mutate)
        return await self._run(commit)

    def _write_daily_body(self, db, entry, owner):
        body = canonical_json(entry)
        if len(body) > 131072:
            raise DailyConflict("entry_too_large")
        db.execute(
            "INSERT INTO experiences VALUES(?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(experience_id) DO UPDATE SET scope_key=excluded.scope_key,"
            "owner_key=excluded.owner_key,generation=excluded.generation,kind=excluded.kind,"
            "period=excluded.period,created_at=excluded.created_at,expires_at=excluded.expires_at,"
            "pinned=excluded.pinned,value_json=excluded.value_json",
            (entry.experience_id, entry.context.scope_key, owner,
             self._generation(db, entry.context), entry.kind.value, entry.period, entry.created_at,
             entry.expires_at, int(entry.pinned), body))

    async def auto_daily_blocked(self, context, kind, day):
        owner = owner_key(context.instance_id, context.persona_id)
        def read(db):
            return bool(db.execute(
                "SELECT 1 FROM experience_daily WHERE owner_key=? AND kind=? AND day=?",
                (owner, kind, day)).fetchone() or db.execute(
                "SELECT 1 FROM experience_jobs WHERE owner_key=? AND kind=? AND day=? "
                "AND status IN ('queued','running')", (owner, kind, day)).fetchone())
        return await self._run(read)

    async def save_auto_daily(self, entry, generations, *, timezone, day, watermarks=()):
        from .sqlite import _Rejected
        owner = owner_key(entry.context.instance_id, entry.context.persona_id)
        def commit(db):
            def mutate():
                if db.execute("SELECT 1 FROM experience_daily WHERE owner_key=? AND kind=? AND day=?",
                              (owner, entry.kind.value, day)).fetchone() or db.execute(
                        "SELECT 1 FROM experience_jobs WHERE owner_key=? AND kind=? AND day=? "
                        "AND status IN ('queued','running')", (owner, entry.kind.value, day)).fetchone():
                    return {"status": "rejected", "reason_code": "daily_content_preserved"}
                for source, generation in generations:
                    self._check_generation(db, source, generation)
                for source, expected in watermarks:
                    row = db.execute("SELECT human_watermark FROM scopes WHERE scope_key=?",
                                     (source.scope_key,)).fetchone()
                    if (row[0] if row else 0) != expected:
                        raise DailyConflict("new_human_message")
                # Do not delete old automatic history. A same-ID duplicate stays intact.
                previous = db.execute("SELECT 1 FROM experiences WHERE experience_id=?",
                                      (entry.experience_id,)).fetchone()
                if not previous:
                    self._write_daily_body(db, entry, owner)
                db.execute("INSERT INTO experience_daily VALUES(?,?,?,?,?,1,'auto',?)",
                           (owner, entry.kind.value, day, timezone, entry.experience_id, self.clock()))
                return {"status": "duplicate" if previous else "created", "reason_code": "experience_saved"}
            try:
                return self._transaction(db, mutate)
            except (ValueError, _Rejected):
                return {"status": "rejected", "reason_code": "daily_content_preserved"}
        return await self._run(commit)

    async def query_persona_experiences(self, instance_id, persona_id, kind, *, page=1,
                                       page_size=10, query=""):
        if kind not in ("diary", "dream") or type(page) is not int or not 1 <= page <= 1000000 or page_size != 10:
            raise ValueError("invalid_record_query")
        from .sqlite import LIVE_EXPERIENCE
        def read(db):
            where = ("kind=? AND json_extract(value_json,'$.context.instance_id')=? "
                     f"AND json_extract(value_json,'$.context.persona_id')=? AND {LIVE_EXPERIENCE} "
                     "AND instr(lower(value_json),lower(?))>0")
            args = (kind, instance_id, persona_id, self.clock(), self.clock(), self.clock(), query)
            total = db.execute(f"SELECT COUNT(*) FROM experiences WHERE {where}", args).fetchone()[0]
            rows = db.execute(f"SELECT * FROM experiences WHERE {where} "
                              "ORDER BY created_at DESC,experience_id DESC LIMIT 10 OFFSET ?",
                              (*args, (page - 1) * 10))
            items = []
            for row in rows:
                value = json.loads(row["value_json"])
                daily = db.execute("SELECT day FROM experience_daily WHERE experience_id=?",
                                   (row["experience_id"],)).fetchone()
                items.append({"id": row["experience_id"], "created_at": row["created_at"],
                              "value": value, "context": value["context"],
                              "day": daily[0] if daily else "", "status": "recorded"})
            return {"items": items, "total": total, "page": page, "page_size": 10}
        return await self._run(read)

    async def dream_wake_candidates(self, context, now):
        """Body-free list; only saved automatic dreams from a live sleep window."""
        def read(db):
            rows = db.execute(
                """SELECT experience_id,value_json,generation FROM experiences
                   WHERE kind='dream' AND created_at>? AND created_at<=?
                   AND json_extract(value_json,'$.context.instance_id')=?
                   AND json_extract(value_json,'$.context.persona_id')=?
                   AND json_extract(value_json,'$.dream_profile.automatic')=1
                   AND json_extract(value_json,'$.dream_profile.notify_enabled')=1
                   ORDER BY created_at DESC LIMIT 8""",
                (now - 43200, now, context.instance_id, context.persona_id)).fetchall()
            return [{"id": r["experience_id"], "profile": json.loads(r["value_json"])["dream_profile"],
                     "source": json.loads(r["value_json"])["context"], "generation": r["generation"]}
                    for r in rows]
        return await self._run(read)
