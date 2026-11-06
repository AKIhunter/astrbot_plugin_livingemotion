"""Additive vector tables, exclusively through the host store transaction lock."""

from __future__ import annotations

from ..contracts import canonical_json, stable_key


class VectorStore:
    def __init__(self, store, *, max_records=10000):
        if type(max_records) is not int or not 1 <= max_records <= 10000:
            raise ValueError("vector_record_limit")
        self.store, self.max_records = store, max_records

    async def _run(self, operation):
        return await self.store._run(
            lambda db: self.store._transaction(db, lambda: operation(db))
        )

    async def open(self):
        def create(db):
            db.execute("""CREATE TABLE IF NOT EXISTS le_memory_epochs (
                scope TEXT NOT NULL, source TEXT NOT NULL, epoch INTEGER NOT NULL,
                PRIMARY KEY(scope,source))""")
            db.execute("""CREATE TABLE IF NOT EXISTS le_memory_text (
                key TEXT PRIMARY KEY, scope TEXT NOT NULL, account TEXT NOT NULL,
                source TEXT NOT NULL, generation INTEGER NOT NULL,
                body TEXT NOT NULL, evidence TEXT NOT NULL, occurred REAL NOT NULL,
                expires REAL NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS le_memory_vectors (
                key TEXT NOT NULL REFERENCES le_memory_text(key) ON DELETE CASCADE,
                namespace TEXT NOT NULL, dimension INTEGER NOT NULL, vector TEXT NOT NULL,
                PRIMARY KEY(key,namespace))""")
            db.execute("""CREATE TABLE IF NOT EXISTS le_memory_legacy_hidden (
                scope TEXT NOT NULL, account TEXT NOT NULL, source TEXT NOT NULL,
                PRIMARY KEY(scope,account,source))""")
            db.execute("CREATE INDEX IF NOT EXISTS le_memory_account ON le_memory_text(account)")
            # A host clear physically erases texts in the very same transaction.
            db.execute("""CREATE TRIGGER IF NOT EXISTS le_memory_scope_clear
                AFTER UPDATE OF generation ON scopes WHEN NEW.generation != OLD.generation
                BEGIN DELETE FROM le_memory_text WHERE scope=NEW.scope_key; END""")
        await self._run(create)

    @staticmethod
    def _epochs(db, context, source):
        values = []
        for item in ("", source):
            row = db.execute(
                "SELECT epoch FROM le_memory_epochs WHERE scope=? AND source=?",
                (context.scope_key, item),
            ).fetchone()
            values.append(row[0] if row else 0)
        return tuple(values)

    def _cleanup(self, db):
        db.execute("DELETE FROM le_memory_text WHERE expires<=?", (self.store.clock(),))
        db.execute("""DELETE FROM le_memory_text WHERE NOT EXISTS (
            SELECT 1 FROM scopes s WHERE s.scope_key=le_memory_text.scope
            AND s.generation=le_memory_text.generation)""")

    async def prepare(self, request, material, generation):
        """Capture deletion epochs before any embedding; duplicates do not renew TTL."""
        ref = material.evidence
        key = stable_key(ref.context.account_key, ref.source_id)
        payload = canonical_json(ref)

        def capture(db):
            self._cleanup(db)
            if self.store._generation(db, ref.context) != generation:
                return None, "stale_generation"
            self.store._check_generation(db, ref.context, generation)
            old = db.execute(
                "SELECT body,evidence FROM le_memory_text WHERE key=?", (key,)
            ).fetchone()
            if old and tuple(old) != (material.text, payload):
                return None, "source_conflict"
            return (key, self._epochs(db, ref.context, ref.source_id)), "prepared"
        return await self._run(capture)

    async def put(self, material, generation, lease, namespace, vector, *, commit_guard=None):
        ref = material.evidence
        key, epochs = lease

        def write(db):
            self._cleanup(db)
            if (self.store._generation(db, ref.context) != generation
                    or self._epochs(db, ref.context, ref.source_id) != epochs
                    or ref.expires_at <= self.store.clock()
                    or commit_guard is not None and commit_guard() is not True):
                return "stale_generation"
            self.store._check_generation(db, ref.context, generation)
            payload = canonical_json(ref)
            old = db.execute(
                "SELECT body,evidence FROM le_memory_text WHERE key=?", (key,)
            ).fetchone()
            if old and tuple(old) != (material.text, payload):
                return "source_conflict"
            db.execute("INSERT OR IGNORE INTO le_memory_text VALUES(?,?,?,?,?,?,?,?,?)", (
                key, ref.context.scope_key, ref.context.account_key, ref.source_id,
                generation, material.text, payload, ref.occurred_at, ref.expires_at,
            ))
            db.execute("INSERT OR IGNORE INTO le_memory_vectors VALUES(?,?,?,?)", (
                key, namespace, len(vector), canonical_json(vector),
            ))
            # Keep at most four model indexes per text, without extending text TTL.
            db.execute("""DELETE FROM le_memory_vectors WHERE key=? AND namespace IN (
                SELECT namespace FROM le_memory_vectors WHERE key=? AND namespace!=?
                ORDER BY namespace LIMIT -1 OFFSET 3)""", (key, key, namespace))
            db.execute("""DELETE FROM le_memory_text WHERE key IN (
                SELECT key FROM le_memory_text ORDER BY occurred DESC,key
                LIMIT -1 OFFSET ?)""", (self.max_records,))
            return "stored" if not old else "duplicate"
        return await self._run(write)

    async def rows(self, context, namespace):
        def read(db):
            self._cleanup(db)
            return [dict(row) for row in db.execute(
                """SELECT t.*,v.dimension,v.vector FROM le_memory_text t
                JOIN le_memory_vectors v ON t.key=v.key WHERE t.account=? AND v.namespace=?
                ORDER BY t.occurred DESC,t.key LIMIT ?""",
                (context.account_key, namespace, self.max_records),
            )]
        return await self._run(read)

    async def forget(self, context, source=None):
        def erase(db):
            db.execute("""INSERT INTO le_memory_epochs VALUES(?,?,1)
                ON CONFLICT(scope,source) DO UPDATE SET epoch=epoch+1""",
                (context.scope_key, ""))
            # The old explicit DB stays read-only; this persistent mask prevents revival.
            db.execute("INSERT OR IGNORE INTO le_memory_legacy_hidden VALUES(?,?,?)", (
                context.scope_key, context.account_key if source is not None else "",
                source if source is not None else "",
            ))
            if source is None:
                db.execute("DELETE FROM le_memory_text WHERE scope=?", (context.scope_key,))
            else:
                db.execute("DELETE FROM le_memory_text WHERE account=? AND source=?",
                           (context.account_key, source))
        await self._run(erase)
