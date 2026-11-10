"""Pure night transitions. This module is the sole writer of night energy."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from typing import Any, Mapping

from ..contracts import (
    ActorRole, Availability, Context, Event, IntentStatus, NightPhase, NightState,
    SleepState, canonical_json, finite, stable_key,
)

RULE_VERSION = "night-1"


@dataclass(frozen=True)
class NightPolicy:
    awake_cost_per_hour: float = 4.0
    sleep_gain_per_hour: float = 12.0
    drowsy_threshold: float = 30.0
    max_sleep_seconds: float = 57600.0
    settling_timeout: float = 120.0
    waking_timeout: float = 300.0
    interaction_cost: float = 0.2
    interaction_window: float = 300.0
    interaction_budget: float = 2.0
    event_ttl: float = 7200.0
    dedup_capacity: int = 192

    def __post_init__(self) -> None:
        for name in ("awake_cost_per_hour", "sleep_gain_per_hour",
                     "drowsy_threshold", "interaction_cost", "interaction_budget"):
            finite(getattr(self, name), name, 0, 100)
        for name, maximum in (("max_sleep_seconds", 86400), ("settling_timeout", 600),
                              ("waking_timeout", 3600), ("interaction_window", 3600),
                              ("event_ttl", 86400)):
            finite(getattr(self, name), name, 1, maximum)
        if type(self.dedup_capacity) is not int or not 1 <= self.dedup_capacity <= 192:
            raise ValueError("invalid dedup_capacity")


@dataclass(frozen=True)
class ReplyReceipt:
    """Transport-confirmed outcome, not generated text or a user-supplied claim."""

    context: Context
    status: IntentStatus
    occurred_at: float
    request_id: str | None = None
    message_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", IntentStatus(self.status))
        finite(self.occurred_at, "occurred_at", 0)
        for value in (self.request_id, self.message_id):
            _identifier(value)
        if self.request_id is None and self.message_id is None:
            raise ValueError("receipt requires a request or message ID")


def _identifier(value: str | None) -> None:
    if value is not None and (
        not isinstance(value, str) or not value.strip() or len(value) > 512
    ):
        raise ValueError("invalid reply ID")


def _counter(value: int, name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"invalid {name}")


def _validate(state: NightState, now: float) -> None:
    finite(now, "now", 0)
    _counter(state.unread_watermark, "unread_watermark")
    if state.phase == NightPhase.ASLEEP and (
        state.sleep_started_at is None or state.sleep_started_at > state.updated_at
    ):
        raise ValueError("asleep state requires a settled sleep start")
    if state.phase in (NightPhase.SETTLING, NightPhase.WAKING):
        if state.transition_deadline is None:
            raise ValueError("transition requires an absolute deadline")


def _awake(state: NightState, reason: str, policy: NightPolicy,
           *, force: bool = False) -> NightState:
    phase = NightPhase.AWAKE if force or state.energy > policy.drowsy_threshold else (
        NightPhase.DROWSY
    )
    return replace(state, phase=phase, sleep_started_at=None, wake_at=None,
                   transition_deadline=None, sleep_stage=None, awaiting_reply_id=None,
                   reason_codes=(reason,))


def _energy(value: float, elapsed: float, rate: float) -> float:
    return min(100.0, max(0.0, value + elapsed / 3600.0 * rate))


def sleep_stage(sleep_started_at: float, *, now: float) -> str:
    """A product timing model, not a measurement of biological sleep."""
    finite(sleep_started_at, "sleep_started_at", 0)
    finite(now, "now", 0)
    position = max(0.0, now - sleep_started_at) % 5400.0
    for boundary, stage in ((300, "N1"), (1500, "N2"), (3600, "N3"), (5400, "REM")):
        if position < boundary:
            return stage
    raise AssertionError("unreachable stage")


def advance_night(
    state: NightState, *, now: float, policy: NightPolicy = NightPolicy(),
    enabled: bool = True, recovering: bool = False,
) -> NightState:
    """Settle elapsed time once; recovery never replays missed actions."""
    _validate(state, now)
    effective = max(state.updated_at, now)
    rollback = now < state.updated_at
    result = state
    if state.phase == NightPhase.ASLEEP:
        end = min(state.wake_at if state.wake_at is not None else float("inf"),
                  state.sleep_started_at + policy.max_sleep_seconds)
        asleep_elapsed = max(0.0, min(effective, end) - state.updated_at)
        energy = _energy(state.energy, asleep_elapsed, policy.sleep_gain_per_hour)
        energy = _energy(energy, max(0.0, effective - max(end, state.updated_at)),
                         -policy.awake_cost_per_hour)
        result = replace(state, energy=energy, updated_at=effective)
        if effective >= end:
            deadline = (effective if recovering else end) + policy.waking_timeout
            finite(deadline, "waking deadline", 0)
            result = replace(result, phase=NightPhase.WAKING, wake_at=end,
                             transition_deadline=deadline, sleep_stage=None,
                             awaiting_reply_id=None,
                             reason_codes=("offline_wake" if recovering else "natural_wake",))
        else:
            result = replace(result, sleep_stage=sleep_stage(state.sleep_started_at,
                                                             now=effective))
    else:
        result = replace(state, updated_at=effective, energy=_energy(
            state.energy, effective - state.updated_at, -policy.awake_cost_per_hour
        ))

    if not enabled:
        result = _awake(result, "night_disabled", policy, force=True)
    elif result.phase == NightPhase.SETTLING and effective >= result.transition_deadline:
        result = _awake(result, "settling_timeout", policy)
    elif result.phase == NightPhase.WAKING and effective >= result.transition_deadline:
        result = _awake(result, "waking_timeout", policy)
    elif result.phase in (NightPhase.AWAKE, NightPhase.DROWSY):
        phase = NightPhase.DROWSY if result.energy <= policy.drowsy_threshold else NightPhase.AWAKE
        if phase != result.phase:
            result = replace(result, phase=phase, reason_codes=("energy_threshold",))
    if rollback:
        result = replace(result, reason_codes=tuple(dict.fromkeys(
            (*result.reason_codes, "clock_rollback")
        )))
    return result


def _reply_hash(context: Context, kind: str, value: str | None) -> str | None:
    if value is None:
        return None
    return stable_key(context.scope_key, context.persona_revision,
                      context.identity_revision, sorted(set(context.audience)), kind, value)


def begin_sleep(
    state: NightState, context: Context, *, now: float, wake_at: float,
    request_id: str | None = None, message_id: str | None = None,
    manual: bool = False, policy: NightPolicy = NightPolicy(), enabled: bool = True,
) -> NightState:
    """Register pending final reply, or sleep immediately when none is pending."""
    _identifier(request_id)
    _identifier(message_id)
    finite(wake_at, "wake_at", 0)
    result = advance_night(state, now=now, policy=policy, enabled=enabled)
    if not enabled:
        return result
    if now < state.updated_at:
        return result
    if not now < wake_at <= now + policy.max_sleep_seconds:
        raise ValueError("sleep window must be positive and bounded")
    if result.phase in (NightPhase.SETTLING, NightPhase.ASLEEP, NightPhase.WAKING):
        return result
    pending = request_id is not None or message_id is not None
    if manual and pending:
        raise ValueError("manual sleep must not masquerade as a reply receipt")
    if pending:
        token = canonical_json({
            "v": 1, "at": now,
            "request": _reply_hash(context, "request", request_id),
            "message": _reply_hash(context, "message", message_id),
        })
        return replace(result, phase=NightPhase.SETTLING, wake_at=wake_at,
                       sleep_started_at=None, sleep_stage=None, awaiting_reply_id=token,
                       transition_deadline=min(wake_at, now + policy.settling_timeout),
                       reason_codes=("awaiting_successful_reply",))
    return replace(result, phase=NightPhase.ASLEEP, sleep_started_at=now,
                   wake_at=wake_at, sleep_stage="N1", transition_deadline=None,
                   awaiting_reply_id=None,
                   reason_codes=("manual_sleep" if manual else "scheduled_sleep",))


def apply_reply_receipt(
    state: NightState, receipt: ReplyReceipt, *, now: float,
    policy: NightPolicy = NightPolicy(), enabled: bool = True,
) -> NightState:
    result = advance_night(state, now=now, policy=policy, enabled=enabled)
    if result.phase != NightPhase.SETTLING or now < state.updated_at:
        return result
    if receipt.status != IntentStatus.SUCCEEDED:
        return replace(result, reason_codes=("reply_not_succeeded",))
    try:
        token = json.loads(result.awaiting_reply_id or "")
        finite(token["at"], "reply registered at", 0)
        matches = [
            token[kind] == _reply_hash(receipt.context, kind, value)
            for kind, value in (("request", receipt.request_id), ("message", receipt.message_id))
            if token.get(kind) is not None and value is not None
        ]
        valid = token["v"] == 1 and matches and all(matches)
        valid = valid and token["at"] <= receipt.occurred_at <= now
    except (ValueError, KeyError, TypeError):
        valid = False
    if not valid:
        return replace(result, reason_codes=("reply_mismatch",))
    if result.wake_at is None or result.wake_at <= now:
        return _awake(result, "sleep_window_elapsed", policy)
    # Never backdate sleep into time already settled as awake while waiting.
    return replace(result, phase=NightPhase.ASLEEP, sleep_started_at=now,
                   sleep_stage="N1", transition_deadline=None, awaiting_reply_id=None,
                   reason_codes=("successful_reply_settled",))


def wake_night(
    state: NightState, *, now: float, reason: str = "called",
    policy: NightPolicy = NightPolicy(), enabled: bool = True,
) -> NightState:
    if reason not in ("called", "manual"):
        raise ValueError("wake reason must be called or manual")
    result = advance_night(state, now=now, policy=policy, enabled=enabled)
    if not enabled or now < state.updated_at:
        return result
    if result.phase == NightPhase.SETTLING:
        return _awake(result, f"{reason}_wake", policy, force=True)
    if result.phase != NightPhase.ASLEEP:
        return result
    return replace(result, phase=NightPhase.WAKING, wake_at=now,
                   transition_deadline=now + policy.waking_timeout,
                   sleep_stage=None, awaiting_reply_id=None,
                   reason_codes=(f"{reason}_wake",))


def finish_waking(
    state: NightState, *, now: float, policy: NightPolicy = NightPolicy(),
    enabled: bool = True,
) -> NightState:
    result = advance_night(state, now=now, policy=policy, enabled=enabled)
    if result.phase == NightPhase.WAKING and now >= state.updated_at:
        return _awake(result, "catchup_complete", policy)
    return result


def night_availability(
    state: NightState, *, now: float, block_chat: bool = False,
    exempt: bool = False, enabled: bool = True, policy: NightPolicy = NightPolicy(),
) -> Availability:
    """`exempt` must come from a verified wake/admin entry, not message content."""
    current = advance_night(state, now=now, policy=policy, enabled=enabled)
    if not enabled or exempt:
        return Availability(True, ("night_disabled" if not enabled else "night_exempt",))
    unavailable = current.phase in (NightPhase.SETTLING, NightPhase.ASLEEP, NightPhase.WAKING)
    return Availability(not unavailable, (f"night_{current.phase.value}",),
                        block_chat=bool(block_chat and unavailable))


def apply_interaction(
    state: NightState, event: Event, *, context: Context, now: float,
    runtime: Mapping[str, Any] | None = None, policy: NightPolicy = NightPolicy(),
    enabled: bool = True,
) -> dict[str, Any]:
    """Bounded human interaction cost; persist runtime with the event and state."""
    result = advance_night(state, now=now, policy=policy, enabled=enabled)
    data = dict(runtime or {})
    if data.get("scope_key", context.scope_key) != context.scope_key:
        raise ValueError("interaction runtime scope mismatch")
    seen = dict(data.get("seen", {}))
    charges = list(data.get("charges", ()))
    for at in seen.values():
        finite(at, "dedup expiry", 0)
    for at, cost in charges:
        finite(at, "charge time", 0)
        finite(cost, "charge cost", 0, 100)
    if len(seen) > policy.dedup_capacity or len(charges) > policy.dedup_capacity:
        raise ValueError("interaction runtime exceeds capacity")
    effective = result.updated_at
    seen = {key: expiry for key, expiry in seen.items() if expiry >= effective}
    charges = [(at, cost) for at, cost in charges if at > effective - policy.interaction_window]
    reason = "interaction_applied"
    cost = 0.0
    if not enabled:
        reason = "night_disabled"
    elif event.context.scope_key != context.scope_key or (
        event.context.persona_revision != context.persona_revision
        or event.context.identity_revision != context.identity_revision
        or set(event.context.audience) != set(context.audience)
    ):
        reason = "interaction_scope_mismatch"
    elif event.actor_role != ActorRole.HUMAN or event.event_type != "message" or (
        not event.actor_id or event.actor_id != event.context.account_id
        or not event.reliable_source
        or any(ref.kind.value != "interaction" for ref in event.evidence)
    ):
        reason = "unsupported_interaction"
    elif now < state.updated_at or event.occurred_at > now:
        reason = "interaction_clock_mismatch"
    elif event.occurred_at < now - policy.event_ttl:
        reason = "interaction_expired"
    elif event.idempotency_key in seen:
        reason = "duplicate_interaction"
    elif len(seen) >= policy.dedup_capacity or len(charges) >= policy.dedup_capacity:
        reason = "guard_capacity"
    else:
        seen[event.idempotency_key] = event.occurred_at + policy.event_ttl
        if result.phase in (NightPhase.ASLEEP, NightPhase.WAKING):
            reason = "interaction_not_awake"
        else:
            cost = min(policy.interaction_cost, max(
                0.0, policy.interaction_budget - sum(value for _, value in charges)
            ))
            if cost:
                charges.append((effective, cost))
                result = replace(result, energy=max(0.0, result.energy - cost))
                if result.phase == NightPhase.AWAKE and result.energy <= policy.drowsy_threshold:
                    result = replace(result, phase=NightPhase.DROWSY)
            else:
                reason = "interaction_budget"
    result = replace(result, reason_codes=(reason,))
    return {
        "night": result, "applied": cost > 0, "cost": cost, "reason_codes": (reason,),
        "runtime": {"scope_key": context.scope_key, "seen": seen, "charges": charges},
        "rule_version": RULE_VERSION,
    }


# Version two uses integer tenths and a microsecond remainder. The old pure
# functions above retain their version-one semantics for existing consumers.
@dataclass(frozen=True)
class LifePolicy:
    reply_cost_units: int = 40
    fatigue_units_per_minute: int = 8
    recovery_units_per_minute: int = 15
    wake_reply_limit: int = 3
    wake_window_seconds: int = 600
    wake_mode: str = "chat"

    def __post_init__(self):
        for name in ("reply_cost_units", "fatigue_units_per_minute", "recovery_units_per_minute"):
            if type(getattr(self, name)) is not int or not 0 <= getattr(self, name) <= 1000:
                raise ValueError("invalid fixed energy rate")
        for name in ("wake_reply_limit", "wake_window_seconds"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError("invalid wake bound")
        if self.wake_mode not in ("chat", "never", "both"):
            raise ValueError("invalid wake mode")


@dataclass(frozen=True)
class SleepCycle:
    cycle_id: str
    kind: str
    start: float
    wake: float
    deep: float | None = None
    drowsy: float | None = None
    base_wake: float | None = None
    lie_in_minutes: int = 0

    def __post_init__(self):
        finite(self.start, "cycle start", 0)
        finite(self.wake, "cycle wake", self.start)
        if self.kind not in ("night", "nap", "manual") or self.wake <= self.start:
            raise ValueError("invalid sleep cycle")
        if self.kind == "night" and not (
            self.start < self.drowsy < self.deep < (self.base_wake or self.wake)
        ):
            raise ValueError("invalid sleep timeline")


def life_policy(config):
    return LifePolicy(
        int(round(config.energy_reply_cost * 10)),
        int(round(config.energy_fatigue_per_minute * 10)),
        int(round(config.energy_recovery_per_minute * 10)),
        config.wake_reply_limit, config.wake_window_minutes * 60, config.wake_mode,
    )


def life_state(state):
    if state.policy_version == 2:
        return state
    display = {
        NightPhase.AWAKE: SleepState.AWAKE, NightPhase.DROWSY: SleepState.GROGGY,
        NightPhase.SETTLING: SleepState.DROWSY, NightPhase.ASLEEP: SleepState.DEEP_SLEEP,
        NightPhase.WAKING: SleepState.GROGGY,
    }[state.phase]
    units = int(round(state.energy * 10))
    return replace(state, policy_version=2, display_state=display,
                   energy_units=units, energy=units / 10, energy_remainder=0)


def display_phase(display):
    # v1 retains five old enum values; groggy is communicative, not v1 blocking.
    return {
        SleepState.AWAKE: NightPhase.AWAKE, SleepState.GROGGY: NightPhase.DROWSY,
        SleepState.NAP: NightPhase.ASLEEP, SleepState.DROWSY: NightPhase.ASLEEP,
        SleepState.DEEP_SLEEP: NightPhase.ASLEEP,
    }[display]


def _display(state, display, reason):
    return replace(state, display_state=display, phase=display_phase(display),
                   reason_codes=(reason,),
                   sleep_started_at=(state.cycle_started_at or state.updated_at)
                   if display in (SleepState.NAP, SleepState.DROWSY, SleepState.DEEP_SLEEP)
                   else None,
                   sleep_stage=None, transition_deadline=None, awaiting_reply_id=None)


def _cycle_display(state, at, *, allow_sleep):
    if not allow_sleep:
        return SleepState.GROGGY if state.energy < 10 or (
            state.cycle_kind == "night" and state.cycle_started_at is not None
            and state.cycle_started_at <= at < (state.wake_at or at)
        ) else SleepState.AWAKE
    if state.wake_at is None:
        return SleepState.DROWSY if state.display_state == SleepState.DROWSY and (
            state.energy_units < 100
        ) else SleepState.GROGGY if state.energy_units < 100 else SleepState.AWAKE
    if at >= state.wake_at:
        return SleepState.AWAKE
    # 梦中惊醒有独立的短唤醒窗；到期仍按原夜晚时间重新入睡。
    if (state.wake_session and state.wake_session.startswith("dream:")
            and state.wake_window_deadline is not None and at < state.wake_window_deadline
            and state.wake_replies_used < state.wake_reply_limit):
        return SleepState.GROGGY if state.energy < 10 else SleepState.AWAKE
    if state.deep_sleep_at is not None and at >= state.deep_sleep_at:
        return SleepState.DEEP_SLEEP
    if state.wake_session:
        if state.wake_replies_used >= state.wake_reply_limit or (
            state.wake_window_deadline is not None and at >= state.wake_window_deadline
        ):
            return SleepState.DROWSY
        return SleepState.GROGGY if state.energy < 10 else SleepState.AWAKE
    if state.cycle_kind == "nap":
        return SleepState.NAP
    if state.cycle_kind == "manual":
        return SleepState.DROWSY
    return SleepState.DROWSY if state.drowsy_at is not None and at >= state.drowsy_at else (
        SleepState.GROGGY
    )


def advance_life(state, *, now, cycle=None, fatigue_windows=(), policy=LifePolicy(),
                 allow_sleep=True):
    """Settle all rate boundaries once. Returns state and body-free event deltas."""
    finite(now, "now", 0)
    state = life_state(state)
    if now < state.updated_at:
        return replace(state, reason_codes=("clock_rollback",)), ()
    changes = []
    original = state
    if cycle is not None and state.cycle_id != cycle.cycle_id and (
        state.wake_at is None or state.wake_at <= now or (
            cycle.kind == "night" and state.cycle_kind == "nap"
        )
    ):
        state = replace(
            state, cycle_id=cycle.cycle_id, cycle_kind=cycle.kind,
            cycle_started_at=cycle.start, wake_at=cycle.wake, deep_sleep_at=cycle.deep,
            drowsy_at=cycle.drowsy, base_wake_at=cycle.base_wake,
            lie_in_minutes=cycle.lie_in_minutes, wake_score=None, wake_failures=0,
            wake_session=None, wake_replies_used=0, wake_reply_limit=0,
            first_reply_submitted_at=None, wake_window_deadline=None,
        )
    start = state.updated_at
    boundaries = {start, now}
    for value in (state.cycle_started_at, state.drowsy_at, state.deep_sleep_at,
                  state.wake_at, state.wake_window_deadline):
        if value is not None and start < value < now:
            boundaries.add(value)
    for left, right in fatigue_windows:
        boundaries.update(value for value in (left, right) if start < value < now)
    points = sorted(boundaries)
    for left, right in zip(points, points[1:]):
        at = (left + right) / 2
        display = _cycle_display(state, at, allow_sleep=allow_sleep) if (
            state.cycle_started_at is None or state.cycle_started_at <= at
        ) else (SleepState.GROGGY if state.energy < 10 else SleepState.AWAKE)
        sleeping = display in (SleepState.NAP, SleepState.DROWSY, SleepState.DEEP_SLEEP)
        fatigue = any(a <= at < b for a, b in fatigue_windows)
        draining = fatigue and not sleeping
        rate = policy.fatigue_units_per_minute if draining else policy.recovery_units_per_minute
        # A rate-direction boundary discards only the previous sub-tenth residue.
        previous_direction = state.energy_direction
        reason = "fatigue" if draining else "recovery"
        remainder = state.energy_remainder if previous_direction == reason else 0
        total = int(round((right - left) * 1_000_000)) * rate + remainder
        units, remainder = divmod(total, 60_000_000)
        before = state.energy_units
        after = min(1000, max(0, before + (-units if draining else units)))
        state = replace(state, energy_units=after, energy=after / 10,
                        energy_remainder=remainder if 0 < after < 1000 else 0,
                        energy_direction=reason,
                        reason_codes=(reason,))
        if before != after:
            changes.append({"occurred_at": right, "category": reason, "before_units": before,
                            "after_units": after, "reason_code": reason})
    state = replace(state, updated_at=now)
    display = _cycle_display(state, now, allow_sleep=allow_sleep)
    state = _display(state, display, state.reason_codes[0] if state.reason_codes else "clock")
    if display == SleepState.DEEP_SLEEP and state.sleep_started_at is not None:
        state = replace(state, sleep_stage=sleep_stage(state.sleep_started_at, now=now))
    if state.wake_at is not None and now >= state.wake_at:
        state = replace(state, wake_score=None, wake_failures=0, wake_session=None,
                        wake_replies_used=0, wake_reply_limit=0,
                        first_reply_submitted_at=None, wake_window_deadline=None)
    if state.display_state != original.display_state or state.cycle_id != original.cycle_id:
        changes.append({"occurred_at": now, "category": "sleep" if display in (
            SleepState.NAP, SleepState.DROWSY, SleepState.DEEP_SLEEP
        ) else "wake", "before_units": state.energy_units, "after_units": state.energy_units,
                        "reason_code": "timeline"})
    return state, tuple(changes)


def chat_wake_eligible(state, event, *, policy=LifePolicy()):
    return (
        event.actor_role == ActorRole.HUMAN and event.event_type == "message"
        and event.reliable_source and event.actor_id
        and event.actor_id == event.context.account_id and policy.wake_mode != "never"
        and (event.context.scene_kind.value == "private" or (
            policy.wake_mode == "both" and event.context.scene_kind.value == "group"
            and "native_bot_mention" in event.signals
        )) and state.display_state in (SleepState.NAP, SleepState.DROWSY)
    )


def chat_wake(state, event, *, policy=LifePolicy(), dice=(0, 0)):
    """Caller persists event idempotency. Deep sleep never rolls or increments."""
    if state.display_state == SleepState.DEEP_SLEEP:
        return state, False, "deep_sleep_no_chat_wake"
    if not chat_wake_eligible(state, event, policy=policy):
        return state, False, "wake_not_eligible"
    score = state.wake_score
    if state.energy_units < 100:
        if score is None:
            if len(dice) != 2 or any(type(d) is not int or not 0 <= d <= 9 for d in dice):
                raise ValueError("wake requires two 0..9 dice")
            score = sum(dice)
        else:
            score += 1
        if score <= 8:
            return replace(state, wake_score=score, wake_failures=state.wake_failures + 1,
                           reason_codes=("wake_roll_failed",)), False, "wake_roll_failed"
    display = SleepState.GROGGY if state.energy_units < 100 else SleepState.AWAKE
    return replace(
        _display(state, display, "chat_wake"), wake_score=None, wake_failures=0,
        wake_session=stable_key(state.cycle_id, event.idempotency_key),
        wake_replies_used=0, wake_reply_limit=policy.wake_reply_limit,
        first_reply_submitted_at=None, wake_window_deadline=None,
    ), True, "chat_wake"


def start_life_reply(state, *, policy=LifePolicy()):
    if state.display_state not in (SleepState.AWAKE, SleepState.GROGGY):
        return state, False
    if state.wake_session:
        if state.wake_replies_used >= state.wake_reply_limit:
            return _display(state, SleepState.DROWSY, "wake_rounds_exhausted"), False
        state = replace(state, wake_replies_used=state.wake_replies_used + 1)
        if state.wake_replies_used >= state.wake_reply_limit:
            state = _display(state, SleepState.DROWSY, "wake_rounds_exhausted")
    return state, True


def submit_life_reply(state, *, now, policy=LifePolicy(), allow_sleep=True):
    before = state.energy_units
    after = max(0, before - policy.reply_cost_units)
    state = replace(state, energy=after / 10, energy_units=after,
                    reason_codes=("reply",))
    if state.wake_session and state.first_reply_submitted_at is None:
        state = replace(state, first_reply_submitted_at=now,
                        wake_window_deadline=now + policy.wake_window_seconds)
    if after < 100 and state.display_state == SleepState.AWAKE:
        state = _display(state, SleepState.GROGGY, "low_energy")
    if after < 100 and (state.wake_at is None or state.wake_at <= now):
        state = replace(state, wake_at=None, cycle_id=None, cycle_kind=None,
                        cycle_started_at=None, deep_sleep_at=None, drowsy_at=None)
        state = _display(state, SleepState.DROWSY if allow_sleep else SleepState.GROGGY,
                         "low_energy_rest")
    return state, ({"occurred_at": now, "category": "reply", "before_units": before,
                    "after_units": after, "reason_code": "reply_submitted"},)
