"""Current-message evidence only; recalled history supplies context, never points."""
import json
import re
from collections.abc import Mapping

SIGNALS = {"insult", "praise", "constructive_criticism", "teaching", "care",
           "gratitude", "apology", "sadness", "anxiety", "joy", "surprise"}
_INSULT = re.compile(r"(?:你|您|you).{0,8}(?:傻逼|傻子|蠢货|废物|垃圾|白痴|滚|去死|idiot|stupid|useless)", re.I)
_PRAISE = re.compile(r"(?:你|您|you).{0,12}(?:真棒|很棒|厉害|优秀|做得好|说得好|靠谱|聪明|great|brilliant|helpful)", re.I)
_CONTEXT = re.compile(r"(?:这个词|这句话|引用|转述|骂你|不是说你|不要说|别说|例如|比如|翻译|什么意思|小说|台词)")
_NEGATION = re.compile(r"(?:不|没|别|莫|并非|not|never).{0,5}$", re.I)
_QUOTE = re.compile(r'“[^”]*”|「[^」]*」|『[^』]*』|"[^"]*"|‘[^’]*’|`[^`]*`')


def direct_text(text):
    # Quote removal prevents discussion of abuse from being scored as abuse.
    return _QUOTE.sub("", text[:4096])


def _asserted(text, pattern):
    for match in pattern.finditer(text):
        start = max(text.rfind(p, 0, match.start()) for p in "。！？.!?\n；;") + 1
        clause = text[start:match.end()]
        if not _CONTEXT.search(clause) and not _NEGATION.search(
                text[max(start, match.start() - 8):match.start()]):
            # Negation inside a directed expression: “你并不聪明”.
            if not re.search(r"(?:你|您|you).{0,3}(?:不|没|并非|not)", match.group(), re.I):
                return True
    return False


def local_appraisals(body):
    text = direct_text(body)
    result = set()
    if _asserted(text, _INSULT):
        result.add("insult")
    if _asserted(text, _PRAISE):
        result.add("praise")
    if (not _CONTEXT.search(text) and re.search(r"(?:你|您).{0,8}(?:错|不对|有误|遗漏)", text)
            and re.search(r"因为|依据|证据|根据|原文|实际|所以|应当", text)):
        result.add("constructive_criticism")
    if (not _CONTEXT.search(text) and re.search(r"教你|教给你|建议你|你可以", text)
            and re.search(r"因为|先.{2,}再|步骤|原理|原因|这样.{1,}可以", text)):
        result.add("teaching")
    if (not _CONTEXT.search(text) and re.search(
            r"(?:你|您).{0,6}(?:辛苦了|好好休息|照顾好自己)|抱抱你|陪着你|关心你", text)):
        result.add("care")
    if not _CONTEXT.search(text) and re.search(r"谢谢你|感谢你|多谢你", text):
        result.add("gratitude")
    if not _CONTEXT.search(text) and re.search(r"对不起|向你道歉|我错了", text):
        result.add("apology")
    return tuple(sorted(result))


def parse_suggestion(value, body):
    """Require a literal, unquoted current-message span for every model label."""
    from .emotion import _unique_object, _number
    if isinstance(value, str):
        if len(value) > 4096:
            raise ValueError("model_output_too_long")
        text = value.strip()
        if text.startswith("```json\n") and text.endswith("\n```"):
            text = text[8:-4]
        value = json.loads(text, object_pairs_hook=_unique_object)
    if not isinstance(value, Mapping) or set(value) - {
            "rule_version", "delta", "confidence", "appraisals"}:
        raise ValueError("model_schema")
    confidence = _number(value.get("confidence", 1), "model_confidence", 0, 1)
    rows = value.get("appraisals", [])
    if not isinstance(rows, list) or len(rows) > 8:
        raise ValueError("appraisal_schema")
    signals = set()
    direct = direct_text(body)
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"signal", "evidence"}:
            raise ValueError("appraisal_schema")
        signal, span = row["signal"], row["evidence"]
        if (not isinstance(signal, str) or signal not in SIGNALS
                or not isinstance(span, str) or not 2 <= len(span) <= 256
                or span not in body or span not in direct):
            raise ValueError("appraisal_evidence_invalid")
        # Explicit denials, quotations and vocabulary lessons are not assertions.
        if _CONTEXT.search(span) or re.search(r"不是说你|并非|没有|不要|别骂|not|never", span, re.I):
            continue
        if signal in ("insult", "praise") and not _asserted(
                direct, re.compile(re.escape(span))):
            continue
        if confidence >= .65:
            signals.add(signal)
    return {k: v for k, v in value.items() if k != "appraisals"}, tuple(sorted(signals))
