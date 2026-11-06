"""Version-one shared kernel. No host, storage, model or plugin imports.

Times are finite UTC Unix seconds; revisions are opaque strings.
Context keys preserve source scopes, never identity-provider projections.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, is_dataclass
from enum import Enum
import hashlib
import json
import math
from typing import Any, Mapping

API_VERSION = 1
SCHEMA_VERSION = 3
_PLAIN_JSON_SCALARS = frozenset((str, int, float, bool, type(None)))
_NATIVE_FIELDS: dict[type, tuple[str, ...]] = {}


class _GenericConversion(Exception):
    pass


def _native_contract_json(value: Any) -> Any:
    """One pass for known contract snapshots containing only native values."""
    kind = type(value)
    if kind in _PLAIN_JSON_SCALARS:
        return value
    names = _NATIVE_FIELDS.get(kind)
    if names is not None:
        return {name: _native_contract_json(getattr(value, name)) for name in names}
    if kind is tuple or kind is list:
        return [_native_contract_json(item) for item in value]
    if kind in (SceneKind, ActorRole, ContentKind, NightPhase, SleepState, IntentStatus):
        return value.value
    # Custom values keep asdict's deepcopy, mapping and subclass behavior.
    raise _GenericConversion


class SceneKind(str, Enum):
    PRIVATE = "private"
    GROUP = "group"
    PUBLIC_COMMENT = "public_comment"


class ActorRole(str, Enum):
    BOT = "bot"
    HUMAN = "human"
    UNKNOWN = "unknown"


class ContentKind(str, Enum):
    INTERACTION = "interaction"
    BOT_ACTION = "bot_action"
    OBSERVATION = "observation"
    FACT = "fact"
    DIARY = "diary"
    DREAM = "dream"
    SUMMARY = "summary"
    LEGACY_UNKNOWN = "legacy_unknown"


class NightPhase(str, Enum):
    AWAKE = "awake"
    DROWSY = "drowsy"
    SETTLING = "settling"
    ASLEEP = "asleep"
    WAKING = "waking"


class SleepState(str, Enum):
    AWAKE = "awake"
    NAP = "nap"
    GROGGY = "groggy"
    DROWSY = "drowsy"
    DEEP_SLEEP = "deep_sleep"


class IntentStatus(str, Enum):
    PENDING = "pending"
    RESERVED = "reserved"
    GENERATING = "generating"
    SENDING = "sending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


def finite(value: float, name: str, low: float | None = None,
           high: float | None = None) -> None:
    # Persisted JSON numbers are exact built-ins; subclasses/bool still use
    # the original type checks and every value still gets finite/range checks.
    kind = type(value)
    if kind is not float and kind is not int and (
        isinstance(value, bool) or not isinstance(value, (float, int))
    ):
        raise ValueError(f"{name}: expected finite number")
    if not math.isfinite(value) or (low is not None and value < low) or (
        high is not None and value > high
    ):
        raise ValueError(f"{name}: out of range")


def _text(value: str, name: str, *, optional: bool = False) -> None:
    if not isinstance(value, str) or len(value) > 512 or (
        not optional and not value.strip()
    ):
        raise ValueError(f"{name}: invalid identifier")


def to_dict(value: Any) -> Any:
    """Convert contract values to JSON-compatible data, without host objects."""
    # Guard snapshots have many plain leaves: avoid dataclass/typing dispatch
    # for each one, while keeping Enum, subclasses and custom mappings unchanged.
    kind = type(value)
    if kind in _PLAIN_JSON_SCALARS:
        return value
    if kind is dict:
        return {str(k): to_dict(v) for k, v in value.items()}
    if kind is list or kind is tuple:
        return [to_dict(v) for v in value]
    if kind in _NATIVE_FIELDS:
        try:
            return _native_contract_json(value)
        except _GenericConversion:
            pass
    if is_dataclass(value) and not isinstance(value, type):
        return to_dict(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(k): to_dict(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_dict(v) for v in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(to_dict(value), ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def stable_key(*parts: Any) -> str:
    return hashlib.sha256(canonical_json(parts).encode("utf-8")).hexdigest()


def state_persona_key(context) -> str:
    return stable_key("state-persona", context.instance_id, context.persona_id)


def state_owner_key(context, shared: bool) -> str:
    return stable_key("state-shared", context.instance_id, context.persona_id) if shared else (
        context.scope_key
    )


@dataclass(frozen=True)
class Context:
    bot_id: str
    persona_id: str
    adapter_id: str
    platform: str
    scene_kind: SceneKind
    scene_id: str
    account_id: str = ""
    persona_revision: str = "0"
    identity_revision: str = "0"
    audience: tuple[str, ...] = ()
    route: str | None = None
    instance_id: str = "local"

    def __post_init__(self) -> None:
        for name in ("bot_id", "persona_id", "adapter_id", "platform", "scene_id",
                     "persona_revision", "identity_revision", "instance_id"):
            _text(getattr(self, name), name)
        _text(self.account_id, "account_id", optional=True)
        object.__setattr__(self, "scene_kind", SceneKind(self.scene_kind))
        object.__setattr__(self, "audience", tuple(self.audience))
        for member in self.audience:
            _text(member, "audience")
        if self.scene_kind == SceneKind.PUBLIC_COMMENT and self.route is not None:
            raise ValueError("public comments cannot carry a sending route")

    @property
    def scope_key(self) -> str:
        return stable_key(self.instance_id, self.bot_id, self.persona_id, self.adapter_id,
                          self.platform, self.scene_kind, self.scene_id)

    @property
    def account_key(self) -> str:
        return stable_key(self.scope_key, self.account_id)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Context:
        return cls(**dict(value))


@dataclass(frozen=True)
class ScopeSelection:
    """Authenticated management selector, never a sending context."""
    persona_id: str
    view_scope: str = "global"
    scene_id: str | None = None
    platform: str | None = None

    def __post_init__(self) -> None:
        _text(self.persona_id, "persona_id")
        if self.view_scope not in ("global", "private", "group"):
            raise ValueError("invalid view scope")
        for name in ("scene_id", "platform"):
            if getattr(self, name) is not None:
                _text(getattr(self, name), name)


@dataclass(frozen=True)
class StateOwner:
    """Immutable mutation ticket. Source generation remains separate."""
    owner_key: str
    persona_key: str
    mode: str
    revision: int
    generation: int = 0

    def __post_init__(self) -> None:
        _text(self.owner_key, "owner_key")
        _text(self.persona_key, "persona_key")
        if self.mode not in ("shared", "scene"):
            raise ValueError("invalid state mode")
        for name in ("revision", "generation"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError(f"invalid {name}")


@dataclass(frozen=True)
class EvidenceRef:
    provider: str
    source_id: str
    context: Context
    subject_id: str
    holder_id: str
    kind: ContentKind
    occurred_at: float
    expires_at: float | None = None
    sensitive: bool = True
    exportable: bool = False
    authorization: str | None = None
    source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("provider", "source_id", "subject_id", "holder_id"):
            _text(getattr(self, name), name)
        finite(self.occurred_at, "occurred_at", 0)
        if self.expires_at is not None:
            finite(self.expires_at, "expires_at", self.occurred_at)
        object.__setattr__(self, "kind", ContentKind(self.kind))


@dataclass(frozen=True)
class Event:
    event_id: str
    producer: str
    event_type: str
    context: Context
    actor_role: ActorRole
    occurred_at: float
    source_id: str
    actor_id: str = ""
    body: str = ""
    signals: tuple[str, ...] = ()
    confidence: float = 1.0
    evidence: tuple[EvidenceRef, ...] = ()
    reliable_source: bool = True
    rule_version: str = "1"

    def __post_init__(self) -> None:
        for name in ("event_id", "producer", "event_type", "source_id"):
            _text(getattr(self, name), name)
        _text(self.actor_id, "actor_id", optional=True)
        finite(self.occurred_at, "occurred_at", 0)
        finite(self.confidence, "confidence", 0, 1)
        if not isinstance(self.body, str):
            raise ValueError("body: expected text")
        object.__setattr__(self, "actor_role", ActorRole(self.actor_role))
        object.__setattr__(self, "signals", tuple(self.signals))
        for signal in self.signals:
            _text(signal, "signal")

    @property
    def idempotency_key(self) -> str:
        # Producer event_id is correlation, not a substitute for a source ID.
        return stable_key(self.producer, self.context.scope_key,
                          self.context.account_id, self.source_id, self.event_type)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Event:
        data = dict(value)
        if not isinstance(data.get("context"), Context):
            data["context"] = Context.from_dict(data["context"])
        refs = []
        for ref in data.get("evidence", ()):
            if isinstance(ref, EvidenceRef):
                refs.append(ref)
            else:
                item = dict(ref)
                item["context"] = Context.from_dict(item["context"])
                refs.append(EvidenceRef(**item))
        data["evidence"] = tuple(refs)
        return cls(**data)


@dataclass(frozen=True)
class BotAffect:
    pleasure: float = 0.0
    arousal: float = 0.3
    stress: float = 0.0
    social_need: float = 0.3
    labels: tuple[str, ...] = ("calm",)
    updated_at: float = 0.0
    reason_codes: tuple[str, ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()
    rule_version: str = "1"

    def __post_init__(self) -> None:
        finite(self.pleasure, "pleasure", -1, 1)
        for name in ("arousal", "stress", "social_need"):
            finite(getattr(self, name), name, 0, 1)
        finite(self.updated_at, "updated_at", 0)


@dataclass(frozen=True)
class HumanObservation:
    subject_id: str
    labels: tuple[str, ...]
    confidence: float
    occurred_at: float
    expires_at: float
    evidence: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        _text(self.subject_id, "subject_id")
        finite(self.confidence, "confidence", 0, 1)
        finite(self.occurred_at, "occurred_at", 0)
        finite(self.expires_at, "expires_at", self.occurred_at)


@dataclass(frozen=True)
class Relationship:
    score: float = 0.0
    stage: str = "unestablished"
    trust: float | None = None
    familiarity: float | None = None
    boundary: float | None = None
    frozen: bool = False
    evidence_complete: bool = True
    identity_revision: str = "0"
    updated_at: float = 0.0
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        finite(self.score, "score", 0, 1000)
        for name in ("trust", "familiarity", "boundary"):
            value = getattr(self, name)
            if value is not None:
                finite(value, name, 0, 1)
        finite(self.updated_at, "updated_at", 0)

    @property
    def normalized(self) -> float:
        return self.score / 1000.0


@dataclass(frozen=True)
class RelationshipContribution:
    """Non-body ledger entry; immutable source scope enables later unbinding."""
    source_id: str
    account_id: str
    occurred_at: float
    delta: float
    reason_code: str
    day: str
    dimension: str = "score"

    def __post_init__(self) -> None:
        for name in ("source_id", "account_id", "reason_code", "day", "dimension"):
            _text(getattr(self, name), name)
        finite(self.occurred_at, "occurred_at", 0)
        finite(self.delta, "delta", -1000, 1000)


@dataclass(frozen=True)
class NightState:
    phase: NightPhase = NightPhase.AWAKE
    energy: float = 100.0
    updated_at: float = 0.0
    sleep_started_at: float | None = None
    wake_at: float | None = None
    transition_deadline: float | None = None
    sleep_stage: str | None = None
    awaiting_reply_id: str | None = None
    unread_watermark: int = 0
    reason_codes: tuple[str, ...] = ()
    display_state: SleepState | None = None
    policy_version: int = 1
    energy_units: int | None = None
    energy_remainder: int = 0
    energy_direction: str = ""
    cycle_id: str | None = None
    cycle_kind: str | None = None
    cycle_started_at: float | None = None
    deep_sleep_at: float | None = None
    drowsy_at: float | None = None
    base_wake_at: float | None = None
    lie_in_minutes: int | None = None
    wake_score: int | None = None
    wake_failures: int = 0
    wake_session: str | None = None
    wake_replies_used: int = 0
    wake_reply_limit: int = 0
    first_reply_submitted_at: float | None = None
    wake_window_deadline: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "phase", NightPhase(self.phase))
        if self.display_state is not None:
            object.__setattr__(self, "display_state", SleepState(self.display_state))
        if self.policy_version not in (1, 2):
            raise ValueError("invalid night policy")
        if self.energy_units is not None and (
            type(self.energy_units) is not int or not 0 <= self.energy_units <= 1000
            or abs(self.energy - self.energy_units / 10) > 1e-9
        ):
            raise ValueError("energy units mismatch")
        for name in ("energy_remainder", "wake_failures", "wake_replies_used",
                     "wake_reply_limit"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError(f"invalid {name}")
        if self.energy_remainder >= 60_000_000:
            raise ValueError("invalid energy remainder")
        if self.energy_direction not in ("", "fatigue", "recovery"):
            raise ValueError("invalid energy direction")
        for name in ("lie_in_minutes", "wake_score"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"invalid {name}")
        finite(self.energy, "energy", 0, 100)
        finite(self.updated_at, "updated_at", 0)
        for name in ("sleep_started_at", "wake_at", "transition_deadline", "cycle_started_at",
                     "deep_sleep_at", "drowsy_at", "base_wake_at",
                     "first_reply_submitted_at", "wake_window_deadline"):
            if getattr(self, name) is not None:
                finite(getattr(self, name), name, 0)


@dataclass(frozen=True)
class BehaviorIntent:
    intent_id: str
    context: Context
    purpose: str
    created_at: float
    expires_at: float
    generation: int
    status: IntentStatus = IntentStatus.PENDING
    human_watermark: int = 0
    evidence: tuple[EvidenceRef, ...] = ()
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.intent_id, "intent_id")
        _text(self.purpose, "purpose")
        finite(self.created_at, "created_at", 0)
        finite(self.expires_at, "expires_at", self.created_at)
        object.__setattr__(self, "status", IntentStatus(self.status))


@dataclass(frozen=True)
class Experience:
    experience_id: str
    context: Context
    kind: ContentKind
    period: str
    created_at: float
    body: str
    evidence: tuple[EvidenceRef, ...] = ()
    expires_at: float | None = None
    pinned: bool = False
    clarity: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", ContentKind(self.kind))
        if self.kind not in (ContentKind.DIARY, ContentKind.DREAM):
            raise ValueError("experience kind must be diary or dream")
        finite(self.created_at, "created_at", 0)
        finite(self.clarity, "clarity", 0, 1)


@dataclass(frozen=True)
class StateWrite:
    """One CAS projection write; expected_version=0 creates an absent record."""
    kind: str
    value: Mapping[str, Any]
    expected_version: int = 0
    record_key: str = ""
    owner: StateOwner | None = None
    energy_events: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class StateRecord:
    kind: str
    value: Mapping[str, Any]
    version: int
    generation: int
    updated_at: float
    record_key: str = ""
    owner: StateOwner | None = None


@dataclass(frozen=True)
class CommitResult:
    status: str
    reason_code: str
    event_key: str | None = None
    generation: int = 0
    versions: Mapping[str, int] = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return self.status == "accepted"


@dataclass(frozen=True)
class Availability:
    available: bool
    reason_codes: tuple[str, ...] = ()
    block_chat: bool = False


@dataclass(frozen=True)
class BehaviorPreview:
    eligible: bool = False
    reason_codes: tuple[str, ...] = ("autonomy_disabled",)
    model_calls: int = 0
    sends: int = 0


# Explicit compatibility names for modules which call the event a domain event.
DomainEvent = Event
BotState = BotAffect
RelationshipState = Relationship

# Limit the single-pass serializer to our stable scalar/tuple contracts.
_NATIVE_FIELDS.update({
    cls: tuple(item.name for item in fields(cls))
    for cls in (Context, Event, EvidenceRef, BotAffect, HumanObservation, Relationship, NightState)
})
