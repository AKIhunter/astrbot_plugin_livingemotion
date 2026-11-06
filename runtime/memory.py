"""Optional composition and accepted-source ingestion; Application owns hook wiring."""

from __future__ import annotations

import asyncio

from ..adapters.embedding import NativeEmbedding
from ..adapters.memory import LivingMemoryAdapter, LocalVectorMemory
from ..contracts import ActorRole, ContentKind, Event, EvidenceRef, stable_key
from ..ports.memory import Material, MemoryRequest


def external_enabled(config):
    return getattr(config, "livingmemory_enabled",
                   getattr(config, "memory_mode", "none") == "external") is True


async def build_memory_backend(store, host, discover, config, *, guard=None):
    if external_enabled(config):
        return LivingMemoryAdapter(
            lambda: discover("astrbot_plugin_livingmemory"),
            read_enabled=getattr(config, "memory_read", False),
            export_enabled=getattr(config, "memory_export", False),
            timeout=getattr(config, "memory_timeout_seconds", 2.0),
        )
    provider_id = getattr(config, "embedding_provider_id", "")
    embedding = (NativeEmbedding(
        host, provider_id, timeout=getattr(config, "embedding_timeout_seconds", 5.0),
    ) if provider_id else None)
    backend = LocalVectorMemory(
        store, embedding, read_enabled=getattr(config, "memory_read", False),
        write_enabled=getattr(config, "memory_write", False),
        max_records=getattr(config, "memory_max_records", 10000),
        retention_days=getattr(config, "memory_retention_days", 30),
        timeout=getattr(config, "memory_timeout_seconds", 2.0), guard=guard,
        legacy_path=store.path.with_name("explicit_memory.sqlite3"),
    )
    await backend.open()
    return backend


class AutoMemoryIngestor:
    def __init__(self, backend, runtime, *, config, guard=None):
        self.backend, self.runtime, self.config, self.guard = backend, runtime, config, guard
        self._closed = False
        self._tasks = set()
        self._token = self._config_token()
        self._counts = {"queued": 0, "stored": 0, "rejected": 0}

    def _config_token(self):
        config = self.config()
        return stable_key(
            getattr(config, "enabled", True), getattr(config, "mode", "active"),
            external_enabled(config), getattr(config, "memory_write", False),
            getattr(config, "embedding_provider_id", ""),
            getattr(config, "memory_retention_days", 30),
        )

    async def _current(self, context, generation):
        config = self.config()
        return (not self._closed and self._token == self._config_token()
                and getattr(config, "enabled", True)
                and getattr(config, "mode", "active") == "active"
                and not external_enabled(config) and getattr(config, "memory_write", False)
                and (self.guard is None or await self.guard(context, generation) is True))

    async def ingest(self, event: Event, *, generation: int):
        """Only callers holding accepted persistence may pass a normalized Event."""
        if (not isinstance(self.backend, LocalVectorMemory)
                or not isinstance(event, Event) or not event.reliable_source
                or not event.body.strip() or len(event.body) > 16000
                or not await self._current(event.context, generation)):
            return {"status": "rejected", "reason_code": "auto_memory_disabled_or_source_invalid"}
        if event.actor_role == ActorRole.HUMAN:
            if event.event_type != "message" or event.actor_id != event.context.account_id:
                return {"status": "rejected", "reason_code": "human_source_invalid"}
            kind = ContentKind.INTERACTION
        elif event.actor_role == ActorRole.BOT:
            if event.event_type != "bot_reply_submitted" or event.actor_id != event.context.bot_id:
                return {"status": "rejected", "reason_code": "bot_submission_source_required"}
            kind = ContentKind.BOT_ACTION
        else:
            return {"status": "rejected", "reason_code": "auto_memory_role_invalid"}
        if event.evidence or event.source_id.startswith("le-export:"):
            return {"status": "rejected", "reason_code": "derived_material_not_ingested"}
        material = Material(EvidenceRef(
            "livingemotion", event.idempotency_key, event.context, event.actor_id,
            event.context.bot_id, kind, event.occurred_at,
            expires_at=event.occurred_at + self.backend.retention_days * 86400,
            source_ids=(event.source_id,),
        ), event.body)
        request = MemoryRequest(stable_key("auto-memory", event.idempotency_key),
                                "auto_ingestion", event.context)
        # Capture delete epochs now, not when a delayed queue worker finally starts.
        prepared, reason = await self.backend.prepare(request, material, generation=generation)
        if prepared is None:
            return {"status": "rejected", "reason_code": reason}

        async def work():
            task = asyncio.current_task()
            self._tasks.add(task)
            try:
                if not await self._current(event.context, generation):
                    self._counts["rejected"] += 1
                    return
                result = await self.backend.remember(
                    request, material, prepared=prepared,
                    commit_guard=lambda: not self._closed and self._token == self._config_token(),
                )
                self._counts["stored" if result.accepted else "rejected"] += 1
            finally:
                self._tasks.discard(task)
        result = await self.runtime.submit(
            request.request_id, event.context, generation, work,
            purpose="embedding", model=False,
        )
        self._counts["queued" if result["status"] == "queued" else "rejected"] += 1
        return result

    def health(self):
        return {"closed": self._closed, **self._counts}

    async def close(self):
        self._closed = True
        tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
