"""Validated safe defaults, independent of AstrBot's configuration wrapper."""

from dataclasses import dataclass, fields
from datetime import time
from decimal import Decimal
import math
from typing import Any, Mapping
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Config:
    enabled: bool = True
    mode: str = "active"
    memory_mode: str = "none"
    memory_read: bool = False
    memory_export: bool = False
    autonomy_enabled: bool = False
    group_autonomy_enabled: bool = False
    emotion_model_enabled: bool = False
    dream_enabled: bool = False
    diary_enabled: bool = False
    night_enabled: bool = True
    night_block_chat: bool = False
    persona_mode: str = "follow"
    persona_id: str = ""
    timezone: str = ""
    provider_id: str = ""
    fallback_provider_id: str = ""
    autonomy_scopes: str = ""
    muted_scopes: str = ""
    night_schedule_enabled: bool = False
    sleep_at: str = "01:00"
    wake_at: str = "08:00"
    diary_at: str = "23:00"
    diary_backfill_yesterday: bool = False
    scheduler_seconds: int = 60
    dnd_start: str = "01:00"
    dnd_end: str = "08:00"
    active_start: str = "00:00"
    active_end: str = "23:59"
    behavior_daily_limit: int = 6
    behavior_scope_daily_limit: int = 2
    behavior_cooldown_seconds: int = 7200
    behavior_unanswered_limit: int = 2
    behavior_random_min_minutes: int = 90
    behavior_random_max_minutes: int = 240
    behavior_idle_minutes: int = 20
    behavior_style: str = "balanced"
    behavior_emotional_share: bool = True
    behavior_provider_id: str = ""
    diary_retries: int = 2
    dream_per_night: int = 2
    diary_retention_days: int = 30
    dream_retention_days: int = 7
    dream_half_life_seconds: int = 86400
    experience_body_chars: int = 2000
    model_concurrency: int = 1
    queue_size: int = 100
    model_daily_limit: int = 48
    emotion_interval_seconds: int = 300
    model_input_tokens: int = 4096
    model_output_tokens: int = 1024
    model_timeout_seconds: int = 30
    window_days: int = 7
    window_per_scope: int = 200
    window_global: int = 10000
    body_max_chars: int = 8000
    event_days: int = 30
    persona_shared_state: bool = True
    night_policy_version: int = 2
    allow_sleep: bool = True
    nap_enabled: bool = True
    nap_start: str = "13:00"
    nap_end: str = "14:30"
    fatigue_start: str = "23:30"
    fatigue_end: str = "07:00"
    deep_sleep_at: str = "02:30"
    lie_in_min_minutes: int = 0
    lie_in_max_minutes: int = 90
    wake_mode: str = "chat"
    wake_reply_limit: int = 3
    wake_window_minutes: int = 10
    energy_reply_cost: float = 4.0
    energy_fatigue_per_minute: float = 0.8
    energy_recovery_per_minute: float = 1.5
    catchup_enabled: bool = True
    catchup_reply_enabled: bool = True
    closing_enabled: bool = False
    closing_random: bool = False
    closing_lead_minutes: int = 5
    diary_provider_id: str = ""
    dream_provider_id: str = ""
    catchup_provider_id: str = ""
    closing_provider_id: str = ""
    home_city: str = ""
    embedding_provider_id: str = ""
    livingmemory_enabled: bool = False
    memory_write: bool = False

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "Config":
        known = {item.name for item in fields(cls)}
        data = {key: val for key, val in value.items() if key in known}
        # Missing new fields identify an old native configuration, not consent
        # to merge its scenes or enable new sleep blocking.
        data.setdefault("persona_shared_state", False)
        data.setdefault("night_policy_version", 1)
        data.setdefault("livingmemory_enabled", value.get("memory_mode") == "external")
        return cls(**data)

    def __post_init__(self) -> None:
        if self.mode not in ("active", "observe_only"):
            raise ValueError("invalid mode")
        if self.memory_mode not in ("none", "local_lite", "external"):
            raise ValueError("invalid memory mode")
        if self.persona_mode not in ("follow", "explicit", "none"):
            raise ValueError("invalid persona mode")
        if self.persona_mode == "explicit" and not self.persona_id:
            raise ValueError("explicit persona required")
        if self.night_policy_version not in (1, 2):
            raise ValueError("invalid night policy version")
        if self.wake_mode not in ("chat", "never", "both"):
            raise ValueError("invalid wake mode")
        if self.behavior_style not in ("gentle", "balanced", "lively"):
            raise ValueError("invalid behavior style")
        if self.behavior_random_min_minutes > self.behavior_random_max_minutes:
            raise ValueError("invalid behavior random interval")
        if self.night_policy_version == 2 and self.night_schedule_enabled and not self.timezone:
            raise ValueError("timezone required for night policy 2")
        if self.timezone:
            ZoneInfo(self.timezone)
        for name in ("sleep_at", "wake_at", "diary_at", "dnd_start", "dnd_end",
                     "active_start", "active_end", "nap_start", "nap_end",
                     "fatigue_start", "fatigue_end", "deep_sleep_at"):
            value = getattr(self, name)
            if len(value) != 5 or time.fromisoformat(value).second:
                raise ValueError("invalid schedule time")
        if self.sleep_at == self.wake_at:
            raise ValueError("empty sleep window")
        if self.dnd_start == self.dnd_end or self.active_start == self.active_end:
            raise ValueError("empty behavior window")
        defaults = {item.name: item.default for item in fields(self)}
        for name, default in defaults.items():
            value = getattr(self, name)
            if isinstance(default, bool) and type(value) is not bool:
                raise ValueError(f"{name}: expected boolean")
            minimum = 0 if name in (
                "diary_retries", "lie_in_min_minutes", "lie_in_max_minutes",
                "closing_lead_minutes",
            ) else 1
            if type(default) is int and (type(value) is not int or value < minimum):
                raise ValueError(f"{name}: expected positive integer")
            if isinstance(default, str) and (not isinstance(value, str) or len(value) > 8192):
                raise ValueError(f"{name}: expected bounded string")
            if type(default) is float:
                if (type(value) not in (int, float) or not math.isfinite(value)
                        or not 0 <= value <= 100
                        or Decimal(str(value)) * 10 != (Decimal(str(value)) * 10).to_integral()):
                    raise ValueError(f"{name}: expected 0..100 in steps of 0.1")
        if self.lie_in_min_minutes > self.lie_in_max_minutes:
            raise ValueError("invalid lie-in interval")
        if self.nap_start == self.nap_end or self.fatigue_start == self.fatigue_end:
            raise ValueError("empty night policy window")
        if self.night_policy_version == 2:
            def minute(value):
                hours, minutes = value.split(":")
                return int(hours) * 60 + int(minutes)
            start = minute(self.fatigue_start)
            deep = (minute(self.deep_sleep_at) - start) % 1440
            wake = (minute(self.wake_at) - start) % 1440
            if not 0 < deep < wake:
                raise ValueError("deep sleep must be between fatigue start and base wake")
        for name, maximum in (
            ("model_concurrency", 8), ("queue_size", 1000),
            ("window_days", 7), ("window_per_scope", 200),
            ("window_global", 10000), ("body_max_chars", 8000),
            ("model_input_tokens", 32768), ("model_output_tokens", 8192),
            ("model_timeout_seconds", 120), ("scheduler_seconds", 3600),
            ("diary_retries", 2), ("dream_per_night", 2),
            ("diary_retention_days", 365), ("dream_retention_days", 30),
            ("experience_body_chars", 8000),
            ("lie_in_max_minutes", 1440), ("wake_reply_limit", 100),
            ("wake_window_minutes", 1440), ("closing_lead_minutes", 60),
            ("behavior_random_max_minutes", 10080), ("behavior_idle_minutes", 1440),
        ):
            if getattr(self, name) > maximum:
                raise ValueError(f"{name}: exceeds safety maximum {maximum}")
