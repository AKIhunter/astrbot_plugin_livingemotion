"""Local provenance checks and optional recall at the single behavior boundary."""

from dataclasses import replace

from ..adapters.memory.base import material_allowed
from ..contracts import ActorRole, ContentKind, Context, Event, EvidenceRef, stable_key
from ..ports.memory import Material, RecallResult, ValidationResult


class Materials:
    async def local_behavior_materials(self, request):
        result = []
        for row in await self.store.read_window(request.context):
            event = Event.from_dict({**row["metadata_json"], "body": row["body"]})
            if not event.reliable_source or not event.body.strip():
                continue
            if (event.actor_role == ActorRole.HUMAN and event.event_type == "message"
                    and event.actor_id == event.context.account_id):
                kind = ContentKind.INTERACTION
            elif (event.actor_role == ActorRole.BOT and event.event_type == "bot_action_succeeded"
                  and event.actor_id == event.context.bot_id):
                kind = ContentKind.BOT_ACTION
            else:
                continue
            item = Material(EvidenceRef(
                "livingemotion", event.idempotency_key, event.context,
                event.actor_id, event.context.bot_id, kind, event.occurred_at,
                expires_at=event.occurred_at + self.config.window_days * 86400,
            ), event.body)
            if material_allowed(item, request.context, self.store.clock()):
                result.append(item)
        return tuple(result)

    async def catchup_materials(self, request):
        record = await self.store.get_state(request.context, "night")
        summary = (record.value.get("_runtime", {}).get("catchup", {}).get("summary")
                   if record else None)
        if (not summary or summary["generation"] != await self.store.get_generation(request.context)
                or request.request_id != stable_key(
                    "catchup-reply-1", summary["summary_id"], summary["generation"])):
            return ()
        ref = EvidenceRef(**{**summary["evidence"],
                             "source_ids": tuple(summary["evidence"]["source_ids"]),
                             "context": Context.from_dict(summary["evidence"]["context"])})
        if not material_allowed(Material(ref, summary["body"]), request.context, self.store.clock()):
            return ()
        rows = {row["event_key"]: row for row in await self.store.read_window(request.context)}
        for raw in summary["sources"]:
            source = EvidenceRef(**{**raw, "source_ids": tuple(raw["source_ids"]),
                                    "context": Context.from_dict(raw["context"])})
            row = rows.get(source.source_id)
            if not row:
                return ()
            event = Event.from_dict({**row["metadata_json"], "body": row["body"]})
            if (source.provider != "livingemotion.local"
                    or event.idempotency_key != source.source_id
                    or replace(event.context, route=None) != source.context
                    or source.source_ids != (event.source_id,)
                    or not event.reliable_source or event.actor_role != ActorRole.HUMAN
                    or event.event_type != "message" or event.actor_id != source.subject_id
                    or source.holder_id != event.actor_id
                    or source.kind != ContentKind.INTERACTION
                    or not material_allowed(Material(source, event.body),
                                            request.context, self.store.clock())):
                return ()
        if tuple(raw["source_id"] for raw in summary["sources"]) != ref.source_ids:
            return ()
        return (Material(ref, summary["body"]),)

    async def behavior_materials(self, request):
        if not await self.validate_context(request.context):
            return RecallResult(reason_codes=("context_changed",))
        if request.purpose == "wake_catchup":
            return RecallResult(await self.catchup_materials(request))
        local = await self.local_behavior_materials(request)
        external = RecallResult()
        if self.config.memory_read:
            # Background recall deliberately does not impersonate a live event.
            external = await self.memory.recall(
                replace(request, query=local[-1].text[:4096] if local else ""),
            )
        selected = list(external.materials[:request.limit])
        for item in reversed(local):
            if item not in selected and len(selected) < request.limit:
                selected.append(item)
        return RecallResult(tuple(selected), external.reason_codes)

    async def validate_behavior_materials(self, request, materials):
        if not await self.validate_context(request.context):
            return ValidationResult(False, reason_codes=("context_changed",))
        if request.purpose == "wake_catchup":
            valid = bool(materials) and materials == await self.catchup_materials(request)
            return ValidationResult(valid, materials if valid else ())
        own = tuple(item for item in materials if item.evidence.provider == "livingemotion")
        current = await self.local_behavior_materials(request)
        if any(item not in current for item in own):
            return ValidationResult(False, reason_codes=("local_evidence_changed",))
        return await self.memory.validate_evidence(request, materials)
