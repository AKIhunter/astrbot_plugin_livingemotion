"""Shared numeric mood and imaginative dream inputs; no transport authorization."""
import json
import math
import random
import re

DEFAULT_THEMES = (
    "赛博朋克", "绿野仙踪", "生活日常", "星际漫游", "海底王国", "古堡奇遇",
    "森林童话", "校园时光", "蒸汽幻想", "云端旅行", "四季庭院", "时光回廊",
)
EMOTIONS = ("joy", "anger", "sadness", "fear", "surprise", "affection")
TONES = {
    "joy": "美梦：轻快、明亮，醒来仍觉得开心。",
    "anger": "气愤的梦：委屈或冲突让我半夜气醒，想向主人诉说。不要编造已发送消息。",
    "sadness": "难过的梦：失落、离别，醒来眼角湿润。",
    "fear": "噩梦：不安、惊吓，半夜醒来想向主人求安慰。不要编造已发送消息。",
    "surprise": "大胆抽象的梦：荒诞跳跃、出乎意料的变形和冒险。",
    "affection": "温情的梦：陪伴、关爱、被接住的安心。",
    "calm": "简单安稳的梦：平静、轻柔，整夜没有惊醒或情绪波动。",
}


def theme_pool(value):
    """JSON or everyday separators, preserving distinct user supplied themes."""
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (ValueError, TypeError):
            parsed = re.split(r"[\n,，;；、]+", value)
    else:
        parsed = value
    if not isinstance(parsed, (list, tuple)):
        raise ValueError("梦境池须为主题列表")
    result = tuple(dict.fromkeys(s.strip() for s in parsed if isinstance(s, str) and s.strip()))
    if not 2 <= len(result) <= 32 or any(
            len(s) > 40 or any(ord(c) < 32 for c in s) for s in result):
        raise ValueError("梦境池须包含2至32个不同主题，每个最多40字")
    return result


def _arousal_above_baseline(value):
    """超出平常唤醒水平的部分：基线本身不算兴奋，动态基准优先。"""
    baseline = 0.3
    if getattr(value, "baseline_refined", False):
        try:
            baseline = float(getattr(value, "baseline_arousal"))
        except (AttributeError, TypeError, ValueError):
            baseline = 0.3
    return max(0.0, float(getattr(value, "arousal")) - baseline)


def six_emotions(value):
    p, a, s, n = (getattr(value, k) for k in ("pleasure", "arousal", "stress", "social_need"))
    positive, negative = max(0, p), max(0, -p)
    # 惊讶只统计相对唤醒基线的增量：基线 arousal 0.3 是平常水平，
    # 若直接乘 arousal，阴天全维加成会把平静状态推成「兴奋」。
    excited = _arousal_above_baseline(value)
    return {
        "joy": positive * (1 - .35 * s),
        "anger": negative * a * (.35 + .65 * s),
        "sadness": negative * (1 - .55 * a) * (1 - .35 * s),
        "fear": s * (.35 + .65 * a),
        "surprise": excited * (.25 + .35 * (1 - abs(p))),
        # 关怀满足社交需求后n可能下降，不能因此把关爱也显示成下降。
        "affection": (.35 * n + .65 * positive) * (1 - .4 * s),
    }


def weather_bonus(report, *, city, day, timezone):
    """Percentage points, exact header match, mutually exclusive severity order."""
    result = dict.fromkeys(EMOTIONS, 0.0)
    if (not city or report is None or report.status != "ok"
            or (report.city, report.day, report.timezone) != (city, day, timezone)):
        return result
    code = getattr(report, "code", None)
    hazard = getattr(report, "hazard", "")
    if code in (95, 96, 99) or hazard in ("typhoon", "hail", "natural_disaster"):
        result["fear"] = .25
    elif code in (71, 73, 75, 77, 85, 86):
        result["affection"] = .4
    elif code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        result["sadness"] = .2
    elif code in (2, 3):
        result = dict.fromkeys(EMOTIONS, .1)
    elif code in (0, 1):
        result["joy"] = .2
    return result


def apply_bonus(emotions, bonus):
    # Overlay is replaceable: refreshing never compounds yesterday's weather.
    return {k: round(min(1, max(0, emotions.get(k, 0)) + bonus.get(k, 0)), 4) for k in EMOTIONS}


def dream_profile(emotions, themes=DEFAULT_THEMES, *, picker=None, nap=False):
    raw = {k: float(emotions.get(k, 0)) for k in EMOTIONS}
    if any(not math.isfinite(v) for v in raw.values()):
        raise ValueError("invalid dream mood")
    values = {k: max(0, min(1, v)) for k, v in raw.items()}
    dominant = max(values, key=values.get)
    if values[dominant] < .25:
        dominant = "calm"
    return {"themes": (picker or random.SystemRandom()).sample(theme_pool(themes), 2),
            "emotions": values, "dominant": dominant, "tone": TONES[dominant],
            "night_event": dominant if dominant in ("anger", "fear") and not nap else "",
            "nap": nap}
