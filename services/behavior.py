"""One guarded autonomous executor; no SQL, scheduler or host dependencies."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
import time
from typing import Any, Protocol
from weakref import WeakValueDictionary
from zoneinfo import ZoneInfo

from ..adapters.memory.base import material_allowed
from ..contracts import (
    ActorRole, Availability, BehaviorIntent, BehaviorPreview, BotAffect,
    CommitResult, ContentKind, Context, Event, EvidenceRef, IntentStatus, NightPhase,
    NightState, Relationship, SceneKind, SleepState, finite, stable_key,
)
from ..domain.proactivity import emotional_share_allowed
from ..ports.memory import Material, MemoryRequest, RecallResult, ValidationResult
from ..storage import SQLiteStore
from .output import public_text_allowed

SEND_POOL = "send"
SEND_PURPOSE = "behavior"
TERMINAL = frozenset(("succeeded", "failed", "cancelled", "unknown"))


@dataclass(frozen=True)
class BehaviorPolicy:
    enabled: bool = True
    mode: str = "active"
    conflict: bool = False
    autonomy_enabled: bool = False
    group_autonomy_enabled: bool = False
    timezone: str | None = None
    whitelist: frozenset[str] = frozenset()
    muted_scopes: frozenset[str] = frozenset()
    dnd: tuple[int, int] = (60, 480)
    active_hours: tuple[tuple[int, int], ...] = ((0, 1440),)
    global_daily_limit: int = 6
    scope_daily_limit: int = 2
    cooldown_seconds: float = 7200
    unanswered_limit: int = 2
    min_energy: float = 20
    min_score: float = 0.35
    intent_ttl_seconds: float = 300
    dependency_timeout_seconds: float = 10
    model_timeout_seconds: float = 30
    send_timeout_seconds: float = 30
    max_input_chars: int = 12000
    max_output_chars: int = 2000
    max_output_tokens: int = 512
    max_pending: int = 100

    def __post_init__(self) -> None:
        for name in ("enabled", "conflict", "autonomy_enabled", "group_autonomy_enabled"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name}: expected boolean")
        if self.mode not in ("active", "observe_only"):
            raise ValueError("invalid_behavior_mode")
        if self.timezone is not None:
            ZoneInfo(self.timezone)
        for start, end in (self.dnd, *self.active_hours):
            if (type(start) is not int or type(end) is not int
                    or not 0 <= start < 1440 or not 0 <= end <= 1440 or start == end):
                raise ValueError("invalid_minute_window")
        for name in ("global_daily_limit", "scope_daily_limit", "unanswered_limit",
                     "max_input_chars", "max_output_chars", "max_output_tokens", "max_pending"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name}: expected positive integer")
        for name in ("intent_ttl_seconds", "dependency_timeout_seconds",
                     "model_timeout_seconds", "send_timeout_seconds"):
            finite(getattr(self, name), name, 0.001)
        finite(self.cooldown_seconds, "cooldown_seconds", 0)
        finite(self.min_energy, "min_energy", 0, 100)
        finite(self.min_score, "min_score", 0, 1)
        object.__setattr__(self, "whitelist", frozenset(self.whitelist))
        object.__setattr__(self, "muted_scopes", frozenset(self.muted_scopes))
        object.__setattr__(self, "dnd", tuple(self.dnd))
        object.__setattr__(self, "active_hours", tuple(map(tuple, self.active_hours)))


@dataclass(frozen=True)
class BehaviorSnapshot:
    context: Context
    affect: BotAffect = field(default_factory=BotAffect)
    relationship: Relationship = field(default_factory=Relationship)
    night: NightState | None = None
    persona_prompt: str = ""
    route_verified: bool = False
    lifecycle_revision: str = ""


@dataclass(frozen=True)
class BehaviorHistory:
    """Durable counts, excluding only the current intent during final checks."""

    global_used: int = 0
    scope_used: int = 0
    last_attempt_at: float | None = None
    unanswered_count: int = 0
    cooldown_until: float | None = None
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value in (self.global_used, self.scope_used, self.unanswered_count):
            if type(value) is not int or value < 0:
                raise ValueError("invalid_behavior_history")
        if self.last_attempt_at is not None:
            finite(self.last_attempt_at, "last_attempt_at", 0)
        if self.cooldown_until is not None:
            finite(self.cooldown_until, "cooldown_until", 0)
        if (not isinstance(self.reason_codes, (tuple, list))
                or any(not isinstance(code, str) or not code.strip() for code in self.reason_codes)):
            raise ValueError("invalid_behavior_history_reasons")
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))


class HistoryReader(Protocol):
    async def __call__(
        self, context: Context, period: str, exclude_intent_id: str | None,
    ) -> BehaviorHistory: ...


@dataclass(frozen=True)
class BehaviorEvaluation:
    eligible: bool
    reason_codes: tuple[str, ...]
    score: float | None = None
    model_calls: int = 0
    sends: int = 0


@dataclass(frozen=True)
class GenerationRequest:
    intent: BehaviorIntent
    snapshot: BehaviorSnapshot
    materials: tuple[Material, ...]
    max_output_tokens: int
    max_output_chars: int


@dataclass(frozen=True)
class SendRequest:
    intent_id: str
    context: Context
    text: str
    authorize: Callable[[], Awaitable[bool]]


@dataclass(frozen=True)
class SendReceipt:
    """Only a trusted transport can attest a complete, correlated confirmation."""

    intent_id: str
    route: str
    status: str = "unknown"
    receipt_id: str | None = None
    confirmed_parts: int = 0
    total_parts: int = 1


class Sender(Protocol):
    async def __call__(self, request: SendRequest) -> SendReceipt | None: ...


@dataclass(frozen=True)
class BehaviorResult:
    intent_id: str
    status: str
    reason_codes: tuple[str, ...]
    score: float | None = None
    model_calls: int = 0
    sender_calls: int = 0
    receipt_recorded: bool = False


@dataclass
class _Attempt:
    intent: BehaviorIntent
    snapshot: BehaviorSnapshot
    policy: BehaviorPolicy
    period: str
    score: float
    reservations: list[str] = field(default_factory=list)
    materials: tuple[Material, ...] = ()
    model_calls: int = 0
    sender_calls: int = 0
    stage: str = "intent_created"
    guard_called: bool = False
    guard_reason: str | None = None
    transport_receipt: dict | None = None
    content: str | None = None


class _Lane:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.pending = 0


_LANES: WeakValueDictionary[str, _Lane] = WeakValueDictionary()


# 管理员手动发送可以跳过的「时机」类原因。硬约束（静音、免打扰、时段、
# 睡眠、精力、额度、身份与来源）一律不可跳过。
_MANUAL_SOFT_REASONS = frozenset({
    "autonomy_disabled", "group_autonomy_disabled", "not_whitelisted",
    "cooldown", "unanswered_backoff", "below_score_threshold",
})


def _inside(minute: int, window: tuple[int, int]) -> bool:
    start, end = window
    return start <= minute < end if start < end else minute >= start or minute < end


def behavior_score(snapshot: BehaviorSnapshot) -> float:
    """Version behavior-1; no score can override a hard veto."""
    affect = snapshot.affect
    return round(
        .50 * snapshot.relationship.normalized + .30 * affect.social_need
        + .10 * (affect.pleasure + 1) / 2 + .10 * (1 - affect.stress), 6,
    )


class BehaviorService:
    def __init__(
        self, store: SQLiteStore, *,
        current: Callable[[Context], Awaitable[BehaviorSnapshot | None]],
        validate_identity: Callable[[Context], Awaitable[bool]],
        validate_evidence: Callable[
            [MemoryRequest, tuple[Material, ...]], Awaitable[ValidationResult]
        ],
        model: Callable[[GenerationRequest], Awaitable[str]],
        sender: Sender,
        policy: Callable[[], BehaviorPolicy] = BehaviorPolicy,
        history: HistoryReader | None = None,
        materials: Callable[[MemoryRequest], Awaitable[RecallResult]] | None = None,
        availability: Callable[[Context], Awaitable[Availability]] | None = None,
        record_success: Callable[[Event, int], Awaitable[CommitResult]] | None = None,
        clock: Callable[[], float] = time.time,
    ):
        self.store = store
        self.current = current
        self.validate_identity = validate_identity
        self.validate_evidence = validate_evidence
        self.model = model
        self.sender = sender
        self.policy = policy
        self.history = history
        self.materials = materials
        self.availability = availability
        self.record_success = record_success or store.commit_event
        self.clock = clock
        self._closed = False
        self._faulted = False
        self._tasks: set[asyncio.Task] = set()
        key = str(store.path.resolve())
        lane = _LANES.get(key)
        if lane is None:
            lane = _Lane()
            _LANES[key] = lane
        self._lane = lane

    def _now(self) -> float:
        now = self.clock()
        finite(now, "behavior_clock", 0)
        return now

    @staticmethod
    def _period(policy: BehaviorPolicy, now: float) -> str:
        if not policy.timezone:
            return ""
        return datetime.fromtimestamp(now, ZoneInfo(policy.timezone)).date().isoformat()

    async def _bounded(self, work, policy: BehaviorPolicy):
        return await asyncio.wait_for(work, timeout=policy.dependency_timeout_seconds)

    def _policy_reasons(
        self, context: Context, policy: BehaviorPolicy, now: float,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if self._closed:
            reasons.append("behavior_closed")
        if self._faulted:
            reasons.append("behavior_storage_fault")
        if not policy.enabled:
            reasons.append("plugin_disabled")
        if policy.mode != "active":
            reasons.append("observe_only")
        if policy.conflict:
            reasons.append("owner_conflict")
        if not policy.autonomy_enabled:
            reasons.append("autonomy_disabled")
        if context.scene_kind == SceneKind.GROUP and not policy.group_autonomy_enabled:
            reasons.append("group_autonomy_disabled")
        if context.scope_key not in policy.whitelist:
            reasons.append("not_whitelisted")
        if context.scope_key in policy.muted_scopes:
            reasons.append("muted")
        if not policy.timezone:
            reasons.append("timezone_required")
        else:
            local = datetime.fromtimestamp(now, ZoneInfo(policy.timezone))
            minute = local.hour * 60 + local.minute
            if _inside(minute, policy.dnd):
                reasons.append("do_not_disturb")
            if not any(_inside(minute, window) for window in policy.active_hours):
                reasons.append("outside_active_hours")
        return tuple(reasons)

    def _snapshot_reasons(
        self, snapshot: BehaviorSnapshot | None, context: Context,
        policy: BehaviorPolicy, now: float, attempt: _Attempt | None,
    ) -> tuple[str, ...]:
        if not isinstance(snapshot, BehaviorSnapshot) or snapshot.context != context:
            return ("context_changed",)
        reasons = []
        if not context.route or snapshot.route_verified is not True:
            reasons.append("unverified_route")
        if not isinstance(snapshot.lifecycle_revision, str) or not snapshot.lifecycle_revision:
            reasons.append("lifecycle_revision_required")
        if not isinstance(snapshot.persona_prompt, str):
            reasons.append("persona_unavailable")
        if snapshot.relationship.identity_revision != context.identity_revision:
            reasons.append("relationship_revision_changed")
        if snapshot.night is not None:
            if (snapshot.night.phase in (NightPhase.SETTLING, NightPhase.ASLEEP)
                    or snapshot.night.display_state in (
                        SleepState.NAP, SleepState.GROGGY, SleepState.DROWSY, SleepState.DEEP_SLEEP,
                    )):
                reasons.append("sleeping")
            if snapshot.night.energy < policy.min_energy:
                reasons.append("low_energy")
        elif self.availability is None:
            reasons.append("availability_unavailable")
        if attempt is not None:
            if behavior_score(snapshot) < policy.min_score:
                reasons.append("below_score_threshold")
            if (attempt.intent.purpose == "proactive:emotional_share"
                    and not emotional_share_allowed(snapshot.relationship, context.scene_kind)):
                reasons.append("relationship_boundary_changed")
            if snapshot.lifecycle_revision != attempt.snapshot.lifecycle_revision:
                reasons.append("lifecycle_changed")
            if snapshot.persona_prompt != attempt.snapshot.persona_prompt:
                reasons.append("persona_changed")
            if policy.timezone != attempt.policy.timezone:
                reasons.append("timezone_changed")
            if self._period(policy, now) != attempt.period:
                reasons.append("quota_period_changed")
            if now >= attempt.intent.expires_at:
                reasons.append("expired_intent")
            if now < attempt.intent.created_at:
                reasons.append("clock_reversed")
        return tuple(reasons)

    async def _gates(
        self, context: Context, *, attempt: _Attempt | None = None,
        manual: bool = False,
    ) -> tuple[BehaviorSnapshot | None, BehaviorPolicy, tuple[str, ...]]:
        policy = self.policy()
        now = self._now()
        reasons = list(self._policy_reasons(context, policy, now))
        if manual:
            # 早退分支也要先滤掉时机类否定，否则手动发送会被它们挡住。
            reasons = [reason for reason in reasons if reason not in _MANUAL_SOFT_REASONS]
        if reasons:
            return None, policy, tuple(reasons)
        snapshot = await self._bounded(self.current(context), policy)
        reasons.extend(self._snapshot_reasons(snapshot, context, policy, now, attempt))
        if manual:
            reasons = [reason for reason in reasons if reason not in _MANUAL_SOFT_REASONS]
        if reasons:
            return snapshot, policy, tuple(reasons)
        if await self._bounded(self.validate_identity(context), policy) is not True:
            reasons.append("identity_invalid")
        if self.availability is not None:
            available = await self._bounded(self.availability(context), policy)
            if not isinstance(available, Availability) or available.available is not True:
                reasons.append("unavailable")
        if attempt is not None:
            if await self.store.get_generation(context) != attempt.intent.generation:
                reasons.append("stale_generation")
            if await self.store.human_watermark(context) != attempt.intent.human_watermark:
                reasons.append("new_human_message")
        if self.history is None:
            reasons.append("behavior_history_unavailable")
        else:
            history = await self._bounded(self.history(
                context, self._period(policy, now),
                attempt.intent.intent_id if attempt else None,
            ), policy)
            if not isinstance(history, BehaviorHistory):
                reasons.append("behavior_history_invalid")
            else:
                reasons.extend(history.reason_codes)
                if history.global_used >= policy.global_daily_limit:
                    reasons.append("global_quota_exhausted")
                if history.scope_used >= policy.scope_daily_limit:
                    reasons.append("scope_quota_exhausted")
                if ((history.last_attempt_at is not None
                     and now - history.last_attempt_at < policy.cooldown_seconds)
                        or (history.cooldown_until is not None and now < history.cooldown_until)):
                    reasons.append("cooldown")
                if history.unanswered_count >= policy.unanswered_limit:
                    reasons.append("unanswered_backoff")
        reasons.extend(self._policy_reasons(context, self.policy(), self._now()))
        reasons.extend(self._snapshot_reasons(
            snapshot, context, self.policy(), self._now(), attempt,
        ))
        if manual:
            # 管理员显式要求「现在发一条」时只跳过时机类的软性门槛；
            # 静音、免打扰、额度、身份、来源这类硬约束永远保留。
            reasons = [reason for reason in reasons if reason not in _MANUAL_SOFT_REASONS]
        return snapshot, policy, tuple(dict.fromkeys(reasons))

    async def evaluate(self, context: Context) -> BehaviorEvaluation:
        """Read-only: no material retrieval, model, reservation or send."""
        try:
            snapshot, policy, reasons = await self._gates(context)
            if reasons:
                return BehaviorEvaluation(False, reasons)
            score = behavior_score(snapshot)
            if score < policy.min_score:
                return BehaviorEvaluation(False, ("below_score_threshold",), score)
            return BehaviorEvaluation(True, ("eligible",), score)
        except Exception:
            return BehaviorEvaluation(False, ("behavior_dependency_unavailable",))

    async def simulate(self, context: Context) -> dict[str, Any]:
        """只生成一条用于页面展示的话：不判时机/冷却/额度，不写库、不发送。

        管理员点「模拟」就是想看「现在这样会说出什么」，所以这里刻意绕开所有
        gate，只用当前人格+情绪+最近素材调一次模型，把文本带回去展示。
        """
        if self._closed:
            return {"status": "unavailable", "reason_code": "behavior_closed", "text": ""}
        policy = self.policy()
        now = self._now()
        try:
            snapshot = await self.current(context)
        except Exception:
            snapshot = None
        if snapshot is None:
            return {"status": "unavailable", "reason_code": "source_unavailable", "text": ""}
        intent = BehaviorIntent(
            stable_key("behavior-simulate", context.scope_key, now), context, "simulate",
            now, now + 300, await self.store.get_generation(context),
        )
        materials: tuple[Material, ...] = ()
        try:
            request = MemoryRequest(intent.intent_id, "simulate", context)
            recall = await (self.materials(request) if self.materials
                            else self._local_materials(request))
            if isinstance(recall, RecallResult):
                materials = tuple(recall.materials)[:3]
        except Exception:
            materials = ()
        try:
            text = await asyncio.wait_for(
                self.model(GenerationRequest(intent, snapshot, materials,
                                             policy.max_output_tokens, policy.max_output_chars)),
                timeout=policy.model_timeout_seconds,
            )
        except Exception:
            return {"status": "failed", "reason_code": "model_unavailable", "text": ""}
        if not isinstance(text, str) or not text.strip():
            return {"status": "failed", "reason_code": "model_output_invalid", "text": ""}
        if not public_text_allowed(text):
            return {"status": "failed", "reason_code": "model_output_unsafe", "text": ""}
        return {"status": "ok", "reason_code": "simulated",
                "text": text.strip()[: policy.max_output_chars],
                "materials": len(materials)}

    async def preview_behavior(self, context: Context) -> BehaviorPreview:
        result = await self.evaluate(context)
        return BehaviorPreview(result.eligible, result.reason_codes, score=result.score)

    async def _local_materials(self, request: MemoryRequest) -> RecallResult:
        rows = await self.store.read_window(request.context)
        result = []
        for row in reversed(rows):
            event = Event.from_dict({**row["metadata_json"], "body": row["body"]})
            if (not event.reliable_source or event.event_type in (
                "dream", "diary", "summary", "fact", "legacy_unknown", "observation",
            )):
                continue
            if event.actor_role == ActorRole.HUMAN and event.actor_id == event.context.account_id:
                kind = ContentKind.INTERACTION
            elif (event.actor_role == ActorRole.BOT
                  and event.event_type == "bot_action_succeeded"
                  and event.actor_id == event.context.bot_id):
                kind = ContentKind.BOT_ACTION
            else:
                continue
            if not event.body.strip():
                continue
            material = Material(EvidenceRef(
                "livingemotion", event.idempotency_key, event.context,
                event.actor_id, event.context.bot_id, kind, event.occurred_at,
                expires_at=event.occurred_at + self.store.config.window_days * 86400,
            ), event.body)
            if material_allowed(material, request.context, self._now()):
                result.append(material)
            if len(result) == request.limit:
                break
        return RecallResult(tuple(reversed(result)))

    async def _valid_materials(self, attempt: _Attempt) -> bool:
        context = attempt.intent.context
        now = self._now()
        materials = attempt.materials
        if not materials or len(materials) > 4:
            return False
        if any(
            not isinstance(item, Material)
            or not material_allowed(item, context, now)
            or item.evidence.holder_id != context.bot_id
            or item.evidence.kind not in (
                ContentKind.INTERACTION, ContentKind.BOT_ACTION,
                ContentKind.FACT, ContentKind.SUMMARY,
            )
            for item in materials
        ):
            return False
        request = MemoryRequest(attempt.intent.intent_id, attempt.intent.purpose, context)
        validation = await self._bounded(
            self.validate_evidence(request, materials), self.policy(),
        )
        # Revocation discards the entire generation, never only its citations.
        return (isinstance(validation, ValidationResult) and validation.valid is True
                and validation.materials == materials)

    async def _review(self, attempt: _Attempt, *, manual: bool = False) -> str | None:
        _, _, reasons = await self._gates(attempt.intent.context, attempt=attempt,
                                          manual=manual)
        if reasons:
            return reasons[0]
        if not await self._valid_materials(attempt):
            return "evidence_invalid"
        # Validators can wait for external I/O. Refresh after they return.
        snapshot, policy, reasons = await self._gates(attempt.intent.context, attempt=attempt,
                                                     manual=manual)
        if reasons:
            return reasons[0]
        latest = await self._bounded(self.current(attempt.intent.context), policy)
        if (not isinstance(latest, BehaviorSnapshot) or latest.context != snapshot.context
                or latest.persona_prompt != snapshot.persona_prompt
                or latest.lifecycle_revision != snapshot.lifecycle_revision
                or latest.route_verified is not True):
            return "context_changed"
        context = attempt.intent.context
        if await self.store.get_generation(context) != attempt.intent.generation:
            return "stale_generation"
        if await self.store.human_watermark(context) != attempt.intent.human_watermark:
            return "new_human_message"
        now, policy = self._now(), self.policy()
        reasons = list(self._policy_reasons(context, policy, now) + self._snapshot_reasons(
            latest, context, policy, now, attempt,
        ))
        if manual:
            reasons = [reason for reason in reasons if reason not in _MANUAL_SOFT_REASONS]
        if reasons:
            return reasons[0]
        if any(not material_allowed(item, context, now) for item in attempt.materials):
            return "evidence_invalid"
        return None

    async def _transition(self, attempt: _Attempt, old: str, new: str, reason: str):
        return await self.store.transition_intent(
            attempt.intent.context, attempt.intent.intent_id, attempt.intent.generation,
            expected_status=old, status=new, reason_code=reason,
            reservation_id=attempt.reservations[0] if attempt.reservations else None,
            transport_receipt=attempt.transport_receipt if new in TERMINAL else None,
            content=attempt.content if new == "sending" else None,
            # 留存模型生成时的情绪；发送前的最新状态不能改写这份快照。
            emotion_snapshot=",".join(attempt.snapshot.affect.labels) if new == "sending" else None,
        )

    def _result(
        self, attempt: _Attempt, status: str, reason: str, *, recorded: bool = False,
    ) -> BehaviorResult:
        return BehaviorResult(
            attempt.intent.intent_id, status, (reason,), attempt.score,
            attempt.model_calls, attempt.sender_calls, recorded,
        )

    async def _settle(
        self, attempt: _Attempt, status: str, reason: str,
    ) -> BehaviorResult:
        try:
            row = await self.store.get_intent(attempt.intent.context, attempt.intent.intent_id)
            if row is None:
                self._faulted = True
                return self._result(attempt, "unknown", "intent_missing")
            old = row["status"]
            if old not in TERMINAL:
                if old == "pending":
                    status = "cancelled"
                elif old == "sending" and status == "cancelled":
                    status = "unknown" if attempt.sender_calls else "failed"
                transition = await self._transition(attempt, old, status, reason)
                if transition["status"] != "updated":
                    row = await self.store.get_intent(
                        attempt.intent.context, attempt.intent.intent_id,
                    )
                    status = row["status"] if row else "unknown"
                    reason = transition["reason_code"]
            else:
                status, reason = old, row["reason_code"]
            for reservation in attempt.reservations:
                await self.store.finish_quota(
                    reservation, status=status if status in TERMINAL else "unknown",
                    reason_code=reason,
                )
            return self._result(attempt, status, reason)
        except Exception:
            # The durable sending marker is recovered as unknown on next startup.
            self._faulted = True
            return self._result(attempt, "unknown", "behavior_storage_fault")

    async def execute(
        self, context: Context, *, intent_id: str, purpose: str = "proactive",
        manual: bool = False,
    ) -> BehaviorResult:
        return await self._enqueue(context, intent_id, purpose, manual=manual)

    async def execute_intent(self, intent: BehaviorIntent) -> BehaviorResult:
        """Consume an unpersisted T5 proposal without refreshing its invalidation tokens."""
        if intent.status != IntentStatus.PENDING:
            return BehaviorResult(intent.intent_id, "rejected", ("proposal_not_pending",))
        return await self._enqueue(intent.context, intent.intent_id, intent.purpose, intent)

    async def _enqueue(
        self, context: Context, intent_id: str, purpose: str,
        proposal: BehaviorIntent | None = None, *, manual: bool = False,
    ) -> BehaviorResult:
        if not isinstance(intent_id, str) or not intent_id.strip() or len(intent_id) > 256:
            raise ValueError("stable_intent_id_required")
        if not isinstance(purpose, str) or not purpose.strip() or len(purpose) > 256:
            raise ValueError("purpose_required")
        if self._closed:
            return BehaviorResult(intent_id, "rejected", ("behavior_closed",))
        if self._lane.pending >= self.policy().max_pending:
            return BehaviorResult(intent_id, "rejected", ("behavior_queue_full",))
        task = asyncio.current_task()
        self._tasks.add(task)
        self._lane.pending += 1
        try:
            async with self._lane.lock:
                return await self._execute(context, intent_id, purpose, proposal, manual=manual)
        finally:
            self._tasks.discard(task)
            self._lane.pending -= 1

    async def _execute(
        self, context: Context, intent_id: str, purpose: str,
        proposal: BehaviorIntent | None, *, manual: bool = False,
    ) -> BehaviorResult:
        attempt = None
        try:
            existing = await self.store.get_intent(context, intent_id)
            if existing:
                return BehaviorResult(intent_id, existing["status"], ("intent_exists",))
            snapshot, policy, reasons = await self._gates(context, manual=manual)
            if reasons:
                return BehaviorResult(intent_id, "rejected", reasons)
            score = behavior_score(snapshot)
            if score < policy.min_score and not manual:
                return BehaviorResult(intent_id, "rejected", ("below_score_threshold",), score)
            # Capture the watermark before any retrieval or generation.
            generation = await self.store.get_generation(context)
            watermark = await self.store.human_watermark(context)
            now = self._now()
            if proposal is not None:
                reason = None
                if proposal.generation != generation:
                    reason = "stale_generation"
                elif proposal.human_watermark != watermark:
                    reason = "new_human_message"
                elif proposal.created_at > now:
                    reason = "future_intent"
                elif proposal.expires_at <= now:
                    reason = "expired_intent"
                if reason:
                    return BehaviorResult(intent_id, "rejected", (reason,))
                intent = proposal
            else:
                intent = BehaviorIntent(
                    intent_id, context, purpose, now, now + policy.intent_ttl_seconds,
                    generation, human_watermark=watermark,
                )
            created = await self.store.create_intent(intent)
            if created["status"] != "created":
                return BehaviorResult(intent_id, created["status"], (created["reason_code"],))
            attempt = _Attempt(intent, snapshot, policy, self._period(policy, now), score)
            reservation = stable_key("behavior-send", intent_id)
            attempt.reservations.append(reservation)
            attempt.stage = "quota_reservation"
            reserved = await self.store.reserve_quota(
                reservation, context, generation, period=attempt.period, purpose=SEND_PURPOSE,
                pool=SEND_POOL, limit=policy.global_daily_limit,
                global_limit=policy.global_daily_limit, scope_limit=policy.scope_daily_limit,
            )
            if reserved["status"] != "reserved":
                return await self._settle(attempt, "cancelled", reserved["reason_code"])
            transition = await self._transition(attempt, "pending", "reserved", "quota_reserved")
            if transition["status"] != "updated":
                return await self._settle(attempt, "cancelled", transition["reason_code"])
            attempt.stage = "materials"
            request = MemoryRequest(intent_id, purpose, context)
            recall = await self._bounded(
                self.materials(request) if self.materials else self._local_materials(request),
                policy,
            )
            if not isinstance(recall, RecallResult):
                return await self._settle(attempt, "cancelled", "materials_invalid")
            attempt.materials = tuple(recall.materials)
            if not await self._valid_materials(attempt):
                return await self._settle(attempt, "cancelled", "no_qualified_materials")
            reason = await self._review(attempt, manual=manual)
            if reason:
                return await self._settle(attempt, "cancelled", reason)
            if (len(snapshot.persona_prompt) + sum(len(item.text) for item in attempt.materials)
                    > policy.max_input_chars):
                return await self._settle(attempt, "cancelled", "model_input_too_large")
            transition = await self._transition(attempt, "reserved", "generating", "generating")
            if transition["status"] != "updated":
                return await self._settle(attempt, "cancelled", transition["reason_code"])
            attempt.stage = "model"
            attempt.model_calls += 1
            text = await asyncio.wait_for(self.model(GenerationRequest(
                intent, snapshot, attempt.materials,
                policy.max_output_tokens, policy.max_output_chars,
            )), timeout=policy.model_timeout_seconds)
            if not isinstance(text, str) or not text.strip() or len(text) > policy.max_output_chars:
                return await self._settle(attempt, "failed", "model_output_invalid")
            if not public_text_allowed(text):
                return await self._settle(attempt, "failed", "model_output_unsafe")
            attempt.stage = "final_review"
            reason = await self._review(attempt, manual=manual)
            if reason:
                return await self._settle(attempt, "cancelled", reason)
            # 正文随 sending 标记一起持久化，发送失败或服务中断仍可回查。
            attempt.content = text.strip()
            transition = await self._transition(attempt, "generating", "sending", "dispatch_claimed")
            if transition["status"] != "updated":
                return await self._settle(attempt, "cancelled", transition["reason_code"])

            send_deadline = asyncio.get_running_loop().time() + self.policy().send_timeout_seconds

            async def authorize() -> bool:
                attempt.guard_called = True
                attempt.guard_reason = await self._review(attempt, manual=manual)
                # Async authorization can finish on the same loop turn as timeout.
                # Refuse a late dispatch even if wait_for cancellation has not run.
                if asyncio.get_running_loop().time() >= send_deadline:
                    raise TimeoutError("send_authorization_expired")
                return attempt.guard_reason is None

            attempt.stage = "send"
            attempt.sender_calls += 1
            receipt = await asyncio.wait_for(
                self.sender(SendRequest(intent_id, context, text.strip(), authorize)),
                timeout=self.policy().send_timeout_seconds,
            )
            status, reason = self._receipt_status(attempt, receipt)
            attempt.transport_receipt = {
                "status": "confirmed" if status == "succeeded" else
                          "rejected" if status == "failed" else "unknown",
                "receipt_id": receipt.receipt_id if status == "succeeded" else None,
            }
            result = await self._settle(attempt, status, reason)
            if result.status != "succeeded" or self._closed:
                return result
            # A send and a local commit cannot be atomic. Never retry the send here.
            event = Event(
                stable_key("behavior-receipt", intent_id, receipt.receipt_id),
                "livingemotion.behavior", "bot_action_succeeded", context, ActorRole.BOT,
                self._now(), receipt.receipt_id, actor_id=context.bot_id, body=text.strip(),
                evidence=tuple(item.evidence for item in attempt.materials),
            )
            try:
                committed = await self.record_success(event, generation)
                recorded = committed.accepted or committed.status == "duplicate"
            except Exception:
                recorded = False
            return self._result(
                attempt, "succeeded",
                "send_confirmed" if recorded else "success_event_not_recorded",
                recorded=recorded,
            )
        except asyncio.CancelledError:
            if attempt:
                await self._settle(
                    attempt, "unknown" if attempt.sender_calls else "cancelled",
                    "send_interrupted" if attempt.sender_calls else "execution_cancelled",
                )
            raise
        except Exception:
            if attempt:
                return await self._settle(
                    attempt, "unknown" if attempt.sender_calls else "failed",
                    f"{attempt.stage}_unavailable",
                )
            return BehaviorResult(intent_id, "rejected", ("behavior_dependency_unavailable",))

    @staticmethod
    def _receipt_status(attempt: _Attempt, receipt: object) -> tuple[str, str]:
        if (not isinstance(receipt, SendReceipt) or receipt.intent_id != attempt.intent.intent_id
                or receipt.route != attempt.intent.context.route):
            return "unknown", "send_unconfirmed"
        if (type(receipt.confirmed_parts) is not int or type(receipt.total_parts) is not int
                or receipt.total_parts < 1
                or not 0 <= receipt.confirmed_parts <= receipt.total_parts):
            return "unknown", "receipt_invalid"
        if (receipt.status == "rejected" and receipt.confirmed_parts == 0):
            return "failed", attempt.guard_reason or "send_rejected"
        if not attempt.guard_called:
            return "unknown", "sender_guard_not_used"
        if attempt.guard_reason:
            return "unknown", "sender_ignored_guard"
        if (receipt.status == "confirmed" and receipt.confirmed_parts == receipt.total_parts
                and isinstance(receipt.receipt_id, str) and receipt.receipt_id.strip()
                and len(receipt.receipt_id) <= 512):
            return "succeeded", "send_confirmed"
        return "unknown", "partial_send" if receipt.confirmed_parts else "send_unconfirmed"

    async def close(self) -> None:
        """Cancel and drain before the lifecycle owner closes SQLite."""
        self._closed = True
        tasks = tuple(task for task in self._tasks if task is not asyncio.current_task())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def execute_control(self, context, *, intent_id, purpose, generate,
                              authorize, on_submit, generation, revision):
        """Closing and catchup share this executor, lane and durable send protocol.

        A caller supplies a purpose-specific authorization check. These messages
        concern an existing conversation and do not require idle autonomy.
        """
        if purpose not in ("closing", "catchup", "dream_wake") or not context.route:
            return "rejected"
        task = asyncio.current_task()
        self._tasks.add(task)
        try:
            async with self._lane.lock:
                return await self._control(
                    context, intent_id, purpose, generate, authorize, on_submit,
                    generation, revision,
                )
        finally:
            self._tasks.discard(task)

    async def _control(self, context, key, purpose, generate, authorize, on_submit,
                       generation, revision):
        async def permitted():
            return (not self._closed and not self._faulted
                    and await self.validate_identity(context)
                    and await self.store.get_generation(context) == generation
                    and await authorize(context, generation, revision))

        if not await permitted():
            return "rejected"
        now = self._now()
        watermark = await self.store.human_watermark(context)
        intent = BehaviorIntent(key, context, purpose, now, now + 300,
                                generation, human_watermark=watermark)
        created = await self.store.create_intent(intent)
        if created.get("status") != "created":
            old = await self.store.get_intent(context, key)
            return "confirmed" if old and old["status"] == "succeeded" else "unknown"
        current_status, dispatched, reserved = "pending", False, False
        result = "rejected"

        transport_receipt = None
        async def transition(new, reason):
            nonlocal current_status
            outcome = await self.store.transition_intent(
                context, key, generation, expected_status=current_status,
                status=new, reason_code=reason,
                reservation_id=key + ":send" if new == "reserved" else None,
                transport_receipt=transport_receipt if new in TERMINAL else None,
            )
            if outcome["status"] != "updated":
                raise ValueError("control_intent_changed")
            current_status = new

        async def send_guard():
            return (await permitted()
                    and await self.store.human_watermark(context) == watermark)

        try:
            period = self._period(self.policy(), now)
            if not period:
                raise ValueError("timezone_required")
            quota = await self.store.reserve_quota(
                key + ":send", context, generation, period=period, purpose=purpose,
                pool="send", limit=self.store.config.behavior_daily_limit,
                global_limit=self.store.config.behavior_daily_limit,
            )
            if quota.get("status") != "reserved":
                raise ValueError("control_quota_unavailable")
            reserved = True
            await transition("reserved", "control_reserved")
            await transition("generating", "control_generation")
            text = await generate()
            if (not isinstance(text, str) or not text.strip()
                    or len(text) > self.policy().max_output_chars or not await send_guard()):
                raise ValueError("control_content_changed")
            # All control outputs pass the same public-text scrubber as proactive
            # messages. An invalid model result cannot reach a platform.
            if not public_text_allowed(text):
                raise ValueError("control_output_unsafe")
            await transition("sending", "control_submit")

            guard_called, guard_allowed = False, False
            deadline = asyncio.get_running_loop().time() + self.policy().send_timeout_seconds
            async def submit_guard():
                nonlocal guard_called, guard_allowed
                guard_called = True
                if not await send_guard():
                    return False
                # This is submission to the host, not a transport receipt.
                allowed = await on_submit(context, key, text)
                if asyncio.get_running_loop().time() >= deadline:
                    raise TimeoutError("send_authorization_expired")
                guard_allowed = bool(allowed)
                return guard_allowed

            dispatched = True
            receipt = await asyncio.wait_for(
                self.sender(SendRequest(key, context, text, submit_guard)),
                timeout=self.policy().send_timeout_seconds,
            )
            confirmed = (isinstance(receipt, SendReceipt)
                         and receipt.intent_id == key and receipt.route == context.route
                         and receipt.status == "confirmed"
                         and guard_called and guard_allowed
                         and isinstance(receipt.receipt_id, str) and bool(receipt.receipt_id)
                         and len(receipt.receipt_id) <= 512
                         and type(receipt.confirmed_parts) is int
                         and type(receipt.total_parts) is int
                         and receipt.confirmed_parts == receipt.total_parts
                         and receipt.total_parts > 0)
            result = "confirmed" if confirmed else "unknown"
            if (isinstance(receipt, SendReceipt) and receipt.status == "rejected"
                    and receipt.intent_id == key and receipt.route == context.route
                    and receipt.confirmed_parts == 0):
                result = "rejected"
            transport_receipt = {"status": result,
                                 "receipt_id": receipt.receipt_id if confirmed else None}
            await transition("succeeded" if confirmed else
                             "failed" if result == "rejected" else "unknown",
                             "send_" + result)
            return result
        except BaseException as exc:
            status = "unknown" if dispatched else (
                "cancelled" if current_status == "pending" else "failed")
            if current_status not in TERMINAL:
                if status not in INTENT_CONTROL_TRANSITIONS.get(current_status, ()):
                    status = "cancelled"
                await asyncio.shield(transition(status, "control_interrupted"))
            if isinstance(exc, asyncio.CancelledError):
                raise
            return "unknown" if dispatched else "rejected"
        finally:
            if reserved:
                await asyncio.shield(self.store.finish_quota(
                    key + ":send", status=("succeeded" if result == "confirmed" else
                                          "unknown" if dispatched else "failed"),
                    reason_code="control_" + result,
                ))


INTENT_CONTROL_TRANSITIONS = {
    "pending": {"cancelled"}, "reserved": {"failed", "cancelled"},
    "generating": {"failed", "cancelled"}, "sending": {"failed", "unknown"},
}
