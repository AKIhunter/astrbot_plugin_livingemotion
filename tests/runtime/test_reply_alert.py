"""连续拦截告警只报一次，成功即恢复。"""

import pytest

from astrbot_plugin_livingemotion.runtime.reply_alert import (
    ALERT_ID, ALERT_TEXT, ALERT_THRESHOLD, ReplyBlockAlert,
)


def test_alerts_exactly_once_at_threshold():
    alert = ReplyBlockAlert()
    fired = [alert.record_blocked() for _ in range(ALERT_THRESHOLD)]
    assert fired == [False] * (ALERT_THRESHOLD - 1) + [True]
    # 继续哑火不再刷屏：运维已经收到过一次提醒了。
    assert all(alert.record_blocked() is False for _ in range(5))


def test_success_resets_streak():
    alert = ReplyBlockAlert(threshold=3)
    alert.record_blocked()
    alert.record_blocked()
    alert.record_allowed()

    assert alert.streak == 0
    assert alert.record_blocked() is False
    assert alert.record_blocked() is False
    assert alert.record_blocked() is True


def test_threshold_is_one_shot_even_if_lowered_by_injection():
    alert = ReplyBlockAlert(threshold=1)
    assert alert.record_blocked() is True
    assert alert.record_blocked() is False


def test_text_is_one_short_hardcoded_line():
    assert ALERT_ID in ALERT_TEXT
    assert "\n" not in ALERT_TEXT
    assert len(ALERT_TEXT) <= 40


def test_invalid_threshold_rejected():
    for bad in (0, -1, 1.5, "3", True):
        with pytest.raises(ValueError):
            ReplyBlockAlert(threshold=bad)
