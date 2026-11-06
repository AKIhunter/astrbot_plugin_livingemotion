"""Pure, deterministic emotion transitions; no I/O and no model invocation.

Persist ``affect``, ``observation`` and ``runtime`` from apply_emotion together
with the event. Runtime is bounded JSON metadata, not a second public snapshot
type. Reload it before every transition, including after a CAS conflict. The
store remains responsible for durable idempotency beyond the live event TTL.
``now`` is always supplied by the caller's clock. No random choices are needed.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any, Mapping
import unicodedata

from ..contracts import (
    ActorRole, BotAffect, ContentKind, Event, EvidenceRef, HumanObservation,
    NightState, Relationship, finite, stable_key, to_dict,
)

RULE_VERSION = "emotion-1"
DIMENSIONS = ("pleasure", "arousal", "stress", "social_need")
BASELINE = (0.0, 0.3, 0.0, 0.3)

# Deltas describe the Bot's appraisal, never a copy of the speaker's feeling.
RULES = {
    "sadness": (0.0, 0.03, 0.02, -0.02),
    "anxiety": (0.0, 0.04, 0.03, -0.02),
    "joy": (0.08, 0.04, -0.02, -0.03),
    "care": (0.12, -0.02, -0.06, -0.06),
    "gratitude": (0.10, 0.02, -0.04, -0.05),
    "conflict": (-0.12, 0.12, 0.14, 0.04),
    "apology": (0.05, -0.04, -0.08, -0.02),
    "boundary_respected": (0.06, -0.02, -0.04, -0.02),
    "boundary_violated": (-0.08, 0.08, 0.12, 0.02),
    "promise_kept": (0.07, 0.01, -0.03, -0.02),
    "promise_broken": (-0.08, 0.04, 0.08, 0.02),
    "interaction": (0.01, 0.01, 0.0, -0.01),
    "reply_succeeded": (0.01, 0.0, 0.0, -0.02),
}
OBSERVATION_LABELS = {"sadness": "sad", "anxiety": "anxious", "joy": "happy"}
_SELF_REPORTS = {
    "\u6211\u5f88\u96be\u8fc7": "sadness",
    "\u6211\u5f88\u4f24\u5fc3": "sadness",
    "\u6211\u6709\u70b9\u96be\u8fc7": "sadness",
    "\u6211\u5f88\u7126\u8651": "anxiety",
    "\u6211\u5f88\u5f00\u5fc3": "joy",
    "i am sad": "sadness", "i feel sad": "sadness",
    "i am anxious": "anxiety", "i am happy": "joy",
}
_NON_EVENTS = {"dream", "diary", "summary", "fact", "legacy_unknown", "observation"}


def _number(value: Any, name: str, low: float | None = None,
            high: float | None = None) -> float:
    try:
        # JSON guard scalars need every check, but no generic dispatch. Zero
        # budget rows decode as ints too; bool/subclasses retain the old path.
        kind = type(value)
        if kind is float or kind is int:
            if not math.isfinite(value) or (low is not None and value < low) or (
                high is not None and value > high
            ):
                raise ValueError(f"{name}: out of range")
            return value if kind is float else float(value)
        finite(value, name, low, high)
    except (OverflowError, TypeError) as exc:
        raise ValueError(f"{name}: expected finite number") from exc
    return float(value)


def _integer(value: Any, name: str, low: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < low:
        raise ValueError(f"{name}: expected integer >= {low}")
    return value


@dataclass(frozen=True)
class EmotionPolicy:
    """Local rule parameters; changing the table/thresholds requires a version."""

    observation_ttl: float = 7200.0
    event_ttl: float = 7200.0
    half_lives: tuple[float, ...] = (1800.0, 1200.0, 2400.0, 3600.0)
    event_cap: float = 0.15
    similar_window: float = 300.0
    similar_limit: int = 3
    similar_budget: float = 0.30
    max_events: int = 192
    sensitivity: float = 1.0

    @property
    def baseline(self) -> tuple[float, ...]:
        return BASELINE

    def __post_init__(self) -> None:
        for name in ("observation_ttl", "event_ttl", "similar_window"):
            _number(getattr(self, name), name, 1, 86400)
        if len(self.half_lives) != 4:
            raise ValueError("half_lives: expected four dimensions")
        for value in self.half_lives:
            _number(value, "half_life", 1, 86400)
        _number(self.event_cap, "event_cap", 0, 0.15)
        _number(self.similar_budget, "similar_budget", 0, 1)
        _number(self.sensitivity, "sensitivity", 0, 1)
        _integer(self.similar_limit, "similar_limit", 1)
        _integer(self.max_events, "max_events", 1)
        if self.max_events > 192:
            raise ValueError("max_events exceeds bounded state payload budget")


def resolve_mode(*, enabled: bool = True, mode: str = "active",
                 conflict: bool = False) -> dict[str, Any]:
    if type(enabled) is not bool or type(conflict) is not bool:
        raise ValueError("enabled/conflict: expected bool")
    if mode not in ("active", "observe_only"):
        raise ValueError("mode: unsupported")
    effective = "observe_only" if conflict else mode
    return {
        "enabled": enabled, "mode": effective,
        "may_inject": enabled and effective == "active",
        "may_autonomous": enabled and effective == "active",
        "reason_codes": (() if enabled else ("disabled",))
        + (("owner_conflict",) if conflict else ()),
    }


def event_signals(event: Event) -> tuple[str, ...]:
    """Recognize only direct, complete first-person reports, not substrings."""
    if event.actor_role == ActorRole.BOT:
        return (("reply_succeeded",) if event.event_type == "bot_action_succeeded"
                else ())
    if event.actor_role != ActorRole.HUMAN or event.event_type in _NON_EVENTS:
        return ()
    signals = set(event.signals).intersection(RULES).difference({"reply_succeeded"})
    text = event.body.casefold().strip().rstrip(".!\u3002\uff01")
    if text in _SELF_REPORTS:
        signals.add(_SELF_REPORTS[text])
    return tuple(sorted(signals or {"interaction"}))


def _event_problem(event: Event, now: float, ttl: float) -> str | None:
    if not event.reliable_source:
        return "unreliable_source"
    if event.occurred_at > now:
        return "future_event"
    if now - event.occurred_at >= ttl:
        return "expired_event"
    if event.event_type in _NON_EVENTS or not event_signals(event):
        return "unsupported_event"
    if event.actor_role == ActorRole.HUMAN and (
        not event.context.account_id
        or not event.actor_id
        or event.actor_id != event.context.account_id
    ):
        return "actor_mismatch"
    if event.actor_role == ActorRole.BOT and event.actor_id != event.context.bot_id:
        return "actor_mismatch"
    return None


def _prepare_guard(runtime: Mapping[str, Any] | None, *, scope_key: str,
                   event: Event, now: float, updated_at: float, ttl: float,
                   window: float, max_events: int) -> tuple[dict[str, Any], str | None]:
    """Shared local accounting helper; copy inputs, fail closed at capacity."""
    raw = dict(runtime or {})
    if raw and (raw.get("version") != 1 or raw.get("scope_key") != scope_key):
        raise ValueError("runtime_scope_or_version_mismatch")
    last = _number(raw.get("last_event_at", updated_at), "last_event_at", 0)
    seen = []
    duplicate = False
    event_key = event.idempotency_key
    for item in raw.get("seen", ()):
        at = item["at"]
        # This full-history loop always has the same lower bound. Inline the
        # exact JSON-float checks; custom numbers retain _number's semantics.
        if type(at) is float:
            if not math.isfinite(at) or at < 0:
                raise ValueError("seen.at: out of range")
        else:
            at = _number(at, "seen.at", 0)
        if not isinstance(item["key"], str):
            raise ValueError("seen.key: expected string")
        if now - at < ttl:
            seen.append({"key": item["key"], "at": at})
            # Reuse the required validation scan; do not walk the same full
            # guard again. Even duplicate/expired rows are still validated.
            duplicate = duplicate or item["key"] == event_key
    stimuli = []
    for item in raw.get("stimuli", ()):
        at, amount = item["at"], item["amount"]
        if type(at) is float:
            if not math.isfinite(at) or at < 0:
                raise ValueError("stimulus.at: out of range")
        else:
            at = _number(at, "stimulus.at", 0)
        if type(amount) is float:
            if not math.isfinite(amount) or amount < 0:
                raise ValueError("stimulus.amount: out of range")
        else:
            amount = _number(amount, "stimulus.amount", 0)
        if not isinstance(item["key"], str):
            raise ValueError("stimulus.key: expected string")
        body_key = item.get("body_key")
        if body_key is not None and not isinstance(body_key, str):
            raise ValueError("stimulus.body_key: expected string")
        if now - at < window:
            stimuli.append({"key": item["key"], "at": at, "amount": amount,
                            "body_key": body_key})
    result = {"version": 1, "scope_key": scope_key, "last_event_at": last,
              "seen": seen, "stimuli": stimuli}
    if now < updated_at or now < last:
        return result, "clock_before_state"
    if duplicate:
        return result, "duplicate_event"
    if event.occurred_at < last:
        return result, "older_event"
    if len(seen) >= max_events or len(stimuli) >= max_events:
        return result, "guard_capacity"
    return result, None


def _stimulus_key(event: Event) -> str:
    # Use appraisal families, not caller-controlled message text or source IDs.
    return stable_key(event.context.account_key, event.actor_role,
                      event_signals(event))


def _body_key(event: Event) -> str | None:
    text = unicodedata.normalize("NFKC", event.body[:4096]).casefold()
    normalized = "".join(character for character in text if character.isalnum())
    return stable_key(event.context.account_key, normalized) if normalized else None


def _stimulus_allowance(runtime: Mapping[str, Any], event: Event, *,
                        limit: int, budget: float) -> float:
    family, body = _stimulus_key(event), _body_key(event)
    rows = [r for r in runtime["stimuli"]
            if r["key"] == family or (body is not None and r.get("body_key") == body)]
    if len(rows) >= limit:
        return 0.0
    return max(0.0, budget - sum(r["amount"] for r in rows))


def _record_guard(runtime: dict[str, Any], event: Event, amount: float) -> None:
    runtime["last_event_at"] = event.occurred_at
    runtime["seen"].append({"key": event.idempotency_key, "at": event.occurred_at})
    runtime["stimuli"].append({"key": _stimulus_key(event),
                               "at": event.occurred_at, "amount": amount,
                               "body_key": _body_key(event)})


def _source(event: Event, *, expires_at: float) -> EvidenceRef:
    return EvidenceRef(
        provider=event.producer, source_id=event.source_id, context=event.context,
        subject_id=event.actor_id, holder_id=event.actor_id,
        kind=(ContentKind.INTERACTION if event.actor_role == ActorRole.HUMAN
              else ContentKind.BOT_ACTION),
        occurred_at=event.occurred_at, expires_at=expires_at,
    )


def _labels(values: tuple[float, ...], *, concern: bool = False) -> tuple[str, ...]:
    pleasure, arousal, stress, social_need = values
    labels = []
    if stress >= 0.55:
        labels.append("strained")
    elif stress >= 0.12:
        labels.append("tense")
    if concern:
        labels.append("concerned")
    if pleasure >= 0.15:
        labels.append("content")
    elif pleasure <= -0.20:
        labels.append("subdued")
    if arousal >= 0.65:
        labels.append("alert")
    if social_need >= 0.65:
        labels.append("seeking_company")
    return tuple(labels or ["calm"])


def decay_affect(state: BotAffect, *, now: float,
                 policy: EmotionPolicy = EmotionPolicy()) -> BotAffect:
    _number(now, "now", 0)
    if now <= state.updated_at:
        return state
    elapsed = now - state.updated_at
    values = tuple(
        baseline + (getattr(state, name) - baseline) * 2 ** (-elapsed / half_life)
        for name, baseline, half_life in zip(DIMENSIONS, policy.baseline, policy.half_lives)
    )
    evidence = tuple(ref for ref in state.evidence
                     if ref.expires_at is not None and ref.expires_at > now)
    concern = "appraisal_concern" in state.reason_codes and bool(evidence)
    return BotAffect(**dict(zip(DIMENSIONS, values)), updated_at=now,
                     labels=_labels(values, concern=concern), evidence=evidence,
                     reason_codes=(("appraisal_concern", "time_decay") if concern
                                   else ("time_decay",)),
                     rule_version=RULE_VERSION)


def observe_human(event: Event, *, now: float,
                  previous: HumanObservation | None = None,
                  policy: EmotionPolicy = EmotionPolicy()) -> HumanObservation | None:
    _number(now, "now", 0)
    if previous is not None and previous.subject_id != event.actor_id:
        raise ValueError("observation_subject_mismatch")
    if previous is not None and any(
        ref.context.account_key != event.context.account_key for ref in previous.evidence
    ):
        raise ValueError("observation_scope_mismatch")
    if previous is not None and previous.expires_at <= now:
        previous = None
    if (event.actor_role != ActorRole.HUMAN
            or _event_problem(event, now, min(policy.event_ttl, policy.observation_ttl))
            or (previous is not None and event.occurred_at <= previous.occurred_at)):
        return previous
    labels = tuple(OBSERVATION_LABELS[s] for s in event_signals(event)
                   if s in OBSERVATION_LABELS)
    if not labels or event.confidence == 0:
        return previous
    expires_at = event.occurred_at + policy.observation_ttl
    return HumanObservation(
        subject_id=event.actor_id, labels=labels, confidence=event.confidence,
        occurred_at=event.occurred_at, expires_at=expires_at,
        evidence=(_source(event, expires_at=expires_at),),
    )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _model_delta(value: Any, cap: float) -> tuple[float, ...]:
    if isinstance(value, str):
        if len(value) > 4096:
            raise ValueError("model_output_too_long")
        text = value.strip()
        if text.startswith("```json\n") and text.endswith("\n```"):
            text = text[8:-4]
        value = json.loads(text, object_pairs_hook=_unique_object)
    if not isinstance(value, Mapping) or set(value) - {"rule_version", "delta", "confidence"}:
        raise ValueError("model_schema")
    if value.get("rule_version") != RULE_VERSION:
        raise ValueError("model_version")
    delta = value.get("delta")
    if not isinstance(delta, Mapping) or not delta or set(delta) - set(DIMENSIONS):
        raise ValueError("model_delta_schema")
    confidence = _number(value.get("confidence", 1), "model_confidence", 0, 1)
    return tuple(_number(delta.get(name, 0), name, -cap, cap) * confidence
                 for name in DIMENSIONS)


def apply_emotion(
    state: BotAffect, event: Event, *, now: float,
    observation: HumanObservation | None = None,
    relationship: Relationship | None = None, night: NightState | None = None,
    runtime: Mapping[str, Any] | None = None, model_suggestion: Any = None,
    policy: EmotionPolicy = EmotionPolicy(), enabled: bool = True,
    mode: str = "active", conflict: bool = False,
) -> dict[str, Any]:
    """Return typed snapshots, JSON runtime and trace; never commit or send.

    ``runtime`` belongs to context.scope_key, observation to context.account_key.
    may_autonomous is mode eligibility only, not permission to bypass hard gates.
    """
    _number(now, "now", 0)
    control = resolve_mode(enabled=enabled, mode=mode, conflict=conflict)
    if any(ref.context.scope_key != event.context.scope_key for ref in state.evidence):
        raise ValueError("affect_scope_mismatch")
    if observation is not None and any(
        ref.context.account_key != event.context.account_key for ref in observation.evidence
    ):
        raise ValueError("observation_scope_mismatch")
    base = decay_affect(state, now=now, policy=policy) if enabled else state
    result = {
        "affect": base, "observation": observation, "runtime": dict(runtime or {}),
        "applied": False, "control": control, "reason_codes": (),
        "trace": {"event_key": event.idempotency_key, "event_id": event.event_id,
                  "occurred_at": event.occurred_at, "processed_at": now,
                  "holder_id": event.context.bot_id, "subject_id": event.actor_id,
                  "confidence": event.confidence, "rule_version": RULE_VERSION,
                  "before": to_dict(state), "after": to_dict(base)},
    }
    if not enabled:
        result["reason_codes"] = ("disabled",)
        return result
    if observation is not None:
        if observation.subject_id != event.context.account_id:
            raise ValueError("observation_subject_mismatch")
        if observation.expires_at <= now:
            result["observation"] = None
    problem = _event_problem(event, now, policy.event_ttl)
    if problem:
        result["reason_codes"] = (problem,)
        return result
    guard, problem = _prepare_guard(
        runtime, scope_key=event.context.scope_key, event=event, now=now,
        updated_at=state.updated_at, ttl=policy.event_ttl,
        window=policy.similar_window, max_events=policy.max_events,
    )
    result["runtime"] = guard
    if problem:
        result["reason_codes"] = (problem,)
        return result
    allowance = _stimulus_allowance(guard, event, limit=policy.similar_limit,
                                    budget=policy.similar_budget)
    if allowance <= 0:
        _record_guard(guard, event, 0.0)
        result["reason_codes"] = ("similar_stimulus_limited",)
        return result
    signals = event_signals(event)
    weight = event.confidence * policy.sensitivity
    if relationship is not None:
        weight *= 0.75 + 0.25 * relationship.normalized
    delta = [sum(RULES[s][i] for s in signals) * weight for i in range(4)]
    reasons = ["rule_" + signal for signal in signals]
    if model_suggestion is not None:
        try:
            refinement = _model_delta(model_suggestion, policy.event_cap)
            if set(signals) <= {"sadness", "anxiety"} and refinement[0] < 0:
                raise ValueError("observation_is_not_bot_pleasure")
            delta = [d + r * weight * 0.5 for d, r in zip(delta, refinement)]
            reasons.append("model_refined")
        except (ValueError, TypeError, OverflowError, RecursionError):
            reasons.append("model_invalid_rule_fallback")
    if night is not None and delta[1] > 0:
        delta[1] *= 0.5 + night.energy / 200.0
    delta = [max(-policy.event_cap, min(policy.event_cap, d)) for d in delta]
    magnitude = max(abs(d) for d in delta)
    scale = min(1.0, allowance / magnitude) if magnitude else 1.0
    # A late but still fresh event arrives already decayed, not freshly revived.
    delta = [d * scale * 2 ** (-(now - event.occurred_at) / half_life)
             for d, half_life in zip(delta, policy.half_lives)]
    values = tuple(max(-1.0 if name == "pleasure" else 0.0,
                       min(1.0, getattr(base, name) + d))
                   for name, d in zip(DIMENSIONS, delta))
    amount = magnitude * scale
    _record_guard(guard, event, amount)
    concern = bool(set(signals) & {"sadness", "anxiety"}) and weight > 0
    if concern:
        reasons.append("appraisal_concern")
    evidence = ((_source(event, expires_at=event.occurred_at + policy.event_ttl),)
                if weight > 0 else base.evidence)
    affect = BotAffect(**dict(zip(DIMENSIONS, values)), updated_at=now,
                       labels=_labels(values, concern=concern), evidence=evidence,
                       reason_codes=tuple(reasons), rule_version=RULE_VERSION)
    result.update(
        affect=affect,
        observation=observe_human(event, now=now, previous=result["observation"],
                                  policy=policy) if event.actor_role == ActorRole.HUMAN
        else result["observation"],
        applied=amount > 0, reason_codes=tuple(reasons),
    )
    result["trace"]["after"] = to_dict(affect)
    return result


def expression_context(
    state: BotAffect, observation: HumanObservation | None, *, now: float,
    enabled: bool = True, mode: str = "active", conflict: bool = False,
    policy: EmotionPolicy = EmotionPolicy(),
) -> dict[str, Any]:
    """Separate holders in structured hints; contains no copied persona/prompt."""
    _number(now, "now", 0)
    if not resolve_mode(enabled=enabled, mode=mode, conflict=conflict)["may_inject"]:
        return {}
    state = decay_affect(state, now=now, policy=policy)
    return {
        "namespace": "livingEmotion",
        "bot": {"holder": "bot", **{name: getattr(state, name) for name in DIMENSIONS},
                "labels": state.labels},
        "human_observation": (
            {"holder": observation.subject_id, "labels": observation.labels,
             "confidence": observation.confidence, "expires_at": observation.expires_at}
            if observation is not None and observation.occurred_at <= now < observation.expires_at
            else None),
    }
