"""Bounded, reversible relationship clues from explicit human statements.

Co-occurrence alone has no meaning. The parser only resolves visible accounts;
its output is an inference with evidence, never an affinity update.
"""

from dataclasses import dataclass
import re

from ..contracts import Context, stable_key


@dataclass(frozen=True)
class RelationshipStatement:
    context: Context
    source_id: str
    kind: str
    at: float
    body: str
    speaker_id: str = ""
    basis: str = "他人陈述"


RELATIONS = {
    "好朋友": "朋友", "好友": "朋友", "朋友": "朋友", "同事": "同事",
    "同学": "同学", "家人": "家人", "亲戚": "亲戚", "室友": "室友",
    "搭档": "搭档", "队友": "队友", "恋人": "恋人", "情侣": "恋人",
    "兄弟": "兄弟姐妹", "姐妹": "兄弟姐妹", "兄妹": "兄弟姐妹",
    "姐弟": "兄弟姐妹", "夫妻": "夫妻",
}
UNCERTAIN = re.compile(r"[?？]|吗|么|是不是|可能|也许|大概|应该|似乎|听说|如果|假如|假设|"
                       r"小说|剧本|角色扮演|梦里|梦见|曾经|以前|过去|开玩笑|未必")
PLATFORM_NAMES = {"qq": ("qq",), "bilibili": ("bilibili", "b站", "uid")}


def _people(nodes, context):
    tokens = {}
    labels = {}
    for node in nodes:
        identifier = node["account_id"]
        names = PLATFORM_NAMES.get(node["platform"], (node["platform"],))
        for name in names:
            tokens[f"{name}:{identifier}".casefold()] = node["id"]
            tokens[f"{name}{identifier}".casefold()] = node["id"]
        if node["platform"] == context.platform:
            tokens[identifier.casefold()] = node["id"]
            tokens[f"@{identifier}".casefold()] = node["id"]
            if context.platform == "qq":
                tokens[f"[cq:at,qq={identifier}]"] = node["id"]
            label = node.get("label", "")
            if isinstance(label, str) and len(label) >= 2 and label != identifier:
                labels.setdefault(label.casefold(), []).append(node["id"])
    tokens.update({label: ids[0] for label, ids in labels.items() if len(ids) == 1 and label not in tokens})
    return tokens


def infer_relationships(nodes, statements, *, limit=200):
    """Newest explicit denial cancels older claims of the same relationship."""
    clues = {}
    relation = "|".join(sorted(RELATIONS, key=len, reverse=True))
    for statement in sorted(statements, key=lambda s: (s.at, s.source_id), reverse=True)[:404]:
        tokens = _people(nodes, statement.context)
        if statement.speaker_id:
            speaker = next((n["id"] for n in nodes if n["platform"] == statement.context.platform
                            and n["account_id"] == statement.speaker_id), None)
            if speaker:
                tokens["我"] = speaker
        if len(tokens) < 2:
            continue
        person = "(" + "|".join(re.escape(t) for t in sorted(tokens, key=len, reverse=True)) + ")"
        # Full clauses prevent an unrelated name elsewhere in a message being linked.
        patterns = (
            re.compile(person + r"\s*(?:和|与|跟|、|及)\s*" + person
                       + r"\s*(?:一直|现在)?\s*(是|不是|不再是|并非|并不是)\s*(?:多年|很好的|很好的老|好)?(" + relation + r")(?:了)?", re.I),
            re.compile(person + r"\s*(是|不是|不再是|并非|并不是)\s*" + person + r"\s*的\s*(" + relation + r")(?:了)?", re.I),
        )
        for clause in re.split(r"[。！!；;\n]", statement.body[:16000])[:80]:
            clause = clause.strip(" \t，,")
            if not clause or UNCERTAIN.search(clause):
                continue
            for number, pattern in enumerate(patterns):
                match = pattern.fullmatch(clause)
                if not match:
                    continue
                if number == 0:
                    left, right, verb, kind = match.groups()
                else:
                    left, verb, right, kind = match.groups()
                source, target = sorted((tokens[left.casefold()], tokens[right.casefold()]))
                if source == target:
                    break
                key = (source, target, RELATIONS[kind])
                negative = verb != "是"
                evidence = {
                    "source_id": statement.source_id, "kind": statement.kind, "at": statement.at,
                    "context_id": statement.context.account_key, "platform": statement.context.platform,
                    "view_scope": statement.context.scene_kind.value, "scene_id": statement.context.scene_id,
                    "basis": ("本人陈述" if statement.speaker_id and "我" in (left, right) else statement.basis),
                    "excerpt": clause[:240],
                }
                clues.setdefault(key, []).append((statement.at, negative, evidence))
                break
    edges = []
    for (source, target, kind), claims in sorted(clues.items()):
        claims.sort(key=lambda c: (c[0], c[1]), reverse=True)  # Same-time denial wins.
        if claims[0][1]:
            continue
        evidence, seen = [], set()
        for _, negative, ref in claims:
            if negative:
                break
            key = (ref["context_id"], ref["kind"], ref["source_id"])
            if key not in seen:
                evidence.append(ref); seen.add(key)
        edges.append({"id": stable_key("peer-clue-v1", source, target, kind),
                      "source": source, "target": target, "relation": kind,
                      "inferred": True, "evidence": evidence[:4]})
    return edges[:limit]
