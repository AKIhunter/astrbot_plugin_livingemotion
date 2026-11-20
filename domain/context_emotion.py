"""Account-scoped 委屈/受伤/害羞. Pure transitions; no provider or host imports.

Current evidence causes a transition. Past help acknowledgements only establish
its basis. Model corrections recompute from the SAME pre-event snapshot.
These intensities never enter the four shared affect dimensions.
"""
from __future__ import annotations

from dataclasses import replace
import json
import re

from ..contracts import (
    ActorRole, ContextAppraisal, ContextEmotion, ContentKind, finite, stable_key, to_dict,
)
from ..prompt_precision import PROMPT_DECIMALS
from .appraisal import direct_text

VERSION = 1
THRESHOLD = .20
MAX_STATE_CHARS = 4096
MAX_SEEN = 16
WINDOW = 300.0
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
_REPORT = re.compile(r"他说|她说|别人说|有人说|他觉得|她觉得|别人觉得")
_DENIAL = re.compile(r"不是说你|并非说你|不觉得你|并不觉得你|没有觉得你|别说你|不要说你|并不是你|不是你从")
_HARM = re.compile(r"你(?:就是|真是|简直是|是|很|真|太|根本|这个|一点都)?"
                   r"(?:个|一个)?(?:没用|废物|垃圾|白痴|蠢货|一无是处)"
                   r"|我不需要你|你不用再陪我")
_HARM_DENIAL = re.compile(r"你.{0,3}(?:不是|并非|不算).{0,3}(?:没用|废物|垃圾|白痴|蠢货|一无是处)")
_DENY_HELP = re.compile(r"你.{0,5}(?:从来|从没|从未|根本).{0,4}(?:帮|关心|付出)")
_UNFAIR = re.compile(r"你.{0,4}(?:没做错|没有错|没错|是无辜的).{0,18}我.{0,8}(?:怪你|责怪你|冤枉你)")
_WARM = re.compile(r"你(?:今天|刚才|现在)?(?:真的|真是|实在|也)?"
                   r"(?:好可爱|很可爱|真可爱|太可爱|好迷人|很迷人)"
                   r"|我(?:真的|很|好)?喜欢你|(?:我)?一直看着你")
_WARM_DENIAL = re.compile(r"你.{0,3}(?:不|没|并非).{0,3}(?:可爱|迷人)|我.{0,3}不喜欢你|不.{0,3}看着你")
_HELP = re.compile(r"(?:谢谢你|感谢你|多谢你).{0,20}(?:帮我|帮了我|帮我解决|解决了|帮了大忙)")
_BOUNDARY = re.compile(r"正常聊(?:天)?(?:就好|吧)|只聊工作|别暧昧|不要暧昧|禁止暧昧|禁止亲密|别撩|不要撩|保持专业")
_REPAIR = re.compile(r"是我误会你|我误会你了|不该怪你|不该骂你|不该说你|"
                     r"你确实帮过我|你之前帮过我|为.{0,8}(?:怪你|骂你|冤枉你).{0,8}道歉")
_EXCUSE = re.compile(r"开玩笑|小题大做|太敏感|至于吗|不道歉|不会道歉")


def empty_state():
    return {"version": VERSION, "items": [], "support": [], "seen": [],
            "updated_at": 0.0, "event_at": 0.0}


def _clauses(body):
    return [s.strip() for s in re.split(r"[。！？.!?\n；;]", direct_text(body)) if s.strip()]


def _direct(span):
    return not (_META.search(span) or _REPORT.search(span) or _DENIAL.search(span))


def _matching(body, pattern):
    return next((s[:256] for s in _clauses(body) if _direct(s) and pattern.search(s)), "")


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
                or set(raw) - {"version", "items", "support", "seen", "updated_at", "event_at"}):
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
            if not isinstance(ref, dict) or set(ref) != {"ref", "at", "expires_at"}:
                return empty_state()
            if not isinstance(ref["ref"], str) or len(ref["ref"]) != 64:
                return empty_state()
            finite(ref["at"], "support_at", 0)
            finite(ref["expires_at"], "support_expiry", ref["at"], ref["at"] + 86400)
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
        return {"version": VERSION, "items": items, "support": support, "seen": seen,
                "updated_at": raw["updated_at"], "event_at": raw.get("event_at", 0)}
    except (ValueError, TypeError, KeyError, OverflowError):
        return empty_state()


def memory_support(materials, context, *, now):
    """Only authorized same-account help acknowledgements support 委屈."""
    result = {}
    for material in materials:
        ref = material.evidence
        if (ref.context.account_key != context.account_key
                or ref.subject_id != context.account_id or ref.holder_id != context.bot_id
                or ref.kind != ContentKind.INTERACTION or ref.occurred_at > now
                or now - ref.occurred_at >= 86400
                or (ref.expires_at is not None and now >= ref.expires_at)):
            continue
        if _matching(material.text[:400], _HELP):
            key = stable_key("context-help", ref.provider, ref.source_id)
            result[key] = material.text[:256]
    return result


def local_appraisals(event, relationship, state, *, relationship_note=""):
    result = []
    proof = tuple(r["ref"] for r in state["support"][-1:])
    unfair = _matching(event.body, _UNFAIR)
    denied = _matching(event.body, _DENY_HELP)
    if unfair:
        result.append(ContextAppraisal("wronged", "admitted_unfair_blame", unfair))
    elif denied and proof:
        result.append(ContextAppraisal("wronged", "devalued_contribution", denied, context_refs=proof))
    else:
        harm = _matching(event.body, _HARM) or denied
        if harm and not _HARM_DENIAL.search(harm):
            result.append(ContextAppraisal("hurt", "direct_devaluation", harm))
    warm = _matching(event.body, _WARM)
    if (warm and relationship.score >= 250 and not _WARM_DENIAL.search(warm)
            and not _BOUNDARY.search(event.body) and not _BOUNDARY.search(relationship_note)):
        result.append(ContextAppraisal("shyness", "warm_attention", warm))
    return tuple(result)


def parse_context_appraisals(value, event, relationship, state, *,
                             support_refs=(), relationship_note=""):
    """Validate structure, subject and real evidence, never gate by vocabulary."""
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
    allowed_refs = set(support_refs) | {r["ref"] for r in state["support"]}
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
                    or appraisal.kind in seen_kinds
                    or any(r not in allowed_refs for r in appraisal.context_refs)):
                raise ValueError("context_appraisal_evidence")
            if (appraisal.action == "increase" and (
                    (appraisal.kind == "wronged"
                     and appraisal.cause_code == "devalued_contribution"
                     and not appraisal.context_refs)
                    or (appraisal.kind == "shyness" and relationship.score < 250))):
                raise ValueError("context_appraisal_basis")
            seen_kinds.add(appraisal.kind)
            accepted.append(appraisal)
        except (ValueError, TypeError, KeyError):
            rejected = True
    return legacy, tuple(accepted), (("context_appraisals_invalid",) if rejected else ())


def apply_context_emotions(raw, event, relationship, *, now, enabled=False,
                           appraisals=(), support_refs=(), relationship_note="",
                           semantic=False):
    finite(now, "now", 0)
    state = read_state(raw, event.context, now=now)
    before = to_dict(state)
    trace = {"before": before["items"], "after": before["items"], "reason_codes": []}
    result = {"state": state, "applied": False, "trace": trace}
    if not enabled:
        return result
    from .emotion import _event_problem, _targets_bot
    problem = _event_problem(event, now, 7200)
    if (problem or event.actor_role != ActorRole.HUMAN or event.event_type != "message"
            or event.confidence < .75 or not _targets_bot(event)
            or now < state["updated_at"] or event.occurred_at < state["event_at"]):
        trace["reason_codes"] = [problem or "context_source_uncertain"]
        return result
    key = event.idempotency_key
    if any(k == key for k, _ in state["seen"]):
        trace["reason_codes"] = ["context_event_duplicate"]
        return result
    # Model mode is authoritative: an empty array must not resurrect rule guesses.
    candidates = {} if semantic else {a.kind: replace(a, confidence=min(a.confidence, event.confidence))
                  for a in local_appraisals(event, relationship, state,
                                            relationship_note=relationship_note)}
    for appraisal in appraisals:
        _, valid, _ = parse_context_appraisals(
            {"context_appraisals": [to_dict(appraisal)]}, event, relationship, state,
            support_refs=support_refs, relationship_note=relationship_note)
        if valid:
            candidates[appraisal.kind] = appraisal
            if appraisal.kind == "wronged" and appraisal.action == "increase":
                candidates.pop("hurt", None)
    items = {r["kind"]: ContextEmotion(**r) for r in state["items"]}
    reasons = []
    if not semantic and _matching(event.body, _BOUNDARY) and items.pop("shyness", None):
        reasons.append("context_boundary_respected")
    if (not semantic and _matching(event.body, _REPAIR) and not _EXCUSE.search(direct_text(event.body))
            and not set(candidates) & {"hurt", "wronged"}):
        for kind in ("hurt", "wronged"):
            if kind in items:
                items[kind] = replace(items[kind], intensity=items[kind].intensity * .4)
                reasons.append("context_cause_repaired")
    for kind, appraisal in candidates.items():
        old = items.get(kind)
        if appraisal.action == "none":
            continue
        if appraisal.action == "clear":
            if items.pop(kind, None):
                reasons.append("context_" + kind + "_cleared")
            continue
        if appraisal.action == "decrease":
            if old:
                items[kind] = replace(old, intensity=max(
                    0, old.intensity - appraisal.strength * appraisal.confidence))
                reasons.append("context_" + kind + "_decreased")
            continue
        cap, _, ttl = POLICIES[kind]
        if kind == "shyness" and relationship.score < 450:
            cap = min(cap, .25)
        stimulus = stable_key(kind, appraisal.cause_code, appraisal.evidence)
        intensity = min(cap, appraisal.strength * appraisal.confidence)
        if old is not None and old.cause_code == appraisal.cause_code:
            if old.stimulus_key == stimulus or (not semantic and now - old.started_at < WINDOW):
                continue
            last_at = next((at for k, at in reversed(state["seen"])
                            if k in old.evidence_refs), old.started_at)
            if not semantic and now - last_at < WINDOW:
                continue
            intensity = min(cap, old.intensity + min(.10, intensity))
            items[kind] = replace(old, intensity=intensity, confidence=appraisal.confidence,
                                  stimulus_key=stimulus, evidence_refs=(key, *appraisal.context_refs)[:2])
        else:
            items[kind] = ContextEmotion(
                kind, event.context.account_id, appraisal.cause_code, intensity,
                appraisal.confidence, now, now, now + ttl,
                stable_key(event.context.account_key, kind, key), stimulus,
                (key, *appraisal.context_refs)[:2])
        reasons.append("context_" + kind)
    if not semantic and _matching(event.body, _HELP):
        state["support"] = (state["support"] + [
            {"ref": key, "at": now, "expires_at": now + 86400}])[-2:]
        reasons.append("context_help_acknowledged")
    if not reasons and not semantic:
        return result
    if not reasons:
        reasons.append("context_no_stimulus")
    if len(state["seen"]) >= MAX_SEEN:
        if semantic:
            # SQLite retains event idempotency; keep only a bounded recent guard
            # here so ordinary no-op turns cannot freeze later repairs.
            state["seen"] = state["seen"][-(MAX_SEEN - 1):]
        else:
            trace["reason_codes"] = ["context_capacity_limited"]
            return {"state": before, "applied": False, "trace": trace}
    state["items"] = [to_dict(i) for i in items.values() if i.intensity > .001]
    state["seen"].append([key, now])
    state["updated_at"] = now
    state["event_at"] = event.occurred_at
    if len(json.dumps(state, ensure_ascii=True)) > MAX_STATE_CHARS:
        trace["reason_codes"] = ["context_capacity_limited"]
        return {"state": before, "applied": False, "trace": trace}
    trace.update(after=state["items"], reason_codes=reasons)
    return {"state": state, "applied": True, "trace": trace}


def expression_items(raw, context, *, now, relationship=None, relationship_note=""):
    rows = sorted(read_state(raw, context, now=now)["items"],
                  key=lambda r: (-r["intensity"], r["kind"]))
    return [{"kind": r["kind"], "label": LABELS[r["kind"]],
             "intensity": round(r["intensity"], PROMPT_DECIMALS), "cause": r["cause_code"],
             "holder": "bot", "target": "current_interlocutor"}
            for r in rows if r["intensity"] >= THRESHOLD and not (
                r["kind"] == "shyness" and (
                    (relationship is not None and relationship.score < 250)
                    or _BOUNDARY.search(relationship_note)))][:2]


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
                or _BOUNDARY.search(relationship_note)):
            continue
        values[row["kind"]] = row["intensity"]
    return values
