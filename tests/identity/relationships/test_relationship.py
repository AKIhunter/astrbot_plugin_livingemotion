"""Synthetic account-ledger, unbinding and relationship-budget counterexamples."""

from copy import deepcopy
from dataclasses import replace
import json
import math
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from astrbot_plugin_livingemotion.contracts import (
    Context, Event, Relationship, RelationshipContribution, canonical_json,
)
from astrbot_plugin_livingemotion.domain.relationship import (
    RelationshipPolicy, apply_relationship, correct_relationship,
    project_relationship, relationship_stage,
)


def context(**changes):
    return replace(Context("bot", "persona", "adapter", "platform", "private",
                           "room", account_id="human"), **changes)


def event(at=1000.0, source="m1", signals=(), **changes):
    return replace(Event(source, "synthetic", "message", context(), "human", at,
                         source, actor_id="human", signals=signals), **changes)


def row(delta, *, source="m1", account="human", dimension="score"):
    return RelationshipContribution(source, account, 1000, delta, "synthetic",
                                    "1970-01-01", dimension)


class RelationshipTransitionTests(unittest.TestCase):
    def test_real_interaction_without_memory_establishes_familiarity_only(self):
        result = apply_relationship(Relationship(), event(), now=1000)
        state = result["relationship"]
        self.assertEqual(state.score, 0.5)
        self.assertEqual(state.familiarity, 0.005)
        self.assertIsNone(state.trust)
        self.assertIsNone(state.boundary)
        self.assertEqual(result["trace"]["charged"], 0.5)
        self.assertEqual(state.normalized, 0.0005)

    def test_legacy_score_does_not_invent_trust_or_boundary(self):
        legacy = Relationship(score=900, evidence_complete=False)
        result = apply_relationship(legacy, event(), now=1000)["relationship"]
        self.assertIsNone(result.trust)
        self.assertIsNone(result.boundary)
        self.assertFalse(result.evidence_complete)

    def test_dimensions_require_their_own_explicit_evidence(self):
        result = apply_relationship(Relationship(), event(signals=("promise_kept",)),
                                    now=1000)
        self.assertAlmostEqual(result["relationship"].trust, 0.52)
        self.assertIsNone(result["relationship"].boundary)
        result = apply_relationship(Relationship(), event(signals=("boundary_violated",)),
                                    now=1000)
        self.assertAlmostEqual(result["relationship"].boundary, 0.47)
        self.assertIsNone(result["relationship"].trust)

    def test_score_stages_and_bounds(self):
        for score, stage in ((0, "stage_0"), (99.9, "stage_0"),
                             (110, "stage_1"), (300, "stage_2"),
                             (600, "stage_3"), (850, "stage_3"), (1000, "stage_4")):
            self.assertEqual(relationship_stage(score), stage)
        positive = apply_relationship(Relationship(score=999), event(signals=("care",)),
                                      now=1000)
        negative = apply_relationship(Relationship(score=1), event(signals=("conflict",)),
                                      now=1000)
        self.assertEqual(positive["relationship"].score, 990)
        self.assertEqual(negative["relationship"].score, 0)
        self.assertEqual(positive["trace"]["charged"], 3)
        self.assertEqual(negative["trace"]["charged"], 5)

    def test_single_event_cap_even_for_many_signals(self):
        result = apply_relationship(Relationship(score=500), event(
            signals=("care", "gratitude", "promise_kept", "boundary_respected")),
            now=1000)
        self.assertEqual(result["trace"]["charged"], 6)
        self.assertEqual(result["relationship"].score, 506)

    def test_positive_and_negative_changes_never_refund_daily_budget(self):
        policy = RelationshipPolicy(daily_budget=8)
        first = apply_relationship(Relationship(score=500),
                                   event(signals=("care",)), now=1000, policy=policy)
        second = apply_relationship(first["relationship"],
                                    event(1400, "m2", ("conflict",)), now=1400,
                                    runtime=first["runtime"], policy=policy)
        third = apply_relationship(second["relationship"],
                                   event(1800, "m3", ("care",)), now=1800,
                                   runtime=second["runtime"], policy=policy)
        self.assertEqual(third["relationship"].score, 501)
        self.assertEqual(third["runtime"]["days"]["1970-01-01"], 6)
        self.assertEqual(third["runtime"]["negative_days"]["1970-01-01"], 5)
        self.assertEqual(third["reason_codes"], ("rule_care",))

    def test_opposing_signals_in_one_event_charge_absolute_motion(self):
        policy = RelationshipPolicy(daily_budget=6)
        result = apply_relationship(Relationship(score=500),
                                    event(signals=("care", "conflict")), now=1000,
                                    policy=policy)
        self.assertEqual(result["trace"]["charged"], 6)
        self.assertAlmostEqual(result["relationship"].score, 498.5)
        self.assertEqual(result["runtime"]["negative_days"]["1970-01-01"], 6)

    def test_budget_survives_midnight_and_delayed_events_use_occurrence_day(self):
        policy = RelationshipPolicy(daily_budget=6)
        first = apply_relationship(Relationship(score=500),
                                   event(86300, "m1", ("promise_broken",)),
                                   now=86300, policy=policy)
        delayed = apply_relationship(first["relationship"], event(86301, "m2", ("care",)),
                                     now=86410, runtime=first["runtime"], policy=policy)
        self.assertTrue(delayed["applied"])
        new_day = apply_relationship(delayed["relationship"],
                                     event(86411, "m3", ("gratitude",)), now=86411,
                                     runtime=delayed["runtime"], policy=policy)
        self.assertTrue(new_day["applied"])
        self.assertEqual(new_day["runtime"]["days"]["1970-01-01"], 3)
        self.assertEqual(new_day["runtime"]["negative_days"]["1970-01-01"], 6)
        self.assertEqual(new_day["runtime"]["days"]["1970-01-02"], 2)

    def test_budget_calendar_uses_configured_timezone(self):
        result = apply_relationship(Relationship(), event(60000), now=60000,
                                    policy=RelationshipPolicy(timezone="Asia/Shanghai"))
        self.assertEqual(result["trace"]["day"], "1970-01-02")

    def test_clock_rollback_cannot_reopen_old_day_budget(self):
        first = apply_relationship(Relationship(), event(90000), now=90000)
        previous = deepcopy(first["runtime"])
        result = apply_relationship(first["relationship"], event(1000, "old"), now=1000,
                                    runtime=first["runtime"])
        self.assertEqual(result["reason_codes"], ("clock_before_state",))
        self.assertEqual(first["runtime"], previous)
        self.assertEqual(result["runtime"]["days"]["1970-01-02"], 0.5)

    def test_no_rewards_for_bot_self_reports_or_imaginary_events(self):
        for changes in (
            {"actor_role": "bot", "actor_id": "bot", "event_type": "bot_action_succeeded"},
            {"actor_role": "unknown"}, {"event_type": "dream"},
            {"event_type": "diary"}, {"reliable_source": False},
        ):
            with self.subTest(changes=changes):
                result = apply_relationship(Relationship(), event(**changes), now=1000)
                self.assertFalse(result["applied"])
                self.assertEqual(result["contributions"], ())

    def test_repeated_source_and_similar_new_ids_are_bounded(self):
        state, runtime = Relationship(), None
        for number in range(100):
            result = apply_relationship(state, event(1000, str(number), ("care",)),
                                        now=1000, runtime=runtime)
            state, runtime = result["relationship"], result["runtime"]
        self.assertEqual(state.score, 9)
        self.assertEqual(runtime["days"]["1970-01-01"], 9)
        result = apply_relationship(state, event(1000, "0", ("care",)), now=1000,
                                    runtime=runtime)
        self.assertEqual(result["reason_codes"], ("duplicate_event",))

    def test_restart_roundtrip_preserves_budget_and_duplicate_guard(self):
        first = apply_relationship(Relationship(), event(), now=1000)
        runtime = json.loads(canonical_json(first["runtime"]))
        result = apply_relationship(first["relationship"], event(), now=1000,
                                    runtime=runtime)
        self.assertEqual(result["reason_codes"], ("duplicate_event",))
        self.assertEqual(result["runtime"]["days"], runtime["days"])

    def test_old_expired_and_mismatched_account_inputs_are_rejected(self):
        first = apply_relationship(Relationship(), event(2000), now=2000)
        result = apply_relationship(first["relationship"], event(1000, "old"), now=2000,
                                    runtime=first["runtime"])
        self.assertEqual(result["reason_codes"], ("older_event",))
        expired = apply_relationship(Relationship(), event(), now=8200)
        self.assertEqual(expired["reason_codes"], ("expired_event",))
        with self.assertRaisesRegex(ValueError, "runtime_scope"):
            apply_relationship(Relationship(), event(
                context=context(account_id="other"), actor_id="other"), now=1000,
                runtime=first["runtime"])

    def test_observe_only_still_updates_and_disabled_does_not(self):
        observed = apply_relationship(Relationship(), event(), now=1000, mode="observe_only")
        self.assertTrue(observed["applied"])
        stopped = apply_relationship(Relationship(), event(), now=1000, enabled=False)
        self.assertFalse(stopped["applied"])
        self.assertEqual(stopped["runtime"], {})

    def test_nonfinite_and_wrong_types_rejected(self):
        for value in (float("nan"), float("inf"), -float("inf"), True, "1", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    Relationship(score=value)
                with self.assertRaises(ValueError):
                    apply_relationship(Relationship(), event(), now=value)
        for change in ({"daily_budget": float("nan")}, {"similar_limit": True},
                       {"event_cap": 11}, {"timezone": "not/a/zone"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                RelationshipPolicy(**change)
        first = apply_relationship(Relationship(), event(), now=1000)
        first["runtime"]["days"]["1970-01-01"] = float("inf")
        with self.assertRaises(ValueError):
            apply_relationship(first["relationship"], event(1001, "m2"), now=1001,
                               runtime=first["runtime"])

    def test_seeded_sequences_stay_bounded_and_budget_monotone_within_day(self):
        rng = random.Random(20261105)
        state, runtime, now = Relationship(score=500), None, 1000.0
        high_water = {}
        for number in range(1000):
            now += rng.choice([0, 1, 301, 8000])
            signal = rng.choice(["care", "conflict", "promise_kept", "promise_broken"])
            result = apply_relationship(state, event(now, str(number // 2), (signal,)),
                                        now=now, runtime=runtime)
            state, runtime = result["relationship"], result["runtime"]
            self.assertTrue(math.isfinite(state.score))
            self.assertGreaterEqual(state.score, 0)
            self.assertLessEqual(state.score, 990)
            for bucket in ("days", "negative_days"):
                for day, amount in runtime.get(bucket, {}).items():
                    self.assertGreaterEqual(amount, high_water.get((bucket, day), 0))
                    self.assertLessEqual(amount, 24)
                    high_water[bucket, day] = amount
                high_water[day] = amount
            canonical_json(result)


class ManualCorrectionTests(unittest.TestCase):
    def test_correction_freeze_and_unfreeze_have_versions_and_audit(self):
        state = Relationship(score=600)
        corrected = correct_relationship(state, context(), now=1000, actor_id="admin",
                                         reason="verified correction", expected_version=2,
                                         current_version=2, score=750, frozen=True)
        self.assertEqual(corrected["version"], 3)
        self.assertEqual(corrected["audit"]["before"]["score"], 600)
        self.assertEqual(corrected["audit"]["after"]["score"], 750)
        self.assertEqual(corrected["audit"]["actor_id"], "admin")
        self.assertEqual(corrected["contributions"][0].delta, 150)
        self.assertIsNone(corrected["relationship"].trust)
        frozen = apply_relationship(corrected["relationship"], event(1001), now=1001)
        self.assertEqual(frozen["reason_codes"], ("relationship_frozen",))
        self.assertEqual(frozen["relationship"].score, 750)
        unfrozen = correct_relationship(corrected["relationship"], context(), now=1002,
                                        actor_id="admin", reason="resume",
                                        expected_version=3, current_version=3, frozen=False)
        self.assertEqual(unfrozen["version"], 4)
        self.assertFalse(unfrozen["relationship"].frozen)
        self.assertEqual(unfrozen["contributions"], ())
        self.assertNotEqual(unfrozen["audit"]["operation_id"], corrected["audit"]["operation_id"])

    def test_manual_correction_does_not_refund_runtime_budget(self):
        first = apply_relationship(Relationship(score=500),
                                   event(signals=("promise_broken",)), now=1000,
                                   policy=RelationshipPolicy(daily_budget=6))
        original = deepcopy(first["runtime"])
        manual = correct_relationship(first["relationship"], context(), now=1001,
                                      actor_id="admin", reason="restore", expected_version=1,
                                      current_version=1, score=500)
        result = apply_relationship(manual["relationship"],
                                    event(1400, "m2", ("promise_broken",)), now=1400,
                                    runtime=first["runtime"],
                                    policy=RelationshipPolicy(daily_budget=6))
        self.assertEqual(result["reason_codes"], ("daily_budget_exhausted",))
        self.assertEqual(first["runtime"], original)

    def test_frozen_event_cannot_be_replayed_after_unfreeze(self):
        first = apply_relationship(Relationship(frozen=True), event(), now=1000)
        changed = correct_relationship(first["relationship"], context(), now=1000,
                                       actor_id="admin", reason="resume", expected_version=1,
                                       current_version=1, frozen=False)
        replay = apply_relationship(changed["relationship"], event(), now=1000,
                                    runtime=first["runtime"])
        self.assertEqual(replay["reason_codes"], ("duplicate_event",))

    def test_late_event_cannot_modify_newer_manual_correction(self):
        first = apply_relationship(Relationship(score=500), event(), now=1000)
        corrected = correct_relationship(first["relationship"], context(), now=1500,
                                         actor_id="admin", reason="reviewed",
                                         expected_version=1, current_version=1, score=600)
        result = apply_relationship(corrected["relationship"],
                                    event(1400, "late", ("conflict",)), now=1600,
                                    runtime=first["runtime"])
        self.assertEqual(result["relationship"].score, 600)
        self.assertEqual(result["reason_codes"], ("older_than_manual_correction",))

    def test_corrections_require_matching_version_reason_actor_and_finite_score(self):
        valid = {"now": 1000, "actor_id": "admin", "reason": "fix",
                 "expected_version": 1, "current_version": 1, "score": 700}
        for changes in (
            {"expected_version": 0}, {"expected_version": True}, {"reason": " "},
            {"actor_id": ""}, {"score": float("nan")}, {"score": 1001},
            {"frozen": "false"}, {"score": None},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                correct_relationship(Relationship(), context(), **{**valid, **changes})


class IdentityProjectionTests(unittest.TestCase):
    def test_binding_then_unbinding_reprojects_without_moving_evidence(self):
        first = context(account_id="a")
        second = context(account_id="b", platform="other", scene_id="room-b")
        ledger = [(first, row(100, account="a")),
                  (second, row(300, account="b"))]
        original = deepcopy(ledger)
        bound = replace(first, identity_revision="bound-v1")
        together = project_relationship(
            ledger, context=bound, authorized_account_keys=(first.account_key, second.account_key),
            identity_revision="bound-v1")
        self.assertEqual(together.score, 400)
        detached = replace(first, identity_revision="unbound-v2")
        own = project_relationship(ledger, context=detached,
                                   authorized_account_keys=(first.account_key,),
                                   identity_revision="unbound-v2")
        self.assertEqual(own.score, 100)
        self.assertEqual(ledger, original)
        with self.assertRaisesRegex(ValueError, "identity_revision_changed"):
            project_relationship(ledger, context=detached, identity_revision="bound-v1")

    def test_unknown_dimensions_remain_unknown_from_score_only_ledger(self):
        result = project_relationship([(context(), row(900))], context=context(),
                                      identity_revision="0")
        self.assertIsNone(result.trust)
        self.assertIsNone(result.familiarity)
        self.assertIsNone(result.boundary)

    def test_binding_does_not_add_normalized_dimensions_into_full_trust(self):
        first, second = context(account_id="a"), context(account_id="b")
        ledger = [(first, row(0.52, account="a", dimension="trust")),
                  (second, row(0.52, account="b", dimension="trust"))]
        result = project_relationship(ledger, context=first, identity_revision="0",
                                      authorized_account_keys=(first.account_key, second.account_key))
        self.assertAlmostEqual(result.trust, 0.52)
        self.assertIsNone(result.boundary)

    def test_empty_authorization_is_not_default_authorization(self):
        result = project_relationship([(context(), row(900))], context=context(),
                                      authorized_account_keys=(), identity_revision="0")
        self.assertEqual(result.score, 0)

    def test_naked_same_account_id_does_not_cross_scope(self):
        for changed in (
            {"bot_id": "other"}, {"persona_id": "other"}, {"adapter_id": "other"},
            {"platform": "other"}, {"scene_id": "other"}, {"scene_kind": "group"},
        ):
            with self.subTest(changed=changed):
                ledger = [(context(), row(10)),
                          (context(**changed), row(900))]
                result = project_relationship(ledger, context=context(), identity_revision="0")
                self.assertEqual(result.score, 10)

    def test_even_explicit_grant_cannot_mix_bot_or_persona(self):
        for changed in ({"bot_id": "other"}, {"persona_id": "other"}):
            source = context(**changed)
            result = project_relationship([(source, row(900))], context=context(),
                                          authorized_account_keys=(source.account_key,),
                                          identity_revision="0")
            self.assertEqual(result.score, 0)

    def test_duplicate_ledger_rows_do_not_double_count_or_accept_conflicts(self):
        item = (context(), row(100))
        result = project_relationship([item, item], context=context(), identity_revision="0")
        self.assertEqual(result.score, 100)
        with self.assertRaisesRegex(ValueError, "conflicting_contribution"):
            project_relationship([item, (context(), row(200))],
                                 context=context(), identity_revision="0")

    def test_unknown_legacy_dimension_not_automatically_aggregated(self):
        result = project_relationship([(context(), row(900, dimension="legacy_score"))],
                                      context=context(), identity_revision="0")
        self.assertEqual(result.score, 0)
        self.assertFalse(result.evidence_complete)

    def test_source_account_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "contribution_account_mismatch"):
            project_relationship([(context(), row(100, account="spoofed"))],
                                 context=context(), identity_revision="0")

    def test_account_snapshot_can_be_rebuilt_from_its_contributions(self):
        state, runtime, ledger = Relationship(), None, []
        for number, signal in enumerate(("care", "promise_kept", "conflict", "boundary_respected")):
            at = 1000 + number * 400
            result = apply_relationship(state, event(at, str(number), (signal,)),
                                        now=at, runtime=runtime)
            state, runtime = result["relationship"], result["runtime"]
            ledger.extend((context(), contribution) for contribution in result["contributions"])
        rebuilt = project_relationship(ledger, context=context(), identity_revision="0")
        for name in ("score", "trust", "familiarity", "boundary"):
            self.assertAlmostEqual(getattr(rebuilt, name), getattr(state, name))


if __name__ == "__main__":
    unittest.main()
