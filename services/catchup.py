"""Bounded local unread excerpts, with original references and no I/O or sender."""

from __future__ import annotations

from dataclasses import dataclass, replace
import asyncio
import json
from typing import Any, Mapping, Sequence
from weakref import WeakValueDictionary

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


@dataclass(frozen=True)
class FullCatchupResult:
    summaries: tuple[str, ...] = ()
    read_count: int = 0
    has_more: bool = False
    blocked: bool = False
    reason: str = ""


def split_full_chunks(rows, *, size=45, hard_cap=80, window_seconds=3600):
    """Migrated count/time/cap boundary; every row retains its complete body."""
    chunks, current = [], []
    for row in rows:
        if current and (len(current) >= min(size, hard_cap)
                        or row["occurred_at"] - current[0]["occurred_at"] >= window_seconds):
            chunks.append(current)
            current = []
        current.append(row)
    if current:
        chunks.append(current)
    return chunks


def transcript_parts(rows, *, byte_budget=2048):
    """Split long messages into identified fragments, without discarding tails."""
    if byte_budget < 256:
        raise ValueError("catchup_input_budget_too_small")
    parts, part, used = [], [], 0
    for row in rows:
        prefix = f"[seq={row['seq']}][source={row['source_id']}]\n"
        # Host source IDs are data; canonical JSON on the model boundary prevents
        # these labels from being interpreted as instructions.
        available = byte_budget - len(prefix.encode("utf-8")) - 32
        if available < 128:
            raise ValueError("catchup_source_identifier_too_large")
        body, offset = row["body"], 0
        while offset < len(body):
            end, consumed = offset, 0
            while end < len(body):
                width = len(body[end].encode("utf-8"))
                if consumed + width > available:
                    break
                consumed += width
                end += 1
            fragment = prefix + f"[offset={offset}]\n" + body[offset:end]
            width = len(fragment.encode("utf-8"))
            if part and used + width + 1 > byte_budget:
                parts.append("\n".join(part))
                part, used = [], 0
            part.append(fragment)
            used += width + 1
            offset = end
    if part:
        parts.append("\n".join(part))
    return parts


def parse_reading(value):
    if isinstance(value, dict):
        data = value
    elif isinstance(value, str):
        decoder = json.JSONDecoder()
        data = None
        for offset, char in enumerate(value):
            if char == "{":
                try:
                    candidate, _ = decoder.raw_decode(value[offset:])
                except ValueError:
                    continue
                if isinstance(candidate, dict):
                    data = candidate
                    break
    else:
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("summary"), str):
        raise ValueError("catchup_reading_failed")
    if not data["summary"].strip():
        raise ValueError("catchup_reading_empty")
    return {"summary": data["summary"][:2000],
            "items": data.get("items", []) if isinstance(data.get("items", []), list) else []}


class FullCatchupService:
    """Persistent full reading and optional historical replies on one source lane.

    Summary I/O is injected and shares the application's generation budget. The
    sender is the same guarded behavior executor; an unknown result blocks replay.
    """

    def __init__(self, archive, *, read_model, reply_model, send, guard,
                 input_byte_budget=2048, reply_enabled=False, max_replies=3):
        self.archive = archive
        self.read_model, self.reply_model = read_model, reply_model
        self.send, self.guard = send, guard
        self.input_byte_budget = input_byte_budget
        self.reply_enabled, self.max_replies = reply_enabled, min(3, max_replies)
        self._locks = WeakValueDictionary()

    async def prepare(self, context, *, exclude_source_id, wake_key, revision):
        lock = self._locks.setdefault(context.scope_key, asyncio.Lock())
        async with lock:
            generation = await self.archive.store.get_generation(context)
            batch = await self.archive.begin(
                context, generation, exclude_source_id=exclude_source_id,
                wake_key=wake_key, revision=revision,
            )
            if batch["status"] in ("sending", "unknown"):
                return FullCatchupResult(blocked=True, reason="historical_send_unknown")
            if batch["status"] == "done":
                return FullCatchupResult(reason="already_read")
            if batch["status"] == "limited":
                return FullCatchupResult(has_more=True, reason="historical_reply_limit")
            # An unfinished batch keeps its source bound, but never reuses a
            # previously generated reply across a persona/configuration revision.
            if batch["revision"] != revision:
                batch["revision"] = revision
            summaries, read_seqs, candidates = [], [], {}
            after = 0
            while True:
                if not await self.guard(context, generation, revision):
                    return FullCatchupResult(has_more=True, reason="context_changed")
                rows = await self.archive.rows(context, batch, after=after)
                if not rows:
                    break
                for chunk in split_full_chunks(rows):
                    valid = []
                    for row in chunk:
                        event = Event.from_dict({**row["metadata_json"], "body": row["body"]})
                        if (event.idempotency_key != row["event_key"]
                                or event.context.scope_key != context.scope_key
                                or event.context.persona_revision != context.persona_revision
                                or set(event.context.audience) != set(context.audience)
                                or (event.context.account_id == context.account_id
                                    and event.context.identity_revision != context.identity_revision)
                                or not event.reliable_source
                                or event.actor_role != ActorRole.HUMAN
                                or event.actor_id != event.context.account_id
                                or event.event_type != "message"
                                or event.occurred_at > self.archive.store.clock()
                                or any(ref.kind != ContentKind.INTERACTION
                                       or (ref.expires_at is not None
                                           and ref.expires_at <= self.archive.store.clock())
                                       for ref in event.evidence)):
                            # Unknown material remains unread. It is never silently
                            # counted as successful reading or inserted in a prompt.
                            continue
                        valid.append(row)
                    if not valid:
                        after = chunk[-1]["seq"]
                        continue
                    fingerprint = stable_key(tuple(
                        (row["seq"], row["event_key"], row["body"]) for row in valid
                    ))
                    chunk_id = stable_key(batch["batch_id"], fingerprint)
                    cached = await self.archive.chunk(chunk_id)
                    if cached is None:
                        readings = []
                        for index, part in enumerate(transcript_parts(
                                valid, byte_budget=self.input_byte_budget)):
                            if not await self.guard(context, generation, revision):
                                return FullCatchupResult(tuple(summaries), has_more=True,
                                                         reason="context_changed")
                            raw = await self.read_model(
                                context, part, stable_key(chunk_id, index, revision),
                                self.reply_enabled,
                            )
                            readings.append(parse_reading(raw))
                        cached = {"summary": "\n".join(r["summary"] for r in readings),
                                  "items": [item for r in readings for item in r["items"]]}
                        if not await self.guard(context, generation, revision):
                            return FullCatchupResult(has_more=True, reason="context_changed")
                        await self.archive.save_chunk(context, batch, valid, cached)
                    summaries.append(cached["summary"])
                    sources = {row["source_id"]: row for row in valid}
                    if self.reply_enabled:
                        for item in cached["items"]:
                            if not isinstance(item, dict):
                                continue
                            source_id = item.get("source_id", item.get("msg_id"))
                            if (source_id in sources and item.get("targets_me") is True
                                    and item.get("answered") is False
                                    and item.get("expired") is False):
                                candidates.setdefault(source_id, sources[source_id])
                    read_seqs.extend(row["seq"] for row in valid)
                    after = chunk[-1]["seq"]
                # Progress is persisted as chunk receipts. There is no max-batch
                # cursor jump; model failure leaves all remaining messages unread.
                if len(rows) < 80:
                    break
            if not await self.guard(context, generation, revision):
                return FullCatchupResult(has_more=True, reason="context_changed")
            batch["value"] = {"read_seqs": read_seqs, "summaries": summaries[-8:],
                              "replies": batch["value"].get("replies", [])}
            pending = {row["seq"] for row in candidates.values()}
            for row in candidates.values():
                source_key = stable_key("historical-reply", batch["batch_id"], row["event_key"])
                if source_key in batch["value"]["replies"]:
                    pending.discard(row["seq"])
                    continue
                key = await self.archive.reserve_reply(
                    context, generation, wake_key, source_key, self.max_replies,
                )
                if key is None:
                    break
                text = await self.reply_model(context, row["body"], key)
                if not await self.guard(context, generation, revision):
                    return FullCatchupResult(has_more=True, reason="context_changed")
                batch["status"] = "sending"
                await self.archive.save_batch(context, batch)
                try:
                    result = await self.send(context, text, key, generation, revision)
                except BaseException:
                    batch["status"] = "unknown"
                    await asyncio.shield(self.archive.save_batch(context, batch))
                    raise
                if result != "confirmed":
                    batch["status"] = "unknown" if result in ("unknown", "submitted") else "submitted"
                    await self.archive.save_batch(context, batch)
                    return FullCatchupResult(tuple(summaries[-8:]), blocked=True,
                                             reason="historical_send_" + result)
                batch["value"]["replies"].append(source_key)
                pending.discard(row["seq"])
                batch["status"] = "submitted"
                await self.archive.save_batch(context, batch)
            handled = [seq for seq in read_seqs if seq not in pending]
            batch["status"] = "limited" if pending else "done"
            await self.archive.save_batch(context, batch, handled=handled)
            return FullCatchupResult(
                tuple(summaries[-8:]), len(handled), has_more=bool(pending),
                reason="historical_reply_limit" if pending else "full_reading_complete",
            )
