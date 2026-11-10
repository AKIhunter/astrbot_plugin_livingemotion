"""Validated safe defaults, independent of AstrBot's configuration wrapper."""

from dataclasses import dataclass, fields
from datetime import time
from decimal import Decimal
import json
import math
import re
from typing import Any, Mapping
from zoneinfo import ZoneInfo
import unicodedata


from .domain.relationship import RELATIONSHIP_DEFAULT_SCORE, RELATIONSHIP_STAGE_NAMES, stage_names as migrate_stage_names
from .domain.dreaming import DEFAULT_THEMES, theme_pool

RELATIONSHIP_STAGE_NAMES_DEFAULT = json.dumps(RELATIONSHIP_STAGE_NAMES, ensure_ascii=False, separators=(",", ":"))
RELATIONSHIP_STAGE_NAMES_FIELD = "relationship_stage_names"


LEGACY_FIELDS = frozenset({
    "memory_mode", "memory_export", "night_enabled", "night_block_chat",
    "sleep_at", "night_policy_version", "autonomy_scopes",
})


def qq_numbers(value: str) -> tuple[str, ...]:
    """Accept common separators; reject malformed entries instead of widening scope."""
    if not isinstance(value, str) or len(value) > 2000:
        raise ValueError("QQ/群号名单应为不超过2000字的文本")
    numbers = tuple(dict.fromkeys(re.split(r"[\s,，;；、]+", value.strip())))
    numbers = tuple(number for number in numbers if number)
    if len(numbers) > 100 or any(not re.fullmatch(r"[1-9][0-9]{4,19}", n) for n in numbers):
        raise ValueError("QQ/群号须为5至20位数字，最多100个，多个号码用逗号或空格分隔")
    return numbers


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
    dream_theme_pool: str = json.dumps(DEFAULT_THEMES, ensure_ascii=False)
    dream_owner_notify: bool = False
    dream_owner_qq: str = ""
    diary_enabled: bool = False
    night_enabled: bool = True
    night_block_chat: bool = False
    persona_mode: str = "follow"
    persona_id: str = ""
    timezone: str = ""
    provider_id: str = ""
    fallback_provider_id: str = ""
    autonomy_scopes: str = ""
    autonomy_qq_ids: str = ""
    autonomy_qq_group_ids: str = ""
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
    # 计数是「UTF-8 字节上界」，不是 token 数：4096 连系统提示（约 2.3KB）
    # 加人格都装不下，日记/梦境永远 input_token_limit。32768 字节约
    # 11k 汉字，主流模型都吃得下。
    model_input_tokens: int = 32768
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
    relationship_stage_names: str = RELATIONSHIP_STAGE_NAMES_DEFAULT
    relationship_stage_descriptions: str = '["","","",""]'
    relationship_special_description: str = ""
    wake_autocatchup_enabled: bool = True
    wake_greeting_enabled: bool = True
    wake_greeting_texts: str = (
        "刚醒，我看看之前你们说了什么。|我醒了，先把这几小时翻一翻。|醒了…看看都说了什么。")
    # 好感是可改写的敏感数据：默认只读，只有管理员在设置里显式打开才出现编辑入口。
    relationship_edit_enabled: bool = False

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "Config":
        known = {item.name for item in fields(cls)}
        data = {key: val for key, val in value.items() if key in known}
        # Missing new fields identify an old native configuration, not consent
        # to merge its scenes or enable new sleep blocking.
        data.setdefault("persona_shared_state", False)
        # The current native schema no longer exposes the old rule-version knob.
        # New number-list fields identify it; raw older mappings retain policy 1.
        data.setdefault("night_policy_version", 2 if (
            "autonomy_qq_ids" in value or "autonomy_qq_group_ids" in value
        ) else 1)
        data.setdefault("livingmemory_enabled", value.get("memory_mode") == "external")
        return cls(**data)

    def __post_init__(self) -> None:
        if not isinstance(self.relationship_stage_descriptions, str) or len(self.relationship_stage_descriptions) > 8192:
            raise ValueError("relationship_stage_descriptions: expected a bounded JSON array")
        try:
            descriptions = json.loads(self.relationship_stage_descriptions)
        except (TypeError, ValueError):
            raise ValueError("relationship_stage_descriptions: expected 4 descriptions") from None
        if (not isinstance(descriptions, list) or len(descriptions) != 4
                or any(not isinstance(value, str) or len(value) > 1000
                       or any(unicodedata.category(c) in ("Cs", "Cf")
                              or (unicodedata.category(c) == "Cc" and c not in "\n\r\t")
                              for c in value) for value in descriptions)):
            raise ValueError("relationship_stage_descriptions: maximum 1000 characters per description")
        object.__setattr__(self, "relationship_stage_descriptions",
                           json.dumps([value.strip() for value in descriptions],
                                      ensure_ascii=False, separators=(",", ":")))
        raw_stage_names = self.relationship_stage_names
        if not isinstance(raw_stage_names, str) or len(raw_stage_names) > 4096:
            raise ValueError("relationship_stage_names: expected a bounded JSON array")
        try:
            stage_names = json.loads(raw_stage_names)
        except json.JSONDecodeError as exc:
            raise ValueError("relationship_stage_names: expected a JSON array") from exc
        if not isinstance(stage_names, list) or len(stage_names) not in (5, 11):
            raise ValueError("relationship_stage_names: expected 5 names (legacy 11 accepted)")
        normalized_names = []
        unique_names = []
        for value in stage_names:
            if (not isinstance(value, str) or len(value) > 100
                    or any(unicodedata.category(char) in ("Cc", "Cf", "Cs", "Zl", "Zp")
                           for char in value)):
                raise ValueError("relationship_stage_names: each name must be at most 100 single-line characters")
            value = value.strip()
            normalized_names.append(value)
            if value:
                unique_names.append(value.casefold())
        if len(set(unique_names)) != len(unique_names):
            raise ValueError("relationship stage names must be unique")
        object.__setattr__(self, "relationship_stage_names",
                           json.dumps(migrate_stage_names(normalized_names), ensure_ascii=False, separators=(",", ":")))
        if (not isinstance(self.relationship_special_description, str)
                or len(self.relationship_special_description) > 1000):
            raise ValueError("relationship_special_description: maximum 1000 characters")
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
        qq_numbers(self.autonomy_qq_ids)
        qq_numbers(self.autonomy_qq_group_ids)
        object.__setattr__(self, "dream_theme_pool", json.dumps(
            theme_pool(self.dream_theme_pool), ensure_ascii=False))
        if self.dream_owner_qq and len(qq_numbers(self.dream_owner_qq)) != 1:
            raise ValueError("梦境主人QQ须为一个合法号码")
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
