"""Fail-closed compatibility with the two public LivingMemory event profiles."""

from __future__ import annotations

import asyncio
import copy
import importlib
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from uuid import uuid4

from ...contracts import ContentKind, EvidenceRef, finite, to_dict
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


_engine_write_locks = {}


def _identity_revision(context):
    value = context.identity_revision
    if not value.startswith("livingmemory:"):
        return None
    revision = value.removeprefix("livingmemory:")
    return int(revision) if revision.isdecimal() else revision


class LivingMemoryAdapter:
    def __init__(
        self,
        provider: Callable[[], object | None],
        *,
        read_enabled: bool = True,
        write_enabled: bool = False,
        export_enabled: bool = False,
        timeout: float = 2.0,
        max_receipts: int = 256,
        event_resolver=None,
    ):
        finite(timeout, "memory_timeout", 0.001, 60)
        if type(max_receipts) is not int or max_receipts < 1:
            raise ValueError("external_memory_limits_invalid")
        self.provider = provider
        self.read_enabled = read_enabled
        self.write_enabled = write_enabled
        self.export_enabled = export_enabled
        self.timeout = timeout
        self.max_receipts = max_receipts
        self.identity = IdentityAdapter(provider, timeout=timeout)
        self.event_resolver = event_resolver
        self._receipts: OrderedDict[str, _Receipt] = OrderedDict()
        self._writes = set()
        self._closed = False

    def _ready(self, provider: object | None) -> bool:
        try:
            return provider is not None and (all(
                callable(getattr(provider, method, None))
                for method in (
                    "resolve_identity_context",
                    "search_memories_for_event",
                )
            ) or (
                callable(getattr(getattr(getattr(provider, "initializer", None),
                                        "memory_engine", None), "search_memories", None))
                and getattr(provider, "config_manager", None) is not None
                and getattr(provider, "context", None) is not None
            ))
        except Exception:  # noqa: BLE001 - a half-unloaded provider is unavailable.
            return False

    @staticmethod
    def _profile(provider):
        if not callable(getattr(provider, "search_memories_for_event", None)):
            return "native"
        return ("validate" if callable(getattr(provider, "validate_identity_results", None))
                else "event_requery")

    async def _native_access(self, provider, event, context):
        if not is_real_event(event, context):
            raise ValueError("external_native_event_required")
        package = type(provider).__module__.rsplit(".", 1)[0]
        scope = importlib.import_module(f"{package}.core.memory_scope")
        access = await scope.resolve_event_memory_access(
            provider.config_manager, provider.context, event,
        )
        if (not access.allowed or not access.scope
                or access.persona_id and access.persona_id != context.persona_id):
            raise ValueError("external_native_scope_denied")
        return scope, access

    async def _snapshot(self, provider, context, event):
        identity = await self.identity.resolve(context, event=event)
        if self._profile(provider) != "native":
            return identity
        owner = str(event.get_self_id() or "")
        if not owner or identity.context != context:
            raise ValueError("external_native_identity_invalid")
        # 原生不提供跨平台身份绑定；只使用宿主真实事件的当前账号和机器人。
        return replace(identity, provider_token=id(provider),
                       owner_account=context.platform + ":" + owner)

    async def _snapshot_valid(self, provider, identity, event):
        try:
            return (self._current_provider() is provider
                    and (await self._snapshot(provider, identity.context, event)).fingerprint
                    == identity.fingerprint)
        except Exception:
            return False

    async def _rows(self, provider, request, event):
        if self._profile(provider) != "native":
            return await provider.search_memories_for_event(
                request.query, event, persona_id=request.context.persona_id, k=request.limit,
            )
        scope, access = await self._native_access(provider, event, request.context)
        with scope.adapter_access(provider.config_manager, event):
            rows = await provider.initializer.memory_engine.search_memories(
                query=request.query, k=request.limit, session_id=access.scope,
                persona_id=request.context.persona_id,
            )
            rows = [row for row in rows if
                    isinstance(_field(row, "metadata"), Mapping)
                    and _field(row, "metadata").get("session_id") == access.scope
                    and scope.adapter_visible(_field(row, "metadata"))]
        _, checked = await self._native_access(provider, event, request.context)
        if checked != access:
            raise ValueError("external_native_scope_changed")
        return rows

    def _current_provider(self) -> object | None:
        try:
            return self.provider()
        except Exception:  # noqa: BLE001 - public plugin discovery is optional.
            return None

    def cache_token(self):
        return (id(self._current_provider()), self.read_enabled, self.write_enabled,
                self.export_enabled, self._closed)

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
        if self._closed:
            reasons.append("external_memory_closed")
        return MemoryCapabilities(
            MemoryMode.EXTERNAL, ready and self.read_enabled and not self._closed,
            False, False, tuple(reasons)
        )

    async def append_source(self, context, content, source_id, source_event_id, kind,
                            *, metadata=None, guard=None):
        if (self._closed or not self.write_enabled or not isinstance(content, str)
                or not content.strip()):
            return AppendResult(reason_code="external_write_disabled_or_invalid")
        provider = self._current_provider()
        try:
            plugin = provider
            initializer = getattr(plugin, "initializer", None)
            engine = getattr(initializer, "memory_engine", None)
            add_memory = getattr(engine, "add_memory", None)
            if not callable(add_memory):
                return AppendResult(reason_code="external_write_engine_unavailable")
            route = context.route
            if not route or not context.persona_id or not context.account_id:
                return AppendResult(reason_code="external_write_source_invalid")
            write_metadata = {
                "source_id": source_id, "source_ids": [source_event_id],
                "source_session_id": route, "adapter_id": context.adapter_id,
                "source_instance": context.instance_id,
                "source_account": context.platform + ":" + context.account_id,
                "subject_accounts": [context.platform + ":" + context.account_id],
                "audience": ("self_private" if context.scene_kind.value == "private"
                             else "origin_group:" + context.scene_id),
                "sensitivity": 0, "content_kind": kind,
            }
            write_metadata.update(metadata or {})
            native = self._profile(provider) == "native"
            if native:
                event = self.event_resolver(context) if self.event_resolver else None
                scope, access = await self._native_access(provider, event, context)
                storage_scope = access.scope
                write_metadata["livingemotion_source_context"] = to_dict(context)
            else:
                storage_scope = route
            owner_account = write_metadata.get("owner_account")
            if not isinstance(owner_account, str) or not owner_account.strip():
                return AppendResult(reason_code="external_write_owner_unresolved")
            revision = _identity_revision(context)
            if revision is not None:
                write_metadata["identity_revision"] = revision
            task = asyncio.current_task()
            self._writes.add(task)
            lock = _engine_write_locks.setdefault(id(engine), asyncio.Lock())
            async with lock:
                if self._closed or self._current_provider() is not provider or (guard and not await guard()):
                    return AppendResult(reason_code="external_write_context_changed")
                connection = getattr(engine, "db_connection", None)
                if connection is None:
                    return AppendResult(reason_code="external_write_engine_unavailable")
                async with connection.execute(
                    "SELECT 1 FROM documents WHERE json_valid(metadata) "
                    "AND json_extract(metadata, '$.source_id') = ? LIMIT 1", (source_id,)
                ) as cursor:
                    if await cursor.fetchone():
                        return AppendResult(True, "duplicate")
                if self._closed or self._current_provider() is not provider or (guard and not await guard()):
                    return AppendResult(reason_code="external_write_context_changed")
                async def store():
                    return await add_memory(
                        content=content, session_id=storage_scope,
                        persona_id=context.persona_id, metadata=write_metadata,
                    )
                if native:
                    _, checked = await self._native_access(provider, event, context)
                    if checked != access:
                        return AppendResult(reason_code="external_write_context_changed")
                    with scope.adapter_access(provider.config_manager, event, write=True):
                        await asyncio.wait_for(store(), max(10.0, self.timeout))
                else:
                    await asyncio.wait_for(store(), max(10.0, self.timeout))
                return AppendResult(True, "stored")
        except asyncio.CancelledError:
            raise
        except Exception:
            return AppendResult(reason_code="external_write_failed")
        finally:
            if 'task' in locals():
                self._writes.discard(task)

    async def close(self):
        self._closed = True
        tasks = tuple(task for task in self._writes if task is not asyncio.current_task())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    def _material(self, row: object, request, identity: IdentitySnapshot, token: str,
                  *, native=False) -> Material:
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
        if native and subjects[0] != identity.source_account:
            raise ValueError("external_native_subject_mismatch")
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
        if not native and ("livingmemory:" + str(revision)) != identity.context.identity_revision:
            raise ValueError("external_revision_missing_or_changed")
        if native:
            # 来源不完整的原生摘要不能伪装成 Emotion 的可引用证据。
            # 旧 OneID 记录仍留在库内，待后续单独清洗或补齐来源。
            from ...contracts import Context
            source = metadata.get("livingemotion_source_context")
            if not isinstance(source, Mapping) or Context.from_dict(source) != request.context:
                raise ValueError("external_native_source_context_unproven")
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
        identity = await self._snapshot(provider, request.context, event)
        if identity.provider_token != id(provider) or identity.context != request.context:
            return RecallResult(reason_codes=("external_identity_not_current",))
        try:
            rows = await asyncio.wait_for(
                self._rows(provider, request, event),
                self.timeout,
            )
            if not await self._snapshot_valid(provider, identity, event):
                return RecallResult(reason_codes=("external_identity_changed",))
            if not isinstance(rows, list):
                return RecallResult(reason_codes=("external_result_contract_invalid",))
            accepted, reasons = [], set()
            for row in rows[: request.limit]:
                token = uuid4().hex
                try:
                    material = self._material(row, request, identity, token,
                                              native=self._profile(provider) == "native")
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
            if not await self._snapshot_valid(provider, receipt.identity, event):
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
                    self._rows(provider, request, event),
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
                            native=receipt.profile == "native",
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
                    await self._snapshot_valid(provider, receipt.identity, event)
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
