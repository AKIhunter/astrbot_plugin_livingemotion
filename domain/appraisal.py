"""Current-message evidence only; recalled history supplies context, never points."""
import json
import re
from collections.abc import Mapping

SIGNALS = {"insult", "praise", "constructive_criticism", "teaching", "care",
           "gratitude", "apology", "sadness", "anxiety", "joy", "surprise",
           "threat", "conflict", "boundary_respected", "boundary_violated",
           "promise_kept", "promise_broken", "disappointment"}
_INSULT = re.compile(r"(?:你|您|you).{0,8}(?:傻逼|傻子|蠢货|废物|垃圾|白痴|滚|去死|idiot|stupid|useless)", re.I)
_PRAISE = re.compile(r"(?:你|您|you).{0,12}(?:真棒|很棒|厉害|优秀|做得好|说得好|靠谱|聪明|great|brilliant|helpful)", re.I)
_CONTEXT = re.compile(r"(?:这个词|这句话|引用|转述|不是说你|不要说|别说|例如|比如|翻译|什么意思|小说|台词)")
_NEGATION = re.compile(r"(?:不(?!然)|没|别|莫|并非|not|never).{0,5}$", re.I)
_QUOTE = re.compile(r'“[^”]*”|「[^」]*」|『[^』]*』|"[^"]*"|‘[^’]*’|`[^`]*`')
_REPORTED = re.compile(r"(?:他|她|他们|她们|别人|朋友|同事|小明).{0,4}(?:说|觉得|认为|骂|感谢)")
_THREAT = re.compile(
    r"(?:杀了你|弄死你|要你好看|封你的(?:号|账号)|把你的(?:账号|号).{0,4}封|"
    r"不然.{0,8}(?:封你|打你|揍你))")


def direct_text(text):
    # Quote removal prevents discussion of abuse from being scored as abuse.
    return _QUOTE.sub("", text[:4096])


def _asserted(text, pattern):
    for match in pattern.finditer(text):
        start = max(text.rfind(p, 0, match.start()) for p in "。！？.!?\n；;") + 1
        clause = text[start:match.end()]
        if not (_CONTEXT.search(clause) or _REPORTED.search(clause)) and not _NEGATION.search(
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
    if _asserted(text, _THREAT):
        result.add("threat")
    # Evidence is checked per sentence: an apology can mention the withdrawn insult.
    for clause in re.split(r"[。！？.!?\n；;]", text):
        if _CONTEXT.search(clause) or _REPORTED.search(clause):
            continue
        if _asserted(clause, re.compile(
                r"给你降智|(?:你|您).{0,6}(?:被降智|能力被削弱|能力下降了)")):
            result.add("disappointment")
        if (re.search(r"(?:你|您).{0,8}(?:错|不对|有误|遗漏)|"
                      r"(?:这次|你的).{0,6}(?:结论|计算).{0,6}(?:问题|错误)", clause)
                and re.search(r"因为|依据|证据|根据|原文|实际|所以|应当|把\d+写成", clause)):
            result.add("constructive_criticism")
        if (re.search(r"教你|教给你|建议你|你可以", clause)
                and re.search(r"因为|先.{2,}再|步骤|原理|原因|这样.{1,}可以", clause)):
            result.add("teaching")
        if _asserted(clause, re.compile(
                r"(?:你|您).{0,6}(?:辛苦了|好好休息|照顾好自己)|"
                r"抱抱你|陪着你|关心你|我(?:来|会|帮你|可以帮你).{0,8}"
                r"(?:解决|处理|问问|分担|照顾)|我帮你")):
            result.add("care")
        if _asserted(clause, re.compile(r"谢谢你|感谢你|多谢你")):
            result.add("gratitude")
        if (re.search(r"对不起|向你道歉|我错了", clause)
                and re.search(r"向你道歉|我错了|我.{0,6}(?:不该|误会|冤枉|冒犯|骂|伤害).{0,8}你",
                              clause)
                and not re.search(r"不(?:会|想|要).{0,3}道歉|不觉得.{0,3}错|"
                                  r"(?:对不起|我错了).{0,4}(?:才怪|个鬼)", clause)):
            result.add("apology")
        if (_asserted(clause, re.compile(r"尊重你的(?:边界|意愿|选择)"))
                or re.search(r"你不想.{0,12}我不(?:再|会)|"
                             r"你说.{0,8}不要.{0,12}我不(?:再|会)", clause)):
            result.add("boundary_respected")
        if re.search(r"你(?:说|不想).{0,12}(?:我偏要|我就要)|不管你的(?:边界|意愿)", clause):
            result.add("boundary_violated")
        if _asserted(clause, re.compile(r"你.{0,6}(?:烦人|讨厌)|闭嘴|别烦我")):
            result.add("conflict")
        if re.search(r"答应你.{0,12}(?:已经|按时|如约).{0,8}(?:完成|做好|办好)|"
                     r"我.{0,6}(?:按约定|履行承诺).{0,8}(?:帮你|给你)", clause):
            result.add("promise_kept")
        if re.search(r"答应你.{0,12}(?:故意不|偏不|就不)|故意.{0,6}违约", clause):
            result.add("promise_broken")
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
            "rule_version", "delta", "confidence", "appraisals", "control"}:
        raise ValueError("model_schema")
    confidence = _number(value.get("confidence", 1), "model_confidence", 0, 1)
    if "control" in value:
        _number(value["control"], "control", 0, 1)
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
        if _CONTEXT.search(span) or _REPORTED.search(span):
            continue
        if signal in ("insult", "praise", "threat", "care", "gratitude", "conflict") and not _asserted(
                direct, re.compile(re.escape(span))):
            continue
        # Relationship labels require current linguistic evidence as well as a model vote.
        # Emotion-only labels retain their existing schema.
        if signal not in {"sadness", "anxiety", "joy", "surprise"} and signal not in local_appraisals(span):
            continue
        if confidence >= .65:
            signals.add(signal)
    return {k: v for k, v in value.items() if k != "appraisals"}, tuple(sorted(signals))
