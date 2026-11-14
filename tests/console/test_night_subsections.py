"""长夜分区归类回归：27+ 个字段必须落进五个小卡片，不能有漏网的。"""

import pytest

from astrbot_plugin_livingemotion.config import LEGACY_FIELDS, Config
from astrbot_plugin_livingemotion.runtime.console import (
    NIGHT_SUBSECTIONS, field_section, night_subsection,
)

NIGHT_KEYS = [f.name for f in __import__("dataclasses").fields(Config)
              if f.name not in LEGACY_FIELDS and field_section(f.name) == "night"]


def test_every_night_field_has_a_subsection():
    missing = [name for name in NIGHT_KEYS if not night_subsection(name)]
    assert missing == []


def test_subsection_ids_are_declared():
    declared = {key for key, _ in NIGHT_SUBSECTIONS}
    used = {night_subsection(name) for name in NIGHT_KEYS}
    assert used <= declared
    assert used == declared, "五个小卡片都要有字段，否则会出现空卡片"


def test_comfort_line_lives_in_energy_card():
    assert night_subsection("energy_comfort_percent") == "energy"


def test_wake_at_is_schedule_not_wake_rule():
    # 起床时间属于作息表；只有唤醒规则才进「聊天唤醒」。
    assert night_subsection("wake_at") == "schedule"
    for name in ("wake_mode", "wake_reply_limit", "wake_window_minutes"):
        assert night_subsection(name) == "wake"


def test_non_night_fields_have_no_subsection():
    for name in ("enabled", "mode", "diary_enabled", "persona_id"):
        assert night_subsection(name) == ""
