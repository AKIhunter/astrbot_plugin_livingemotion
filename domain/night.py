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
    reply_cost_units: int = 20
    fatigue_units_per_minute: int = 5
    recovery_units_per_minute: int = 10
    wake_reply_limit: int = 10
    wake_window_seconds: int = 600
    wake_mode: str = "chat"
    daytime_recovery_enabled: bool = False

    def __post_init__(self):
        for name in ("reply_cost_units", "fatigue_units_per_minute", "recovery_units_per_minute"):
            if type(getattr(self, name)) is not int or not 0 <= getattr(self, name) <= 1000:
                raise ValueError("invalid fixed energy rate")
        for name in ("wake_reply_limit", "wake_window_seconds"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError("invalid wake bound")
        if self.wake_mode not in ("chat", "never", "both"):
            raise ValueError("invalid wake mode")
        if type(self.daytime_recovery_enabled) is not bool:
            raise ValueError("invalid daytime recovery switch")


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
        if self.kind not in ("night", "nap", "manual", "recovery") or self.wake <= self.start:
            raise ValueError("invalid sleep cycle")
        if self.kind == "night" and not (
            self.start < self.deep < (self.base_wake or self.wake)
            and (self.drowsy is None or self.start < self.drowsy < self.deep)
        ):
            raise ValueError("invalid sleep timeline")


def life_policy(config):
    return LifePolicy(
        int(round(config.energy_reply_cost * 10)),
        int(round(config.energy_fatigue_per_minute * 10)),
        int(round(config.energy_recovery_per_minute * 10)),
        config.wake_reply_limit, config.wake_window_minutes * 60, config.wake_mode,
        daytime_recovery_enabled=getattr(config, "energy_daytime_recovery_enabled", False),
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
        SleepState.NAP: NightPhase.ASLEEP, SleepState.DROWSY: NightPhase.DROWSY,
        SleepState.DEEP_SLEEP: NightPhase.ASLEEP,
    }[display]


def _display(state, display, reason):
    sleeping = display in (SleepState.NAP, SleepState.DEEP_SLEEP)
    was_sleeping = state.display_state in (SleepState.NAP, SleepState.DEEP_SLEEP)
    return replace(state, display_state=display, phase=display_phase(display),
                   reason_codes=(reason,),
                   sleep_started_at=(state.sleep_started_at if was_sleeping else None)
                   or state.updated_at if sleeping else None,
                   sleep_stage=None, transition_deadline=None, awaiting_reply_id=None)


def energy_display(state):
    """20% is groggy; only zero is drowsy. Neither state counts as sleep."""
    return (SleepState.AWAKE if state.energy_units > 200 else
            SleepState.GROGGY if state.energy_units > 0 else SleepState.DROWSY)


def _clear_wake(state):
    return replace(state, wake_score=None, wake_failures=0, wake_session=None,
                   wake_replies_used=0, wake_reply_limit=0,
                   first_reply_submitted_at=None, wake_window_deadline=None)


def finish_life_wake(state, *, now):
    """Conversation completion must not silently re-enter its old nap."""
    state = replace(_clear_wake(state), cycle_kind="awake", quiet_since=now)
    return _display(state, energy_display(state), "wake_complete")


def _cycle_display(state, at, *, allow_sleep):
    if not allow_sleep:
        return energy_display(state)
    if state.wake_at is None or at >= state.wake_at:
        return energy_display(state)
    # 梦中惊醒有独立的短唤醒窗；到期仍按原夜晚时间重新入睡。
    if (state.wake_session and state.wake_session.startswith("dream:")
            and state.wake_window_deadline is not None and at < state.wake_window_deadline
            and state.wake_replies_used < state.wake_reply_limit):
        return SleepState.GROGGY
    if state.deep_sleep_at is not None and at >= state.deep_sleep_at:
        return SleepState.DEEP_SLEEP
    if state.wake_session:
        if state.wake_window_deadline is not None and at >= state.wake_window_deadline:
            return energy_display(state)
        return SleepState.GROGGY
    if state.cycle_kind == "nap":
        return SleepState.NAP if state.energy_units < 1000 else energy_display(state)
    if state.cycle_kind in ("manual", "recovery"):
        return (SleepState.DEEP_SLEEP if state.energy_units <= 200 else
                SleepState.NAP if state.energy_units < 1000 else energy_display(state))
    # Fatigue start is not a sleep command: before fixed deep sleep, energy decides.
    return energy_display(state)


def advance_life(state, *, now, cycle=None, fatigue_windows=(), policy=LifePolicy(),
                 allow_sleep=True, recovery_cycle_factory=None):
    """Settle all rate boundaries once. Returns state and body-free event deltas."""
    finite(now, "now", 0)
    state = life_state(state)
    if now < state.updated_at:
        return replace(state, reason_codes=("clock_rollback",)), ()
    changes = []
    original = state
    pending_cycle = None
    if (cycle is not None and state.cycle_id != cycle.cycle_id
            and state.wake_at is not None and state.wake_at > state.updated_at):
        pending_cycle = cycle
    elif cycle is not None and state.cycle_id != cycle.cycle_id:
        state = replace(
            state, cycle_id=cycle.cycle_id, cycle_kind=cycle.kind,
            cycle_started_at=cycle.start, wake_at=cycle.wake, deep_sleep_at=cycle.deep,
            drowsy_at=cycle.drowsy, base_wake_at=cycle.base_wake,
            lie_in_minutes=cycle.lie_in_minutes, wake_score=None, wake_failures=0,
            wake_session=None, wake_replies_used=0, wake_reply_limit=0,
            first_reply_submitted_at=None, wake_window_deadline=None,
        )
    start = state.updated_at
    state = replace(state, quiet_since=state.quiet_since if state.quiet_since is not None
                    else start)
    boundaries = {start, now}
    for value in (state.cycle_started_at, state.drowsy_at, state.deep_sleep_at,
                  state.wake_at, state.wake_window_deadline):
        if value is not None and start < value < now:
            boundaries.add(value)
    for left, right in fatigue_windows:
        boundaries.update(value for value in (left, right) if start < value < now)
    install_at = (max(start, pending_cycle.deep if pending_cycle.kind == "night"
                      else pending_cycle.start) if pending_cycle is not None else None)
    if install_at is not None and start < install_at <= now:
        boundaries.add(install_at)
    points = sorted(boundaries)
    cursor = start
    fixed_completed = False
    while True:
        if pending_cycle is not None and cursor >= install_at:
            state = replace(
                _clear_wake(state), cycle_id=pending_cycle.cycle_id, cycle_kind=pending_cycle.kind,
                cycle_started_at=pending_cycle.start, wake_at=pending_cycle.wake,
                deep_sleep_at=pending_cycle.deep, drowsy_at=pending_cycle.drowsy,
                base_wake_at=pending_cycle.base_wake, lie_in_minutes=pending_cycle.lie_in_minutes,
            )
            points = sorted(set(points) | {
                x for x in (pending_cycle.wake, pending_cycle.deep)
                if x is not None and cursor < x <= now
            })
            pending_cycle = None
            fixed_completed = False
        # Settle threshold/timer transitions at their actual timestamp, not the next poll.
        fixed_sleep = (allow_sleep and state.deep_sleep_at is not None
                       and state.wake_at is not None
                       and state.deep_sleep_at <= cursor < state.wake_at)
        if state.wake_at is not None and cursor >= state.wake_at:
            # Only completion of a fixed night resets energy. Supplementary sleep does not.
            if (allow_sleep and state.deep_sleep_at is not None
                    and start < state.wake_at <= cursor and not fixed_completed):
                before = state.energy_units
                state = replace(state, energy_units=1000, energy=100,
                                energy_remainder=0)
                if before != 1000:
                    changes.append({"occurred_at": state.wake_at, "category": "recovery",
                                    "before_units": before, "after_units": 1000,
                                    "reason_code": "fixed_sleep_complete"})
                fixed_completed = True
            state = _clear_wake(state)
            if state.cycle_kind == "recovery":
                # 截止必须真正结束补觉；低精力也要重新静默30分钟，不能当场续开。
                state = replace(state, cycle_kind="awake", quiet_since=cursor)
        if (state.wake_session and state.wake_window_deadline is not None
                and cursor >= state.wake_window_deadline):
            state = finish_life_wake(state, now=cursor)
        if (not fixed_sleep and state.energy_units == 1000
                and state.cycle_kind in ("nap", "manual", "recovery")):
            # A completed nap stays completed when later fatigue/replies reduce energy.
            state = replace(state, cycle_kind="awake")
        display = _cycle_display(state, cursor, allow_sleep=allow_sleep) if (
            state.cycle_started_at is None or state.cycle_started_at <= cursor
        ) else energy_display(state)
        if (allow_sleep and not fixed_sleep and not state.wake_session
                and display in (SleepState.GROGGY, SleepState.DROWSY)
                and cursor >= state.quiet_since + 1800
                and recovery_cycle_factory is not None):
            recovery = recovery_cycle_factory(state, cursor)
            if recovery is not None:
                state = replace(state, cycle_id=recovery.cycle_id, cycle_kind=recovery.kind,
                                cycle_started_at=cursor, wake_at=recovery.wake,
                                base_wake_at=recovery.base_wake, deep_sleep_at=recovery.deep,
                                drowsy_at=None, lie_in_minutes=recovery.lie_in_minutes,
                                sleep_started_at=None)
                points = sorted(set(points) | {
                    x for x in (recovery.wake, recovery.deep) if x is not None and cursor < x <= now
                })
                display = _cycle_display(state, cursor, allow_sleep=allow_sleep)
        previous_display = state.display_state
        state = _display(state, display, "timeline")
        if previous_display != display:
            changes.append({"occurred_at": cursor,
                            "category": "sleep" if display in
                            (SleepState.NAP, SleepState.DEEP_SLEEP) else "wake",
                            "before_units": state.energy_units, "after_units": state.energy_units,
                            "reason_code": "timeline"})
        if cursor >= now:
            break
        right = next(x for x in points if x > cursor)
        sleeping = display in (SleepState.NAP, SleepState.DEEP_SLEEP)
        fatigue = any(a <= cursor < b for a, b in fatigue_windows)
        draining = fatigue and not sleeping
        # 白天恢复为独立开关；夜间未睡眠仍只消耗，睡眠恢复始终保留。
        recovering = sleeping or (policy.daytime_recovery_enabled and not fatigue)
        rate = (policy.fatigue_units_per_minute if draining else
                policy.recovery_units_per_minute if recovering else 0)
        # A rate-direction boundary discards only the previous sub-tenth residue.
        previous_direction = state.energy_direction
        reason = "fatigue" if draining else "recovery" if recovering else ""
        remainder = state.energy_remainder if previous_direction == reason else 0
        if (not sleeping and not state.wake_session and state.energy_units <= 200
                and recovery_cycle_factory is not None):
            quiet_end = state.quiet_since + 1800
            if cursor < quiet_end < right:
                right = quiet_end
        target = (200 if draining and state.energy_units > 200 else 0 if draining else
                  201 if display == SleepState.DEEP_SLEEP and not fixed_sleep
                  and state.energy_units <= 200 else 1000)
        if rate and target != state.energy_units:
            micros = (abs(target - state.energy_units) * 60_000_000 - remainder + rate - 1) // rate
            right = min(right, cursor + micros / 1_000_000)
        total = int(round((right - cursor) * 1_000_000)) * rate + remainder
        units, remainder = divmod(total, 60_000_000)
        before = state.energy_units
        after = min(1000, max(0, before + (-units if draining else units)))
        # 向有效区间移动时保留不足0.1点的余数；只在撞上对应上下限时丢弃。
        keep_remainder = (after > 0 if draining else after < 1000) and bool(rate)
        state = replace(state, energy_units=after, energy=after / 10,
                        energy_remainder=remainder if keep_remainder else 0,
                        energy_direction=reason,
                        reason_codes=(reason or "clock",), updated_at=right)
        if before > 200 >= after:
            state = replace(state, quiet_since=max(state.quiet_since, right))
        if before != after:
            changes.append({"occurred_at": right, "category": reason, "before_units": before,
                            "after_units": after, "reason_code": reason})
        cursor = right
    # Preserve production orphan-session cleanup independently of energy thresholds.
    if state.wake_at is None:
        state = _clear_wake(state)
    if display == SleepState.DEEP_SLEEP and state.sleep_started_at is not None:
        state = replace(state, sleep_stage=sleep_stage(state.sleep_started_at, now=now))
    if state.cycle_id != original.cycle_id:
        changes.append({"occurred_at": now, "category": "sleep" if display in (
            SleepState.NAP, SleepState.DEEP_SLEEP
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
        )) and state.display_state == SleepState.NAP
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
    display = SleepState.GROGGY
    return replace(
        _display(state, display, "chat_wake"), wake_score=None, wake_failures=0,
        wake_session=stable_key(state.cycle_id, event.idempotency_key),
        wake_replies_used=0, wake_reply_limit=policy.wake_reply_limit,
        first_reply_submitted_at=None, wake_window_deadline=None, quiet_since=state.updated_at,
    ), True, "chat_wake"


def start_life_reply(state, *, now=None, policy=LifePolicy()):
    if state.wake_session and (state.wake_at is None or state.cycle_id is None
                              or state.wake_reply_limit <= 0
                              or now is not None and now >= state.wake_at):
        state = _clear_wake(state)
    if state.display_state not in (SleepState.AWAKE, SleepState.GROGGY, SleepState.DROWSY):
        return state, False
    if state.wake_session:
        if state.wake_replies_used >= state.wake_reply_limit:
            # 已占满轮数时只拒绝新请求；在途回复全部结束后才退出恍惚。
            return state, False
        state = replace(state, wake_replies_used=state.wake_replies_used + 1)
    return state, True


def submit_life_reply(state, *, now, policy=LifePolicy(), allow_sleep=True,
                      pending_wake_replies=0):
    before = state.energy_units
    after = max(0, before - policy.reply_cost_units)
    state = replace(state, energy=after / 10, energy_units=after,
                    reason_codes=("reply",), quiet_since=now)
    if state.wake_session and state.first_reply_submitted_at is None:
        state = replace(state, first_reply_submitted_at=now,
                        wake_window_deadline=now + policy.wake_window_seconds)
    if (state.wake_session and state.wake_replies_used >= state.wake_reply_limit
            and pending_wake_replies == 0):
        state = finish_life_wake(state, now=now)
    display = (SleepState.GROGGY if state.wake_session else energy_display(state))
    state = _display(state, display, "reply")
    return state, ({"occurred_at": now, "category": "reply", "before_units": before,
                    "after_units": after, "reason_code": "reply_submitted"},)
