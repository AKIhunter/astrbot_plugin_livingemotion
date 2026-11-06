"""Bounded request reuse and fail-closed final material authorization."""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable

from ...contracts import ContentKind, Context, stable_key
from ...ports.memory import (
    AppendResult,
    Material,
    MemoryCapabilities,
    MemoryMode,
    MemoryRequest,
    RecallResult,
    ValidationResult,
)


def material_allowed(material: Material, context: Context, now: float) -> bool:
    ref = material.evidence
    source = ref.context
    return (
        bool(source.account_id)
        and source.account_key == context.account_key
        and source.persona_revision == context.persona_revision
        and source.identity_revision == context.identity_revision
        and bool(source.audience)
        and bool(context.audience)
        and set(context.audience).issubset(source.audience)
        and type(ref.sensitive) is bool
        and ref.occurred_at <= now
        and (ref.expires_at is None or now < ref.expires_at)
        and (ref.kind != ContentKind.SUMMARY or bool(ref.source_ids))
    )


class NoneMemory:
    def capabilities(self) -> MemoryCapabilities:
        return MemoryCapabilities(MemoryMode.NONE, False, False, reason_codes=("memory_disabled",))

    def cache_token(self) -> object:
        return MemoryMode.NONE

    async def fetch(self, request: MemoryRequest, event: object | None) -> RecallResult:
        return RecallResult(reason_codes=("memory_disabled",))

    async def validate(
        self, request: MemoryRequest, materials: tuple[Material, ...], event: object | None
    ) -> bool:
        return not materials

    async def append(
        self, request: MemoryRequest, material: Material, idempotency_key: str
    ) -> AppendResult:
        return AppendResult(reason_code="export_disabled")


class MemoryGateway:
    """The caller supplies a fresh context at use time, or an authoritative guard.

    No successful validation authorizes a future send after another await:
    the single sender must validate immediately before committing the attempt.
    """

    def __init__(
        self,
        backend=None,
        *,
        clock: Callable[[], float] = time.time,
        max_requests: int = 128,
        context_guard: Callable[[Context, object | None], Awaitable[bool]] | None = None,
    ):
        if type(max_requests) is not int or max_requests < 1:
            raise ValueError("memory_cache_limit_invalid")
        self.backend = backend or NoneMemory()
        self.clock = clock
        self.max_requests = max_requests
        self.context_guard = context_guard
        self._cache: OrderedDict[str, tuple[str, RecallResult]] = OrderedDict()
        self._inflight: dict[str, tuple[str, asyncio.Task]] = {}
        self._lock = asyncio.Lock()
        self._closed = False

    def capabilities(self) -> MemoryCapabilities:
        return self.backend.capabilities()

    async def validate_evidence(
        self,
        request: MemoryRequest,
        materials: tuple[Material, ...],
        *,
        event: object | None = None,
    ) -> ValidationResult:
        try:
            if self._closed:
                return ValidationResult(False, reason_codes=("memory_closed",))
            if self.context_guard and not await self.context_guard(request.context, event):
                return ValidationResult(False, reason_codes=("context_changed",))
            if any(not material_allowed(item, request.context, self.clock()) for item in materials):
                return ValidationResult(False, reason_codes=("evidence_scope_or_expiry_changed",))
            own = tuple(item for item in materials if item.evidence.provider == "livingemotion")
            if any(item.evidence.holder_id != request.context.bot_id for item in own):
                return ValidationResult(False, reason_codes=("evidence_holder_mismatch",))
            if (
                request.context.identity_revision.startswith("livingmemory:")
                and self.context_guard is None
                and any(item.evidence.provider != "livingmemory" for item in materials)
            ):
                return ValidationResult(False, reason_codes=("identity_revalidation_required",))
            other = tuple(item for item in materials if item.evidence.provider != "livingemotion")
            if not await self.backend.validate(request, other, event):
                return ValidationResult(False, reason_codes=("evidence_authorization_changed",))
            # An external validator may have waited for I/O; check the guard again.
            if self.context_guard and not await self.context_guard(request.context, event):
                return ValidationResult(False, reason_codes=("context_changed",))
            if any(not material_allowed(item, request.context, self.clock()) for item in materials):
                return ValidationResult(False, reason_codes=("evidence_scope_or_expiry_changed",))
            return ValidationResult(True, materials)
        except Exception:  # noqa: BLE001 - validation failure must deny the entire result.
            return ValidationResult(False, reason_codes=("evidence_validation_unavailable",))

    async def recall(
        self,
        request: MemoryRequest,
        *,
        event: object | None = None,
        available: tuple[Material, ...] = (),
    ) -> RecallResult:
        if self._closed:
            return RecallResult(reason_codes=("memory_closed",))
        # Only typed materials with a fresh authorization check may skip retrieval.
        eligible = []
        for item in available[:20]:
            if (await self.validate_evidence(request, (item,), event=event)).valid:
                eligible.append(item)
        if eligible:
            result = tuple(eligible[: request.limit])
            if (await self.validate_evidence(request, result, event=event)).valid:
                return RecallResult(result, reused=True)
        try:
            key = stable_key(request.key, self.backend.cache_token())
        except Exception:  # noqa: BLE001 - discovery can fail while another plugin reloads.
            return RecallResult(reason_codes=("memory_provider_unavailable",))
        fingerprint = stable_key(request.query, request.limit)
        async with self._lock:
            cached = self._cache.get(key)
            pending = self._inflight.get(key)
            if cached and cached[0] != fingerprint or pending and pending[0] != fingerprint:
                return RecallResult(reason_codes=("request_purpose_conflict",))
            if cached:
                result = cached[1]
                self._cache.move_to_end(key)
                task = None
                reused = True
            elif pending:
                task, reused = pending[1], True
            elif len(self._inflight) >= self.max_requests:
                return RecallResult(reason_codes=("memory_busy",))
            else:
                task = asyncio.create_task(self._fetch(key, fingerprint, request, event))
                self._inflight[key] = (fingerprint, task)
                reused = False
        if task is not None:
            result = await asyncio.shield(task)
        validation = await self.validate_evidence(request, result.materials, event=event)
        if not validation.valid:
            return RecallResult(reason_codes=validation.reason_codes, reused=reused)
        return RecallResult(result.materials, result.reason_codes, reused)

    async def _fetch(self, key, fingerprint, request, event) -> RecallResult:
        try:
            result = await self.backend.fetch(request, event)
        except Exception:  # noqa: BLE001 - optional backend failure cannot break core state.
            result = RecallResult(reason_codes=("memory_provider_unavailable",))
        finally:
            # The task cannot run until recall has inserted it in _inflight.
            self._inflight.pop(key, None)
        if not self._closed:
            self._cache[key] = (fingerprint, result)
            while len(self._cache) > self.max_requests:
                self._cache.popitem(last=False)
        return result

    async def append_experience(
        self,
        request: MemoryRequest,
        material: Material,
        *,
        idempotency_key: str,
    ) -> AppendResult:
        if not idempotency_key:
            return AppendResult(reason_code="export_key_required")
        if not self.capabilities().append_experience:
            return AppendResult(reason_code="export_disabled_or_unsupported")
        if not (await self.validate_evidence(request, (material,))).valid:
            return AppendResult(reason_code="export_evidence_invalid")
        return await self.backend.append(request, material, idempotency_key)

    async def close(self) -> None:
        self._closed = True
        tasks = [entry[1] for entry in self._inflight.values()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._cache.clear()
        self._inflight.clear()
