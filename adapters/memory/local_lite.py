"""Explicit text records, separate from state and from external memory storage."""

from __future__ import annotations

import asyncio
import json
import math
import sqlite3
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from ...contracts import ContentKind, Context, EvidenceRef, canonical_json, stable_key
from ...ports.memory import (
    AppendResult,
    Material,
    MemoryCapabilities,
    MemoryMode,
    MemoryRequest,
    RecallResult,
)
from .base import material_allowed


class LocalLiteMemory:
    """Small optional fact database; the caller supplies a host data-directory path.

    No automatic extraction, embedding, consolidation or copying of source bodies.
    This database does not share the state store's schema or transactions.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        clock: Callable[[], float] = time.time,
        max_records: int = 1000,
        per_scope: int = 200,
        max_ttl: float = 30 * 86400,
    ):
        if (
            type(max_records) is not int
            or type(per_scope) is not int
            or not 1 <= per_scope <= max_records
            or not math.isfinite(max_ttl)
            or max_ttl <= 0
        ):
            raise ValueError("local_memory_limits_invalid")
        self.path = Path(path)
        self.clock = clock
        self.max_records = max_records
        self.per_scope = per_scope
        self.max_ttl = max_ttl
        self._lock = asyncio.Lock()

    async def _run(self, operation):
        async with self._lock:
            task = asyncio.create_task(asyncio.to_thread(self._sync, operation))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                await task
                raise

    def _sync(self, operation):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path)
        try:
            with db:
                db.execute("""CREATE TABLE IF NOT EXISTS explicit_text (
                    key TEXT PRIMARY KEY, scope TEXT NOT NULL, body TEXT NOT NULL,
                    evidence TEXT NOT NULL, expires REAL NOT NULL, occurred REAL NOT NULL)""")
                db.execute("DELETE FROM explicit_text WHERE expires <= ?", (self.clock(),))
                return operation(db)
        finally:
            db.close()

    def capabilities(self) -> MemoryCapabilities:
        return MemoryCapabilities(MemoryMode.LOCAL_LITE, True, True)

    def cache_token(self):
        return (MemoryMode.LOCAL_LITE, str(self.path))

    async def remember(self, request: MemoryRequest, material: Material) -> AppendResult:
        ref = material.evidence
        if not material_allowed(material, request.context, self.clock()):
            return AppendResult(reason_code="local_source_invalid")
        if (
            ref.provider != "livingemotion"
            or ref.holder_id != request.context.bot_id
            or ref.kind not in {ContentKind.FACT, ContentKind.INTERACTION}
            or ref.expires_at is None
            or not ref.source_ids
            or ref.expires_at - ref.occurred_at > self.max_ttl
        ):
            return AppendResult(reason_code="local_explicit_source_and_expiry_required")
        local = replace(ref, provider="local_lite", exportable=False, authorization=None)
        key = stable_key(local.context.account_key, local.source_id)
        payload = canonical_json(local)

        def put(db):
            old = db.execute(
                "SELECT body,evidence FROM explicit_text WHERE key=?", (key,)
            ).fetchone()
            if old:
                return AppendResult(
                    old == (material.text, payload),
                    "duplicate" if old == (material.text, payload) else "source_conflict",
                )
            db.execute(
                "INSERT INTO explicit_text VALUES(?,?,?,?,?,?)",
                (
                    key,
                    local.context.account_key,
                    material.text,
                    payload,
                    local.expires_at,
                    local.occurred_at,
                ),
            )
            db.execute(
                """DELETE FROM explicit_text WHERE key IN (
                SELECT key FROM explicit_text WHERE scope=? ORDER BY occurred DESC,key
                LIMIT -1 OFFSET ?)""",
                (local.context.account_key, self.per_scope),
            )
            db.execute(
                """DELETE FROM explicit_text WHERE key IN (
                SELECT key FROM explicit_text ORDER BY occurred DESC,key LIMIT -1 OFFSET ?)""",
                (self.max_records,),
            )
            return AppendResult(True, "stored")

        return await self._run(put)

    @staticmethod
    def _decode(body, payload) -> Material:
        value = json.loads(payload)
        value["context"] = Context.from_dict(value["context"])
        value["source_ids"] = tuple(value.get("source_ids", ()))
        return Material(EvidenceRef(**value), body)

    async def fetch(self, request: MemoryRequest, event: object | None) -> RecallResult:
        if not request.query.strip():
            return RecallResult(reason_codes=("local_query_required",))
        rows = await self._run(
            lambda db: db.execute(
                "SELECT body,evidence FROM explicit_text WHERE scope=? ORDER BY occurred DESC,key LIMIT ?",
                (request.context.account_key, self.per_scope),
            ).fetchall()
        )
        terms = request.query.casefold().split()
        candidates = []
        for body, payload in rows:
            material = self._decode(body, payload)
            if material_allowed(material, request.context, self.clock()):
                score = sum(term in body.casefold() for term in terms)
                if score:
                    candidates.append((score, material))
        candidates.sort(key=lambda pair: pair[0], reverse=True)
        return RecallResult(tuple(item for _, item in candidates[: request.limit]))

    async def validate(self, request, materials, event) -> bool:
        for item in materials:
            ref = item.evidence
            if ref.provider != "local_lite" or not material_allowed(
                item, request.context, self.clock()
            ):
                return False
            key = stable_key(ref.context.account_key, ref.source_id)
            row = await self._run(
                lambda db, key=key: db.execute(
                    "SELECT body,evidence FROM explicit_text WHERE key=?",
                    (key,),
                ).fetchone()
            )
            if row is None or self._decode(*row) != item:
                return False
        return True

    async def forget(self, context: Context, source_id: str) -> None:
        key = stable_key(context.account_key, source_id)
        await self._run(lambda db: db.execute("DELETE FROM explicit_text WHERE key=?", (key,)))

    async def append(self, request, material, idempotency_key) -> AppendResult:
        return AppendResult(reason_code="experience_export_unsupported")
