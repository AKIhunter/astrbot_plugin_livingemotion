"""Limit numeric presentation only; persisted state and decisions keep full precision."""

from copy import deepcopy

PROMPT_DECIMALS = 3
AFFECT_FIELDS = (
    "pleasure", "arousal", "stress", "social_need", "control",
    "baseline_pleasure", "baseline_arousal", "baseline_stress", "baseline_social_need",
)
EMOTION_FIELDS = ("joy", "anger", "sadness", "fear", "surprise", "affection")
RELATIONSHIP_FIELDS = ("closeness", "trust", "familiarity", "boundary")


def prompt_numbers(value, fields):
    """Copy and round named numeric fields, preserving timestamps, evidence and types."""
    result = deepcopy(value)
    if isinstance(result, dict):
        for name in fields:
            if type(result.get(name)) is float:
                result[name] = round(result[name], PROMPT_DECIMALS)
    return result


def prompt_mood(value):
    """Experience/dream output copy; never use rounded values to select a dream tone."""
    result = deepcopy(value)
    if isinstance(result, dict):
        for name, fields in (
            ("dimensions", AFFECT_FIELDS),
            ("emotions", EMOTION_FIELDS),
            ("current_emotions", EMOTION_FIELDS),
        ):
            if name in result:
                result[name] = prompt_numbers(result[name], fields)
    return result
