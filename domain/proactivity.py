"""Pure, bounded choices for idle conversation; never grants permission to send."""

from dataclasses import dataclass

from ..contracts import BotAffect, Relationship, SceneKind


@dataclass(frozen=True)
class ConversationMotive:
    key: str
    label: str
    guidance: str
    weight: float


MOTIVES = {
    "memory_followup": ("记忆回访", "从材料中挑一件对方在意的事，自然问问后续；不要把旧状态当成现在，日期不明时不要说今天或昨天。"),
    "care_checkin": ("关心近况", "温和问候近况；只有材料明确支持时才提旧烦恼，不诊断、不说教、不追问隐私。"),
    "light_chat": ("轻松闲聊", "从共同话题或兴趣引出一个轻松的小问题，也可以分享一个想法；不虚构现实经历。"),
    "emotional_share": ("分享心情", "以人格口吻轻描淡写地分享当前心情，再留一点聊天空间；不索取安慰、不抱怨没人理、不制造负担。"),
    "reconnect": ("久别问候", "像重新想起一个熟悉的人，轻松打招呼；不责怪失联、不强调对方欠回复。"),
}


def initiative_probability(score, unanswered, style):
    """Unanswered messages reduce frequency before the hard unanswered ceiling."""
    multiplier = {"gentle": .6, "balanced": 1.0, "lively": 1.25}[style]
    return min(.9, (.25 + .65 * score) * multiplier / (1 + unanswered))


def motives(affect: BotAffect, relationship: Relationship, scene: SceneKind, *,
            emotional_share=True, absent_seconds=0):
    weights = {
        "memory_followup": 1.2 + relationship.normalized,
        "care_checkin": .6 + .8 * relationship.normalized,
        "light_chat": 1.2 + max(0, affect.pleasure),
    }
    # Sharing feelings needs an established private relationship. Shared affect
    # numbers never authorize a private explanation in a group.
    if (emotional_share and scene == SceneKind.PRIVATE and relationship.score >= 600
            and relationship.evidence_complete
            and (relationship.trust is None or relationship.trust >= .55)
            and (relationship.boundary is None or relationship.boundary < .5)):
        weights["emotional_share"] = .5 + affect.social_need + affect.stress
    if absent_seconds >= 3 * 86400 and relationship.score >= 200:
        weights["reconnect"] = 1.5
    return tuple(ConversationMotive(key, *MOTIVES[key], weight)
                 for key, weight in weights.items())


def choose_motive(choices, draw, *, previous=""):
    """Avoid consecutive identical motives when another viable choice exists."""
    available = tuple(choice for choice in choices if choice.key != previous) or choices
    total = sum(choice.weight for choice in available)
    point = max(0, min(float(draw), 1)) * total
    for choice in available:
        point -= choice.weight
        if point < 0:
            return choice
    return available[-1]


def motive_for(purpose):
    key = purpose.removeprefix("proactive:")
    label, guidance = MOTIVES.get(key, MOTIVES["light_chat"])
    return key, label, guidance
