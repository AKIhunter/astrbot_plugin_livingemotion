"""Pure domain calculations with persisted metadata and a single commit boundary."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, fields
from functools import cached_property
from typing import Any

from ..config import Config
from ..contracts import (
    BotAffect,
    Context,
    Event,
    EvidenceRef,
    HumanObservation,
    NightState,
    Relationship,
    RelationshipContribution,
    StateRecord,
    StateWrite,
    to_dict,
)
from ..domain.emotion import apply_emotion, decay_affect
from ..domain.night import apply_interaction
from ..domain.relationship import RelationshipPolicy, apply_relationship
from ..storage import SQLiteStore
from ..storage.sqlite import _ProjectionPayload
from .state_scope import source_affect

_NIGHT_V1_FIELDS = (
    "phase", "energy", "updated_at", "sleep_started_at", "wake_at", "transition_deadline",
    "sleep_stage", "awaiting_reply_id", "unread_watermark", "reason_codes",
)
_NIGHT_FIELDS = tuple(item.name for item in fields(NightState))


def night_payload(state):
    """Night contains only scalar fields and reason codes; no deep-copy walk."""
    names = _NIGHT_V1_FIELDS if state.policy_version == 1 else _NIGHT_FIELDS
    value = {name: getattr(state, name) for name in names}
    value["phase"] = state.phase.value
    if "display_state" in value:
        value["display_state"] = state.display_state.value if state.display_state else None
    value["reason_codes"] = list(state.reason_codes)
    return value


class _ProjectionContext(Context):
    @cached_property
    def scope_key(self) -> str:
        return super().scope_key

    @cached_property
    def account_key(self) -> str:
        return super().account_key


class _ProjectionEvent(Event):
    """Call-local key reuse for guard scans; never retained as identity or state."""

    @cached_property
    def idempotency_key(self) -> str:
        return super().idempotency_key


def projection_event(event: Event) -> Event:
    """Own a key view for one request, leaving caller and custom events untouched."""
    if type(event) is not Event or type(event.context) is not Context:
        return event
    values = {field.name: getattr(event, field.name) for field in fields(Event)}
    values["context"] = _ProjectionContext(
        **{field.name: getattr(event.context, field.name) for field in fields(Context)}
    )
    return _ProjectionEvent(**values)


def snapshot(record: StateRecord | None, cls, **defaults):
    if record is None:
        return cls(**defaults)
    value = {key: val for key, val in record.value.items() if not key.startswith("_")}
    if "evidence" in value:
        value["evidence"] = tuple(
            EvidenceRef(**{**ref, "context": Context.from_dict(ref["context"])})
            for ref in value["evidence"]
        )
    for key in ("labels", "reason_codes"):
        if key in value:
            value[key] = tuple(value[key])
    return cls(**value)


def current_affect(record: StateRecord | None, *, now: float) -> BotAffect:
    return BotAffect() if record is None else decay_affect(snapshot(record, BotAffect), now=now)


@dataclass(frozen=True)
class Projection:
    writes: tuple[StateWrite, ...]
    contributions: tuple[RelationshipContribution, ...]
    traces: tuple[dict[str, Any], ...]
    refinement: dict[str, Any] | None = None
    generation: int | None = None


class Projector:
    def __init__(self, store: SQLiteStore, config, *, config_for_context=None):
        self.store = store
        self.config = config
        self.config_for_context = config_for_context

    async def __call__(self, event: Event) -> Projection:
        event = projection_event(event)
        context, now = event.context, self.store.clock()
        config: Config = (self.config_for_context(context) if self.config_for_context
                          else self.config())
        # Keep the bounded, pure transition next to JSON decoding. Moving the
        # mature guard between the loop and worker repeatedly causes GIL waits.
        return await self.store.project_snapshot(
            context, lambda generation, records: self._calculate(
                event, now, config, generation, records,
            ),
        )

    def _calculate(self, event, now, config, generation, records):
        context = event.context
        owner = getattr(records, "owner", None)
        bot = snapshot(records["bot"], BotAffect)
        if owner and owner.mode == "shared":
            bot = source_affect(bot, context)
        relationship = snapshot(records.get("relationship"), Relationship)
        observation = snapshot(records["observation"], HumanObservation) if records.get(
            "observation"
        ) else None
        night = snapshot(records["night"], NightState, updated_at=now)

        def runtime(kind):
            record = records.get(kind)
            data = dict(record.value.get("_runtime", {})) if record else {}
            if owner and owner.mode == "shared" and kind == "bot" and data:
                data["scope_key"] = context.scope_key
            return data

        night_runtime = runtime("night")
        if night.policy_version == 2 or (config.night_policy_version == 2 and config.timezone):
            # V2 human messages never consume energy. Runtime scheduling and
            # reply submission own time/reply energy, not archive ingestion.
            from ..domain.night import life_state
            night_result = {"night": life_state(night), "runtime": {}, "cost": 0}
        else:
            interaction = night_runtime.get("interaction", {})
            if owner and owner.mode == "shared" and interaction:
                interaction = {**interaction, "scope_key": context.scope_key}
            night_result = apply_interaction(
                night, event, context=context, now=now, runtime=interaction,
                enabled=config.night_enabled,
            )
        emotion = apply_emotion(
            bot, event, now=now, observation=observation, relationship=relationship,
            night=night_result["night"], runtime=runtime("bot"),
            enabled=config.enabled, mode=config.mode,
        )
        relation = apply_relationship(
            relationship, event, now=now, runtime=runtime("relationship"),
            policy=RelationshipPolicy(timezone=getattr(config, "timezone", "") or "UTC"),
            enabled=config.enabled, mode=config.mode,
        ) if context.account_id else None
        writes = []

        def write(kind, value, metadata, *, serialized=None):
            record = records.get(kind)
            # Domain traces already contain canonical snapshots. Keep independent
            # mutable output trees without converting the same dataclass again.
            payload = to_dict(value) if serialized is None else deepcopy(serialized)
            writes.append(StateWrite(
                kind, _ProjectionPayload({**payload, "_runtime": metadata}),
                record.version if record else 0,
                context.account_id if kind in ("relationship", "observation") else "",
                owner,
            ))

        write("bot", emotion["affect"], emotion["runtime"],
              serialized=emotion["trace"]["after"])
        write("night", night_result["night"],
              {**night_runtime, "interaction": night_result["runtime"]},
              serialized=night_payload(night_result["night"]))
        if emotion["observation"] is not None and context.account_id:
            write("observation", emotion["observation"], {})
        if relation is not None:
            write("relationship", relation["relationship"], relation["runtime"],
                  serialized=relation["trace"]["after"])
        return Projection(
            tuple(writes), tuple(relation["contributions"]) if relation else (),
            (_ProjectionPayload({"kind": "emotion", **emotion["trace"],
                                 "reason_codes": emotion["reason_codes"]}),)
            + ((_ProjectionPayload({"kind": "relationship", **relation["trace"]}),)
               if relation else ()),
            {"state": bot, "observation": observation, "relationship": relationship,
             "night": night_result["night"], "runtime": runtime("bot"), "now": now,
             "state_owner": owner}
            if config.emotion_model_enabled and config.mode == "active" else None,
            generation,
        )
