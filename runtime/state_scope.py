"""State ownership is not a route or permission to share source material."""

from dataclasses import replace

from ..contracts import (
    BotAffect, NightPhase, NightState, SleepState,
    state_owner_key as owner_key, state_persona_key as persona_key,
)

__all__ = ["owner_key", "persona_key", "source_affect", "conservative_night"]


def source_affect(state: BotAffect, context) -> BotAffect:
    """Shared numbers do not authorize another scene's explanation/evidence."""
    evidence = tuple(ref for ref in state.evidence
                     if all(getattr(ref.context, name) == getattr(context, name) for name in (
                         "instance_id", "bot_id", "persona_id", "adapter_id",
                         "platform", "scene_kind", "scene_id",
                     )))
    if evidence == state.evidence:
        return state
    return replace(state, evidence=evidence,
                   reason_codes=state.reason_codes if evidence == state.evidence else ())


def conservative_night(states, *, now):
    """Carry restrictions, not a fresh full battery, across mode boundaries."""
    if not states:
        return NightState(updated_at=now)
    active = [s for s in states if s.wake_at is not None and s.wake_at > now]
    rank = {None: 0, SleepState.AWAKE: 0, SleepState.GROGGY: 1,
            SleepState.NAP: 2, SleepState.DROWSY: 3, SleepState.DEEP_SLEEP: 4}
    chosen = max(active or states, key=lambda s: (
        rank.get(s.display_state, 0) if s.policy_version == 2 else (
            4 if s.phase == NightPhase.ASLEEP else 2 if s.phase == NightPhase.SETTLING else 0
        ), s.wake_at or 0,
    ))
    energy = min(s.energy for s in states)
    energy_source = min(states, key=lambda s: s.energy)
    deadlines = [s.wake_window_deadline for s in states if s.wake_window_deadline is not None]
    used = max(s.wake_replies_used for s in states)
    result = replace(
        chosen, energy=energy, energy_units=int(round(energy * 10))
        if chosen.policy_version == 2 else None,
        energy_remainder=energy_source.energy_remainder,
        energy_direction=energy_source.energy_direction,
        updated_at=max(s.updated_at for s in states),
        wake_at=max((s.wake_at for s in active), default=chosen.wake_at),
        wake_replies_used=used,
        wake_window_deadline=min(deadlines) if deadlines else chosen.wake_window_deadline,
        awaiting_reply_id=None, reason_codes=("state_mode_conservative",),
    )
    if result.wake_session and (
        used >= result.wake_reply_limit or (
            result.wake_window_deadline is not None and now >= result.wake_window_deadline
        )
    ):
        result = replace(result, display_state=SleepState.DROWSY, phase=NightPhase.ASLEEP)
    return result
