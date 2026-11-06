"""Pure, fail-closed legacy constraints. No SQL, clocks, reservations or effects."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from zoneinfo import ZoneInfo

from ..contracts import Context

MAX_RECORDS = 2000
PURPOSES = frozenset({"behavior", "emotion", "diary", "dream", "export"})
CLASSIFICATIONS = frozenset({
    "legacy_unknown", "human_observation", "relationship_baseline",
    "diary_subjective_private", "dream_imagined_private", "task_history_never_resume",
    "legacy_window_reference_only", "night_baseline", "cooldown_quota_baseline",
})


def _count(value) -> int:
    if type(value) is not int or not 0 <= value <= 2**53:
        raise ValueError("legacy_invalid_count")
    return value


def _time(value) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1e15:
        raise ValueError("legacy_invalid_time")
    return value


def _text(value) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError("legacy_invalid_source")
    return value


def _result(reasons=(), **values) -> dict:
    return {
        "allowed": not reasons, "reason_codes": tuple(sorted(set(reasons))),
        "global_used_floor": 0, "scope_used_floor": 0, "unanswered_floor": 0,
        "cooldown_until": None, "last_attempt_at": None, "sources": (),
        "rule_version": "legacy_constraints_v1",
        **values,
    }


def evaluate_legacy_constraints(
    records, context: Context, now: float, *, purpose: str = "behavior",
    timezone: str = "", human_watermark: int = 0,
) -> dict:
    """Evaluate a complete, bounded legacy_baselines snapshot without mutating it.

    Floors are legacy-only: the caller adds native usage exactly once. Within
    one source installation the global counter overlaps session counters.
    Counts with an unproven period remain a floor AND deny execution. No unknown
    range is guessed away. An old attempt is explanatory, never a new cooldown.
    """
    try:
        _time(now)
        _count(human_watermark)
        if purpose not in PURPOSES or not isinstance(context, Context):
            raise ValueError("legacy_invalid_context_or_purpose")
        if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
            raise TypeError("legacy_invalid_records")
        if len(records) > MAX_RECORDS:
            raise ValueError("legacy_record_limit")
        return _evaluate(records, context, now, purpose, timezone, human_watermark)
    except (ValueError, TypeError, KeyError, OverflowError):
        return _result(("legacy_constraints_invalid",))


def evaluate_legacy(rows, context, *, purpose, timezone, now, human_watermark) -> dict:
    """Frozen integration entry point; kept identical to the core handoff."""
    return evaluate_legacy_constraints(
        rows, context, now, purpose=purpose, timezone=timezone,
        human_watermark=human_watermark,
    )


def _period_used(baseline, binding, timezone, now, reasons) -> int:
    used = _count(baseline.get("quota_used"))
    original_timezone = binding.get("timezone")
    if not original_timezone or original_timezone != timezone:
        reasons.add("legacy_timezone_unresolved")
        return used
    try:
        zone = ZoneInfo(original_timezone)
        period = date.fromisoformat(baseline["quota_period"])
        if period.isoformat() != baseline["quota_period"]:
            raise ValueError
        current = datetime.fromtimestamp(now, zone).date()
    except (ValueError, TypeError, KeyError, OverflowError, OSError):
        reasons.add("legacy_quota_period_unresolved")
        return used
    if period > current:
        reasons.add("legacy_quota_period_in_future")
    return used if period >= current else 0


def _evaluate(records, context, now, purpose, timezone, human_watermark):
    reasons, sources, seen = set(), [], {}
    groups = {}
    scope_used = unanswered = 0
    cooldown = None
    for record in records:
        if not isinstance(record, Mapping) or not isinstance(record.get("value"), Mapping):
            raise TypeError
        value = record["value"]
        identity = _text(record["record_key"])
        source_id = _text(value["source_id"])
        _text(value["source_hash"])
        _count(record["generation"])
        _count(record["version"])
        _time(record["updated_at"])
        key = (source_id, identity)
        if key in seen:
            if seen[key] != record:
                reasons.add("legacy_conflicting_records")
            continue
        seen[key] = record
        classification = value["classification"]
        if classification not in CLASSIFICATIONS or type(value["identity_resolved"]) is not bool:
            raise ValueError
        target = Context.from_dict(value["target_context"])
        if target.scope_key != record["scope_key"] or target.instance_id != context.instance_id:
            raise ValueError
        resolved = value["identity_resolved"]
        same_scope = resolved and target.scope_key == context.scope_key
        same_owner = resolved and all(
            getattr(target, key) == getattr(context, key)
            for key in ("instance_id", "bot_id", "persona_id", "adapter_id", "platform")
        )
        baseline = value.get("baseline", {})
        binding = value.get("runtime_constraints", {})
        if not isinstance(baseline, Mapping) or not isinstance(binding, Mapping):
            raise TypeError
        if binding and binding.get("version") != 1:
            raise ValueError
        explanation = {
            "record_key": identity, "source_id": source_id,
            "source_hash": value["source_hash"], "classification": classification,
            "scope_key": record["scope_key"],
        }
        # Unknown private archives never become authorized exports. Even known
        # archives are not source-authorized merely because a switch was enabled.
        if purpose == "export" and (same_owner or not resolved):
            reasons.add("legacy_export_forbidden")
            sources.append(explanation)
            continue
        if purpose == "dream" and classification == "night_baseline":
            if not resolved:
                reasons.add("legacy_scope_unresolved")
            elif not same_owner:
                continue
            used = baseline.get("dream_quota_used")
            if used is None or _count(used) != 0:
                reasons.add("legacy_dream_period_unresolved")
            if baseline.get("phase") not in ("awake", "asleep"):
                reasons.add("legacy_night_state_unresolved")
            sources.append(explanation)
            continue
        if purpose != "behavior" or classification != "cooldown_quota_baseline":
            continue
        level = baseline.get("level")
        if level not in ("global", "session"):
            raise ValueError
        # All sessions contribute to the instance-wide send pool; only their
        # own scope receives cooldown/unanswered constraints.
        if not resolved:
            reasons.add("legacy_scope_unresolved")
        if binding.get("quota_scope") != ("instance" if level == "global" else "scope"):
            reasons.add("legacy_quota_scope_unresolved")
        used = _period_used(baseline, binding, timezone, now, reasons)
        group = groups.setdefault(source_id, {"global": [], "sessions": {}})
        if level == "global":
            group["global"].append(used)
        else:
            session = _text(baseline["source_session_id"])
            if session in group["sessions"]:
                # Two different source records claiming the same session are
                # not assumed to be independent or successive snapshots.
                reasons.add("legacy_session_overlap_unresolved")
            group["sessions"][session] = max(used, group["sessions"].get(session, 0))
            if same_scope or not resolved:
                scope_used += used
                until = baseline.get("cooldown_until")
                if until is None:
                    reasons.add("legacy_cooldown_unresolved")
                else:
                    until = _time(until)
                    cooldown = max(cooldown or 0, until)
                    if now < until:
                        reasons.add("legacy_cooldown_active")
                old_unanswered = _count(baseline.get("unanswered_count"))
                watermark = binding.get("import_human_watermark")
                if watermark is None:
                    if old_unanswered:
                        reasons.add("legacy_human_watermark_unresolved")
                    unanswered += old_unanswered
                elif not resolved or human_watermark <= _count(watermark):
                    unanswered += old_unanswered
                explanation["last_attempt_at"] = baseline.get("last_attempt_at")
                if explanation["last_attempt_at"] is not None:
                    _time(explanation["last_attempt_at"])
        explanation["quota_used_floor"] = used
        sources.append(explanation)
    if len(groups) > 1:
        # Source installation names alone cannot prove disjoint sends.
        reasons.add("legacy_multiple_sources_unreconciled")
    global_used = sum(max(max(g["global"], default=0), sum(g["sessions"].values()))
                      for g in groups.values())
    return _result(
        reasons, global_used_floor=global_used, scope_used_floor=scope_used,
        unanswered_floor=unanswered, cooldown_until=cooldown, sources=tuple(sources),
    )
