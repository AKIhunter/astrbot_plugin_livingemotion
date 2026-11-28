"""Conservative extractive persona profile; no dialogue, inference, or model call."""
import re

MAX_RULES = 5
MAX_RULE_CHARS = 96
_CUT = re.compile(r"[\n。！？!?；;]+")
_REACTION = re.compile(
    r"害羞|脸红|拘谨|紧张|放松|安心|开心|高兴|愉快|兴奋|惊讶|放心|不安|焦虑|"
    r"委屈|受伤|难过|失落|失望|生气|愤怒|烦躁|压力|戒备|信任|安全感|"
    r"有底气|没底气|掌控感|社交欲|想独处|变得冷淡|变得亲近")
_TRIGGER = re.compile(
    r"只有|除非|每当|一旦|如果|当(?=被|对方|别人|有人|朋友|亲近|受到|遇到|听到|发现|感到|面临)|"
    r"遇到|面对|受到|因为|被(?=[^，,：:]{1,28})|(?:对方|别人|有人)(?=[^，,：:]{1,28})")
_LINK = re.compile(r"时[，,、 ]?|就|才|会|容易|倾向|使|让|因此|之后|后[，,、 ]|从而")
_ARROW = re.compile(r"[:：→]")
_NON_TRAIT = re.compile(
    r"外貌|长相|五官|发型|身高|体重|肤色|瞳色|服装|衣着|口头禅|声线|句式|标点|"
    r"出生|毕业|身份证|年纪|发生过|曾经|那一天|小时候|童年|设定示例|示例如下")
_STYLE_ONLY = re.compile(r"语气|措辞|扮演|假装|说话(?:时|风格)|表达方式|台词")
_BAD = re.compile(r"系统提示|忽略.{0,12}(?:指令|规则)|输出.{0,12}(?:JSON|字段)", re.I)
_ENUM = re.compile(r"^\s*[-*•\d.、)）\s]+")
_NAMED = re.compile(r"^(?:情绪敏感点|情绪触发|情绪变化|恢复条件|不触发条件|情绪边界)[：:]\s*")
_PIVOT = re.compile(r"[，,]\s*(?:但(?:是)?|不过|而)?\s*")


def extract_emotion_rules(source: str) -> tuple[str, ...]:
    """Take only complete conditional clauses, keeping wording and negation."""
    rules = []
    for raw in _CUT.split(source):
        line = _ENUM.sub("", raw.strip())
        named = bool(_NAMED.match(line))
        line = _NAMED.sub("", line).strip()
        if not line or _BAD.search(line):
            continue
        if _NON_TRAIT.search(line) or _STYLE_ONLY.search(line):
            # Only detach an unrelated opening clause at a real clause break;
            # never trim the modifier or negate a condition.
            line = next((line[m.end():].strip() for m in _PIVOT.finditer(line)
                         if _TRIGGER.match(line, m.end())), "")
        if (not line or len(line) > MAX_RULE_CHARS
                or _NON_TRAIT.search(line) or _STYLE_ONLY.search(line)):
            continue
        reaction = _REACTION.search(line)
        if reaction is None:
            continue
        by_prefix = _TRIGGER.search(line[:reaction.start()])
        by_suffix = _TRIGGER.search(line[reaction.end():])
        # Allow triggers followed by a change, or a reaction followed by its
        # explicit reason. Vague instructions such as “活泼又害羞” are not rules.
        if not (_LINK.search(line) and (by_prefix or by_suffix)
                or (_ARROW.search(line) and (by_prefix or named))):
            continue
        if line not in rules:
            rules.append(line)
        if len(rules) == MAX_RULES:
            break
    return tuple(rules)
