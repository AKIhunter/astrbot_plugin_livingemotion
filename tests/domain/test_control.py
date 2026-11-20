"""Control changes expression and derived mood, never stimuli or permissions."""
from dataclasses import replace
from itertools import product
from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.contracts import BotAffect
from astrbot_plugin_livingemotion.domain.dreaming import dream_profile, six_emotions
from astrbot_plugin_livingemotion.domain.emotion import (
    apply_control, apply_emotion, control_expression, decay_affect, expression_context,
)
from astrbot_plugin_livingemotion.services.behavior import BehaviorSnapshot, behavior_score
from astrbot_plugin_livingemotion.domain.proactivity import motives


def old_emotions(state):
    p, a, s, n = state.pleasure, state.arousal, state.stress, state.social_need
    positive, negative = max(0, p), max(0, -p)
    baseline = state.baseline_arousal if state.baseline_refined else .3
    return {
        "joy": positive * (1 - .35 * s),
        "anger": negative * a * (.35 + .65 * s),
        "sadness": negative * (1 - .55 * a) * (1 - .35 * s),
        "fear": s * (.35 + .65 * a),
        "surprise": max(0, a - baseline) * (.25 + .35 * (1 - abs(p))),
        "affection": (.35 * n + .65 * positive) * (1 - .4 * s),
    }


def test_control_matrix_preserves_neutral_zero_bounds_and_direction():
    # 180 four-axis states × 2 baselines × 5 controls = 1,800 deterministic projections.
    for p, a, s, n in product((-1, -.6, 0, .6, 1), (0, .3, .7, 1),
                              (0, .6, 1), (0, .3, 1)):
        for refined in (False, True):
            state = BotAffect(pleasure=p, arousal=a, stress=s, social_need=n,
                              baseline_refined=refined, baseline_arousal=.2)
            original = old_emotions(state)
            assert six_emotions(state) == original
            rows = [six_emotions(replace(state, control=c)) for c in (0, .2, .5, .8, 1)]
            assert all(0 <= v <= 1 for row in rows for v in row.values())
            for key in ("joy", "surprise", "affection"):
                assert all(row[key] == original[key] for row in rows)
            for key in ("anger", "sadness", "fear"):
                if original[key] == 0:
                    assert all(row[key] == 0 for row in rows)
            assert [row["anger"] for row in rows] == sorted(row["anger"] for row in rows)
            for key in ("sadness", "fear"):
                assert [row[key] for row in rows] == sorted(
                    (row[key] for row in rows), reverse=True)
            assert state.control == .5  # Projection never accumulates into the input.


@pytest.mark.parametrize("control,expected", [
    (.2, (.254856, .3264912, .59892)),
    (.5, (.3108, .29151, .483)),
    (.8, (.366744, .2565288, .36708)),
])
def test_conflict_example_matches_approved_formula(control, expected):
    state = BotAffect(pleasure=-.6, arousal=.7, stress=.6, social_need=.3, control=control)
    values = six_emotions(state)
    assert tuple(values[k] for k in ("anger", "sadness", "fear")) == pytest.approx(expected)


def test_legacy_four_axis_value_defaults_to_neutral():
    state = BotAffect(pleasure=-.6, arousal=.7, stress=.6)
    legacy = SimpleNamespace(**{k: getattr(state, k) for k in
                                 ("pleasure", "arousal", "stress", "social_need")})
    assert six_emotions(legacy) == old_emotions(state)


def test_new_dream_candidates_follow_control_without_mutating_old_profile():
    state = BotAffect(arousal=.3, stress=.44, social_need=0, control=.2)
    low = dream_profile(six_emotions(state))
    assert low["dominant"] == low["night_event"] == "fear"
    high = dream_profile(six_emotions(replace(state, control=.8)))
    assert high["dominant"] == "calm" and high["night_event"] == ""
    assert low["night_event"] == "fear"  # A persisted old dream is not recalculated.


@pytest.mark.parametrize("value", [True, -.1, 1.1, float("nan"), float("inf"), "0.5"])
def test_control_projection_rejects_invalid_values(value):
    state = SimpleNamespace(pleasure=0, arousal=.3, stress=0, social_need=.3, control=value)
    with pytest.raises(ValueError):
        six_emotions(state)


@pytest.mark.parametrize("control,style", [
    (.2, "谨慎解释，必要时澄清一个关键点。"),
    (.35, "按当前情绪和人格自然表达。"),
    (.5, "按当前情绪和人格自然表达。"),
    (.65, "按当前情绪和人格自然表达。"),
    (.8, "更直接、坚定地表达意愿和边界。"),
])
def test_expression_boundaries_use_current_control(control, style):
    state = BotAffect(control=control, control_at=100, updated_at=100)
    assert control_expression(state) == {"control": control, "control_style": style}
    assert expression_context(state, None, now=100)["bot"]["control_style"] == style
    assert expression_context(state, None, now=100, mode="observe_only") == {}
    assert expression_context(state, None, now=100, enabled=False) == {}


def test_expression_uses_decayed_control_without_writing_or_changing_four_axes():
    state = BotAffect(control=.8, control_at=100, updated_at=100)
    result = expression_context(state, None, now=7300)
    assert result["bot"]["control"] == pytest.approx(.575)
    assert result["bot"]["control_style"] == "按当前情绪和人格自然表达。"
    assert state.control == .8 and state.updated_at == state.control_at == 100


@pytest.mark.parametrize("confidence,expected", [(.74, .5), (.75, .6), (1, .6)])
def test_model_control_confidence_gate_and_independent_clock(confidence, expected):
    state = BotAffect(updated_at=100)
    result = apply_control(state, 1, now=200, confidence=confidence)
    assert result.control == pytest.approx(expected)
    assert result.updated_at == state.updated_at
    assert apply_control(result, None, now=1000) == result
    assert decay_affect(result, now=200 + 3600).control == pytest.approx(
        .5 + (result.control - .5) / 2)


def test_control_does_not_change_rule_budget_or_proactive_decisions(le_event):
    first = apply_emotion(BotAffect(), replace(le_event, signals=("praise",)), now=le_event.occurred_at)
    second = apply_emotion(BotAffect(control=1, control_at=le_event.occurred_at),
                           replace(le_event, signals=("praise",)), now=le_event.occurred_at)
    for key in ("pleasure", "arousal", "stress", "social_need"):
        assert getattr(first["affect"], key) == getattr(second["affect"], key)
    assert first["trace"]["joy"] == second["trace"]["joy"]
    assert six_emotions(first["affect"])["joy"] == six_emotions(second["affect"])["joy"] <= .05
    one = BehaviorSnapshot(le_event.context, affect=first["affect"])
    two = replace(one, affect=replace(one.affect, control=1))
    assert behavior_score(one) == behavior_score(two)
    assert motives(one.affect, one.relationship, le_event.context.scene_kind) == motives(
        two.affect, two.relationship, le_event.context.scene_kind)
