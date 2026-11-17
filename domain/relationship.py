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

import json

from ..contracts import (
    ActorRole, Context, Event, Relationship, RelationshipContribution, SceneKind,
    stable_key, to_dict,
)
from .emotion import (
    _event_problem, _integer, _number, _prepare_guard, _record_guard,
    _stimulus_allowance, resolve_mode,
)

RELATIONSHIP_STAGE_NAMES = (
    "反感", "陌生", "友好", "亲近", "独特",
)
RELATIONSHIP_STAGE_DESCRIPTIONS = (
    "反感：保持距离，可以冷淡或表达不满，不羞辱、威胁或攻击对方；"
    "正常答疑，个人生图及新生图承诺遵守本轮阶段概率判定。",
    "陌生：礼貌、谨慎，先了解对方，避免擅自亲密；"
    "正常答疑，个人生图及新生图承诺遵守本轮阶段概率判定。",
    "友好：自然友善，肯定对方的善意、合理批评和教导。",
    "亲近：更主动关心、温柔陪伴，关怀程度加倍，尊重对方边界。",
)
RELATIONSHIP_DEFAULT_SCORE = 200.0
IMAGE_REFUSAL_FIELDS = (
    "relationship_image_refusal_averse",
    "relationship_image_refusal_unfamiliar",
    "relationship_image_refusal_friendly",
    "relationship_image_refusal_close",
    "relationship_image_refusal_unique",
)
IMAGE_REFUSAL_DEFAULTS = (90, 60, 30, 10, 5)


def image_refusal_percent(index, config=None):
    """固定阶段序号对应配置；运行时夹取，异常类型沿用该阶段默认值。"""
    value = getattr(config, IMAGE_REFUSAL_FIELDS[index], IMAGE_REFUSAL_DEFAULTS[index])
    return max(0, min(100, value)) if type(value) is int else IMAGE_REFUSAL_DEFAULTS[index]

RULE_VERSION = "relationship-3"
MIN_SCORE_DELTA = 5.0  # raw/10: final nonzero automatic motion must be 0.5–1.
SCORE_RULES = {
    "insult": -10.0, "threat": -10.0, "praise": 5.0,
    "constructive_criticism": 5.0, "teaching": 5.0,
    "care": 10.0, "gratitude": 5.0, "conflict": -5.0, "apology": 5.0,
    "boundary_respected": 5.0, "boundary_violated": -5.0,
    "promise_kept": 10.0, "promise_broken": -10.0,
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

    event_cap: float = 10.0
    daily_budget: float = 24.0
    event_ttl: float = 7200.0
    similar_window: float = 300.0
    similar_limit: int = 3
    similar_budget: float = 10.0
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
    """显示分数raw/10；连续小数按下一档下界划分，100为管理员独特档。"""
    _number(score, "score", 0, 1000)
    return f"stage_{sum(score >= threshold for threshold in (110, 250, 450, 1000))}"


def stage_names(names):
    """Accept the old 11 names and preserve the administrator's special name."""
    return [names[i] for i in (0, 2, 5, 6, 10)] if len(names) == 11 else list(names)


def initial_relationship() -> Relationship:
    """仅用于不存在的关系；默认值不是可跨来源累加的真实证据。"""
    return Relationship(score=RELATIONSHIP_DEFAULT_SCORE,
                        stage=relationship_stage(RELATIONSHIP_DEFAULT_SCORE),
                        evidence_complete=False, reason_codes=("initial_relationship_default",))


def relationship_stage_dto(score: float, config=None) -> dict[str, Any]:
    key = relationship_stage(score)
    index = int(key.rsplit("_", 1)[1])
    names = (json.loads(config.relationship_stage_names) if config is not None
             else RELATIONSHIP_STAGE_NAMES)
    names = stage_names(names)
    name = names[index].strip() or RELATIONSHIP_STAGE_NAMES[index]
    return {"stage": key, "stage_key": key, "stage_index": index, "stage_name": name,
            "stage_type": RELATIONSHIP_STAGE_NAMES[index]}


def relationship_behavior(score, config=None, *, note=""):
    stage = relationship_stage_dto(score, config)
    index = stage["stage_index"]
    custom = json.loads(getattr(config, "relationship_stage_descriptions", '["","","",""]'))
    descriptions = (
        *(value.strip() or default for value, default in zip(custom, RELATIONSHIP_STAGE_DESCRIPTIONS)),
        note or (getattr(config, "relationship_special_description", "") if config else "")
        or "独特：遵循管理员定义的特殊关系，自然关心并尊重边界。",
    )
    refusal = image_refusal_percent(index, config)
    return {**stage, "score": round(score / 10, 2), "raw_score": score,
            "care_multiplier": 2 if index >= 3 else 1,
            "description": descriptions[index], "ordinary_max": 99,
            # 关系只控制个人请求的接受，不授予管理权限，也不撤销已接受的义务。
            # 保留公开字段表示本阶段存在接受机会；具体本轮许可由运行时判定。
            "may_accept_image_request": refusal < 100,
            "image_refusal_percent": refusal,
            "request_boundary": (
                "个人生图和新生图承诺按本轮阶段概率判定，不按分数一律拒绝；"
                "婉拒不登记待办，仍正常交流和答疑。已接受的任务继续跟进。"
                "情绪影响措辞，不追加随机婉拒；用户命令不授予管理权限。")}


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


def relationship_evidence(event: Event) -> tuple[tuple[str, ...], str]:
    """A source scope identifies the sender; native targeting identifies the recipient."""
    from .appraisal import local_appraisals
    if ("native_other_target" in event.signals
            or (event.context.scene_kind != SceneKind.PRIVATE
                and not set(event.signals) & {"native_bot_mention", "native_bot_reply"})):
        return (), "relationship_subject_unknown"
    if event.confidence < .65:
        return (), "no_confident_evidence"
    signals = tuple(sorted((set(event.signals) | set(local_appraisals(event.body)))
                           .intersection(SCORE_RULES)))
    return signals, "" if signals else "no_relationship_evidence"


def apply_relationship(
    state: Relationship, event: Event, *, now: float,
    runtime: Mapping[str, Any] | None = None,
    policy: RelationshipPolicy = RelationshipPolicy(),
    enabled: bool = True, mode: str = "active", conflict: bool = False,
) -> dict[str, Any]:
    """Apply one real human event using persisted absolute daily accounting.

    Runtime belongs to context.account_key, not OneID. Charge only final motion,
    with strongest-tier aggregation and independent positive/negative budgets.
    Frozen/unknown/neutral evidence consumes the guard but no scoring budget.
    """
    _number(now, "now", 0)
    control = resolve_mode(enabled=enabled, mode=mode, conflict=conflict)
    result = {
        "relationship": state, "runtime": dict(runtime or {}),
        "contributions": (), "applied": False, "reason_codes": (),
        "trace": {"event_key": event.idempotency_key, "event_id": event.event_id,
                  "occurred_at": event.occurred_at, "processed_at": now,
                  "rule_version": RULE_VERSION, "before": to_dict(state),
                  "after": to_dict(state), "charged": 0.0, "delta_display": 0.0},
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
    # 重复/乱序/冻结的早退也必须保留负向预算，不能靠重放恢复扣分额度。
    if (runtime or {}).get("negative_days"):
        guard["negative_days"] = _budgets(
            {"days": runtime["negative_days"]}, now=now, policy=policy)
    result["runtime"] = guard
    if problem:
        result["reason_codes"] = (problem,)
        return result
    if state.frozen:
        _record_guard(guard, event, 0)
        result["reason_codes"] = ("relationship_frozen",)
        return result
    if state.score == 1000 and "manual_correction" in state.reason_codes:
        _record_guard(guard, event, 0)
        result["reason_codes"] = ("administrator_special_relationship",)
        return result
    day = _day(event.occurred_at, policy)
    signals, evidence_problem = relationship_evidence(event)
    result["trace"].update(day=day, signals=list(signals),
                           subject="bot" if evidence_problem != "relationship_subject_unknown"
                           else "unknown")
    if evidence_problem:
        _record_guard(guard, event, 0)
        result["reason_codes"] = (evidence_problem,)
        return result
    # Explicit negative conduct wins; positive wording never offsets it.
    negative = any(SCORE_RULES.get(s, 0) < 0 for s in signals)
    signals = tuple(s for s in signals if (SCORE_RULES[s] < 0) == negative)
    if negative or (runtime or {}).get("negative_days"):
        guard["negative_days"] = _budgets(
            {"days": (runtime or {}).get("negative_days", {})}, now=now, policy=policy)
    bucket = guard["negative_days"] if negative else guard["days"]
    available = max(0.0, policy.daily_budget - bucket.get(day, 0.0))
    # Neutral/unknown messages retain deduplication, but cannot use up a later
    # real appraisal's occurrence limit (notably a threat with no emotion weight).
    scoring_guard = {**guard, "stimuli": [r for r in guard["stimuli"] if r["amount"] > 0]}
    similar = _stimulus_allowance(scoring_guard, event, limit=policy.similar_limit,
                                  budget=policy.similar_budget)
    proposed = (min if negative else max)(SCORE_RULES[s] for s in signals)
    room = state.score if negative else max(0.0, 990.0 - state.score)
    limit = min(abs(proposed), policy.event_cap, available, similar, room)
    if limit < MIN_SCORE_DELTA:
        _record_guard(guard, event, 0)
        result["reason_codes"] = (
            "daily_budget_exhausted" if available < MIN_SCORE_DELTA
            else "similar_stimulus_limited" if similar < MIN_SCORE_DELTA
            else "score_space_below_minimum" if room < MIN_SCORE_DELTA
            else "event_budget_below_minimum",)
        return result
    # Confidence gates evidence; it never shrinks 0.5 into a sub-minimum reward.
    charged = limit
    scale = charged / abs(proposed)
    score = state.score + (-charged if negative else charged)
    # Legacy scores may contain fractions; tolerate only machine rounding noise.
    assert MIN_SCORE_DELTA - 1e-9 <= abs(score - state.score) <= 10.0 + 1e-9
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
    bucket[day] = bucket.get(day, 0.0) + charged
    _record_guard(guard, event, charged)
    updated = replace(
        state, score=score, stage=relationship_stage(score), **dimensions,
        identity_revision=event.context.identity_revision, updated_at=now,
        reason_codes=tuple(dict.fromkeys((
            *(("initial_relationship_default",)
              if "initial_relationship_default" in state.reason_codes else ()),
            *reasons,
        ))),
    )
    result.update(relationship=updated, contributions=tuple(changes),
                  applied=bool(changes), reason_codes=reasons)
    result["trace"].update(after=to_dict(updated), charged=charged, day=day,
                           selected_signals=list(signals),
                           delta_display=round((score - state.score) / 10, 6))
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
        reason_codes=tuple(dict.fromkeys((
            "manual_correction",
            *(("initial_relationship_default",)
              if "initial_relationship_default" in state.reason_codes else ()),
        ))),
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
    identity_revision: str, baseline_score: float = 0.0,
) -> Relationship:
    """Recompute from immutable source rows under a *current* authorized grant.

    None means only the current source account. An explicit empty grant means
    nothing. Raw IDs, matching names and historical identity revisions are not
    authorization. No prior aggregate snapshot is accepted as new evidence.
    Normalized dimensions are averaged over known source accounts, not added
    into artificial certainty.

    baseline_score 是调用方确认的新关系起点，只应用一次，不作为来源贡献。
    """
    if identity_revision != context.identity_revision:
        raise ValueError("identity_revision_changed")
    _number(baseline_score, "baseline_score", 0, 1000)
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
    score = max(0.0, min(990.0, (baseline_score if allowed else 0.0) + totals["score"]))
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
