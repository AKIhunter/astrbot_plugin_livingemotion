"""Source-scoped unread archive, separate from the short prompt window.

The archive never uses a persona state owner as its source key. Every write
checks the original scope generation, including late summary completions.
"""

from __future__ import annotations

import json

from ..contracts import Context, Event, canonical_json, stable_key, to_dict


class CatchupArchive:
    def __init__(self, store):
        self.store = store

    async def open(self):
        statements = (
            """CREATE TABLE IF NOT EXISTS catchup_messages(
               seq INTEGER PRIMARY KEY AUTOINCREMENT,event_key TEXT UNIQUE NOT NULL,
               scope_key TEXT NOT NULL,generation INTEGER NOT NULL,source_id TEXT NOT NULL,
               occurred_at REAL NOT NULL,body TEXT NOT NULL,metadata_json TEXT NOT NULL,
               handled INTEGER NOT NULL DEFAULT 0)""",
            """CREATE INDEX IF NOT EXISTS catchup_pending
               ON catchup_messages(scope_key,generation,handled,seq)""",
            """CREATE TABLE IF NOT EXISTS catchup_batches(
               batch_id TEXT PRIMARY KEY,scope_key TEXT NOT NULL,generation INTEGER NOT NULL,
               upper_seq INTEGER NOT NULL,wake_key TEXT NOT NULL,status TEXT NOT NULL,
               revision TEXT NOT NULL,value_json TEXT NOT NULL,updated_at REAL NOT NULL)""",
            """CREATE INDEX IF NOT EXISTS catchup_batch_scope
               ON catchup_batches(scope_key,generation,updated_at)""",
            """CREATE TABLE IF NOT EXISTS catchup_chunks(
               chunk_id TEXT PRIMARY KEY,batch_id TEXT NOT NULL,first_seq INTEGER NOT NULL,
               last_seq INTEGER NOT NULL,source_hash TEXT NOT NULL,value_json TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS catchup_reply_attempts(
               scope_key TEXT NOT NULL,generation INTEGER NOT NULL,wake_key TEXT NOT NULL,
               attempt INTEGER NOT NULL,reply_key TEXT NOT NULL,
               PRIMARY KEY(scope_key,generation,wake_key,attempt))""",
        )

        def create(db):
            def operation():
                for statement in statements:
                    db.execute(statement)
            return self.store._transaction(db, operation)
        await self.store._run(create)

    async def append(self, event: Event, generation: int):
        def write(db):
            def operation():
                self.store._check_generation(db, event.context, generation)
                db.execute(
                    """INSERT OR IGNORE INTO catchup_messages
                       (event_key,scope_key,generation,source_id,occurred_at,body,metadata_json)
                       VALUES(?,?,?,?,?,?,?)""",
                    (event.idempotency_key, event.context.scope_key, generation, event.source_id,
                     event.occurred_at, event.body,
                     canonical_json({**to_dict(event), "body": ""})),
                )
                cutoff = self.store.clock() - self.store.config.window_days * 86400
                db.execute("DELETE FROM catchup_messages WHERE occurred_at<=?", (cutoff,))
                db.execute(
                    """DELETE FROM catchup_messages WHERE seq IN
                       (SELECT seq FROM catchup_messages ORDER BY seq DESC LIMIT -1 OFFSET ?)""",
                    (self.store.config.window_global,),
                )
            return self.store._transaction(db, operation)
        return await self.store._run(write)

    async def mark_consumed(self, context, generation, source_id):
        """A correlated native result consumes only its original source."""
        def write(db):
            def operation():
                self.store._check_generation(db, context, generation)
                return db.execute(
                    """UPDATE catchup_messages SET handled=1 WHERE scope_key=?
                       AND generation=? AND source_id=?""",
                    (context.scope_key, generation, source_id),
                ).rowcount
            return self.store._transaction(db, operation)
        return await self.store._run(write)

    async def reserve_reply(self, context, generation, wake_key, reply_key, limit):
        """Charge actual generation attempts across batches and restarts."""
        def write(db):
            def operation():
                self.store._check_generation(db, context, generation)
                count = db.execute(
                    """SELECT COUNT(*) FROM catchup_reply_attempts
                       WHERE scope_key=? AND generation=? AND wake_key=?""",
                    (context.scope_key, generation, wake_key),
                ).fetchone()[0]
                if count >= limit:
                    return None
                attempt = count + 1
                db.execute(
                    "INSERT INTO catchup_reply_attempts VALUES(?,?,?,?,?)",
                    (context.scope_key, generation, wake_key, attempt, reply_key),
                )
                return stable_key(reply_key, wake_key, attempt)
            return self.store._transaction(db, operation)
        return await self.store._run(write)

    async def begin(self, context, generation, *, exclude_source_id, wake_key, revision):
        now = self.store.clock()

        def begin(db):
            def operation():
                self.store._check_generation(db, context, generation)
                old = db.execute(
                    """SELECT * FROM catchup_batches WHERE scope_key=? AND generation=?
                       AND status NOT IN ('done','limited') ORDER BY updated_at LIMIT 1""",
                    (context.scope_key, generation),
                ).fetchone()
                if old:
                    # A later wake or revision never replaces an unfinished upper bound.
                    return self._batch(old)
                trigger = db.execute(
                    """SELECT MIN(seq) FROM catchup_messages WHERE scope_key=?
                       AND generation=? AND source_id=?""",
                    (context.scope_key, generation, exclude_source_id),
                ).fetchone()[0] if exclude_source_id else None
                upper = trigger - 1 if trigger else db.execute(
                    """SELECT COALESCE(MAX(seq),0) FROM catchup_messages
                       WHERE scope_key=? AND generation=?""",
                    (context.scope_key, generation),
                ).fetchone()[0]
                batch_id = stable_key("full-catchup-v2", context.scope_key, generation, upper)
                row = {
                    "batch_id": batch_id, "scope_key": context.scope_key,
                    "generation": generation, "upper_seq": upper, "wake_key": wake_key,
                    "status": "reading", "revision": revision,
                    "value": {"summaries": [], "replies": [], "read_seqs": []},
                    "updated_at": now,
                }
                db.execute(
                    """INSERT OR IGNORE INTO catchup_batches VALUES(?,?,?,?,?,?,?,?,?)""",
                    (batch_id, context.scope_key, generation, upper, wake_key, "reading", revision,
                     canonical_json(row["value"]), now),
                )
                actual = db.execute(
                    "SELECT * FROM catchup_batches WHERE batch_id=?", (batch_id,),
                ).fetchone()
                if actual["status"] == "limited" and actual["wake_key"] != wake_key:
                    db.execute(
                        """UPDATE catchup_batches SET status='reading',wake_key=?
                           WHERE batch_id=?""", (wake_key, batch_id),
                    )
                    actual = db.execute(
                        "SELECT * FROM catchup_batches WHERE batch_id=?", (batch_id,),
                    ).fetchone()
                return self._batch(actual)
            return self.store._transaction(db, operation)
        return await self.store._run(begin)

    @staticmethod
    def _batch(row):
        value = dict(row)
        value["value"] = json.loads(value.pop("value_json"))
        return value

    async def rows(self, context, batch, *, after=0, limit=80):
        def read(db):
            self.store._check_generation(db, context, batch["generation"])
            rows = db.execute(
                """SELECT * FROM catchup_messages WHERE scope_key=? AND generation=?
                   AND seq>? AND seq<=? AND handled=0 ORDER BY seq LIMIT ?""",
                (context.scope_key, batch["generation"], after, batch["upper_seq"], limit),
            )
            return [{**dict(row), "metadata_json": json.loads(row["metadata_json"])}
                    for row in rows]
        return await self.store._run(read)

    async def chunk(self, chunk_id):
        def read(db):
            row = db.execute(
                "SELECT value_json FROM catchup_chunks WHERE chunk_id=?", (chunk_id,),
            ).fetchone()
            return json.loads(row[0]) if row else None
        return await self.store._run(read)

    async def save_chunk(self, context, batch, rows, value):
        fingerprint = stable_key(tuple((row["seq"], row["event_key"], row["body"]) for row in rows))
        chunk_id = stable_key(batch["batch_id"], fingerprint)

        def write(db):
            def operation():
                self.store._check_generation(db, context, batch["generation"])
                for row in rows:
                    actual = db.execute(
                        "SELECT event_key,body FROM catchup_messages WHERE seq=? AND scope_key=?",
                        (row["seq"], context.scope_key),
                    ).fetchone()
                    if not actual or tuple(actual) != (row["event_key"], row["body"]):
                        raise ValueError("catchup_source_changed")
                db.execute(
                    "INSERT OR IGNORE INTO catchup_chunks VALUES(?,?,?,?,?,?)",
                    (chunk_id, batch["batch_id"], rows[0]["seq"], rows[-1]["seq"],
                     fingerprint, canonical_json(value)),
                )
            return self.store._transaction(db, operation)
        await self.store._run(write)
        return chunk_id

    async def save_batch(self, context: Context, batch, *, handled=()):
        def write(db):
            def operation():
                self.store._check_generation(db, context, batch["generation"])
                old = db.execute(
                    "SELECT status FROM catchup_batches WHERE batch_id=?", (batch["batch_id"],),
                ).fetchone()
                if not old or old[0] in ("sending", "unknown"):
                    # Only the explicit send settlement may clear the sending marker.
                    if batch["status"] not in ("sending", "unknown", "submitted"):
                        raise ValueError("catchup_send_result_unknown")
                db.execute(
                    """UPDATE catchup_batches SET status=?,revision=?,value_json=?,updated_at=?
                       WHERE batch_id=?""",
                    (batch["status"], batch["revision"], canonical_json(batch["value"]), self.store.clock(),
                     batch["batch_id"]),
                )
                db.executemany(
                    """UPDATE catchup_messages SET handled=1
                       WHERE seq=? AND scope_key=? AND generation=? AND seq<=?""",
                    [(seq, context.scope_key, batch["generation"], batch["upper_seq"])
                     for seq in handled],
                )
            return self.store._transaction(db, operation)
        return await self.store._run(write)
