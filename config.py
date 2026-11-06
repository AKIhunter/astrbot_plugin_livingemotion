"""Validated safe defaults, independent of AstrBot's configuration wrapper."""

from dataclasses import dataclass, fields
from datetime import time
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

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "Config":
        known = {item.name for item in fields(cls)}
        return cls(**{key: val for key, val in value.items() if key in known})

    def __post_init__(self) -> None:
        if self.mode not in ("active", "observe_only"):
            raise ValueError("invalid mode")
        if self.memory_mode not in ("none", "local_lite", "external"):
            raise ValueError("invalid memory mode")
        if self.persona_mode not in ("follow", "explicit", "none"):
            raise ValueError("invalid persona mode")
        if self.persona_mode == "explicit" and not self.persona_id:
            raise ValueError("explicit persona required")
        if self.timezone:
            ZoneInfo(self.timezone)
        for name in ("sleep_at", "wake_at", "diary_at", "dnd_start", "dnd_end",
                     "active_start", "active_end"):
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
            minimum = 0 if name == "diary_retries" else 1
            if type(default) is int and (type(value) is not int or value < minimum):
                raise ValueError(f"{name}: expected positive integer")
            if isinstance(default, str) and (not isinstance(value, str) or len(value) > 8192):
                raise ValueError(f"{name}: expected bounded string")
        for name, maximum in (
            ("model_concurrency", 8), ("queue_size", 1000),
            ("window_days", 7), ("window_per_scope", 200),
            ("window_global", 10000), ("body_max_chars", 8000),
            ("model_input_tokens", 32768), ("model_output_tokens", 8192),
            ("model_timeout_seconds", 120), ("scheduler_seconds", 3600),
            ("diary_retries", 2), ("dream_per_night", 2),
            ("diary_retention_days", 365), ("dream_retention_days", 30),
            ("experience_body_chars", 8000),
        ):
            if getattr(self, name) > maximum:
                raise ValueError(f"{name}: exceeds safety maximum {maximum}")
