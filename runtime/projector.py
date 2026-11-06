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
        generation, records = await self.store.read_projection(context)
        bot = snapshot(records["bot"], BotAffect)
        relationship = snapshot(records.get("relationship"), Relationship)
        observation = snapshot(records["observation"], HumanObservation) if records.get(
            "observation"
        ) else None
        night = snapshot(records["night"], NightState, updated_at=now)

        def runtime(kind):
            record = records.get(kind)
            return dict(record.value.get("_runtime", {})) if record else {}

        night_runtime = runtime("night")
        night_result = apply_interaction(
            night, event, context=context, now=now,
            runtime=night_runtime.get("interaction", {}), enabled=config.night_enabled,
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
                kind, {**payload, "_runtime": metadata},
                record.version if record else 0,
                context.account_id if kind in ("relationship", "observation") else "",
            ))

        write("bot", emotion["affect"], emotion["runtime"],
              serialized=emotion["trace"]["after"])
        write("night", night_result["night"],
              {**night_runtime, "interaction": night_result["runtime"]})
        if emotion["observation"] is not None and context.account_id:
            write("observation", emotion["observation"], {})
        if relation is not None:
            write("relationship", relation["relationship"], relation["runtime"],
                  serialized=relation["trace"]["after"])
        return Projection(
            tuple(writes), tuple(relation["contributions"]) if relation else (),
            ({"kind": "emotion", **emotion["trace"],
              "reason_codes": emotion["reason_codes"]},)
            + (({"kind": "relationship", **relation["trace"]},) if relation else ()),
            {"state": bot, "observation": observation, "relationship": relationship,
             "night": night_result["night"], "runtime": runtime("bot"), "now": now}
            if config.emotion_model_enabled and config.mode == "active" else None,
            generation,
        )
