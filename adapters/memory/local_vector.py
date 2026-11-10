"""Source-isolated local cosine recall and generation-guarded asynchronous writes."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace

from ...contracts import ContentKind, Context, EvidenceRef, finite
from ...ports.memory import (
    AppendResult,
    Material,
    MemoryCapabilities,
    MemoryMode,
    RecallResult,
    ValidationResult,
)
from ...storage.vector import VectorStore
from ..embedding import checked_vector
from .base import material_allowed
from .legacy import LegacyExplicitReader


class LocalVectorMemory:
    def __init__(self, store, embedding, *, read_enabled=True, write_enabled=False,
                 max_records=10000, retention_days=30, timeout=2.0, guard=None,
                 legacy_path=None):
        if type(retention_days) is not int or not 1 <= retention_days <= 30:
            raise ValueError("vector_retention_invalid")
        finite(timeout, "vector_timeout", 0.001, 60)
        self.store, self.embedding = store, embedding
        self.data = VectorStore(store, max_records=max_records)
        self.read_enabled, self.write_enabled = read_enabled, write_enabled
        self.retention_days, self.timeout, self.guard = retention_days, timeout, guard
        self.legacy = (LegacyExplicitReader(legacy_path, clock=store.clock)
                       if legacy_path is not None else None)
        self._closed = False
        self._revision = 0
        self._writes = set()

    async def open(self):
        await self.data.open()

    def cache_token(self):
        return ("local_vector", self._revision, self.read_enabled, self.write_enabled,
                self._closed, self.legacy.cache_token() if self.legacy else None)

    def capabilities(self):
        legacy = self.legacy is not None and self.legacy.available()
        ready = not self._closed and (self.embedding is not None or legacy)
        return MemoryCapabilities(
            MemoryMode.LOCAL_VECTOR, ready and self.read_enabled, ready and self.read_enabled,
            reason_codes=(("embedding_not_configured",) if self.embedding is None else ())
            + (("legacy_explicit_text_readonly",) if legacy else ()),
        )

    async def _current(self, context, generation):
        return (not self._closed
                and await self.store.get_generation(context) == generation
                and (self.guard is None or await self.guard(context, generation) is True))

    async def prepare(self, request, material, *, generation=None):
        ref = material.evidence
        if (not self.write_enabled or self._closed or self.embedding is None
                or not material_allowed(material, request.context, self.store.clock())
                or ref.provider != "livingemotion" or ref.holder_id != request.context.bot_id
                or not ref.source_ids or ref.expires_at is None
                or ref.expires_at - ref.occurred_at > self.retention_days * 86400):
            return None, "local_source_invalid_or_write_disabled"
        if generation is None:
            generation = await self.store.get_generation(request.context)
        if not await self._current(request.context, generation):
            return None, "context_changed"
        local = Material(replace(ref, provider="local_vector", exportable=False,
                                 authorization=None), material.text)
        lease, reason = await self.data.prepare(request, local, generation)
        return ((local, generation, lease) if lease else None), reason

    async def remember(self, request, material, *, generation=None, prepared=None,
                       commit_guard=None):
        if prepared is None:
            prepared, reason = await self.prepare(request, material, generation=generation)
            if prepared is None:
                return AppendResult(reason_code=reason)
        local, generation, lease = prepared
        task = asyncio.current_task()
        self._writes.add(task)
        try:
            if not self.write_enabled or not await self._current(request.context, generation):
                return AppendResult(reason_code="context_changed")
            binding = await self.embedding.binding()
            vector = checked_vector(await binding.embed(local.text), binding.dimension)
            current = await self.embedding.binding()
            if (current.fingerprint != binding.fingerprint or not self.write_enabled
                    or not await self._current(request.context, generation)):
                return AppendResult(reason_code="context_or_embedding_changed")
            reason = await self.data.put(
                local, generation, lease, binding.namespace_for(len(vector)), vector,
                commit_guard=lambda: (not self._closed and self.write_enabled
                                      and (commit_guard is None or commit_guard() is True)),
            )
            self._revision += 1
            return AppendResult(reason in ("stored", "duplicate"), reason)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - optional embedding/storage errors fail closed.
            return AppendResult(reason_code="embedding_unavailable")
        finally:
            self._writes.discard(task)

    @staticmethod
    def _decode(row):
        ref = json.loads(row["evidence"])
        ref["context"] = Context.from_dict(ref["context"])
        ref["source_ids"] = tuple(ref.get("source_ids", ()))
        return Material(EvidenceRef(**ref), row["body"])

    async def _fetch(self, request):
        generation = await self.store.get_generation(request.context)
        if not await self._current(request.context, generation):
            return RecallResult(reason_codes=("context_changed",))
        binding = await self.embedding.binding()
        query = checked_vector(await binding.embed(request.query), binding.dimension)
        rows = await self.data.rows(request.context, binding.namespace_for(len(query)))
        candidates = []
        for row in rows:
            try:
                material = self._decode(row)
                vector = checked_vector(json.loads(row["vector"]), len(query))
                if (row["dimension"] != len(query) or row["generation"] != generation
                        or not material_allowed(material, request.context, self.store.clock())):
                    continue
                score = sum(a * b for a, b in zip(query, vector))
                if score > 0:
                    candidates.append((score, row["key"], material))
            except (ValueError, TypeError, KeyError):
                continue
        current = await self.embedding.binding()
        if (current.fingerprint != binding.fingerprint
                or not await self._current(request.context, generation)):
            return RecallResult(reason_codes=("context_or_embedding_changed",))
        candidates.sort(key=lambda item: (-item[0], item[1]))
        return RecallResult(tuple(item[2] for item in candidates[:request.limit]))

    async def fetch(self, request, event=None):
        if self._closed or not self.read_enabled:
            return RecallResult(reason_codes=("local_read_disabled",))
        if not request.query.strip():
            return RecallResult(reason_codes=("local_query_required",))
        legacy, reasons = (), ()
        if self.legacy is not None:
            try:
                generation = await self.store.get_generation(request.context)
                if not await self._current(request.context, generation):
                    return RecallResult(reason_codes=("context_changed",))
                legacy = await self.data._run(
                    lambda db: self.legacy.fetch(db, self.data, request)
                    if (not self._closed and self.read_enabled
                        and self.store._generation(db, request.context) == generation) else (),
                )
            except Exception:  # noqa: BLE001 - corrupt or unavailable v1 DB is optional.
                reasons = ("legacy_explicit_text_unavailable",)
        if self.embedding is None:
            return RecallResult(legacy, reasons + ("embedding_not_configured",))
        try:
            result = await asyncio.wait_for(self._fetch(request), self.timeout)
        except TimeoutError:
            result = RecallResult(reason_codes=("local_recall_timeout",))
        except Exception:  # noqa: BLE001 - recall must not break native chat.
            result = RecallResult(reason_codes=("embedding_unavailable",))
        # Lexical v1 scores are not cosine scores. Preserve explicit matches first.
        seen = {item.evidence.source_id for item in legacy}
        materials = legacy + tuple(item for item in result.materials
                                   if item.evidence.source_id not in seen)
        return RecallResult(materials[:request.limit], reasons + result.reason_codes)

    async def validate(self, request, materials, event=None):
        if not materials:
            return True
        if self._closed or not self.read_enabled:
            return False
        try:
            generation = await self.store.get_generation(request.context)
            if not await self._current(request.context, generation):
                return False
            current = None
            if any(item.evidence.provider == "local_vector" for item in materials):
                if self.embedding is None:
                    return False
                binding = await self.embedding.binding()
                current = await self.embedding.binding()
                if current.fingerprint != binding.fingerprint:
                    return False

            def check(db):
                # The body/TTL/generation snapshot is the last asynchronous boundary.
                self.data._cleanup(db)
                if (self._closed or not self.read_enabled
                        or self.store._generation(db, request.context) != generation):
                    return False
                for material in materials:
                    if material.evidence.provider == "local_lite":
                        if self.legacy is None or not self.legacy.validate(
                            db, self.data, request, material,
                        ):
                            return False
                        continue
                    if (material.evidence.provider != "local_vector"
                            or current is None
                            or not material_allowed(
                                material, request.context, self.store.clock())):
                        return False
                    rows = [dict(row) for row in db.execute(
                        """SELECT t.*,v.dimension,v.namespace FROM le_memory_text t
                        JOIN le_memory_vectors v ON t.key=v.key
                        WHERE t.account=? AND t.source=?""",
                        (request.context.account_key, material.evidence.source_id),
                    )]
                    if not any(row["generation"] == generation
                               and row["namespace"] == current.namespace_for(row["dimension"])
                               and (not current.dimension or current.dimension == row["dimension"])
                               and self._decode(row) == material for row in rows):
                        return False
                return True
            return await self.data._run(check)
        except Exception:  # noqa: BLE001 - a failed authorization check denies evidence.
            return False

    async def recall(self, request, *, event=None, available=()):
        result = await self.fetch(request, event)
        if not await self.validate(request, result.materials, event):
            return RecallResult(reason_codes=("evidence_authorization_changed",))
        return result

    async def validate_evidence(self, request, materials, *, event=None):
        valid = await self.validate(request, materials, event)
        return ValidationResult(valid, materials if valid else ())

    async def forget(self, context, source_id=None):
        await self.data.forget(context, source_id)
        self._revision += 1

    async def append(self, request, material, idempotency_key):
        return AppendResult(reason_code="experience_export_unsupported")

    async def close(self):
        self._closed = True
        tasks = tuple(task for task in self._writes if task is not asyncio.current_task())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if self.embedding is not None:
            await self.embedding.close()
