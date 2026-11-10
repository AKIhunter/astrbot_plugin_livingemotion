"""Optional composition and accepted-source ingestion; Application owns hook wiring."""

from __future__ import annotations

import asyncio

from ..adapters.embedding import NativeEmbedding
from ..adapters.memory import LivingMemoryAdapter, LocalVectorMemory
from ..contracts import ActorRole, ContentKind, Event, EvidenceRef, Experience, stable_key
from ..ports.memory import Material, MemoryRequest


def external_enabled(config):
    return getattr(config, "livingmemory_enabled",
                   getattr(config, "memory_mode", "none") == "external") is True


async def build_memory_backend(store, host, discover, config, *, guard=None):
    if external_enabled(config):
        return LivingMemoryAdapter(
            lambda: discover("astrbot_plugin_livingmemory"),
            read_enabled=getattr(config, "memory_read", False),
            write_enabled=getattr(config, "memory_write", False),
            export_enabled=getattr(config, "memory_export", False),
            timeout=getattr(config, "memory_timeout_seconds", 10.0),
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
    def __init__(self, backend, runtime, *, config, guard=None, owner_account_resolver=None):
        self.backend, self.runtime, self.config, self.guard = backend, runtime, config, guard
        self.owner_account_resolver = owner_account_resolver
        self._closed = False
        self._tasks = set()
        self._token = self._config_token()
        self._counts = {"queued": 0, "stored": 0, "rejected": 0}
        self._epoch = 0

    def _config_token(self):
        config = self.config()
        return stable_key(
            getattr(config, "enabled", True),
            external_enabled(config), getattr(config, "memory_write", False),
            getattr(config, "embedding_provider_id", ""),
            getattr(config, "memory_retention_days", 30),
        )

    async def _current(self, context, generation):
        config = self.config()
        return (not self._closed and self._token == self._config_token()
                and getattr(config, "enabled", True)
                and getattr(config, "memory_write", False)
                and (self.guard is None or await self.guard(context, generation) is True))

    async def ingest(self, event: Event, *, generation: int):
        """Persist the complete accepted source body without semantic filtering."""
        epoch = self._epoch
        if (not isinstance(event, Event) or not event.reliable_source
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
        if event.source_id.startswith("le-export:"):
            return {"status": "rejected", "reason_code": "derived_material_not_ingested"}
        if isinstance(self.backend, LocalVectorMemory):
            material = Material(EvidenceRef(
                "livingemotion", event.idempotency_key, event.context, event.actor_id,
                event.context.bot_id, kind, event.occurred_at,
                expires_at=event.occurred_at + self.backend.retention_days * 86400,
                source_ids=(event.source_id,),
            ), event.body)
            request = MemoryRequest(stable_key("auto-memory", event.idempotency_key),
                                    "auto_ingestion", event.context)
            prepared, reason = await self.backend.prepare(request, material, generation=generation)
            if prepared is None:
                return {"status": "rejected", "reason_code": reason}

            async def write():
                return await self.backend.remember(
                    request, material, prepared=prepared,
                    commit_guard=lambda: epoch == self._epoch and not self._closed
                    and self._token == self._config_token(),
                )
            purpose = "embedding"
        elif isinstance(self.backend, LivingMemoryAdapter):
            request = None

            async def external_guard():
                return (epoch == self._epoch and not self._closed
                        and await self._current(event.context, generation))

            async def write():
                owner_account = (self.owner_account_resolver(event.context)
                                 if self.owner_account_resolver else "")
                if not isinstance(owner_account, str) or not owner_account.strip():
                    return {"status": "rejected", "reason_code": "memory_owner_unresolved"}
                return await self.backend.append_source(
                    event.context, event.body, event.idempotency_key,
                    event.source_id, kind.value,
                    metadata={"owner_account": owner_account}, guard=external_guard,
                )
            purpose = "memory_write"
        else:
            return {"status": "rejected", "reason_code": "memory_backend_unsupported"}

        async def work():
            task = asyncio.current_task()
            self._tasks.add(task)
            try:
                if not await self._current(event.context, generation):
                    self._counts["rejected"] += 1
                    return
                result = await write()
                accepted = result.accepted if hasattr(result, "accepted") else result.get("status") == "stored"
                self._counts["stored" if accepted else "rejected"] += 1
            finally:
                self._tasks.discard(task)
        result = await self.runtime.submit(
            stable_key("auto-memory", event.idempotency_key), event.context, generation, work,
            purpose=purpose, model=False,
        )
        self._counts["queued" if result["status"] == "queued" else "rejected"] += 1
        return result

    async def ingest_experience(self, experience: Experience, *, generations):
        epoch = self._epoch
        if (not isinstance(experience, Experience) or not experience.body.strip()
                or not await self._current(experience.context, dict(generations).get(experience.context))):
            return {"status": "rejected", "reason_code": "auto_memory_disabled_or_source_invalid"}
        context = experience.context
        generation = dict(generations).get(context)
        source_id = stable_key("experience", experience.experience_id, experience.kind.value)
        source_ids = tuple(ref.source_id for ref in experience.evidence) or (source_id,)
        text = experience.body
        source_account = context.platform + ":" + context.account_id
        metadata = {"content_kind": experience.kind.value, "source_id": source_id,
                    "source_ids": source_ids, "imagined": experience.kind == ContentKind.DREAM,
                    "source_session_id": context.route, "audience": (
                        "self_private" if context.scene_kind.value == "private"
                        else "origin_group:" + context.scene_id),
                    "source_account": source_account,
                    "subject_accounts": [source_account], "sensitivity": 0,
                    "expires_at": experience.expires_at}
        async def write():
            if isinstance(self.backend, LocalVectorMemory):
                expires_at = experience.expires_at
                if expires_at is None or expires_at - experience.created_at > self.backend.retention_days * 86400:
                    expires_at = experience.created_at + self.backend.retention_days * 86400
                evidence = EvidenceRef(
                    "livingemotion", source_id, context, context.account_id, context.bot_id,
                    experience.kind, experience.created_at, expires_at,
                    source_ids=(source_id,),
                )
                material = Material(evidence, text)
                request = MemoryRequest(source_id, "experience_ingestion", context)
                prepared, reason = await self.backend.prepare(request, material, generation=generation)
                if prepared is None:
                    return {"status": "rejected", "reason_code": reason}
                return await self.backend.remember(
                    request, material, prepared=prepared,
                    commit_guard=lambda: epoch == self._epoch and not self._closed
                    and self._token == self._config_token(),
                )
            if isinstance(self.backend, LivingMemoryAdapter):
                owner_account = (self.owner_account_resolver(context)
                                 if self.owner_account_resolver else "")
                if not isinstance(owner_account, str) or not owner_account.strip():
                    return {"status": "rejected", "reason_code": "memory_owner_unresolved"}
                metadata["owner_account"] = owner_account

                async def external_guard():
                    return (epoch == self._epoch and not self._closed
                            and await self._current(context, generation))

                return await self.backend.append_source(
                    context, text, source_id, source_id, experience.kind.value,
                    metadata=metadata, guard=external_guard,
                )
            return {"status": "rejected", "reason_code": "memory_backend_unsupported"}
        async def work():
            task = asyncio.current_task()
            self._tasks.add(task)
            try:
                if epoch != self._epoch or not all([await self._current(ctx, gen) for ctx, gen in generations]):
                    return
                result = await write()
                accepted = result.accepted if hasattr(result, "accepted") else result.get("status") == "stored"
                self._counts["stored" if accepted else "rejected"] += 1
            finally:
                self._tasks.discard(task)
        return await self.runtime.submit(source_id, context, generation, work,
                                         purpose="memory_write", model=False)

    def health(self):
        return {"closed": self._closed, **self._counts}

    async def close(self):
        self._closed = True
        self._epoch += 1
        tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
