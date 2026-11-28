"""Select evidence for an appraisal, without scoring it or making model calls."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol

from ..contracts import ContentKind, EvidenceRef, stable_key
from .context_emotion import HELP_EVIDENCE_SECONDS, _HELP_DENIAL, _boundary_directive, _help_evidence, _help_topic

SCAN_ROWS = 48
SEND_ROWS = 8
TEXT_CHARS = 400
NEAR_SECONDS = 600
LOOKBACK_SECONDS = HELP_EVIDENCE_SECONDS
_BACK = re.compile(r"刚才|刚刚|刚说|之前|以前|当时|上次|昨天|那(?:次|件|句|段|条)|你(?:说过|提到)|还记得|这次")
_HELP_TOPIC = re.compile(r"帮(?:忙|过|我|上|了|没)|付出|贡献|做过|做了|帮你")
_HELP_FOCUS = re.compile(r"(?:帮(?:过|了)?我|帮我)(?:在|做|解决|处理)?([^。！？.!?，,、；;\n]{2,64})")
_HELP_VAGUE = {"什么", "这件事", "那件事", "任何事", "做过什么", "任何忙", "做任何事"}
_QUOTE = re.compile(r"“([^”\n]{4,160})”|「([^」\n]{4,160})」|『([^』\n]{4,160})』|\"([^\"\n]{4,160})\"")
_QUOTED_REFERENCE = re.compile(r"你(?:刚才|刚刚|之前|上次)?(?:说|提到)|你那句|你说的|那句")
_STANDALONE = re.compile(r"(?:你好|早上好|晚安|再见|在吗|收到)[！!。？?~～ ]*")
_NON_WORD = re.compile(r"[^\w\u4e00-\u9fff]+|_", re.UNICODE)
_CJK = re.compile(r"[\u4e00-\u9fff]{2,}")
_LATIN = re.compile(r"[a-z0-9]{3,}")
_STOP = {"刚才", "刚刚", "之前", "上次", "这次", "以前", "当时", "谢谢", "感谢", "然后", "可以"}


def _norm(text: str) -> str:
    return _NON_WORD.sub("", text.casefold())


def _keys(text: str) -> set[str]:
    result = set(_LATIN.findall(text.casefold()))
    for span in _CJK.findall(text):
        result.update(span[i:i + 2] for i in range(len(span) - 1))
    return result - _STOP


def _excerpt(text: str, focus: int = 0) -> str:
    if len(text) <= TEXT_CHARS:
        return text
    start = min(max(0, focus - 100), len(text) - TEXT_CHARS)
    # Keep an excerpt verbatim; the payload marks it as an excerpt separately.
    return text[start:start + TEXT_CHARS]


def _overlap_focus(text: str, keys: set[str]) -> int:
    if len(text) <= TEXT_CHARS or not keys:
        return 0
    alternatives = sorted(keys, key=lambda s: (-len(s), s))
    matches = [m.start() for m in re.finditer("|".join(map(re.escape, alternatives)), text, re.I)]
    if not matches:
        return 0
    # Prefer a compact cluster of anchors to unrelated leading content.
    best, count, end = matches[0], 0, 0
    for start, at in enumerate(matches):
        while end < len(matches) and matches[end] - at < 240:
            end += 1
        if end - start > count:
            best, count = at, end - start
    return best


def _help_proof(message, evidence):
    clause, topic = _help_evidence(evidence)
    if not topic:
        return ""
    explicit = _help_topic(message, _HELP_DENIAL)
    if explicit:
        return clause if explicit == topic else ""
    focus = _HELP_FOCUS.search(message)
    if focus:
        subject = focus.group(1).strip()
        wanted = _keys(subject) - {"什么", "事情", "东西", "一次", "这件", "那件", "这个", "那个"}
        if wanted and subject not in _HELP_VAGUE and not wanted.intersection(_keys(clause)):
            return ""
    return clause


def _active_boundary(rows, at):
    active = []
    for row in sorted(rows, key=lambda row: row["at"]):
        if row["role"] != "human" or not 0 <= at - row["at"] <= NEAR_SECONDS:
            continue
        change = _boundary_directive(row["text"])
        if change is None:
            continue
        setting, terms, span = change
        matching = [entry for entry in active if not terms.isdisjoint(entry[0])
                    and (setting or entry[1]["at"] < row["at"])]
        active = [entry for entry in active if entry not in matching]
        if setting:
            active.append((terms.union(*(entry[0] for entry in matching)), row, span))
    return (active[-1][1]["ref"], active[-1][2]) if active else ("", "")


@dataclass(frozen=True)
class Dialogue:
    rows: tuple[Evidence, ...]
    required_ref: str = ""
    unresolved: bool = False


class MemoryCandidate(Protocol):
    @property
    def evidence(self) -> EvidenceRef: ...

    @property
    def text(self) -> str: ...


@dataclass(frozen=True)
class Evidence:
    priority: int
    ref: str
    text: str
    at: float
    role: str = ""
    kind: str = ""
    excerpt: bool = False
    help_proof: bool = False
    boundary: bool = False
    material: MemoryCandidate | None = None

    def history_row(self):
        return {"ref": self.ref, "role": self.role, "at": self.at, "text": self.text,
                **({"excerpt": True} if self.excerpt else {})}

    def memory_row(self):
        return {"ref": self.ref, "kind": self.kind, "text": self.text,
                **({"excerpt": True} if self.excerpt else {})}


def select_dialogue(body, rows, *, at, reply_id="", native_reply=False, reply_text="",
                    semantic_refs=(), include_near=False):
    """Rows are already verified against the current conversation and identity."""
    query = _keys(body[:4096])
    looking_back, help_topic = bool(_BACK.search(body)), bool(_HELP_TOPIC.search(body))
    quotes = tuple(next(v for v in m.groups() if v) for m in _QUOTE.finditer(body[:4096]))
    requires_anchor = bool(native_reply or reply_id or (quotes and _QUOTED_REFERENCE.search(body)))
    anchor = None
    if reply_id:
        anchor = next((row for row in rows if row["role"] == "bot"
                       and row["event_id"] == reply_id), None)
    # An adapter's delivery ID can differ from the archive's submission ID.
    # Use the native quoted text only when it matches one scoped Bot reply exactly.
    if anchor is None and requires_anchor:
        if reply_text:
            found = [row for row in rows if row["role"] == "bot"
                     and row["text"].strip() == reply_text]
        else:
            found = [row for row in rows if row["role"] == "bot"
                     and any(quote in row["text"] for quote in quotes)]
        if len(found) == 1:
            anchor = found[0]

    picked = []
    near = [row["ref"] for row in rows if 0 <= at - row["at"] <= NEAR_SECONDS][-2:]
    latest_boundary, boundary_span = _active_boundary(rows, at)
    for i, row in enumerate(rows):
        text = row["text"]
        age = at - row["at"]
        if age < 0:
            continue
        shared = query & _keys(text)
        proof_text = (_help_proof(body, text)
                      if help_topic and row["role"] == "human" and 0 < age < LOOKBACK_SECONDS else "")
        boundary = row["ref"] == latest_boundary
        if row is anchor:
            rank = 100
        elif boundary:
            rank = 95
        elif proof_text:
            rank = 90
        elif row["ref"] in semantic_refs and 0 < age < LOOKBACK_SECONDS:
            rank = 89  # Active incident; a candidate reference, not evidence of repair.
        elif anchor is not None and i > 0 and rows[i - 1] is anchor and age <= LOOKBACK_SECONDS:
            rank = 86  # The next turn may repair or reverse the cited line.
        elif anchor is not None and i + 1 < len(rows) and rows[i + 1] is anchor:
            rank = 83
        elif (looking_back or age <= NEAR_SECONDS) and age <= LOOKBACK_SECONDS and len(shared) >= 2:
            rank = 70 + min(len(shared), 9)
        elif row["ref"] in near and (include_near or not _STANDALONE.fullmatch(body.strip())):
            rank = 50
        else:
            continue
        focus = (next((text.index(q) for q in quotes if q in text), 0) if row is anchor
                 else _overlap_focus(text, shared))
        if proof_text and proof_text in text and not (row is anchor or boundary):
            focus = text.index(proof_text)
        if boundary:
            if row is not anchor:
                focus = text.index(boundary_span)
        snippet = _excerpt(text, focus)
        picked.append(Evidence(rank, row["ref"], snippet, row["at"], role=row["role"],
                               excerpt=snippet != text,
                               help_proof=bool(proof_text and proof_text in snippet),
                               boundary=boundary))
    picked.sort(key=lambda item: (-item.priority, -item.at, item.ref))
    # Repeated acknowledgements do not crowd out other context.
    unique = {}
    for item in picked:
        unique.setdefault((item.role, _norm(item.text)), item)
    return Dialogue(tuple(unique.values())[:SEND_ROWS],
                    anchor["ref"] if anchor else "", requires_anchor and anchor is None)


def recall_relevant(body, dialogue):
    # A specific preceding quote/acknowledgement is already enough to explain
    # this turn unless the speaker also refers to another prior interaction.
    return bool((_BACK.search(body) or _HELP_TOPIC.search(body)) and (
        not dialogue.required_ref or _HELP_TOPIC.search(body)))


def select_memories(body, candidates, context, *, at, dialogue):
    """Default to one relevant memory. Add a second only for new explicit facts."""
    current = _keys(body[:4096])
    history = [item.text for item in dialogue.rows]
    ranked = []
    for material in candidates[:2]:
        ref, text = material.evidence, material.text
        if ref.occurred_at > at or ref.kind not in (ContentKind.INTERACTION, ContentKind.SUMMARY):
            continue
        # External provenance has already been checked by the gateway. Compare
        # legacy raw IDs and the platform-qualified IDs it uses for native LM.
        subjects = {context.account_id, f"{context.platform}:{context.account_id}"}
        holders = {context.bot_id, f"{context.platform}:{context.bot_id}"}
        proof = (_help_proof(body, text) if _HELP_TOPIC.search(body)
                 and ref.kind == ContentKind.INTERACTION and ref.context.account_key == context.account_key
                 and ref.subject_id in subjects and ref.holder_id in holders
                 and 0 < at - ref.occurred_at < LOOKBACK_SECONDS
                 and (ref.expires_at is None or ref.expires_at > at) else "")
        shared = current & _keys(text)
        if not proof and len(shared) < 2:
            continue
        focus = _overlap_focus(text, shared)
        if proof:
            if proof in text:
                focus = text.index(proof)
        snippet = _excerpt(text, focus)
        norm = _norm(snippet)
        overlap = current & _keys(snippet)
        if not norm or any(norm in _norm(t) for t in history):
            continue
        proven = bool(proof and proof in snippet)
        if not proven and len(overlap) < 2:
            continue
        key = stable_key("emotion-memory", ref.provider, ref.source_id)
        item = Evidence(88 if proven else 74, key, snippet, ref.occurred_at,
                        kind=ref.kind.value, excerpt=snippet != text, help_proof=proven,
                        material=material)
        ranked.append((item, overlap, norm))
    # Python's stable sort retains the retrieval order on an exact tie.
    ranked.sort(key=lambda row: (-row[0].priority, -len(row[1]), -row[0].at))
    if not ranked:
        return ()
    first, covered, first_text = ranked[0]
    result = [first]
    for item, overlap, norm in ranked[1:]:
        if (item.ref != first.ref and norm not in first_text and first_text not in norm
                and len(overlap - covered) >= 2):
            result.append(item)
    return tuple(result)


def pack_evidence(system, base, dialogue, memories, *, count, budget, contextual, persona_rules):
    """Pack actual provider messages. The current sentence and safety gates are immutable."""
    packet = dict(base, persona=[], memories=[])
    if contextual:
        packet.update(recent_dialogue=[], context_support_refs=[])

    if dialogue.unresolved or count(system, packet) > budget:
        return None, ()
    included, selected = [], []
    boundary_rows = [item for item in dialogue.rows if item.boundary]
    mandatory = {row.ref for row in boundary_rows}
    if dialogue.required_ref:
        mandatory.add(dialogue.required_ref)
    if contextual:
        # A reference and an applicable explicit boundary must fit together.
        packet["recent_dialogue"] = [
            row.history_row() for row in sorted(dialogue.rows, key=lambda item: item.at)
            if row.ref in mandatory]
        if count(system, packet) > budget:
            return None, ()
        selected.extend(row for row in dialogue.rows if row.ref in mandatory)
        packet["context_support_refs"] = [row.ref for row in selected if row.help_proof]
        if count(system, packet) > budget:
            return None, ()

    def add(item):
        if item.material is not None:
            # Never replace the first ranked memory with a weaker second
            # memory that only made sense as a supplement.
            if item is not memories[0] and not included:
                return
            target, value = "memories", item.memory_row()
        else:
            target, value = "recent_dialogue", item.history_row()
        packet[target].append(value)
        if contextual and item.help_proof:
            packet["context_support_refs"].append(item.ref)
        if count(system, packet) > budget:
            packet[target].pop()
            if contextual and item.help_proof:
                packet["context_support_refs"].pop()
            return
        (included if item.material is not None else selected).append(item)

    optional = sorted((*dialogue.rows, *memories) if contextual else memories,
                      key=lambda item: (-item.priority, -item.at, item.ref))
    # Factual evidence first; personality is relevant only after the stimulus is clear.
    for item in optional:
        if item.ref not in mandatory and item.priority >= 80:
            add(item)
    for rule in persona_rules:
        packet["persona"].append(rule)
        if count(system, packet) > budget:
            packet["persona"].pop()
    for item in optional:
        if item.ref not in mandatory and item.priority < 80:
            add(item)
    if contextual:
        # Deterministic chronological presentation, including rows with the same time.
        packet["recent_dialogue"] = [row.history_row() for row in
                                     sorted(selected, key=lambda row: (row.at, dialogue.rows.index(row)))]
    return packet, tuple(item.material for item in included)
