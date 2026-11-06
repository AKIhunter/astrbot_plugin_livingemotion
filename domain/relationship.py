"""Source-account relationship transitions and authorized ledger projections.

Persist relationship, runtime, contributions and audit in the same transaction.
Every contribution must be stored alongside the event's original Context.
There is no identity binding table or database access in this module. The caller
supplies current authorization and checks its revision again before any use.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

from ..contracts import (
    ActorRole, Context, Event, Relationship, RelationshipContribution, SceneKind,
    stable_key, to_dict,
)
from .emotion import (
    _event_problem, _integer, _number, _prepare_guard, _record_guard,
    _stimulus_allowance, event_signals, resolve_mode,
)

RULE_VERSION = "relationship-1"
SCORE_RULES = {
    "interaction": 0.5, "sadness": 0.5, "anxiety": 0.5, "joy": 1.0,
    "care": 3.0, "gratitude": 2.0, "conflict": -5.0, "apology": 2.0,
    "boundary_respected": 3.0, "boundary_violated": -5.0,
    "promise_kept": 4.0, "promise_broken": -6.0,
}
DIMENSION_RULES = {
    "promise_kept": ("trust", 0.02),
    "promise_broken": ("trust", -0.02),
    "boundary_respected": ("boundary", 0.03),
    "boundary_violated": ("boundary", -0.03),
}


@dataclass(frozen=True)
class RelationshipPolicy:
    """Rule-local configuration, not a replacement shared Relationship type."""

    event_cap: float = 6.0
    daily_budget: float = 24.0
    event_ttl: float = 7200.0
    similar_window: float = 300.0
    similar_limit: int = 3
    similar_budget: float = 9.0
    max_events: int = 192
    timezone: str = "UTC"

    def __post_init__(self) -> None:
        _number(self.event_cap, "event_cap", 0, 10)
        _number(self.daily_budget, "daily_budget", 0, 100)
        _number(self.event_ttl, "event_ttl", 1, 86400)
        _number(self.similar_window, "similar_window", 1, 86400)
        _number(self.similar_budget, "similar_budget", 0, 100)
        _integer(self.similar_limit, "similar_limit", 1)
        _integer(self.max_events, "max_events", 1)
        if self.max_events > 192:
            raise ValueError("max_events exceeds bounded state payload budget")
        if not isinstance(self.timezone, str):
            raise ValueError("timezone: expected IANA name")
        try:
            ZoneInfo(self.timezone)
        except (KeyError, ValueError) as exc:
            raise ValueError("timezone: expected IANA name") from exc


def _day(at: float, policy: RelationshipPolicy) -> str:
    try:
        return datetime.fromtimestamp(at, timezone.utc).astimezone(
            ZoneInfo(policy.timezone)).date().isoformat()
    except (OverflowError, OSError, ValueError) as exc:
        raise ValueError("timestamp outside supported calendar") from exc


def relationship_stage(score: float) -> str:
    _number(score, "score", 0, 1000)
    for ceiling, label in (
        (100, "unestablished"), (300, "acquainted"),
        (600, "familiar"), (850, "close"),
    ):
        if score < ceiling:
            return label
    return "trusted"


def _budgets(runtime: Mapping[str, Any] | None, *, now: float,
             policy: RelationshipPolicy) -> dict[str, float]:
    # Fresh delayed events can belong to yesterday; keep its budget at midnight.
    earliest = _day(max(0.0, now - policy.event_ttl), policy)
    latest = _day(now, policy)
    result = {}
    for day, used in (runtime or {}).get("days", {}).items():
        if not isinstance(day, str):
            raise ValueError("budget.day: expected ISO date")
        try:
            if datetime.strptime(day, "%Y-%m-%d").date().isoformat() != day:
                raise ValueError("noncanonical date")
        except ValueError as exc:
            raise ValueError("budget.day: expected ISO date") from exc
        amount = _number(used, "budget.used", 0)
        if day >= earliest:
            # Future buckets are retained through clock rollback, never refunded.
            result[day] = amount
    if len(result) > 4:
        raise ValueError("budget calendar inconsistent with event horizon")
    result.setdefault(latest, 0.0)
    return result


def _contribution(event: Event, day: str, delta: float,
                  reason: str, dimension: str = "score") -> RelationshipContribution:
    return RelationshipContribution(
        source_id=event.idempotency_key, account_id=event.context.account_id,
        occurred_at=event.occurred_at, delta=delta, reason_code=reason,
        day=day, dimension=dimension,
    )


def apply_relationship(
    state: Relationship, event: Event, *, now: float,
    runtime: Mapping[str, Any] | None = None,
    policy: RelationshipPolicy = RelationshipPolicy(),
    enabled: bool = True, mode: str = "active", conflict: bool = False,
) -> dict[str, Any]:
    """Apply one real human event using persisted absolute daily accounting.

    Runtime belongs to context.account_key, not OneID. Proposed absolute motion
    is charged even at score saturation or when opposite signals cancel. A
    frozen relationship consumes the event guard but no score/dimension budget.
    """
    _number(now, "now", 0)
    control = resolve_mode(enabled=enabled, mode=mode, conflict=conflict)
    result = {
        "relationship": state, "runtime": dict(runtime or {}),
        "contributions": (), "applied": False, "reason_codes": (),
        "trace": {"event_key": event.idempotency_key, "event_id": event.event_id,
                  "occurred_at": event.occurred_at, "processed_at": now,
                  "rule_version": RULE_VERSION, "before": to_dict(state),
                  "after": to_dict(state), "charged": 0.0},
    }
    if not control["enabled"]:
        result["reason_codes"] = ("disabled",)
        return result
    problem = _event_problem(event, now, policy.event_ttl)
    if problem or event.actor_role != ActorRole.HUMAN:
        result["reason_codes"] = (problem or "human_evidence_required",)
        return result
    if ("manual_correction" in state.reason_codes
            and event.occurred_at < state.updated_at):
        result["reason_codes"] = ("older_than_manual_correction",)
        return result
    guard, problem = _prepare_guard(
        runtime, scope_key=event.context.account_key, event=event, now=now,
        updated_at=state.updated_at, ttl=policy.event_ttl,
        window=policy.similar_window, max_events=policy.max_events,
    )
    guard["days"] = _budgets(runtime, now=now, policy=policy)
    result["runtime"] = guard
    if problem:
        result["reason_codes"] = (problem,)
        return result
    if state.frozen:
        _record_guard(guard, event, 0)
        result["reason_codes"] = ("relationship_frozen",)
        return result
    day = _day(event.occurred_at, policy)
    available = max(0.0, policy.daily_budget - guard["days"].get(day, 0.0))
    similar = _stimulus_allowance(guard, event, limit=policy.similar_limit,
                                  budget=policy.similar_budget)
    limit = min(policy.event_cap, available, similar)
    if limit <= 0:
        _record_guard(guard, event, 0)
        result["reason_codes"] = (
            "daily_budget_exhausted" if available <= 0
            else "similar_stimulus_limited" if similar <= 0
            else "event_budget_disabled",)
        return result
    signals = event_signals(event)
    proposed = [SCORE_RULES[s] * event.confidence for s in signals if s in SCORE_RULES]
    absolute = sum(abs(value) for value in proposed)
    if absolute == 0:
        _record_guard(guard, event, 0)
        result["reason_codes"] = ("no_confident_evidence",)
        return result
    charged = min(limit, absolute)
    scale = charged / absolute
    score = max(0.0, min(1000.0, state.score + sum(proposed) * scale))
    changes = []
    reasons = tuple("rule_" + signal for signal in signals)
    if score != state.score:
        changes.append(_contribution(event, day, score - state.score,
                                     "interaction_appraisal"))
    dimensions = {name: getattr(state, name) for name in ("trust", "familiarity", "boundary")}
    dimension_deltas = {"familiarity": 0.005 * event.confidence * scale}
    for signal in signals:
        if signal in DIMENSION_RULES:
            dimension, delta = DIMENSION_RULES[signal]
            dimension_deltas[dimension] = (
                dimension_deltas.get(dimension, 0.0) + delta * event.confidence * scale)
    for name, delta in dimension_deltas.items():
        if delta == 0:
            continue
        previous = dimensions[name]
        start = (0.0 if name == "familiarity" else 0.5) if previous is None else previous
        value = max(0.0, min(1.0, start + delta))
        dimensions[name] = value
        # An initial measured value is evidence, not a guessed legacy dimension.
        changes.append(_contribution(event, day, value - (previous or 0.0),
                                     "observed_" + name, name))
    guard["days"][day] = guard["days"].get(day, 0.0) + charged
    _record_guard(guard, event, charged)
    updated = replace(
        state, score=score, stage=relationship_stage(score), **dimensions,
        identity_revision=event.context.identity_revision, updated_at=now,
        reason_codes=reasons,
    )
    result.update(relationship=updated, contributions=tuple(changes),
                  applied=bool(changes), reason_codes=reasons)
    result["trace"].update(after=to_dict(updated), charged=charged, day=day)
    return result


def correct_relationship(
    state: Relationship, context: Context, *, now: float, actor_id: str,
    reason: str, expected_version: int, current_version: int,
    score: float | None = None, frozen: bool | None = None,
    policy: RelationshipPolicy = RelationshipPolicy(),
) -> dict[str, Any]:
    """Authenticated admin service only: CAS correction plus append-only audit.

    actor_id is an audit identity, NOT authentication. Caller must authorize it.
    No daily runtime is returned: a correction never refunds automatic budgets.
    Commit the audit, contributions, snapshot and new version atomically.
    """
    _number(now, "now", state.updated_at)
    _integer(expected_version, "expected_version")
    _integer(current_version, "current_version")
    if expected_version != current_version:
        raise ValueError("version_conflict")
    for name, value in (("actor_id", actor_id), ("reason", reason),
                        ("account_id", context.account_id)):
        if not isinstance(value, str) or not value.strip() or len(value) > 512:
            raise ValueError(f"{name}: required nonempty text, maximum 512")
    if score is None and frozen is None:
        raise ValueError("correction_requires_change")
    if score is not None:
        _number(score, "score", 0, 1000)
    if frozen is not None and type(frozen) is not bool:
        raise ValueError("frozen: expected bool")
    updated = replace(
        state, score=state.score if score is None else score,
        stage=relationship_stage(state.score if score is None else score),
        frozen=state.frozen if frozen is None else frozen, updated_at=now,
        identity_revision=context.identity_revision,
        reason_codes=("manual_correction",),
    )
    version = current_version + 1
    operation_id = stable_key(context.account_key, "manual_relationship", version)
    audit = {
        "operation_id": operation_id, "actor_id": actor_id, "reason": reason,
        "scope_key": context.scope_key, "account_id": context.account_id,
        "occurred_at": now, "expected_version": expected_version, "version": version,
        "rule_version": RULE_VERSION, "before": to_dict(state), "after": to_dict(updated),
    }
    contributions = ()
    if updated.score != state.score:
        contributions = (RelationshipContribution(
            source_id=operation_id, account_id=context.account_id, occurred_at=now,
            delta=updated.score - state.score, reason_code="manual_correction",
            day=_day(now, policy),
        ),)
    return {"relationship": updated, "version": version, "audit": audit,
            "contributions": contributions}


def project_relationship(
    contributions: Iterable[tuple[Context, RelationshipContribution]], *,
    context: Context, authorized_account_keys: Iterable[str] | None = None,
    identity_revision: str,
) -> Relationship:
    """Recompute from immutable source rows under a *current* authorized grant.

    None means only the current source account. An explicit empty grant means
    nothing. Raw IDs, matching names and historical identity revisions are not
    authorization. No prior aggregate snapshot is accepted as new evidence.
    Normalized dimensions are averaged over known source accounts, not added
    into artificial certainty.
    """
    if identity_revision != context.identity_revision:
        raise ValueError("identity_revision_changed")
    allowed = ({context.account_key} if authorized_account_keys is None
               else set(authorized_account_keys))
    totals = {"score": 0.0, "trust": 0.0, "familiarity": 0.0, "boundary": 0.0}
    source_dimensions: dict[tuple[str, str], float] = {}
    seen = {}
    updated_at = 0.0
    complete = True
    for source, row in contributions:
        if source.account_key not in allowed:
            continue
        if (source.instance_id != context.instance_id
                or source.bot_id != context.bot_id
                or source.persona_id != context.persona_id
                or source.scene_kind != context.scene_kind):
            continue
        if (source.account_key == context.account_key
                and set(source.audience) != set(context.audience)):
            continue
        if source.scene_kind != SceneKind.PRIVATE and (
                source.scope_key != context.scope_key
                or set(source.audience) != set(context.audience)):
            continue
        if (source.account_key != context.account_key
                and (source.platform, source.account_id) == (context.platform, context.account_id)):
            continue
        if row.account_id != source.account_id:
            raise ValueError("contribution_account_mismatch")
        if row.dimension not in totals:
            complete = False
            continue
        key = (source.account_key, row.source_id, row.dimension)
        if key in seen:
            if seen[key] != row:
                raise ValueError("conflicting_contribution")
            continue
        seen[key] = row
        totals[row.dimension] += row.delta
        _number(totals[row.dimension], "projection_total")
        if row.dimension != "score":
            source_key = (source.account_key, row.dimension)
            source_dimensions[source_key] = source_dimensions.get(source_key, 0.0) + row.delta
        updated_at = max(updated_at, row.occurred_at)
    score = max(0.0, min(1000.0, totals["score"]))
    dimensions = {}
    for name in ("trust", "familiarity", "boundary"):
        measurements = [max(0.0, min(1.0, value))
                        for (_, dimension), value in source_dimensions.items()
                        if dimension == name]
        dimensions[name] = sum(measurements) / len(measurements) if measurements else None
    return Relationship(
        score=score, stage=relationship_stage(score), **dimensions,
        evidence_complete=complete, identity_revision=identity_revision,
        updated_at=updated_at, reason_codes=("authorized_source_projection",),
    )
