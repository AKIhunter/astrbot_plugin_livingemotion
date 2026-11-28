"""Account-scoped 委屈/受伤/害羞. Pure transitions; no provider or host imports.

Current evidence causes a transition. Past help acknowledgements only establish
its basis. Deferred appraisals merge into the latest state by emotion kind.
These intensities never enter the four shared affect dimensions.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
import json
import re

from ..contracts import (
    ActorRole, ContextAppraisal, ContextEmotion, ContentKind, account_person_key, finite,
    stable_key, to_dict,
)
from ..prompt_precision import PROMPT_DECIMALS
from .appraisal import direct_text

VERSION = 1
THRESHOLD = .20
MAX_STATE_CHARS = 4096
MAX_SEEN = 16
MAX_REPAIRS = 8
WINDOW = 300.0
HELP_EVIDENCE_SECONDS = 86400
POLICIES = {
    "wronged": (.70, 1800.0, 7200.0),
    "hurt": (.70, 1800.0, 7200.0),
    "shyness": (.60, 480.0, 2400.0),
}
LABELS = {"wronged": "委屈", "hurt": "受伤", "shyness": "害羞"}
CAUSES = {
    "wronged": {"devalued_contribution", "admitted_unfair_blame"},
    "hurt": {"direct_devaluation"},
    "shyness": {"warm_attention"},
}
_META = re.compile(r"词义|什么意思|如何实现|怎么实现|解释.{0,3}情绪|翻译|例如|比如|小说|台词|引用|转述")
_REPORT = re.compile(
    r"听说|据说|转达|复述|代.{0,8}(?:说|感谢|道歉)"
    r"|我(?:刚才|之前|昨天)?(?:说过|曾说|听.{1,8}说|告诉(?:过|了))"
    r"|(?:他|她|别人|有人|朋友|同事|客户|对方).{0,8}(?:说|觉得|认为|道歉|感谢|谢谢|表示|告诉)"
    r"|(?:^|[，,])\s*(?!我|认真|老实|实话|坦白)"
    r"[^，,：:\s]{1,12}(?:说|说过|表示|写道|回复|告诉我)(?=[，,：:]|你|我)")
_QUOTED = re.compile(r'^>|[“”「」『』‘’"]')
_DENIAL = re.compile(r"不是说你|并非说你|不觉得你|并不觉得你|没有觉得你|别说你|不要说你|并不是你|不是你从")
_HYPOTHETICAL = re.compile(r"如果|假如|假设|要是|假装|难道|谁说")
_INSULT = r"(?:没用|废物|垃圾|白痴|蠢货|一无是处)"
_HARM = re.compile(r"你(?:就是|真是|简直是|是|很|真|太|根本|这个|一点都)?(?:个|一个)?" + _INSULT)
_HARM_DENIAL = re.compile(r"你.{0,3}(?:不是|并非|不算).{0,3}" + _INSULT)
_DENY_HELP = re.compile(r"你.{0,5}(?:从来|从没|从未|根本).{0,4}(?:帮|关心|付出)")
_HELP_DENIAL = re.compile(
    r"你(?:刚才|之前|以前|这次)?(?:从来(?:都)?(?:没有|没|不曾)|从没(?:有)?|"
    r"从未|根本(?:就)?(?:没有|没|不曾))帮(?:过|了)?我([^，,、：:]{0,80})(?=[，,、：:]|$)")
_UNFAIR = re.compile(r"你.{0,4}(?:没做错|没有错|没错|是无辜的).{0,18}我"
                     r"(?:就是要|偏要|仍然要|还是要|就要|却要|要)?(?:怪你|责怪你|冤枉你)")
# Bare compliments can be dialogue practice or teasing; only direct affection
# has enough evidence to move shyness without looking at the surrounding turn.
# 明确的亲密举动（亲亲/抱抱/贴贴等）算温柔亲密关注，可由规则直接判定；
# 容貌夸奖与注视要看上下文（可能是练习台词或玩笑），交给语义精炼层判断。
_WARM = re.compile(
    r"我(?:真的|真心|很|好|特别)?喜欢(?:你(?=$|[啊呀呢啦哦喔，,、 ]|这个人)"
    r"|(?:跟|和)你(?:待|呆)在一起)"
    r"|(?:亲亲|抱抱|抱一下|贴贴|蹭蹭|摸摸头|揉揉头)你")
_WARM_TECH = re.compile(r"代码|方案|文档|逻辑|思路|分析|回答|文章|设计|功能|接口|实现|配置|报告")
_WARM_DENIAL = re.compile(r"你.{0,3}(?:不|没|并非).{0,3}(?:可爱|迷人)|我.{0,3}不喜欢你|不.{0,3}看着你")
_HELP_ACK = re.compile(r"^(?:我(?:真的)?)?(?:谢谢你|感谢你|多谢你)(?:刚才|之前|上次|昨天|这次)?"
                       r"帮(?:了|过)?我([^，,、：:]{0,80})(?=[，,、：:]|$)")
_HELP_RESTORED = re.compile(
    r"^(?:你(?:之前|刚才)?确实帮(?:过|了)?我([^，,、：:]{0,80})"
    r"|([^，,、：:]{2,64})(?:确实|的确)是你帮我(?:解决|处理|修好|排查)(?:的|了)?)"
    r"(?=[，,、：:]|$)")
_HELP_UNCERTAIN = re.compile(r"才怪|反话|开玩笑|愿意|答应|打算|有空|能不能|以后|明天|还没|还在"
                             r"|没有帮|没帮|不是你帮|帮我看看|帮我.{0,24}(?:一下|好吗|行吗)")
_BOUNDARY_NAMES = {
    "work": r"只(?:聊|谈)工作(?:相关(?:的)?(?:事|话题))?",
    "professional": r"保持专业",
    "intimacy": r"(?:(?:别|不要|禁止|不许)(?:再|继续)?(?:暧昧|亲密|撩(?:我)?))",
    "neutral": r"正常聊(?:天)?(?:就好|吧)",
}
_BOUNDARY_TERM = "|".join(f"(?P<{kind}>{pattern})" for kind, pattern in _BOUNDARY_NAMES.items())
_BOUNDARY = re.compile(_BOUNDARY_TERM)
_BOUNDARY_SET = re.compile(
    r"(?:我(?:希望|要求)|从现在(?:起|开始)|接下来|以后|今后|我们|咱们|你|聊天时|聊天|"
    r"请你|请|还是|就|都|只要|必须|但|先|要){0,7}\s*(?:" + _BOUNDARY_TERM +
    r")(?:就好|一点|吧|了)?")
_BOUNDARY_WITHDRAW = re.compile(
    r"(?:(?:现在|以后)?(?:我们|咱们)?(?:现在|以后)?(?:不用|不必|不需要)再?"
    r"|我收回(?:刚才|之前|之前说的|刚才说的)?(?:的)?)\s*(?:" + _BOUNDARY_TERM +
    r")(?:的要求|的边界|那句话|了|吧)?")
_INTIMACY_WITHDRAW = re.compile(
    r"我收回(?:刚才|之前)的(?:要求|边界)[，,](?:现在)?(?:可以|不介意)(?:暧昧|亲密|撒娇)(?:了)?")
_BOUNDARY_DISCLAIMED = re.compile(r"(?<!开玩笑)才怪|开玩笑的|这是反话")
_UNFAIR_REPAIR = re.compile(r"(?:(?:是)?我(?:刚才|之前)?不该(?:怪你|责怪你|冤枉你)"
                            r"|我为.{0,8}(?:怪你|冤枉你).{0,8}道歉)(?:了)?")
_HARM_REPAIR = re.compile(
    r"(?:(?:是)?我(?:刚才|之前)?不该(?:骂你|贬低你|说你是(?:个|一个)?" + _INSULT + r")"
    r"|我为.{0,8}(?:骂你|贬低你).{0,8}道歉)(?:了)?")
_POINTED_REPAIR = re.compile(
    r"我收回(?:(?:刚才|之前)(?:说的|的)?)?(?:那句话?|这句话?|那番话|说的话)"
    r"(?:了)?(?=$|[。！？.!?，, ])"
    r"|(?:刚才|之前)那样说(?:不妥|不对)[，,]我收回(?:$|[。！？.!?，, ])")
_NAMED_REPAIR = re.compile(
    r"我收回(?:刚才|之前)(?:关于|说的|那句|这句)?([^，,。！？\n]{2,80}?)"
    r"(?:的)?(?:那句话|这句话|那番话|整句话|说法|的话)(?:了)?(?=$|[。！？.!?，, ])")
_EXCUSE = re.compile(r"开玩笑(?!才怪)|随口一说|小题大做|太敏感|至于吗|不道歉|不会道歉|对不起才怪")
_VAGUE_TOPIC = re.compile(r"(?:(?:这|那|什么|任何|一件|一些|个|了|过)*"
                          r"(?:事情|事|东西|忙|问题|什么)?)(?:了|的)?")


def empty_state():
    return {"version": VERSION, "items": [], "support": [], "seen": [],
            "updated_at": 0.0, "event_at": 0.0}


def _clauses(body):
    return [s.strip() for s in re.split(r"[。！？!?\n；;]|\.(?=\s|$)", direct_text(body))
            if s.strip()]


def _direct(span):
    return not (_QUOTED.search(span) or _META.search(span) or _REPORT.search(span) or _DENIAL.search(span)
                or _HYPOTHETICAL.search(span))


def _matching(body, pattern):
    return next((s[:256] for s in _direct_clauses(body) if pattern.search(s[:256])), "")


def _direct_clauses(body):
    return (span for span in _clauses(body) if span in body and _direct(span))


def _parts(span):
    return (value.strip() for value in re.split(r"[，,、]", span) if value.strip())


def _repair_span(body, pattern):
    return next((part for span in _direct_clauses(body)
                 for part in _parts(span) if pattern.fullmatch(part)), "")


def _topic(text):
    text = re.sub(r"^(?:解决|处理|修好|排查)(?:了)?", "", text.strip())
    text = re.sub(r"(?:的|了)$", "", text).strip()
    text = re.sub(r"\s+", "", text.casefold())
    return stable_key("context-help-topic", text) if not _VAGUE_TOPIC.fullmatch(text) else ""


def _help_topic(body, pattern):
    span = _matching(body, pattern)
    match = pattern.search(span)
    if not match:
        return ""
    return _topic(next((part for part in match.groups() if part), ""))


def _help_evidence(text, patterns=(_HELP_ACK, _HELP_RESTORED)):
    if _EXCUSE.search(direct_text(text)):
        return "", ""
    for span in _direct_clauses(text):
        if _HELP_UNCERTAIN.search(span):
            continue
        for pattern in patterns:
            match = pattern.match(span)
            if match and (topic := _topic(next(part for part in match.groups() if part is not None))):
                return span, topic
    return "", ""


def context_help_topic(text):
    """Return the opaque topic key for a direct, specific help acknowledgement."""
    return _help_evidence(text)[1]


def _proof(state, topic, at):
    if not topic:
        return ()
    return tuple(row["ref"] for row in reversed(state["support"])
                 if row.get("topic") == topic and row["at"] < at < row["expires_at"])[:1]


def _appraisal_topic(appraisal, event, state, help_refs):
    """Resolve only selected proof; an explicit conflicting topic invalidates it."""
    topics = {row["topic"] for row in state["support"]
              if row["ref"] in appraisal.context_refs and row.get("topic")
              and row["at"] < event.occurred_at < row["expires_at"]}
    if isinstance(help_refs, Mapping):
        topics.update(value for ref in appraisal.context_refs
                      if isinstance((value := help_refs.get(ref)), str) and len(value) == 64)
    current = (_help_topic(event.body, _HELP_DENIAL) if appraisal.action == "increase"
               else context_help_topic(event.body))
    if current:
        topics.add(current)
    if len(topics) > 1:
        raise ValueError("context_help_topic_mismatch")
    return next(iter(topics), "")


def _remember_repair(repairs, cause, topic, at):
    rows = {(kind, focus): when for kind, focus, when in repairs}
    rows[cause, topic] = at
    if len(rows) > MAX_REPAIRS:
        # Preserve ordering under saturation: fold the oldest topic fences into
        # a contribution-only cutoff rather than permitting an old resurrection.
        floor = ("devalued_contribution", "")
        oldest = sorted((key for key in rows if key[1]), key=rows.__getitem__)
        retired = oldest[:1 if floor in rows else 2]
        rows[floor] = max(rows.get(floor, 0), *(rows.pop(key) for key in retired))
    return [[kind, focus, when] for (kind, focus), when in rows.items()]


def _repair_evidence(appraisal, state, topic, support_refs):
    evidence, cause = appraisal.evidence, appraisal.cause_code
    linked = {item["evidence_refs"][0] for item in state["items"]
              if item["cause_code"] == cause and item["evidence_refs"]}
    if cause == "devalued_contribution":
        if not topic:
            return False
        if _help_evidence(evidence, (_HELP_RESTORED,))[1] == topic:
            return True
    else:
        pattern = _UNFAIR_REPAIR if cause == "admitted_unfair_blame" else _HARM_REPAIR
        if _repair_span(evidence, pattern):
            return True
    linked.intersection_update(appraisal.context_refs)
    if named := _NAMED_REPAIR.search(evidence):
        if not isinstance(support_refs, Mapping):
            return False
        for ref in appraisal.context_refs:
            text = support_refs.get(ref, "")
            if ((ref in linked or topic and context_help_topic(text) == topic)
                    and named[1] in direct_text(text)):
                return True
        return False
    return bool((linked or topic) and _POINTED_REPAIR.search(evidence))


def _boundary_directive(body):
    if _BOUNDARY_DISCLAIMED.search(direct_text(body)):
        return None
    groups = {True: set(), False: set()}
    setting = ""
    for span in _direct_clauses(body):
        if _EXCUSE.search(span):
            continue
        if _INTIMACY_WITHDRAW.fullmatch(span):
            groups[False].add("intimacy")
        for part in _parts(span):
            if match := _BOUNDARY_SET.fullmatch(part):
                groups[True].add(match.lastgroup)
                setting = setting or part
            elif match := _BOUNDARY_WITHDRAW.fullmatch(part):
                groups[False].add(match.lastgroup)
    for setting_active, terms in groups.items():
        if terms:
            return setting_active, terms, setting
    return None


def _boundary_groups(groups, active, terms):
    remaining = [group for group in groups if terms.isdisjoint(group)]
    if active:
        # Terms imposed together name the same restriction; independent ones persist.
        merged = terms.union(*(group for group in groups if not terms.isdisjoint(group)))
        remaining.append(sorted(merged))
    return remaining


def _direct_harm(body):
    return next((part[:256] for span in _direct_clauses(body) for part in _parts(span)
                 if _HARM.search(part[:256]) and not (
                     _HARM_DENIAL.search(part) or _HARM_REPAIR.fullmatch(part))), "")


def _direct_evidence(body, evidence):
    parts = _clauses(evidence)
    if not parts or evidence not in direct_text(body):
        return False
    spans = tuple(_direct_clauses(body))
    return all(any(part in span for span in spans) for part in parts)


def human_labels(body):
    """Self reports describe the human, never a bot stimulus."""
    text = direct_text(body)
    if _META.search(text) or _REPORT.search(text):
        return ()
    return tuple(name for name, word in (
        ("wronged", "委屈"), ("hurt", "受伤"), ("shyness", "害羞")
    ) if re.search(r"我.{0,40}" + word, text) and not re.search(
        r"我.{0,8}(?:不|没|并非).{0,4}" + word + r"|我觉得你", text))


def read_state(raw, context, *, now):
    """Invalid optional metadata degrades locally; legacy affect remains usable."""
    finite(now, "now", 0)
    if raw is None:
        return empty_state()
    try:
        if (not isinstance(raw, dict) or type(raw.get("version")) is not int
                or raw["version"] != VERSION
                or len(json.dumps(raw, ensure_ascii=True)) > MAX_STATE_CHARS
                or ("owner" in raw and raw["owner"] != account_person_key(context))
                or set(raw) - {"version", "items", "support", "seen", "updated_at", "event_at",
                               "owner", "marks", "boundary", "boundary_terms", "repairs",
                               "wronged_topic"}):
            return empty_state()
        finite(raw.get("updated_at"), "context_updated_at", 0)
        finite(raw.get("event_at", 0), "context_event_at", 0)
        if not all(isinstance(raw.get(k), list) for k in ("items", "support", "seen")):
            return empty_state()
        if len(raw["items"]) > 8 or len(raw["support"]) > 2 or len(raw["seen"]) > MAX_SEEN:
            return empty_state()
        items = []
        for row in raw["items"]:
            item = ContextEmotion(**row)
            cap, half_life, ttl = POLICIES[item.kind]
            if (item.target != context.account_id or item.cause_code not in CAUSES[item.kind]
                    or item.intensity > cap or item.expires_at - item.started_at > ttl):
                return empty_state()
            if now >= item.expires_at:
                continue
            intensity = item.intensity * 2 ** (-max(0, now - item.updated_at) / half_life)
            if intensity > .001:
                items.append(to_dict(replace(
                    item, intensity=intensity, updated_at=max(now, item.updated_at))))
        support = []
        for ref in raw["support"]:
            if not isinstance(ref, dict) or set(ref) - {"ref", "at", "expires_at", "topic"}:
                return empty_state()
            if any(not isinstance(ref[k], str) or len(ref[k]) != 64
                   for k in ("ref", "topic") if k in ref) or "ref" not in ref:
                return empty_state()
            finite(ref["at"], "support_at", 0)
            finite(ref["expires_at"], "support_expiry", ref["at"], ref["at"] + HELP_EVIDENCE_SECONDS)
            if ref["expires_at"] > now:
                support.append(dict(ref))
        seen = []
        for row in raw["seen"]:
            if not isinstance(row, list) or len(row) != 2 or not isinstance(row[0], str):
                return empty_state()
            if len(row[0]) != 64:
                return empty_state()
            finite(row[1], "seen_at", 0)
            if now - row[1] < WINDOW:
                seen.append(list(row))
        state = {"version": VERSION, "items": items, "support": support, "seen": seen,
                 "updated_at": raw["updated_at"], "event_at": raw.get("event_at", 0)}
        if "owner" in raw:
            state["owner"] = raw["owner"]
        if "boundary" in raw:
            if type(raw["boundary"]) is not bool:
                return empty_state()
            state["boundary"] = raw["boundary"]
        if "boundary_terms" in raw:
            groups = raw["boundary_terms"]
            used = set()
            if not raw.get("boundary") or not isinstance(groups, list) or not groups:
                return empty_state()
            for group in groups:
                if (not isinstance(group, list) or not group or len(group) > len(_BOUNDARY_NAMES)
                        or len(set(group)) != len(group)
                        or any(term not in _BOUNDARY_NAMES or term in used for term in group)):
                    return empty_state()
                used.update(group)
            state["boundary_terms"] = [list(group) for group in groups]
        marks = {}
        for kind, mark in raw.get("marks", {}).items():
            if (kind not in POLICIES or not isinstance(mark, list) or len(mark) != 2
                    or not isinstance(mark[1], str) or len(mark[1]) != 64):
                return empty_state()
            at = mark[0]
            finite(at, "context_mark_at", 0)
            if now - at < POLICIES["wronged"][2]:
                marks[kind] = list(mark)
        if marks:
            state["marks"] = marks
        repairs = raw.get("repairs", [])
        if not isinstance(repairs, list) or len(repairs) > MAX_REPAIRS:
            return empty_state()
        live_repairs = []
        for row in repairs:
            if not isinstance(row, list) or len(row) != 3:
                return empty_state()
            cause, topic, at = row
            if (cause not in CAUSES["wronged"] | CAUSES["hurt"]
                    or not isinstance(topic, str) or len(topic) not in (0, 64)
                    or (topic and cause != "devalued_contribution")):
                return empty_state()
            finite(at, "context_repair_at", 0)
            if now - at < POLICIES["wronged"][2]:
                live_repairs.append(list(row))
        if live_repairs:
            state["repairs"] = live_repairs
        if "wronged_topic" in raw:
            topic = raw["wronged_topic"]
            if not isinstance(topic, str) or len(topic) != 64:
                return empty_state()
            if any(row["cause_code"] == "devalued_contribution" for row in items):
                state["wronged_topic"] = topic
        return state
    except (ValueError, TypeError, KeyError, OverflowError, AttributeError):
        return empty_state()


def memory_support(materials, context, *, now):
    """Only authorized same-account help acknowledgements support 委屈."""
    result = {}
    for material in materials:
        ref = material.evidence
        if (ref.context.account_key != context.account_key
                or ref.subject_id != context.account_id or ref.holder_id != context.bot_id
                or ref.kind != ContentKind.INTERACTION or ref.occurred_at > now
                or now - ref.occurred_at >= HELP_EVIDENCE_SECONDS
                or (ref.expires_at is not None and now >= ref.expires_at)):
            continue
        if context_help_topic(material.text[:256]):
            key = stable_key("context-help", ref.provider, ref.source_id)
            result[key] = material.text[:256]
    return result


def local_appraisals(event, relationship, state, *, relationship_note="", boundary=False):
    result = []
    if _EXCUSE.search(direct_text(event.body)):
        return ()
    proof = _proof(state, _help_topic(event.body, _HELP_DENIAL), event.occurred_at)
    unfair = _matching(event.body, _UNFAIR)
    denied = _matching(event.body, _HELP_DENIAL)
    if unfair:
        result.append(ContextAppraisal("wronged", "admitted_unfair_blame", unfair))
    elif denied and proof:
        result.append(ContextAppraisal("wronged", "devalued_contribution", denied, context_refs=proof))
    harm = _direct_harm(event.body)
    if harm:
        result.append(ContextAppraisal("hurt", "direct_devaluation", harm))
    warm = _matching(event.body, _WARM)
    if (warm and relationship.score >= 250 and not _WARM_DENIAL.search(warm)
            and not _WARM_TECH.search(warm)
            and not state.get("boundary") and not boundary
            and not _BOUNDARY.search(relationship_note)):
        result.append(ContextAppraisal("shyness", "warm_attention", warm))
    return tuple(result)


def parse_context_appraisals(value, event, relationship, state, *,
                             support_refs=(), relationship_note="", help_refs=None,
                             dialogue_boundary=False):
    """Validate evidence; a ref-to-text mapping also verifies named retractions."""
    if isinstance(value, str):
        from .emotion import _unique_object
        text = value.strip()
        if text.startswith("```json\n") and text.endswith("\n```"):
            text = text[8:-4]
        if len(text) > 4096:
            raise ValueError("model_output_too_long")
        value = json.loads(text, object_pairs_hook=_unique_object)
    if not isinstance(value, dict):
        raise ValueError("model_schema")
    legacy = {k: v for k, v in value.items() if k != "context_appraisals"}
    if "context_appraisals" not in value:
        return legacy, (), ("context_appraisals_missing",)
    rows = value.get("context_appraisals", [])
    accepted, rejected = [], False
    if not isinstance(rows, list) or len(rows) > 8:
        return legacy, (), ("context_appraisals_invalid",)
    help_topics = help_refs
    allowed_refs = set(support_refs)
    if help_topics is None:
        help_refs = set(_proof(state, _help_topic(event.body, _HELP_DENIAL), event.occurred_at))
        allowed_refs.update(help_refs)
    elif isinstance(help_topics, Mapping):
        help_refs = {ref for ref, topic in help_topics.items()
                     if ref in allowed_refs and isinstance(topic, str) and len(topic) == 64}
    else:
        help_refs = set(help_topics) & allowed_refs
    seen_kinds = set()
    for row in rows:
        try:
            if not isinstance(row, dict) or set(row) - {
                "kind", "cause_code", "evidence", "confidence", "strength", "context_refs",
                "action", "holder", "target",
            }:
                raise ValueError("context_appraisal_schema")
            appraisal = ContextAppraisal(**row)
            if (appraisal.cause_code not in CAUSES[appraisal.kind]
                    or appraisal.confidence < .75
                    or appraisal.evidence not in event.body
                    or not _direct_evidence(event.body, appraisal.evidence)
                    or appraisal.kind in seen_kinds
                    or any(r not in allowed_refs for r in appraisal.context_refs)):
                raise ValueError("context_appraisal_evidence")
            if (appraisal.action == "increase"
                    and appraisal.cause_code in ("direct_devaluation", "admitted_unfair_blame")
                    and any(_DENY_HELP.search(span)
                            and any(part in span or span in part for part in
                                    _clauses(appraisal.evidence))
                            for span in _direct_clauses(event.body))
                    and not (_direct_harm(appraisal.evidence) if appraisal.kind == "hurt"
                             else _matching(appraisal.evidence, _UNFAIR))):
                raise ValueError("context_appraisal_basis")
            if (appraisal.action == "increase" and (
                    (appraisal.kind == "wronged"
                     and appraisal.cause_code == "devalued_contribution"
                     and not help_refs.intersection(appraisal.context_refs))
                    or (appraisal.kind == "shyness" and (
                        relationship.score < 250 or state.get("boundary", dialogue_boundary)
                        or _boundary_directive(event.body) is not None
                        or _BOUNDARY.search(relationship_note))))):
                raise ValueError("context_appraisal_basis")
            topic = (_appraisal_topic(appraisal, event, state, help_topics)
                     if appraisal.cause_code == "devalued_contribution" else "")
            if appraisal.action in ("decrease", "clear") and (
                    _EXCUSE.search(direct_text(event.body))
                    or (appraisal.kind != "shyness"
                        and not _repair_evidence(appraisal, state, topic, support_refs))):
                raise ValueError("context_appraisal_basis")
            seen_kinds.add(appraisal.kind)
            accepted.append(appraisal)
        except (ValueError, TypeError, KeyError):
            rejected = True
    return legacy, tuple(accepted), (("context_appraisals_invalid",) if rejected else ())


def apply_realtime_context_emotions(raw, event, relationship, *, now, enabled=False,
                                   relationship_note=""):
    """Project only directly established evidence, before provider work."""
    return _transition(raw, event, relationship, now=now, enabled=enabled,
                       realtime=True, relationship_note=relationship_note)


def apply_deferred_context_emotions(raw, event, relationship, *, now, appraisals,
                                   support_refs=(), relationship_note="", help_refs=None,
                                   dialogue_boundary=False):
    """Merge a verified result into the latest matching record at completion time.

    The caller owns authorization and the CAS. A retry reuses the same event and
    appraisals with a fresh record. Pass verified ref -> context_help_topic(text)
    entries as help_refs to bind paraphrases to their topic; an ID set still works.
    For named retractions, pass ref -> packed text as support_refs.
    """
    return _transition(raw, event, relationship, now=now, appraisals=appraisals,
                       support_refs=support_refs, relationship_note=relationship_note,
                       help_refs=help_refs, dialogue_boundary=dialogue_boundary)


def apply_context_emotions(raw, event, relationship, *, now, enabled=False,
                           appraisals=(), support_refs=(), relationship_note="",
                           semantic=False, help_refs=None, dialogue_boundary=False):
    """Compatibility for callers still doing strict, single-event recomputation."""
    return _transition(raw, event, relationship, now=now, enabled=enabled, realtime=True,
                       strict=semantic, appraisals=appraisals, support_refs=support_refs,
                       relationship_note=relationship_note, help_refs=help_refs,
                       dialogue_boundary=dialogue_boundary)


def _transition(raw, event, relationship, *, now, enabled=True, realtime=False,
                strict=False, appraisals=(), support_refs=(), relationship_note="",
                help_refs=None, dialogue_boundary=False):
    state = read_state(raw, event.context, now=now)
    before = to_dict(state)
    trace = {"before": before["items"], "after": before["items"], "reason_codes": []}
    result = {"state": before, "applied": False, "trace": trace}
    if not enabled:
        return result
    if isinstance(raw, dict) and "owner" in raw and "owner" not in state:
        trace["reason_codes"] = ["context_source_uncertain"]
        return result
    from .emotion import _event_problem, _targets_bot
    problem = _event_problem(event, now, 7200)
    at, key = event.occurred_at, event.idempotency_key
    if (problem or event.actor_role != ActorRole.HUMAN or event.event_type != "message"
            or event.confidence < .75 or not _targets_bot(event)
            or now < state["updated_at"] or (strict and at < state["event_at"])):
        trace["reason_codes"] = [problem or "context_source_uncertain"]
        return result
    seen_event = any(k == key for k, _ in state["seen"])
    if seen_event and ((not appraisals and not strict) or "owner" not in state):
        trace["reason_codes"] = ["context_event_duplicate"]
        return result

    items = {r["kind"]: ContextEmotion(**r) for r in state["items"]}
    marks = state.get("marks", {})
    repairs = state.get("repairs", [])
    reasons, skipped = [], []
    boundary = _boundary_directive(event.body)
    local = {a.kind: a for a in local_appraisals(
        event, relationship, state, relationship_note=relationship_note, boundary=boundary is not None)}

    def mark_for(kind):
        if kind in marks:
            return marks[kind]
        # Legacy rows can still supply their own incident's ordering.
        old = items.get(kind)
        if old:
            last = next(((seen_at, ref) for ref, seen_at in reversed(state["seen"])
                         if old.evidence_refs and ref == old.evidence_refs[0]), None)
            return last or (old.started_at, old.evidence_refs[0] if old.evidence_refs else "")
        return -1, ""

    def eligible(kind, *, deferred=False):
        last_at, last_key = mark_for(kind)
        if last_key == key:
            skipped.append("context_event_duplicate")
        elif at < last_at or (deferred and at == last_at):
            # Without a reliable ordering for equal timestamps, a callback never
            # displaces an already observed same-kind transition.
            skipped.append("context_kind_superseded")
        else:
            return True
        return False

    def mark(kind):
        marks[kind] = [at, key]

    def repaired_since(cause, topic):
        return any(previous == cause and (not focus or focus == topic) and when >= at
                   for previous, focus, when in repairs)

    def apply_appraisal(appraisal, *, deferred):
        nonlocal repairs
        kind, cause = appraisal.kind, appraisal.cause_code
        old = items.get(kind)
        cap, half_life, ttl = POLICIES[kind]
        if appraisal.action == "none" or not eligible(kind, deferred=deferred):
            return
        if now >= at + ttl:
            skipped.append("context_kind_expired")
            return
        topic = (_appraisal_topic(appraisal, event, state, help_refs)
                 if cause == "devalued_contribution" else "")
        change = appraisal.strength * min(appraisal.confidence, event.confidence)
        factor = 2 ** (-(now - at) / half_life)
        if appraisal.action != "increase" and (not old or old.cause_code != cause):
            return
        if (appraisal.action in ("clear", "decrease") and cause == "devalued_contribution"
                and (not topic or topic != state.get("wronged_topic"))):
            skipped.append("context_help_topic_mismatch")
            return
        if repaired_since(cause, topic):
            skipped.append("context_cause_already_repaired")
            return
        if appraisal.action == "clear":
            items.pop(kind)
            if kind == "wronged":
                state.pop("wronged_topic", None)
            reasons.append("context_" + kind + "_cleared")
            if kind == "shyness":
                mark(kind)
            else:
                repairs = _remember_repair(repairs, cause, topic, at)
            return
        if appraisal.action == "decrease":
            if change:
                items[kind] = replace(old, intensity=max(
                    0, old.intensity - change * factor))
                reasons.append("context_" + kind + "_decreased")
                if kind == "shyness":
                    mark(kind)
                else:
                    repairs = _remember_repair(repairs, cause, topic, at)
            return
        if not change:
            return
        if kind == "shyness" and relationship.score < 450:
            cap = min(cap, .25)
        stimulus = stable_key(kind, cause, appraisal.evidence)
        same_topic = (cause != "devalued_contribution" or not topic
                      or topic == state.get("wronged_topic"))
        # Repair leaves a reading to decay but ends that incident's dedup window.
        repaired = old and any(
            previous_cause == cause and repaired_topic == topic
            and old.started_at <= repair_at < at
            for previous_cause, repaired_topic, repair_at in repairs
        )
        confidence = min(appraisal.confidence, event.confidence)
        if old is not None and old.cause_code == cause and same_topic and not repaired:
            if (old.stimulus_key == stimulus
                    or ((not deferred or kind in local) and at - mark_for(kind)[0] < WINDOW)):
                return
            intensity = min(cap * factor, old.intensity + min(.10, change) * factor)
            items[kind] = replace(old, intensity=intensity, confidence=confidence,
                                  stimulus_key=stimulus, evidence_refs=(key, *appraisal.context_refs)[:2])
        else:
            items[kind] = ContextEmotion(
                kind, event.context.account_id, cause, min(cap, change) * factor,
                confidence, at, now, at + ttl,
                stable_key(event.context.account_key, kind, key), stimulus,
                (key, *appraisal.context_refs)[:2])
            if kind == "wronged":
                state.pop("wronged_topic", None)
                if cause == "devalued_contribution" and topic:
                    state["wronged_topic"] = topic
        reasons.append("context_" + kind)
        mark(kind)

    if realtime and not seen_event:
        if boundary is not None:
            active, terms, _ = boundary
            groups = state.get("boundary_terms", [])
            remaining = _boundary_groups(groups, active, terms)
            # A legacy true flag has no recorded terms to compare with a named release.
            release = (not active and state.get("boundary") and (not groups or groups != remaining))
            if (active or release) and eligible("shyness", deferred=not active):
                state["boundary"] = bool(remaining)
                if remaining:
                    state["boundary_terms"] = remaining
                else:
                    state.pop("boundary_terms", None)
                items.pop("shyness", None)
                mark("shyness")
                reasons.append("context_boundary_respected" if active else "context_boundary_withdrawn")

        if not _EXCUSE.search(direct_text(event.body)):
            repaired_topic = _help_evidence(event.body, (_HELP_RESTORED,))[1]
            targets = []
            if repaired_topic:
                targets.append(("wronged", "devalued_contribution", repaired_topic))
            if _repair_span(event.body, _UNFAIR_REPAIR):
                targets.append(("wronged", "admitted_unfair_blame", ""))
            if _repair_span(event.body, _HARM_REPAIR):
                targets.append(("hurt", "direct_devaluation", ""))
            for kind, cause, repaired_topic in targets:
                current = local.get(kind)
                current_topic = (_help_topic(event.body, _HELP_DENIAL)
                                 if current and current.cause_code == "devalued_contribution" else "")
                if (current and current.cause_code == cause and current_topic == repaired_topic
                        or repaired_since(cause, repaired_topic) or not eligible(kind)):
                    continue
                old = items.get(kind)
                if (old and old.cause_code == cause and
                        (not repaired_topic or state.get("wronged_topic") == repaired_topic)):
                    items[kind] = replace(old, intensity=old.intensity * (.5 if repaired_topic else .4))
                    reasons.append("context_cause_repaired")
                else:
                    # A specific repair can arrive before its incident is classified.
                    reasons.append("context_repair_fence")
                # Repair is not a new appraisal; a different topic can still arrive late.
                repairs = _remember_repair(repairs, cause, repaired_topic, at)

        for appraisal in local.values():
            apply_appraisal(appraisal, deferred=False)
        proved_topic = context_help_topic(event.body)
        if proved_topic and not any(r.get("topic") == proved_topic and r["at"] >= at
                                    for r in state["support"]):
            row = {"ref": key, "at": at, "expires_at": at + HELP_EVIDENCE_SECONDS, "topic": proved_topic}
            support = [r for r in state["support"] if r.get("topic") != proved_topic]
            state["support"] = sorted(support + [row], key=lambda r: r["at"])[-2:]
            reasons.append("context_help_acknowledged")

    if appraisals:
        _, valid, invalid = parse_context_appraisals(
            {"context_appraisals": [to_dict(a) for a in appraisals]}, event, relationship, state,
            support_refs=support_refs, relationship_note=relationship_note,
            help_refs=help_refs, dialogue_boundary=dialogue_boundary)
        skipped.extend(invalid)
        for appraisal in valid:
            apply_appraisal(appraisal, deferred=True)

    if strict and not reasons and not skipped:
        reasons.append("context_no_stimulus")
    if not reasons:
        trace["reason_codes"] = list(dict.fromkeys(skipped or (
            ["context_no_stimulus"] if not realtime else [])))
        return result

    state["items"] = [to_dict(i) for i in items.values() if i.intensity > .001]
    if not any(item["cause_code"] == "devalued_contribution" for item in state["items"]):
        state.pop("wronged_topic", None)
    if marks:
        state["marks"] = marks
    if repairs:
        state["repairs"] = repairs
    if not seen_event:
        state["seen"] = (state["seen"] + [[key, at]])[-MAX_SEEN:]
    state["owner"] = account_person_key(event.context)
    state["updated_at"] = now
    state["event_at"] = max(state["event_at"], at)
    while state["seen"] and len(json.dumps(state, ensure_ascii=True)) > MAX_STATE_CHARS:
        state["seen"].pop(0)
    if len(json.dumps(state, ensure_ascii=True)) > MAX_STATE_CHARS:
        trace["reason_codes"] = ["context_capacity_limited"]
        return result
    trace.update(after=state["items"], reason_codes=list(dict.fromkeys(reasons + skipped)))
    return {"state": state, "applied": True, "trace": trace}


def expression_items(raw, context, *, now, relationship=None, relationship_note=""):
    state = read_state(raw, context, now=now)
    rows = sorted(state["items"], key=lambda r: (-r["intensity"], r["kind"]))
    return [{"kind": r["kind"], "label": LABELS[r["kind"]],
             "intensity": round(r["intensity"], PROMPT_DECIMALS), "cause": r["cause_code"],
             "holder": "bot", "target": "current_interlocutor"}
            for r in rows if r["intensity"] >= THRESHOLD and not (
                r["kind"] == "shyness" and (
                    (relationship is not None and relationship.score < 250)
                    or state.get("boundary") or _BOUNDARY.search(relationship_note)))][:2]


def collected_values(raw, context, *, now, relationship=None, relationship_note=""):
    """Display all measured values, even below the expression threshold.

    No stimulus after collection is a measured zero; disabled or unselected
    contexts are handled by the caller and remain explicitly uncollected.
    """
    state = read_state(raw, context, now=now)
    if not state["updated_at"]:
        return {}
    values = {kind: 0.0 for kind in POLICIES}
    for row in state["items"]:
        if row["kind"] == "shyness" and (
                (relationship is not None and relationship.score < 250)
                or state.get("boundary") or _BOUNDARY.search(relationship_note)):
            continue
        values[row["kind"]] = row["intensity"]
    return values
