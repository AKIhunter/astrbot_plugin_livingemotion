"""回复被状态机连续拦截时的运维告警。

文案与阈值一律硬编码：这条消息是给运维者的，不是角色台词。
它不读配置、不随情绪变化、不参与人格表达——所以它能做到「一句话说清」。
"""

from __future__ import annotations

ALERT_ID = "LE-ALERT-001"
ALERT_THRESHOLD = 3
ALERT_TEXT = f"[{ALERT_ID}] 回复连续被拦截，bot 可能已静音。"


class ReplyBlockAlert:
    """连续拦截计数：恰好到阈值时告警一次，不重复刷屏。

    任何一次成功提交都清零，所以它衡量的是「连续」而不是「累计」——
    偶发一两句被可解释地拦下（睡觉、精力见底）不会触发，
    只有卡在同一个坑里反复哑火才会。
    """

    def __init__(self, threshold: int = ALERT_THRESHOLD) -> None:
        if type(threshold) is not int or threshold < 1:
            raise ValueError("invalid alert threshold")
        self.threshold = threshold
        self.streak = 0

    def record_blocked(self) -> bool:
        """记一次拦截，返回本次是否需要发告警。"""
        self.streak += 1
        return self.streak == self.threshold

    def record_allowed(self) -> None:
        """成功提交一次即视为恢复。"""
        self.streak = 0
