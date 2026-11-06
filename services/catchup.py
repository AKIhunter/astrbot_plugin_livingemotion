"""Bounded local unread excerpts, with original references and no I/O or sender."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

from ..contracts import (
    ActorRole, BehaviorIntent, ContentKind, Context, Event, EvidenceRef, NightPhase,
    NightState, canonical_json, finite, stable_key, to_dict,
)


@dataclass(frozen=True)
class CatchupPolicy:
    max_rows: int = 200
    max_messages: int = 16
    max_excerpt_chars: int = 160
    max_summary_chars: int = 2048
    max_batches: int = 3
    max_age_seconds: float = 86400.0

    def __post_init__(self) -> None:
        for name, maximum in (("max_rows", 200), ("max_messages", 32),
                              ("max_excerpt_chars", 512), ("max_summary_chars", 4096),
                              ("max_batches", 8)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError(f"invalid {name}")
        if self.max_summary_chars < 16:
            raise ValueError("summary budget too small")
        finite(self.max_age_seconds, "max_age_seconds", 1, 604800)


@dataclass(frozen=True)
class CatchupSummary:
    summary_id: str
    body: str
    evidence: EvidenceRef
    sources: tuple[EvidenceRef, ...]
    generation: int
    wake_key: str
    through_seq: int
    high_watermark: int


def _seq(value: int, name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"invalid {name}")


def _wake_key(state: NightState, context: Context) -> str:
    return stable_key(context.scope_key, context.persona_revision, context.identity_revision,
                      sorted(set(context.audience)), state.sleep_started_at, state.wake_at,
                      state.transition_deadline)


def _original(row: Mapping[str, Any], context: Context, now: float,
              policy: CatchupPolicy) -> Event | None:
    try:
        metadata = dict(row["metadata_json"])
        metadata["body"] = row["body"]
        event = Event.from_dict(metadata)
        if row["event_key"] != event.idempotency_key:
            return None
        if row["actor_role"] != event.actor_role or row["account_id"] != event.context.account_id:
            return None
        if row["occurred_at"] != event.occurred_at or row["event_id"] != event.event_id:
            return None
        if event.context.scope_key != context.scope_key or (
            event.context.persona_revision != context.persona_revision
            or event.context.identity_revision != context.identity_revision
            or set(event.context.audience) != set(context.audience)
        ):
            return None
        if event.actor_role != ActorRole.HUMAN or event.event_type != "message" or (
            not event.reliable_source or not event.actor_id
            or event.actor_id != event.context.account_id or not event.body.strip()
            or any(ref.kind != ContentKind.INTERACTION for ref in event.evidence)
        ):
            return None
        if not now - policy.max_age_seconds < event.occurred_at <= now:
            return None
        if any(ref.expires_at is not None and ref.expires_at <= now for ref in event.evidence):
            return None
        return event
    except (ValueError, TypeError, KeyError):
        return None


def build_catchup(
    state: NightState, context: Context, rows: Sequence[Mapping[str, Any]], *,
    now: float, high_watermark: int, generation: int,
    runtime: Mapping[str, Any] | None = None, policy: CatchupPolicy = CatchupPolicy(),
) -> dict[str, Any]:
    """Consume one ordered read_window page. Returned state/runtime need one CAS."""
    finite(now, "now", 0)
    for name, value in (("high_watermark", high_watermark), ("generation", generation),
                        ("unread_watermark", state.unread_watermark)):
        _seq(value, name)
    if len(rows) > policy.max_rows:
        raise ValueError("window page exceeds max_rows")
    sequences = [row["seq"] for row in rows]
    for seq in sequences:
        _seq(seq, "row seq")
    if any(left >= right for left, right in zip(sequences, sequences[1:])):
        raise ValueError("window page must be strictly ordered")
    data = dict(runtime or {})
    result = {
        "night": state, "runtime": data, "summary": None, "applied": False,
        "has_more": False, "reason_codes": ("not_waking",),
    }
    if state.phase != NightPhase.WAKING:
        data.pop("summary", None)
        return result
    if state.transition_deadline is None:
        raise ValueError("waking requires a deadline")
    if now < state.updated_at or now >= state.transition_deadline:
        data.pop("summary", None)
        result["reason_codes"] = ("catchup_outside_transition",)
        return result
    if data and (data.get("scope_key") != context.scope_key or data.get("generation") != generation):
        raise ValueError("catchup runtime scope or generation mismatch")
    key = _wake_key(state, context)
    if data.get("wake_key") != key:
        data = {
            "scope_key": context.scope_key, "generation": generation, "wake_key": key,
            "high_watermark": max(high_watermark, state.unread_watermark),
            "batches": 0, "completed": False,
        }
    upper = data["high_watermark"]
    _seq(upper, "frozen high watermark")
    _seq(data["batches"], "batches")
    result["runtime"] = data
    if data["completed"] or data["batches"] >= policy.max_batches:
        previous = data.get("summary")
        if previous is not None and previous["evidence"]["expires_at"] <= now:
            data.pop("summary", None)
        result["reason_codes"] = ("catchup_already_complete",)
        return result

    after = state.unread_watermark
    cursor = after
    lines: list[str] = []
    sources: list[EvidenceRef] = []
    consumed_chars = 0
    budget_stop = False
    skipped = 0
    source_chars = 0
    for row in rows:
        seq = row["seq"]
        if seq <= after:
            continue
        if seq > upper:
            break
        event = _original(row, context, now, policy)
        if event is None:
            cursor = seq
            skipped += 1
            continue
        prefix = f"[{len(sources) + 1}] "
        remaining = policy.max_summary_chars - consumed_chars - len(prefix) - bool(lines)
        if len(sources) >= policy.max_messages or remaining < 1:
            budget_stop = True
            break
        excerpt = " ".join(event.body.split())[:min(remaining, policy.max_excerpt_chars)]
        expires = min([event.occurred_at + policy.max_age_seconds] + [
            ref.expires_at for ref in event.evidence if ref.expires_at is not None
        ])
        source = EvidenceRef(
            provider="livingemotion.local", source_id=event.idempotency_key,
            context=replace(event.context, route=None), subject_id=event.actor_id,
            holder_id=event.actor_id, kind=ContentKind.INTERACTION,
            occurred_at=event.occurred_at, expires_at=expires,
            source_ids=(event.source_id,),
        )
        size = len(canonical_json(source))
        if size > 8192:
            cursor = seq
            skipped += 1
            continue
        if source_chars + size > 16384:
            budget_stop = True
            break
        source_chars += size
        sources.append(source)
        lines.append(prefix + excerpt)
        consumed_chars += len(lines[-1]) + (1 if len(lines) > 1 else 0)
        cursor = seq
    # Short pages (or a row beyond the frozen bound) prove remaining rows were
    # pruned or absent. A full page never proves exhaustion of the local window.
    exhausted = not budget_stop and (
        len(rows) < policy.max_rows or any(seq > upper for seq in sequences)
    )
    if exhausted:
        cursor = max(cursor, upper)
    done = cursor >= upper or data["batches"] + 1 >= policy.max_batches
    data = {**data, "batches": data["batches"] + 1, "completed": done}
    summary = None
    if sources:
        summary_id = stable_key("catchup-1", key, generation, after, cursor,
                                tuple(source.source_id for source in sources))
        summary_ref = EvidenceRef(
            provider="livingemotion.catchup", source_id=summary_id,
            context=replace(context, route=None), subject_id=context.bot_id,
            holder_id=context.bot_id, kind=ContentKind.SUMMARY, occurred_at=now,
            expires_at=min(source.expires_at for source in sources),
            source_ids=tuple(source.source_id for source in sources),
        )
        summary = CatchupSummary(summary_id, "\n".join(lines), summary_ref, tuple(sources),
                                 generation, key, cursor, upper)
    # Only the latest bounded summary is retained, never an accumulating history.
    data["summary"] = to_dict(summary)
    if len(canonical_json(data)) > 32768:
        raise ValueError("catchup runtime exceeds persistence budget")
    return {
        "night": replace(state, unread_watermark=cursor), "runtime": data,
        "summary": summary, "applied": cursor > after, "has_more": not done,
        "skipped_rows": skipped,
        "reason_codes": ("catchup_budget" if done and cursor < upper else
                         "catchup_complete" if done else "catchup_page",),
    }


def catchup_intent(
    summary: CatchupSummary, state: NightState, context: Context, *,
    now: float, generation: int,
) -> BehaviorIntent | None:
    """Optional handoff to T6. No delivery, announcement or retry is performed."""
    finite(now, "now", 0)
    _seq(generation, "generation")
    ref = summary.evidence
    if not context.route or state.phase != NightPhase.WAKING or state.transition_deadline is None or (
        now < state.updated_at or now >= state.transition_deadline
        or ref.expires_at is None or now >= ref.expires_at
        or ref.context.scope_key != context.scope_key
        or ref.context.persona_revision != context.persona_revision
        or ref.context.identity_revision != context.identity_revision
        or set(ref.context.audience) != set(context.audience)
        or summary.generation != generation
        or summary.wake_key != _wake_key(state, context)
        or summary.through_seq > state.unread_watermark
        or ref.occurred_at > now
    ):
        return None
    return BehaviorIntent(
        intent_id=stable_key("catchup-reply-1", summary.summary_id, generation),
        context=context, purpose="wake_catchup", created_at=now,
        expires_at=min(state.transition_deadline, ref.expires_at), generation=generation,
        human_watermark=summary.high_watermark, evidence=(ref, *summary.sources),
        reason_codes=("bounded_local_catchup",),
    )
