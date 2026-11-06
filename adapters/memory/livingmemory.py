"""Fail-closed compatibility with the two public LivingMemory event profiles."""

from __future__ import annotations

import asyncio
import copy
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from uuid import uuid4

from ...contracts import ContentKind, EvidenceRef, finite
from ...ports.memory import AppendResult, Material, MemoryCapabilities, MemoryMode, RecallResult
from ..identity import IdentityAdapter, IdentitySnapshot, is_real_event


@dataclass(frozen=True)
class _Receipt:
    material: Material
    row: object
    identity: IdentitySnapshot
    provider: object
    query: str
    limit: int
    profile: str


def _field(row: object, key: str):
    return row.get(key) if isinstance(row, Mapping) else getattr(row, key, None)


class LivingMemoryAdapter:
    def __init__(
        self,
        provider: Callable[[], object | None],
        *,
        read_enabled: bool = True,
        export_enabled: bool = False,
        timeout: float = 2.0,
        max_receipts: int = 256,
    ):
        finite(timeout, "memory_timeout", 0.001, 60)
        if type(max_receipts) is not int or max_receipts < 1:
            raise ValueError("external_memory_limits_invalid")
        self.provider = provider
        self.read_enabled = read_enabled
        self.export_enabled = export_enabled
        self.timeout = timeout
        self.max_receipts = max_receipts
        self.identity = IdentityAdapter(provider, timeout=timeout)
        self._receipts: OrderedDict[str, _Receipt] = OrderedDict()

    def _ready(self, provider: object | None) -> bool:
        try:
            return provider is not None and all(
                callable(getattr(provider, method, None))
                for method in (
                    "resolve_identity_context",
                    "search_memories_for_event",
                )
            )
        except Exception:  # noqa: BLE001 - a half-unloaded provider is unavailable.
            return False

    @staticmethod
    def _profile(provider):
        return ("validate" if callable(getattr(provider, "validate_identity_results", None))
                else "event_requery")

    def _current_provider(self) -> object | None:
        try:
            return self.provider()
        except Exception:  # noqa: BLE001 - public plugin discovery is optional.
            return None

    def cache_token(self):
        return id(self._current_provider()), self.read_enabled, self.export_enabled

    def capabilities(self) -> MemoryCapabilities:
        reasons = [
            "external_background_authorization_unsupported",
            "external_idempotent_export_unsupported",
        ]
        ready = self._ready(self._current_provider())
        if not ready:
            reasons.append("external_provider_unavailable")
        if not self.read_enabled:
            reasons.append("external_read_disabled")
        return MemoryCapabilities(
            MemoryMode.EXTERNAL, ready and self.read_enabled, False, False, tuple(reasons)
        )

    def _material(self, row: object, request, identity: IdentitySnapshot, token: str) -> Material:
        metadata = _field(row, "metadata")
        if not isinstance(metadata, Mapping):
            raise TypeError("external_provenance_missing")
        # The original route is a source assertion. Never replace a missing source
        # route with the current query's route, or infer ownership from persona.
        route = metadata.get("source_session_id")
        if not route or route != request.context.route:
            raise ValueError("external_original_scene_unproven")
        if (
            not identity.owner_account
            or metadata.get("owner_account") != identity.owner_account
            or metadata.get("source_account") != identity.source_account
            or metadata.get("persona_id") != request.context.persona_id
            or metadata.get("identity_history_mixed")
        ):
            raise ValueError("external_source_mismatch")
        subjects = metadata.get("subject_accounts")
        if not isinstance(subjects, (list, tuple)) or len(subjects) != 1 or not subjects[0]:
            raise ValueError("external_subject_unproven")
        # Current scope grants do not make missing provenance public.
        audience = metadata.get("audience")
        expected_audience = (
            "self_private"
            if request.context.scene_kind == "private"
            else "origin_group:" + request.context.scene_id
        )
        if audience != expected_audience:
            raise ValueError("external_audience_mismatch")
        sensitivity = metadata.get("sensitivity")
        if type(sensitivity) is not int or not 0 <= sensitivity <= 3:
            raise ValueError("external_sensitivity_missing")
        revision = metadata.get("_identity_revision")
        if ("livingmemory:" + str(revision)) != identity.context.identity_revision:
            raise ValueError("external_revision_missing_or_changed")
        source_ids = metadata.get("source_ids")
        window = metadata.get("source_window")
        kind = metadata.get("content_kind")
        if not kind and isinstance(window, Mapping):
            kind = ContentKind.SUMMARY
        kind = ContentKind(kind)
        if kind == ContentKind.SUMMARY and not source_ids:
            if (
                not isinstance(window, Mapping)
                or window.get("session_id") != route
                or type(window.get("start_index")) is not int
                or type(window.get("end_index")) is not int
                or not 0 <= window["start_index"] < window["end_index"]
            ):
                raise ValueError("external_source_window_missing")
            source_ids = (f"{route}#window:{window['start_index']}:{window['end_index']}",)
        if not isinstance(source_ids, (list, tuple)) or not source_ids:
            raise ValueError("external_source_mapping_missing")
        if not all(isinstance(value, str) and value for value in source_ids):
            raise ValueError("external_source_mapping_invalid")
        doc_id = _field(row, "doc_id")
        if type(doc_id) not in (str, int) or not str(doc_id):
            raise ValueError("external_document_id_missing")
        ref = EvidenceRef(
            provider="livingmemory",
            source_id=str(doc_id),
            context=replace(request.context, route=route),
            subject_id=subjects[0],
            holder_id=identity.owner_account,
            kind=kind,
            occurred_at=metadata.get("create_time"),
            expires_at=metadata.get("expires_at"),
            sensitive=sensitivity > 0,
            exportable=False,
            authorization=token,
            source_ids=tuple(source_ids),
        )
        return Material(ref, _field(row, "content"))

    async def fetch(self, request, event) -> RecallResult:
        if not self.read_enabled:
            return RecallResult(reason_codes=("external_read_disabled",))
        if not is_real_event(event, request.context):
            return RecallResult(reason_codes=("external_background_authorization_unsupported",))
        provider = self._current_provider()
        if not self._ready(provider):
            return RecallResult(reason_codes=("external_provider_unavailable",))
        identity = await self.identity.resolve(request.context, event=event)
        if identity.provider_token != id(provider) or identity.context != request.context:
            return RecallResult(reason_codes=("external_identity_not_current",))
        try:
            rows = await asyncio.wait_for(
                provider.search_memories_for_event(
                    request.query,
                    event,
                    persona_id=request.context.persona_id,
                    k=request.limit,
                ),
                self.timeout,
            )
            if self._current_provider() is not provider or not await self.identity.validate(
                identity, event=event
            ):
                return RecallResult(reason_codes=("external_identity_changed",))
            if not isinstance(rows, list):
                return RecallResult(reason_codes=("external_result_contract_invalid",))
            accepted, reasons = [], set()
            for row in rows[: request.limit]:
                token = uuid4().hex
                try:
                    material = self._material(row, request, identity, token)
                except (TypeError, ValueError, KeyError):
                    reasons.add("external_provenance_incomplete_or_out_of_scope")
                    continue
                self._receipts[token] = _Receipt(
                    material, copy.deepcopy(row), identity, provider,
                    request.query, request.limit, self._profile(provider),
                )
                accepted.append(material)
            while len(self._receipts) > self.max_receipts:
                self._receipts.popitem(last=False)
            return RecallResult(tuple(accepted), tuple(sorted(reasons)))
        except Exception:  # noqa: BLE001 - optional plugin facade may fail during reload.
            return RecallResult(reason_codes=("external_provider_unavailable",))

    async def validate(self, request, materials, event) -> bool:
        if not materials:
            return True
        provider = self._current_provider()
        if (
            not self.read_enabled
            or not self._ready(provider)
            or not is_real_event(event, request.context)
        ):
            return False
        receipts = []
        for material in materials:
            receipt = self._receipts.get(material.evidence.authorization)
            if (
                receipt is None
                or receipt.material != material
                or receipt.provider is not provider
                or receipt.identity.context != request.context
                or receipt.query != request.query
                or receipt.limit != request.limit
                or receipt.profile != self._profile(provider)
            ):
                return False
            receipts.append(receipt)
        for receipt in receipts:
            if not await self.identity.validate(receipt.identity, event=event):
                return False
        try:
            if receipts[0].profile == "validate":
                rows = await asyncio.wait_for(
                    provider.validate_identity_results(
                        [copy.deepcopy(receipt.row) for receipt in receipts]
                    ),
                    self.timeout,
                )
            else:
                rows = await asyncio.wait_for(
                    provider.search_memories_for_event(
                        receipts[0].query, event,
                        persona_id=request.context.persona_id, k=receipts[0].limit,
                    ),
                    self.timeout,
                )
            if (
                self._current_provider() is not provider
                or not isinstance(rows, list)
            ):
                return False
            # Never authorize by revision or ID alone; compare body and provenance.
            for receipt in receipts:
                matched = False
                for row in rows[:request.limit]:
                    try:
                        material = self._material(
                            row, request, receipt.identity,
                            receipt.material.evidence.authorization,
                        )
                    except (TypeError, ValueError, KeyError):
                        continue
                    if (material == receipt.material
                            and _field(row, "metadata") == _field(receipt.row, "metadata")):
                        matched = True
                        break
                if not matched:
                    return False
            return all(
                [
                    await self.identity.validate(receipt.identity, event=event)
                    for receipt in receipts
                ]
            )
        except Exception:  # noqa: BLE001 - failed final authorization is never permissive.
            return False

    async def append(self, request, material, idempotency_key) -> AppendResult:
        # search_context/project_identity are not background authorization or
        # idempotent write facades. Do not probe arbitrary method names.
        return AppendResult(
            reason_code=(
                "external_idempotent_export_unsupported"
                if self.export_enabled
                else "external_export_disabled"
            )
        )
