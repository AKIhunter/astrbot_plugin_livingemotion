"""Read-only v1 explicit records; never migrate, embed, or clean the old database."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from ...contracts import ContentKind, stable_key
from .base import material_allowed
from .local_lite import LocalLiteMemory


class LegacyExplicitReader:
    def __init__(self, path, *, clock, limit=200):
        self.path, self.clock, self.limit = Path(path), clock, limit

    def cache_token(self):
        try:
            stat = self.path.stat()
            return (str(self.path), stat.st_mtime_ns, stat.st_size)
        except OSError:
            return (str(self.path), None)

    def available(self):
        return self.path.is_file()

    def _rows(self, context, source=None):
        if not self.available():
            return ()
        # mode=ro also rejects accidental CREATE/cleanup and does not create a missing DB.
        with closing(sqlite3.connect(
            self.path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.1,
        )) as db:
            db.row_factory = sqlite3.Row
            if source is not None:
                return db.execute(
                    "SELECT * FROM explicit_text WHERE scope=? AND key=?",
                    (context.account_key, stable_key(context.account_key, source)),
                ).fetchall()
            return db.execute(
                """SELECT * FROM explicit_text WHERE scope=? AND expires>?
                ORDER BY occurred DESC,key LIMIT ?""",
                (context.account_key, self.clock(), self.limit),
            ).fetchall()

    def _decode(self, row, context):
        try:
            material = LocalLiteMemory._decode(row["body"], row["evidence"])
            ref = material.evidence
            if (row["key"] != stable_key(context.account_key, ref.source_id)
                    or row["scope"] != context.account_key
                    or row["expires"] != ref.expires_at or row["occurred"] != ref.occurred_at
                    or ref.provider != "local_lite" or ref.holder_id != context.bot_id
                    or ref.kind not in (ContentKind.FACT, ContentKind.INTERACTION)
                    or not ref.source_ids or ref.expires_at is None
                    or ref.exportable or ref.authorization is not None
                    or not material_allowed(material, context, self.clock())):
                return None
            return material
        except (ValueError, TypeError, KeyError):
            return None

    @staticmethod
    def _visible(db, data, context, source):
        # A source clear predating the upgrade also denies all v1 bodies in that scope.
        if data.store._generation(db, context) != 0:
            return False
        return db.execute(
            """SELECT 1 FROM le_memory_legacy_hidden WHERE scope=?
            AND ((account='' AND source='') OR (account=? AND source=?))""",
            (context.scope_key, context.account_key, source),
        ).fetchone() is None

    def fetch(self, db, data, request):
        terms = request.query.casefold().split()
        candidates = []
        for row in self._rows(request.context):
            material = self._decode(row, request.context)
            if material is None or not self._visible(
                db, data, request.context, material.evidence.source_id,
            ):
                continue
            score = sum(term in material.text.casefold() for term in terms)
            if score:
                candidates.append((score, material))
        candidates.sort(key=lambda pair: -pair[0])
        return tuple(item for _, item in candidates[:request.limit])

    def validate(self, db, data, request, material):
        source = material.evidence.source_id
        if not self._visible(db, data, request.context, source):
            return False
        return any(self._decode(row, request.context) == material
                   for row in self._rows(request.context, source))
