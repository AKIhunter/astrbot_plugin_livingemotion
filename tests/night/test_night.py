"""Synthetic clock/receipt traces; no host, external memory, or sender."""

from dataclasses import replace
import json
import math
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from astrbot_plugin_livingemotion.contracts import (
    Context, Event, IntentStatus, NightPhase, NightState, canonical_json,
)
from astrbot_plugin_livingemotion.domain.night import (
    NightPolicy, ReplyReceipt, advance_night, apply_interaction, apply_reply_receipt,
    begin_sleep, finish_waking, night_availability, sleep_stage, wake_night,
)


def context(**changes):
    return replace(Context("bot", "persona", "adapter", "platform", "private", "room",
                           account_id="human", audience=("human",)), **changes)


def message(at=1000, source="m1", **changes):
    return replace(Event(source, "local", "message", context(), "human", at, source,
                         actor_id="human", body="synthetic"), **changes)


def awake(at=1000, energy=80):
    return NightState(updated_at=at, energy=energy)


def asleep(at=1000, until=10000):
    return begin_sleep(awake(at), context(), now=at, wake_at=until)


def settling(**changes):
    return begin_sleep(awake(), context(), now=1000, wake_at=10000,
                       **({"request_id": "r1"} | changes))


class TimeTests(unittest.TestCase):
    def test_all_five_phases(self):
        state = advance_night(awake(energy=31), now=1900)
        self.assertEqual(state.phase, NightPhase.DROWSY)
        state = begin_sleep(state, context(), now=1900, wake_at=10000, request_id="r1")
        self.assertEqual(state.phase, NightPhase.SETTLING)
        state = apply_reply_receipt(state, ReplyReceipt(context(), "succeeded", 1901, "r1"),
                                    now=1901)
        self.assertEqual(state.phase, NightPhase.ASLEEP)
        state = advance_night(state, now=10000)
        self.assertEqual(state.phase, NightPhase.WAKING)
        state = finish_waking(state, now=10001)
        self.assertEqual(state.phase, NightPhase.AWAKE)

    def test_elapsed_not_tick_count(self):
        direct = advance_night(awake(), now=4600)
        stepped = awake()
        for now in range(1000, 4601, 37):
            stepped = advance_night(stepped, now=now)
        stepped = advance_night(stepped, now=4600)
        self.assertAlmostEqual(direct.energy, 76)
        self.assertAlmostEqual(direct.energy, stepped.energy)

    def test_sleep_energy_segments_at_wake(self):
        state = begin_sleep(awake(energy=20), context(), now=1000, wake_at=4600)
        result = advance_night(state, now=6400)
        self.assertEqual(result.energy, 30)
        self.assertEqual(result.phase, NightPhase.DROWSY)

    def test_energy_caps_before_post_wake_drain(self):
        state = asleep(until=8200)
        result = advance_night(state, now=11800)
        self.assertEqual(result.energy, 96)

    def test_sleep_stage_boundaries_and_cycle(self):
        for offset, expected in ((0, "N1"), (299, "N1"), (300, "N2"),
                                 (1499, "N2"), (1500, "N3"), (3599, "N3"),
                                 (3600, "REM"), (5399, "REM"), (5400, "N1")):
            with self.subTest(offset=offset):
                self.assertEqual(sleep_stage(1000, now=1000 + offset), expected)

    def test_stage_uses_absolute_start_after_reload(self):
        state = NightState(**json.loads(canonical_json(asleep())))
        result = advance_night(state, now=4600)
        self.assertEqual(result.sleep_stage, "REM")
        self.assertEqual(advance_night(result, now=4600).energy, result.energy)

    def test_nap(self):
        state = asleep(until=2200)
        result = advance_night(state, now=2200)
        self.assertEqual(result.phase, NightPhase.WAKING)
        self.assertEqual(result.energy, 84)

    def test_nap_across_midnight(self):
        state = asleep(at=86300, until=87500)
        result = advance_night(state, now=87500)
        self.assertEqual(result.energy, 84)
        self.assertEqual(result.phase, NightPhase.WAKING)

    def test_rollback_does_not_double_charge_or_recharge(self):
        state = advance_night(asleep(), now=1600)
        backwards = advance_night(state, now=1200)
        self.assertEqual(backwards.energy, state.energy)
        self.assertEqual(backwards.updated_at, 1600)
        self.assertEqual(backwards.sleep_stage, state.sleep_stage)
        self.assertIn("clock_rollback", backwards.reason_codes)
        self.assertEqual(advance_night(backwards, now=1600).energy, state.energy)

    def test_offline_recovery_enters_one_bounded_transition(self):
        result = advance_night(asleep(until=4600), now=1_000_000, recovering=True)
        self.assertEqual(result.phase, NightPhase.WAKING)
        self.assertEqual(result.energy, 0)
        self.assertEqual(result.transition_deadline, 1_000_300)
        again = advance_night(result, now=1_000_200, recovering=True)
        self.assertEqual(again.transition_deadline, result.transition_deadline)
        self.assertIn(advance_night(again, now=1_000_300).phase,
                      (NightPhase.AWAKE, NightPhase.DROWSY))

    def test_missing_wake_time_still_has_maximum_sleep(self):
        state = replace(asleep(), wake_at=None)
        result = advance_night(state, now=1000 + NightPolicy().max_sleep_seconds)
        self.assertEqual(result.phase, NightPhase.WAKING)

    def test_restored_overlong_sleep_is_capped(self):
        state = replace(asleep(), wake_at=1_000_000)
        result = advance_night(state, now=1000 + NightPolicy().max_sleep_seconds)
        self.assertEqual(result.phase, NightPhase.WAKING)

    def test_normal_timer_jump_expires_waking(self):
        result = advance_night(asleep(until=2000), now=2300)
        self.assertEqual(result.phase, NightPhase.AWAKE)

    def test_repeated_sleep_does_not_restart_existing_window(self):
        state = advance_night(asleep(), now=1100)
        result = begin_sleep(state, context(), now=1100, wake_at=9000)
        self.assertEqual(result.sleep_started_at, 1000)
        self.assertEqual(result.wake_at, 10000)

    def test_sleep_window_invalid(self):
        for until in (999, 1000, 100000, float("inf"), float("nan"), True):
            with self.subTest(until=until), self.assertRaises(ValueError):
                begin_sleep(awake(), context(), now=1000, wake_at=until)

    def test_bad_state_or_clock_rejected(self):
        for now in (-1, float("nan"), float("inf"), True):
            with self.subTest(now=now), self.assertRaises(ValueError):
                advance_night(awake(), now=now)
        for state in (NightState(phase="asleep"), NightState(phase="waking"),
                      NightState(unread_watermark=-1), NightState(unread_watermark=True)):
            with self.subTest(state=state), self.assertRaises(ValueError):
                advance_night(state, now=1000)

    def test_bad_policies_rejected(self):
        for changes in ({"awake_cost_per_hour": float("nan")},
                        {"waking_timeout": 0}, {"waking_timeout": 3601},
                        {"max_sleep_seconds": float("inf")}, {"dedup_capacity": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                NightPolicy(**changes)


class ReceiptTests(unittest.TestCase):
    def test_request_receipt_survives_json_roundtrip(self):
        state = NightState(**json.loads(canonical_json(settling())))
        result = apply_reply_receipt(state, ReplyReceipt(context(), "succeeded", 1001, "r1"),
                                    now=1001)
        self.assertEqual(result.phase, NightPhase.ASLEEP)
        self.assertIsNone(result.awaiting_reply_id)
        self.assertLess(len(state.awaiting_reply_id), 512)

    def test_message_only_receipt(self):
        state = settling(request_id=None, message_id="out1")
        result = apply_reply_receipt(
            state, ReplyReceipt(context(), "succeeded", 1001, message_id="out1"), now=1001
        )
        self.assertEqual(result.phase, NightPhase.ASLEEP)

    def test_both_bound_ids_must_not_conflict(self):
        state = settling(message_id="out1")
        bad = ReplyReceipt(context(), "succeeded", 1001, "r1", "wrong")
        self.assertEqual(apply_reply_receipt(state, bad, now=1001).phase, NightPhase.SETTLING)
        good = replace(bad, message_id="out1")
        self.assertEqual(apply_reply_receipt(state, good, now=1001).phase, NightPhase.ASLEEP)

    def test_other_scope_and_revision_never_settle(self):
        for field, value in (("bot_id", "b2"), ("persona_id", "p2"), ("adapter_id", "a2"),
                             ("platform", "p2"), ("scene_kind", "group"), ("scene_id", "s2"),
                             ("instance_id", "i2"), ("persona_revision", "v2"),
                             ("identity_revision", "v2")):
            with self.subTest(field=field):
                receipt = ReplyReceipt(context(**{field: value}), "succeeded", 1001, "r1")
                self.assertEqual(apply_reply_receipt(settling(), receipt, now=1001).phase,
                                 NightPhase.SETTLING)

    def test_all_non_success_outcomes_leave_pending(self):
        for status in IntentStatus:
            if status == IntentStatus.SUCCEEDED:
                continue
            with self.subTest(status=status):
                result = apply_reply_receipt(
                    settling(), ReplyReceipt(context(), status, 1001, "r1"), now=1001
                )
                self.assertEqual(result.phase, NightPhase.SETTLING)
                self.assertIsNotNone(result.awaiting_reply_id)

    def test_stale_future_missing_or_wrong_ids_rejected(self):
        for receipt in (ReplyReceipt(context(), "succeeded", 999, "r1"),
                        ReplyReceipt(context(), "succeeded", 1002, "r1"),
                        ReplyReceipt(context(), "succeeded", 1001, "wrong"),
                        ReplyReceipt(context(), "succeeded", 1001, message_id="r1")):
            with self.subTest(receipt=receipt):
                self.assertEqual(apply_reply_receipt(settling(), receipt, now=1001).phase,
                                 NightPhase.SETTLING)

    def test_settling_timeout_cancels_instead_of_sleeping(self):
        state = advance_night(settling(), now=1120)
        self.assertEqual(state.phase, NightPhase.AWAKE)
        receipt = ReplyReceipt(context(), "succeeded", 1100, "r1")
        self.assertEqual(apply_reply_receipt(state, receipt, now=1121).phase, NightPhase.AWAKE)

    def test_reply_at_deadline_is_too_late(self):
        receipt = ReplyReceipt(context(), "succeeded", 1120, "r1")
        self.assertEqual(apply_reply_receipt(settling(), receipt, now=1120).phase,
                         NightPhase.AWAKE)

    def test_duplicate_success_does_not_reset_sleep(self):
        receipt = ReplyReceipt(context(), "succeeded", 1001, "r1")
        state = apply_reply_receipt(settling(), receipt, now=1001)
        result = apply_reply_receipt(state, receipt, now=1050)
        self.assertEqual(result.sleep_started_at, 1001)

    def test_delayed_receipt_does_not_backdate_energy(self):
        state = advance_night(settling(), now=1050)
        result = apply_reply_receipt(
            state, ReplyReceipt(context(), "succeeded", 1001, "r1"), now=1060
        )
        self.assertEqual(result.sleep_started_at, 1060)
        self.assertAlmostEqual(result.energy, 80 - 60 / 3600 * 4)

    def test_malformed_legacy_reply_key_never_matches(self):
        receipt = ReplyReceipt(context(), "succeeded", 1001, "r1")
        for key in ("r1", "{}", "null", "[]", '{"v":1,"at":true}'):
            with self.subTest(key=key):
                result = apply_reply_receipt(replace(settling(), awaiting_reply_id=key),
                                             receipt, now=1001)
                self.assertEqual(result.phase, NightPhase.SETTLING)

    def test_invalid_receipt_ids(self):
        for kwargs in ({}, {"request_id": ""}, {"message_id": "x" * 513}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ReplyReceipt(context(), "succeeded", 1001, **kwargs)


class ControlTests(unittest.TestCase):
    def test_called_and_manual_wake_distinguished(self):
        for reason in ("called", "manual"):
            result = wake_night(asleep(), now=1050, reason=reason)
            self.assertEqual(result.phase, NightPhase.WAKING)
            self.assertEqual(result.reason_codes, (f"{reason}_wake",))
            self.assertEqual(result.wake_at, 1050)

    def test_repeated_wake_does_not_extend_deadline(self):
        state = wake_night(asleep(), now=1050)
        again = wake_night(state, now=1100)
        self.assertEqual(again.transition_deadline, 1350)

    def test_wake_cancels_settling_and_late_receipt(self):
        state = wake_night(settling(), now=1050)
        self.assertEqual(state.phase, NightPhase.AWAKE)
        state = apply_reply_receipt(state, ReplyReceipt(context(), "succeeded", 1051, "r1"),
                                    now=1051)
        self.assertEqual(state.phase, NightPhase.AWAKE)

    def test_manual_sleep(self):
        state = begin_sleep(awake(), context(), now=1000, wake_at=2000, manual=True)
        self.assertEqual(state.reason_codes, ("manual_sleep",))
        with self.assertRaises(ValueError):
            begin_sleep(awake(), context(), now=1000, wake_at=2000, manual=True, request_id="r")

    def test_disable_clears_all_pending_night_controls(self):
        for initial in (settling(), asleep(), wake_night(asleep(), now=1000)):
            with self.subTest(phase=initial.phase):
                result = advance_night(initial, now=1050, enabled=False)
                self.assertEqual(result.phase, NightPhase.AWAKE)
                self.assertIsNone(result.awaiting_reply_id)
                self.assertIsNone(result.transition_deadline)
                self.assertIsNone(result.sleep_started_at)

    def test_disabled_begin_or_receipt_never_sleeps(self):
        result = begin_sleep(awake(), context(), now=1000, wake_at=2000, enabled=False)
        self.assertEqual(result.phase, NightPhase.AWAKE)
        result = apply_reply_receipt(
            settling(), ReplyReceipt(context(), "succeeded", 1001, "r1"),
            now=1001, enabled=False,
        )
        self.assertEqual(result.phase, NightPhase.AWAKE)

    def test_sleep_does_not_block_native_chat_by_default(self):
        result = night_availability(asleep(), now=1000)
        self.assertFalse(result.available)
        self.assertFalse(result.block_chat)

    def test_explicit_block_has_verified_exemptions(self):
        for initial in (settling(), asleep(), wake_night(asleep(), now=1000)):
            with self.subTest(phase=initial.phase):
                self.assertTrue(night_availability(initial, now=1000, block_chat=True).block_chat)
                exempt = night_availability(initial, now=1000, block_chat=True, exempt=True)
                self.assertTrue(exempt.available)
                self.assertFalse(exempt.block_chat)

    def test_rollback_does_not_trigger_manual_transition(self):
        for result in (begin_sleep(awake(), context(), now=999, wake_at=2000),
                       wake_night(asleep(), now=999),
                       finish_waking(wake_night(asleep(), now=1000), now=999)):
            self.assertIn("clock_rollback", result.reason_codes)


class InteractionTests(unittest.TestCase):
    def test_bounded_cost_and_duplicate(self):
        result = apply_interaction(awake(), message(), context=context(), now=1000)
        self.assertAlmostEqual(result["night"].energy, 79.8)
        repeated = apply_interaction(result["night"], message(), context=context(), now=1000,
                                     runtime=result["runtime"])
        self.assertFalse(repeated["applied"])
        self.assertEqual(repeated["night"].energy, result["night"].energy)

    def test_flood_budget_and_runtime_roundtrip(self):
        state, runtime = awake(), None
        for index in range(100):
            result = apply_interaction(state, message(source=str(index)), context=context(),
                                       now=1000, runtime=runtime)
            state = result["night"]
            runtime = json.loads(canonical_json(result["runtime"]))
        self.assertAlmostEqual(state.energy, 78)
        self.assertLessEqual(len(runtime["charges"]), 192)

    def test_budget_refreshes_only_after_real_time(self):
        policy = NightPolicy(interaction_cost=2)
        first = apply_interaction(awake(), message(), context=context(), now=1000, policy=policy)
        blocked = apply_interaction(first["night"], message(source="m2"), context=context(),
                                    now=1000, runtime=first["runtime"], policy=policy)
        self.assertFalse(blocked["applied"])
        refreshed = apply_interaction(blocked["night"], message(1300, "m3"), context=context(),
                                      now=1300, runtime=blocked["runtime"], policy=policy)
        self.assertEqual(refreshed["cost"], 2)

    def test_wrong_scope_and_derived_events_do_not_cost(self):
        for event in (message(context=context(scene_id="other")), message(event_type="summary"),
                      message(actor_role="bot"), message(actor_id="impostor"),
                      message(reliable_source=False), message(at=1001)):
            with self.subTest(event=event):
                self.assertFalse(apply_interaction(
                    awake(), event, context=context(), now=1000
                )["applied"])

    def test_messages_do_not_wake_or_drain_sleep(self):
        result = apply_interaction(asleep(), message(), context=context(), now=1000)
        self.assertEqual(result["night"].phase, NightPhase.ASLEEP)
        self.assertEqual(result["cost"], 0)

    def test_expired_event_and_full_guard(self):
        expired = apply_interaction(awake(10000), message(1000), context=context(), now=10000)
        self.assertFalse(expired["applied"])
        policy = NightPolicy(dedup_capacity=1)
        first = apply_interaction(awake(), message(), context=context(), now=1000, policy=policy)
        result = apply_interaction(first["night"], message(source="m2"), context=context(),
                                   now=1000, runtime=first["runtime"], policy=policy)
        self.assertEqual(result["reason_codes"], ("guard_capacity",))

    def test_runtime_scope_and_nonfinite_charge_rejected(self):
        for runtime in ({"scope_key": "other"}, {"charges": [(1000, float("nan"))]},
                        {"seen": {"x": float("inf")}}):
            with self.subTest(runtime=runtime), self.assertRaises(ValueError):
                apply_interaction(awake(), message(), context=context(), now=1000,
                                  runtime=runtime)


class GeneratedTraceTests(unittest.TestCase):
    def test_seeded_clock_restart_and_receipt_interleavings(self):
        rng = random.Random(20261105)
        state = awake()
        now = 1000
        for index in range(2000):
            now = max(0, now + rng.choice((-120, 0, 1, 30, 300, 10000)))
            previous = state
            action = rng.randrange(5)
            if action == 0:
                state = advance_night(state, now=now, recovering=bool(index % 2))
            elif action == 1:
                state = begin_sleep(state, context(), now=now, wake_at=now + 3600,
                                    request_id="r1")
            elif action == 2:
                receipt = ReplyReceipt(context(scene_id=rng.choice(("room", "other"))),
                                       rng.choice(tuple(IntentStatus)), now, "r1")
                state = apply_reply_receipt(state, receipt, now=now)
                if previous.phase == NightPhase.SETTLING and state.phase == NightPhase.ASLEEP:
                    self.assertEqual(receipt.status, IntentStatus.SUCCEEDED)
                    self.assertEqual(receipt.context.scope_key, context().scope_key)
            elif action == 3:
                state = wake_night(state, now=now)
            else:
                state = finish_waking(state, now=now)
            state = NightState(**json.loads(canonical_json(state)))
            self.assertTrue(math.isfinite(state.energy))
            self.assertGreaterEqual(state.energy, 0)
            self.assertLessEqual(state.energy, 100)
            self.assertGreaterEqual(state.updated_at, previous.updated_at)
            if state.phase == NightPhase.ASLEEP:
                self.assertIsNotNone(state.sleep_started_at)
                self.assertIsNone(state.awaiting_reply_id)
            if previous.phase == state.phase == NightPhase.WAKING:
                self.assertEqual(previous.transition_deadline, state.transition_deadline)

    def test_seeded_elapsed_partition_invariance(self):
        rng = random.Random(20261105)
        for _ in range(100):
            end = rng.randint(5000, 20000)
            state = asleep(until=4500)
            direct = advance_night(state, now=end)
            for at in sorted(rng.randint(1000, end) for _ in range(30)):
                state = advance_night(state, now=at)
            state = advance_night(state, now=end)
            self.assertAlmostEqual(state.energy, direct.energy)
            self.assertEqual(state.phase, direct.phase)


if __name__ == "__main__":
    unittest.main()
