"""配置面板完整性：任何可编辑字段都必须有中文标签和帮助文案。

这类缺失会让整个设置页直接 KeyError 崩溃（新增字段忘记同步 CONFIG_HELP），
所以必须用测试锁住，而不是靠人记得。
"""

from dataclasses import fields

from astrbot_plugin_livingemotion.config import LEGACY_FIELDS, Config
from astrbot_plugin_livingemotion.runtime.config_help import CONFIG_HELP
from astrbot_plugin_livingemotion.runtime.console import FIELD_LABELS

EDITABLE = [f.name for f in fields(Config) if f.name not in LEGACY_FIELDS]


def test_every_field_has_help_text():
    missing = [name for name in EDITABLE if name not in CONFIG_HELP]
    assert missing == [], "缺 CONFIG_HELP 会让 config_dto 抛 KeyError：%s" % missing


def test_every_field_has_chinese_label():
    missing = [name for name in EDITABLE if name not in FIELD_LABELS]
    assert missing == [], "缺 FIELD_LABELS 会显示成「高级设置：xxx」：%s" % missing


def test_help_text_is_a_triple():
    bad = [name for name in EDITABLE
           if not isinstance(CONFIG_HELP.get(name), tuple) or len(CONFIG_HELP[name]) != 3
           or not all(isinstance(part, str) and part.strip() for part in CONFIG_HELP[name])]
    assert bad == []
