"""Synthetic T3 fixtures. Run with unittest; no host or paid model required."""

from copy import deepcopy
from dataclasses import replace
import json
import math
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from astrbot_plugin_livingemotion.contracts import (
    ActorRole, BotAffect, Context, Event, HumanObservation, NightState,
    Relationship, canonical_json,
)
from astrbot_plugin_livingemotion.domain.emotion import (
    BASELINE, DIMENSIONS, RULE_VERSION, EmotionPolicy, apply_control, apply_emotion,
    control_value, decay_affect, emotion_policy, event_signals, expression_context,
    observe_human, resolve_mode, shift_baseline,
)


def context(**changes):
    return replace(Context("bot", "persona", "adapter", "platform", "private",
                           "room", account_id="human"), **changes)


def event(at=1000.0, source="m1", signals=(), **changes):
    return replace(Event(source, "synthetic", "message", context(), ActorRole.HUMAN,
                         at, source, actor_id="human", signals=signals), **changes)


def values(state):
    return tuple(getattr(state, name) for name in DIMENSIONS)


class SemanticTests(unittest.TestCase):
    def test_sadness_is_observed_not_copied_to_bot(self):
        message = event(body="\u6211\u5f88\u96be\u8fc7")
        result = apply_emotion(BotAffect(), message, now=1000)
        self.assertEqual(result["observation"].labels, ("sad",))
        self.assertEqual(result["observation"].subject_id, "human")
        self.assertEqual(result["affect"].pleasure, 0)
        self.assertIn("concerned", result["affect"].labels)
        self.assertNotIn("sad", result["affect"].labels)
        self.assertEqual(result["trace"]["holder_id"], "bot")
        self.assertEqual(result["trace"]["subject_id"], "human")
        source = result["affect"].evidence[0]
        self.assertEqual((source.holder_id, source.subject_id), ("human", "human"))

    def test_frozen_rule_sample_version_one(self):
        result = apply_emotion(BotAffect(), event(signals=("care",)), now=1000)
        self.assertEqual(values(result["affect"]), (0.12, 0.27999999999999997, 0.0, 0.24))
        self.assertEqual(result["affect"].rule_version, RULE_VERSION)
        self.assertEqual(result["trace"]["rule_version"], RULE_VERSION)

    def test_quotes_third_person_negation_and_dream_not_self_report(self):
        for body in (
            '"I am sad"', "my friend says I am sad", "I am not sad",
            "Yesterday I was sad", "\u4ed6\u8bf4\u6211\u5f88\u96be\u8fc7",
            "\u6211\u4e0d\u96be\u8fc7", "\u68a6\u91cc\u6211\u5f88\u96be\u8fc7",
        ):
            with self.subTest(body=body):
                self.assertEqual(event_signals(event(body=body)), ("interaction",))
                self.assertIsNone(observe_human(event(body=body), now=1000))

    def test_no_generated_narrative_or_unknown_actor_as_real_interaction(self):
        for kind in ("dream", "diary", "summary", "fact", "legacy_unknown", "observation"):
            with self.subTest(kind=kind):
                result = apply_emotion(BotAffect(), event(event_type=kind, signals=("care",)),
                                       now=1000)
                self.assertFalse(result["applied"])
                self.assertEqual(result["reason_codes"], ("unsupported_event",))
        self.assertFalse(apply_emotion(BotAffect(), event(actor_role="unknown"),
                                       now=1000)["applied"])

    def test_no_actor_impersonation(self):
        for message in (
            event(actor_id="other"),
            event(context=context(account_id="")),
            event(actor_role="bot", actor_id="human", event_type="bot_action_succeeded"),
        ):
            self.assertEqual(apply_emotion(BotAffect(), message, now=1000)["reason_codes"],
                             ("actor_mismatch",))

    def test_bot_action_requires_success_receipt(self):
        for kind in ("message", "bot_action_failed", "bot_action_unknown"):
            message = event(actor_id="bot", actor_role="bot", event_type=kind,
                            signals=("sadness",), body="I am sad")
            self.assertFalse(apply_emotion(BotAffect(), message, now=1000)["applied"])
        success = event(actor_id="bot", actor_role="bot", event_type="bot_action_succeeded")
        result = apply_emotion(BotAffect(), success, now=1000)
        self.assertTrue(result["applied"])
        self.assertIsNone(result["observation"])

    def test_conflict_then_care_then_recovery(self):
        first = apply_emotion(BotAffect(), event(signals=("conflict",)), now=1000)
        self.assertGreater(first["affect"].stress, 0)
        self.assertLess(first["affect"].pleasure, 0)
        second = apply_emotion(first["affect"], event(1001, "m2", ("care",)), now=1001,
                               runtime=first["runtime"])
        self.assertLess(second["affect"].stress, first["affect"].stress)
        self.assertGreater(second["affect"].pleasure, first["affect"].pleasure)
        restored = decay_affect(second["affect"], now=1000000)
        for actual, baseline in zip(values(restored), BASELINE):
            self.assertAlmostEqual(actual, baseline)
        self.assertEqual(restored.labels, ("calm",))
        self.assertEqual(restored.evidence, ())

    def test_relationship_personality_and_readonly_energy_modulate_appraisal(self):
        message = event(signals=("conflict",))
        normal = apply_emotion(BotAffect(), message, now=1000)["affect"]
        low_energy = NightState(energy=0)
        tired = apply_emotion(BotAffect(), message, now=1000, night=low_energy)["affect"]
        self.assertLess(tired.arousal, normal.arousal)
        self.assertEqual(low_energy.energy, 0)
        stranger = apply_emotion(BotAffect(), message, now=1000,
                                 relationship=Relationship(score=0))["affect"]
        close = apply_emotion(BotAffect(), message, now=1000,
                              relationship=Relationship(score=1000))["affect"]
        self.assertLess(stranger.stress, close.stress)
        muted = apply_emotion(BotAffect(), message, now=1000,
                              policy=EmotionPolicy(sensitivity=0))["affect"]
        self.assertEqual(values(muted), BASELINE)

    def test_expression_keeps_holders_separate_and_expires_observation(self):
        result = apply_emotion(BotAffect(), event(signals=("sadness",)), now=1000)
        hints = expression_context(result["affect"], result["observation"], now=1000)
        self.assertEqual(hints["bot"]["holder"], "bot")
        self.assertEqual(hints["human_observation"]["holder"], "human")
        self.assertEqual(hints["bot"]["pleasure"], 0)
        expired = expression_context(result["affect"], result["observation"], now=8200)
        self.assertIsNone(expired["human_observation"])
        self.assertNotIn("concerned", expired["bot"]["labels"])


class TimeAndGuardTests(unittest.TestCase):
    def test_decay_uses_elapsed_time_not_number_of_ticks(self):
        original = BotAffect(pleasure=0.8, arousal=0.9, stress=0.8, social_need=0.9,
                             updated_at=1000)
        direct = decay_affect(original, now=10000)
        ticks = original
        for now in range(1100, 10001, 100):
            ticks = decay_affect(ticks, now=now)
        for first, second in zip(values(direct), values(ticks)):
            self.assertAlmostEqual(first, second)

    def test_clock_rollback_never_reverse_decays(self):
        original = BotAffect(pleasure=0.7, updated_at=1000)
        self.assertIs(decay_affect(original, now=999), original)
        self.assertEqual(apply_emotion(original, event(999), now=999)["reason_codes"],
                         ("clock_before_state",))

    def test_ttl_is_event_time_and_never_refreshes_on_receive(self):
        original = event(1000, signals=("sadness",))
        observation = observe_human(original, now=1500)
        self.assertEqual(observation.expires_at, 8200)
        same = observe_human(original, now=2000, previous=observation)
        self.assertEqual(same.expires_at, 8200)
        self.assertIsNone(observe_human(original, now=8200, previous=observation))
        result = apply_emotion(BotAffect(), original, now=8200)
        self.assertEqual(result["reason_codes"], ("expired_event",))
        self.assertFalse(result["applied"])

    def test_late_event_arrives_already_decayed(self):
        message = event(signals=("care",))
        fresh = apply_emotion(BotAffect(), message, now=1000)["affect"]
        late = apply_emotion(BotAffect(), message, now=2800)["affect"]
        self.assertAlmostEqual(late.pleasure, fresh.pleasure / 2)
        self.assertEqual(late.evidence[0].expires_at, 8200)

    def test_newer_observation_and_affect_cannot_be_overwritten(self):
        first = apply_emotion(BotAffect(), event(2000, "new", ("joy",)), now=2000)
        later = apply_emotion(first["affect"], event(1000, "old", ("sadness",)), now=2000,
                              observation=first["observation"], runtime=first["runtime"])
        self.assertEqual(later["reason_codes"], ("older_event",))
        self.assertEqual(later["affect"], first["affect"])
        self.assertEqual(later["observation"], first["observation"])

    def test_read_decay_does_not_advance_event_watermark(self):
        first = apply_emotion(BotAffect(), event(1000), now=1000)
        read = decay_affect(first["affect"], now=1500)
        later = apply_emotion(read, event(1400, "later", ("care",)), now=1500,
                              runtime=first["runtime"])
        self.assertTrue(later["applied"])

    def test_future_and_unreliable_events_are_rejected(self):
        self.assertEqual(apply_emotion(BotAffect(), event(1001), now=1000)["reason_codes"],
                         ("future_event",))
        self.assertEqual(apply_emotion(BotAffect(), event(reliable_source=False),
                                      now=1000)["reason_codes"], ("unreliable_source",))

    def test_same_source_with_different_event_id_is_duplicate(self):
        message = event(signals=("care",))
        first = apply_emotion(BotAffect(), message, now=1000)
        replay = replace(message, event_id="attacker_new_correlation")
        second = apply_emotion(first["affect"], replay, now=1000, runtime=first["runtime"])
        self.assertEqual(second["reason_codes"], ("duplicate_event",))
        self.assertEqual(second["affect"], first["affect"])

    def test_fifty_new_ids_do_not_bypass_similar_stimulus_budget(self):
        state, runtime, applied = BotAffect(), None, 0
        for number in range(50):
            result = apply_emotion(state, event(1000, str(number), ("care",)), now=1000,
                                   runtime=runtime)
            state, runtime = result["affect"], result["runtime"]
            applied += result["applied"]
        self.assertEqual(applied, 3)
        self.assertAlmostEqual(state.pleasure, 0.3)
        self.assertEqual(result["reason_codes"], ("similar_stimulus_limited",))

    def test_cosmetic_variants_use_same_stimulus_family(self):
        state, runtime = BotAffect(), None
        for number in range(30):
            result = apply_emotion(state, event(1000, str(number),
                                               body="I am sad" + "." * number),
                                   now=1000, runtime=runtime)
            state, runtime = result["affect"], result["runtime"]
        self.assertAlmostEqual(state.stress, 0.06)
        self.assertEqual(result["reason_codes"], ("similar_stimulus_limited",))

    def test_same_body_reclassified_by_model_cannot_reset_stimulus_budget(self):
        state, runtime, applied = BotAffect(), None, 0
        for number, signal in enumerate(
            ("care", "gratitude", "joy", "conflict", "promise_kept", "apology")
        ):
            result = apply_emotion(state, event(1000, str(number), (signal,),
                                               body="the same message"),
                                   now=1000, runtime=runtime)
            state, runtime = result["affect"], result["runtime"]
            applied += result["applied"]
        self.assertEqual(applied, 3)
        self.assertEqual(result["reason_codes"], ("similar_stimulus_limited",))

    def test_guard_is_bounded_and_does_not_evict_live_idempotency_keys(self):
        policy = EmotionPolicy(max_events=3)
        state, runtime = BotAffect(), None
        for number in range(20):
            result = apply_emotion(state, event(1000, str(number)), now=1000,
                                   runtime=runtime, policy=policy)
            state, runtime = result["affect"], result["runtime"]
        self.assertEqual(len(runtime["seen"]), 3)
        self.assertEqual(result["reason_codes"], ("guard_capacity",))

    def test_runtime_roundtrip_is_pure_and_replay_safe(self):
        first = apply_emotion(BotAffect(), event(), now=1000)
        runtime = json.loads(canonical_json(first["runtime"]))
        original = deepcopy(runtime)
        result = apply_emotion(first["affect"], event(), now=1000, runtime=runtime)
        self.assertEqual(runtime, original)
        self.assertEqual(result["reason_codes"], ("duplicate_event",))

    def test_runtime_cannot_be_moved_between_scenes_or_accounts_for_observations(self):
        first = apply_emotion(BotAffect(), event(), now=1000)
        with self.assertRaisesRegex(ValueError, "runtime_scope"):
            apply_emotion(BotAffect(), event(context=context(scene_id="other")),
                          now=1000, runtime=first["runtime"])
        with self.assertRaisesRegex(ValueError, "observation_subject"):
            apply_emotion(BotAffect(), event(), now=1000,
                          observation=HumanObservation("other", ("sad",), 1, 900, 8000))

    def test_busy_scene_cannot_consume_quiet_scene_watermark(self):
        busy = apply_emotion(BotAffect(), event(5000, context=context(scene_id="busy")),
                             now=5000)
        quiet = apply_emotion(BotAffect(), event(4000, context=context(scene_id="quiet")),
                              now=5000)
        self.assertTrue(busy["applied"])
        self.assertTrue(quiet["applied"])
        self.assertNotEqual(busy["runtime"]["scope_key"], quiet["runtime"]["scope_key"])

    def test_default_runtime_fits_foundation_state_payload_limit(self):
        state, runtime = BotAffect(), None
        for number in range(300):
            account = "human" + str(number)
            message = event(1000, str(number), body="a synthetic message",
                            context=context(account_id=account), actor_id=account)
            result = apply_emotion(state, message, now=1000, runtime=runtime)
            state, runtime = result["affect"], result["runtime"]
        envelope = {"snapshot": state, "runtime": runtime}
        self.assertLessEqual(len(canonical_json(envelope)), 65536)

    def test_affect_and_observation_evidence_cannot_cross_scenes(self):
        private = apply_emotion(BotAffect(), event(signals=("sadness",)), now=1000)
        message = event(1001, "group", ("joy",), context=context(scene_kind="group"))
        with self.assertRaisesRegex(ValueError, "affect_scope"):
            apply_emotion(private["affect"], message, now=1001)
        with self.assertRaisesRegex(ValueError, "observation_scope"):
            apply_emotion(BotAffect(), message, now=1001,
                          observation=private["observation"])
        with self.assertRaisesRegex(ValueError, "observation_scope"):
            observe_human(message, now=1001, previous=private["observation"])


class ValidationAndModeTests(unittest.TestCase):
    def test_invalid_numbers_rejected(self):
        invalid = (float("nan"), float("inf"), -float("inf"), True, "0", None)
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    apply_emotion(BotAffect(), event(), now=value)
                with self.assertRaises(ValueError):
                    BotAffect(pleasure=value)
                with self.assertRaises(ValueError):
                    event(confidence=value)
        for value in (-1, 2):
            with self.assertRaises(ValueError):
                BotAffect(stress=value)
        with self.assertRaises(ValueError):
            apply_emotion(BotAffect(), event(), now=10 ** 1000)

    def test_invalid_policy_and_runtime_numbers_rejected(self):
        for change in ({"event_cap": 0.31}, {"similar_limit": True}, {"event_ttl": 0},
                       {"sensitivity": 2}, {"rule_gain": 4}, {"half_lives": (1, 2)},
                       {"half_lives": (1, 2, float("nan"), 4)}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                EmotionPolicy(**change)
        first = apply_emotion(BotAffect(), event(), now=1000)
        first["runtime"]["stimuli"][0]["amount"] = float("nan")
        with self.assertRaises(ValueError):
            apply_emotion(first["affect"], event(1001, "m2"), now=1001,
                          runtime=first["runtime"])

    def test_invalid_models_all_fall_back_to_rules(self):
        message = event(signals=("care",))
        expected = values(apply_emotion(BotAffect(), message, now=1000)["affect"])
        invalid = [
            "", "not JSON", "[]", '{"error": "upstream failed"}', None,
            {"rule_version": RULE_VERSION, "delta": {"pleasure": float("nan")}},
            {"rule_version": RULE_VERSION, "delta": {"pleasure": float("inf")}},
            {"rule_version": RULE_VERSION, "delta": {"pleasure": True}},
            {"rule_version": RULE_VERSION, "delta": {"pleasure": "0.1"}},
            {"rule_version": RULE_VERSION, "delta": {"pleasure": 0.151}},
            {"rule_version": RULE_VERSION, "delta": {"pleasure": 10 ** 1000}},
            {"rule_version": "other", "delta": {"pleasure": 0.1}},
            {"rule_version": RULE_VERSION, "delta": {"score": 1}},
            {"rule_version": RULE_VERSION, "delta": {}, "send": True},
            '{"rule_version":"emotion-1","delta":{"pleasure":0.1,"pleasure":0.2}}',
        ]
        for model in invalid:
            with self.subTest(model=str(model)[:120]):
                result = apply_emotion(BotAffect(), message, now=1000,
                                       model_suggestion=model)
                self.assertEqual(values(result["affect"]), expected)
                if model is not None:
                    self.assertIn("model_invalid_rule_fallback", result["reason_codes"])

    def test_valid_model_refines_but_never_overwrites_final_state(self):
        model = {"rule_version": RULE_VERSION, "delta": {"pleasure": 0.15}}
        result = apply_emotion(BotAffect(), event(signals=("care",)), now=1000,
                               model_suggestion="```json\n" + json.dumps(model) + "\n```")
        self.assertEqual(result["affect"].pleasure, 0.15)
        self.assertIn("model_refined", result["reason_codes"])

    def test_model_cannot_copy_human_sadness_into_bot_pleasure(self):
        result = apply_emotion(
            BotAffect(), event(signals=("sadness",)), now=1000,
            model_suggestion={"rule_version": RULE_VERSION, "delta": {"pleasure": -0.15}},
        )
        self.assertEqual(result["affect"].pleasure, 0)
        self.assertIn("model_invalid_rule_fallback", result["reason_codes"])

    def test_zero_confidence_has_no_state_or_observation_evidence(self):
        result = apply_emotion(BotAffect(), event(signals=("sadness",), confidence=0),
                               now=1000)
        self.assertEqual(values(result["affect"]), BASELINE)
        self.assertFalse(result["applied"])
        self.assertIsNone(result["observation"])
        self.assertEqual(result["affect"].evidence, ())

    def test_observe_only_records_but_does_not_inject_or_allow_autonomy(self):
        for mode, conflict in (("observe_only", False), ("active", True)):
            result = apply_emotion(BotAffect(), event(), now=1000, mode=mode,
                                   conflict=conflict)
            self.assertTrue(result["applied"])
            self.assertFalse(result["control"]["may_inject"])
            self.assertFalse(result["control"]["may_autonomous"])
            self.assertEqual(expression_context(result["affect"], None, now=1000,
                                                mode=mode, conflict=conflict), {})

    def test_disabled_is_no_work_and_invalid_modes_fail_closed(self):
        original = BotAffect(pleasure=0.8)
        result = apply_emotion(original, event(), now=1000, enabled=False)
        self.assertIs(result["affect"], original)
        self.assertFalse(result["applied"])
        self.assertEqual(result["runtime"], {})
        for kwargs in ({"mode": "off"}, {"enabled": 1}, {"conflict": "false"}):
            with self.assertRaises(ValueError):
                resolve_mode(**kwargs)

    def test_seeded_clock_replay_and_signal_sequences_stay_finite(self):
        rng = random.Random(20261105)
        state, runtime, now = BotAffect(), None, 1000.0
        for number in range(1000):
            now += rng.choice([0, 1, 20, 301, 7201])
            at = max(0, now - rng.choice([0, 0, 10, 8000]))
            signal = rng.choice(["sadness", "care", "conflict", "apology", "joy"])
            message = event(at, str(number // 2), (signal,))
            before = deepcopy(runtime)
            result = apply_emotion(state, message, now=now, runtime=runtime)
            self.assertEqual(runtime, before)
            state, runtime = result["affect"], result["runtime"]
            for name in DIMENSIONS:
                value = getattr(state, name)
                self.assertTrue(math.isfinite(value))
                self.assertGreaterEqual(value, -1 if name == "pleasure" else 0)
                self.assertLessEqual(value, 1)
            self.assertLessEqual(len(runtime.get("seen", ())), 256)
            canonical_json(result)


class ControlTests(unittest.TestCase):
    """底气只由模型写、独立于四维：规则事件不得重置它。"""

    def test_control_ema_decay_and_rule_independence(self):
        state = apply_control(BotAffect(), 1.0, now=1000)
        self.assertAlmostEqual(state.control, 0.6)
        self.assertEqual(state.control_at, 1000)
        moved = apply_emotion(state, event(signals=("praise",)), now=1001)["affect"]
        self.assertGreater(moved.control, 0.59)
        self.assertEqual(moved.control_at, 1001)
        self.assertEqual(apply_control(moved, None, now=5000).control, moved.control)
        self.assertAlmostEqual(control_value(moved, 1001 + 3600), 0.55, places=3)

    def test_intensity_presets_scale_deltas_and_gates_only(self):
        normal = emotion_policy("normal")
        self.assertEqual(normal.rule_gain, 1.6)
        self.assertAlmostEqual(normal.event_cap, 0.24)
        self.assertAlmostEqual(normal.similar_budget, 0.48)
        self.assertEqual(normal.half_lives, EmotionPolicy().half_lives)
        self.assertEqual(emotion_policy("unknown").rule_gain, 1.6)

    def test_saturated_reads_do_not_drag_baseline_to_the_ceiling(self):
        """贴顶的读数不当平常水平：基准只向安全上限收敛，否则衰减目标也锁死。"""
        hot = BotAffect(
            pleasure=1.0, arousal=1.0, stress=.312, social_need=0.0,
            baseline_pleasure=.9442, baseline_arousal=.9997,
            baseline_stress=.3345, baseline_social_need=.009,
            baseline_refined=True, updated_at=0.0)
        moved = shift_baseline(hot)
        # 愉悦 ceiling 0.85 归一化 -> 0.70；唤醒 0.85。都不会被 1.0 顶到满格。
        self.assertLess(moved.baseline_pleasure, .9442)
        self.assertLess(moved.baseline_arousal, .9997)
        self.assertAlmostEqual(moved.baseline_pleasure, .70 + (.9442 - .70) * .7, places=6)
        self.assertAlmostEqual(moved.baseline_arousal, .85 + (.9997 - .85) * .7, places=6)
        self.assertTrue(moved.baseline_refined)
        # 非饱和维照旧向读数平滑靠拢。
        self.assertAlmostEqual(moved.baseline_stress, .3345 + (.312 - .3345) * .3, places=6)
        self.assertAlmostEqual(moved.baseline_social_need, .009 + (0.0 - .009) * .3, places=6)

    def test_decay_drift_only_moves_the_target_and_is_idempotent(self):
        """天气 drift 改回落目标、不改当前值；同一时刻重算必须逐位相同。"""
        state = BotAffect(pleasure=.5, arousal=.5, stress=.5, social_need=.5,
                          updated_at=0.0)
        policy = emotion_policy("normal")
        plain = decay_affect(state, now=1800, policy=policy)
        rain = (-.05, -.02, .03, .02)
        drifted = decay_affect(state, now=1800, policy=policy, drift=rain)
        self.assertLess(drifted.pleasure, plain.pleasure)
        self.assertLess(drifted.arousal, plain.arousal)
        self.assertGreater(drifted.stress, plain.stress)
        self.assertGreater(drifted.social_need, plain.social_need)
        self.assertEqual(drifted, decay_affect(state, now=1800, policy=policy, drift=rain))
        # 不传 drift 时与旧行为完全一致。
        self.assertEqual(plain, decay_affect(state, now=1800, policy=policy))
        with self.assertRaises(ValueError):
            decay_affect(state, now=1800, policy=policy, drift=(0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
