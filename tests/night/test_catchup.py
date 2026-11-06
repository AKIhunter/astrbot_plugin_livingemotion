"""Local-window provenance and bounded catchup tests."""

from dataclasses import replace
import json
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from astrbot_plugin_livingemotion.contracts import (
    ContentKind, Context, Event, EvidenceRef, NightState, canonical_json, to_dict,
)
from astrbot_plugin_livingemotion.services.catchup import (
    CatchupPolicy, build_catchup, catchup_intent,
)


def context(**changes):
    return replace(Context("bot", "persona", "adapter", "platform", "private", "room",
                           account_id="human", audience=("human",),
                           route="verified:synthetic:room"), **changes)


def waking(**changes):
    return replace(NightState(phase="waking", energy=80, updated_at=1000,
                             sleep_started_at=100, wake_at=1000, transition_deadline=1300),
                   **changes)


def row(seq, **changes):
    event = replace(Event(f"e{seq}", "local", "message", context(), "human", 900 + seq,
                          f"m{seq}", actor_id="human", body=f"synthetic message {seq}"),
                    **changes)
    metadata = to_dict(event)
    del metadata["body"]
    return {
        "seq": seq, "event_key": event.idempotency_key, "event_id": event.event_id,
        "actor_role": event.actor_role.value, "account_id": event.context.account_id,
        "occurred_at": event.occurred_at, "metadata_json": metadata, "body": event.body,
    }


def build(rows, **changes):
    kwargs = {"now": 1000, "high_watermark": 10, "generation": 0}
    kwargs.update(changes)
    return build_catchup(waking(), context(), rows, **kwargs)


class WindowTests(unittest.TestCase):
    def test_original_mapping_and_summary_kind(self):
        result = build([row(1), row(2)])
        summary = result["summary"]
        self.assertEqual(summary.body, "[1] synthetic message 1\n[2] synthetic message 2")
        self.assertEqual(summary.evidence.kind, ContentKind.SUMMARY)
        self.assertEqual(summary.sources[0].kind, ContentKind.INTERACTION)
        self.assertEqual(summary.sources[0].source_ids, ("m1",))
        self.assertEqual(summary.sources[0].subject_id, "human")
        self.assertEqual(summary.evidence.subject_id, "bot")
        self.assertEqual(summary.evidence.source_ids,
                         tuple(source.source_id for source in summary.sources))
        self.assertEqual(result["night"].energy, 80)
        self.assertEqual(result["night"].updated_at, 1000)

    def test_no_memory_no_model_no_sender_needed(self):
        result = build([])
        self.assertIsNone(result["summary"])
        self.assertEqual(result["night"].unread_watermark, 10)
        self.assertFalse(result["has_more"])

    def test_already_read_rows_are_not_summarized(self):
        result = build_catchup(waking(unread_watermark=2), context(), [row(1), row(2), row(3)],
                               now=1000, high_watermark=3, generation=0)
        self.assertEqual(len(result["summary"].sources), 1)
        self.assertEqual(result["summary"].sources[0].source_ids, ("m3",))

    def test_high_watermark_freezes_despite_new_messages(self):
        policy = CatchupPolicy(max_rows=2)
        first = build([row(1), row(2)], high_watermark=4, policy=policy)
        self.assertTrue(first["has_more"])
        second = build_catchup(first["night"], context(), [row(3), row(4)], now=1001,
                               high_watermark=99, generation=0, runtime=first["runtime"],
                               policy=policy)
        self.assertEqual(second["runtime"]["high_watermark"], 4)
        self.assertEqual(second["night"].unread_watermark, 4)
        self.assertFalse(second["has_more"])

    def test_newer_rows_outside_frozen_window_not_consumed(self):
        result = build([row(1), row(2), row(3)], high_watermark=2)
        self.assertEqual(len(result["summary"].sources), 2)
        self.assertEqual(result["night"].unread_watermark, 2)

    def test_restart_keeps_watermark_and_completed_marker(self):
        first = build([row(1), row(2)])
        state = NightState(**json.loads(canonical_json(first["night"])))
        runtime = json.loads(canonical_json(first["runtime"]))
        again = build_catchup(state, context(), [row(1), row(2)], now=1001,
                              high_watermark=10, generation=0, runtime=runtime)
        self.assertIsNone(again["summary"])
        self.assertEqual(again["reason_codes"], ("catchup_already_complete",))

    def test_recompute_before_commit_has_same_summary_and_intent_id(self):
        first = build([row(1), row(2)])
        second = build([row(1), row(2)], now=1001)
        self.assertEqual(first["summary"].summary_id, second["summary"].summary_id)
        intent1 = catchup_intent(first["summary"], first["night"], context(), now=1001,
                                generation=0)
        intent2 = catchup_intent(second["summary"], second["night"], context(), now=1002,
                                generation=0)
        self.assertEqual(intent1.intent_id, intent2.intent_id)
        self.assertEqual(intent1.human_watermark, 10)

    def test_message_and_character_budgets_leave_unconsumed_rows_unread(self):
        policy = CatchupPolicy(max_messages=2, max_excerpt_chars=20, max_summary_chars=35)
        result = build([row(i, body="x" * 1000) for i in range(1, 6)], policy=policy)
        self.assertLessEqual(len(result["summary"].body), 35)
        self.assertEqual(len(result["summary"].sources), 2)
        self.assertEqual(result["night"].unread_watermark, 2)
        self.assertTrue(result["has_more"])

    def test_whitespace_only_is_skipped(self):
        result = build([row(1, body=" \n\t "), row(2, body="alpha\nbeta")])
        self.assertEqual(result["summary"].body, "[1] alpha beta")
        self.assertEqual(result["skipped_rows"], 1)

    def test_page_budget_is_bounded_for_whole_wake(self):
        policy = CatchupPolicy(max_rows=1, max_batches=2)
        first = build([row(1)], policy=policy)
        second = build_catchup(first["night"], context(), [row(2)], now=1001,
                               high_watermark=10, generation=0, runtime=first["runtime"],
                               policy=policy)
        self.assertEqual(second["reason_codes"], ("catchup_budget",))
        self.assertEqual(second["night"].unread_watermark, 2)
        third = build_catchup(second["night"], context(), [row(3)], now=1002,
                              high_watermark=10, generation=0, runtime=second["runtime"],
                              policy=policy)
        self.assertIsNone(third["summary"])
        self.assertFalse(third["has_more"])

    def test_retention_gap_moves_to_known_high_only_after_exhaustion(self):
        first = build([row(2)], policy=CatchupPolicy(max_rows=1))
        self.assertEqual(first["night"].unread_watermark, 2)
        self.assertTrue(first["has_more"])
        last = build_catchup(first["night"], context(), [], now=1001, high_watermark=10,
                             generation=0, runtime=first["runtime"],
                             policy=CatchupPolicy(max_rows=1))
        self.assertEqual(last["night"].unread_watermark, 10)

    def test_next_wake_processes_only_remaining_unread(self):
        first = build([row(1)], policy=CatchupPolicy(max_rows=1, max_batches=1))
        state = replace(first["night"], sleep_started_at=1001, wake_at=1100,
                        updated_at=1100, transition_deadline=1400)
        result = build_catchup(state, context(), [row(2)], now=1100, high_watermark=2,
                               generation=0, runtime=first["runtime"])
        self.assertEqual(result["summary"].sources[0].source_ids, ("m2",))
        self.assertNotEqual(first["summary"].wake_key, result["summary"].wake_key)

    def test_deadline_and_clock_rollback_reject_catchup(self):
        for now in (999, 1300, 10000):
            with self.subTest(now=now):
                result = build([row(1)], now=now)
                self.assertIsNone(result["summary"])
                self.assertEqual(result["night"].unread_watermark, 0)

    def test_not_waking_does_not_consume(self):
        result = build_catchup(NightState(), context(), [row(1)], now=1000,
                               high_watermark=1, generation=0)
        self.assertFalse(result["applied"])
        self.assertIsNone(result["summary"])

    def test_leaving_waking_purges_transient_summary(self):
        first = build([row(1)])
        result = build_catchup(replace(first["night"], phase="awake"), context(), [],
                               now=1001, high_watermark=10, generation=0, runtime=first["runtime"])
        self.assertNotIn("summary", result["runtime"])
        self.assertIn("summary", first["runtime"])

    def test_summary_expiry_purges_body_without_reopening_completed_batch(self):
        first = build([row(1)], policy=CatchupPolicy(max_age_seconds=101))
        result = build_catchup(first["night"], context(), [], now=1003,
                               high_watermark=10, generation=0, runtime=first["runtime"])
        self.assertNotIn("summary", result["runtime"])
        self.assertTrue(result["runtime"]["completed"])

    def test_window_order_and_limits_are_validated(self):
        for rows in ([row(2), row(1)], [row(1), row(1)], [row(i) for i in range(201)],
                     [{**row(1), "seq": True}]):
            with self.subTest(count=len(rows)), self.assertRaises(ValueError):
                build(rows)

    def test_bad_policy_or_watermark_rejected(self):
        for kwargs in ({"max_rows": 201}, {"max_batches": 0}, {"max_messages": True},
                       {"max_summary_chars": 15}, {"max_age_seconds": float("nan")}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                CatchupPolicy(**kwargs)
        with self.assertRaises(ValueError):
            build([], high_watermark=-1)

    def test_payload_remains_bounded_with_unicode_body(self):
        result = build([row(i, body="\u672a\u8bfb" * 1000) for i in range(1, 17)])
        self.assertLessEqual(len(canonical_json(result["runtime"])), 32768)
        self.assertLessEqual(len(result["summary"].body), 2048)


class ProvenanceTests(unittest.TestCase):
    def test_other_scope_and_revision_rejected(self):
        for field, value in (("bot_id", "b2"), ("persona_id", "p2"), ("adapter_id", "a2"),
                             ("platform", "p2"), ("scene_kind", "group"), ("scene_id", "s2"),
                             ("instance_id", "i2"), ("persona_revision", "v2"),
                             ("identity_revision", "v2"), ("audience", ("other",))):
            with self.subTest(field=field):
                result = build([row(1, context=context(**{field: value}))])
                self.assertIsNone(result["summary"])
                self.assertEqual(result["skipped_rows"], 1)

    def test_group_members_remain_separate_original_subjects(self):
        current = context(scene_kind="group", audience=("human", "human2"))
        rows = [
            row(1, context=current),
            row(2, context=replace(current, account_id="human2"), actor_id="human2"),
        ]
        result = build_catchup(waking(), current, rows, now=1000, high_watermark=2, generation=0)
        self.assertEqual(tuple(ref.subject_id for ref in result["summary"].sources),
                         ("human", "human2"))

    def test_summary_dream_diary_or_bot_content_is_not_original(self):
        for kind in ("summary", "dream", "diary", "fact", "observation", "bot_action_succeeded"):
            with self.subTest(kind=kind):
                self.assertIsNone(build([row(1, event_type=kind)])["summary"])
        for role in ("bot", "unknown"):
            with self.subTest(role=role):
                self.assertIsNone(build([row(1, actor_role=role)])["summary"])

    def test_message_with_secondary_summary_evidence_is_rejected(self):
        ref = EvidenceRef("synthetic", "summary1", context(), "bot", "bot", "summary", 900,
                          source_ids=("original",))
        self.assertIsNone(build([row(1, evidence=(ref,))])["summary"])

    def test_expired_original_and_future_original_are_rejected(self):
        for at in (0, 1001):
            with self.subTest(at=at):
                self.assertIsNone(build([row(1, occurred_at=at)],
                                        policy=CatchupPolicy(max_age_seconds=100))["summary"])
        ref = EvidenceRef("local", "r1", context(), "human", "human", "interaction", 900,
                          expires_at=999)
        self.assertIsNone(build([row(1, evidence=(ref,))])["summary"])

    def test_expiry_never_outlives_original_reference(self):
        ref = EvidenceRef("local", "r1", context(), "human", "human", "interaction", 900,
                          expires_at=1100)
        result = build([row(1, evidence=(ref,))])
        self.assertEqual(result["summary"].evidence.expires_at, 1100)
        self.assertEqual(result["summary"].sources[0].expires_at, 1100)

    def test_spoofed_actor_unreliable_key_and_inconsistent_row_rejected(self):
        for bad in (row(1, actor_id="other"), row(1, reliable_source=False),
                    {**row(1), "event_key": "wrong"}, {**row(1), "occurred_at": 1000},
                    {**row(1), "account_id": "other"}, {**row(1), "metadata_json": {}}):
            with self.subTest(bad=bad):
                self.assertIsNone(build([bad])["summary"])

    def test_runtime_cannot_cross_scope_or_clear_generation(self):
        first = build([row(1)])
        with self.assertRaises(ValueError):
            build_catchup(waking(), context(scene_id="other"), [], now=1000,
                           high_watermark=1, generation=0, runtime=first["runtime"])
        with self.assertRaises(ValueError):
            build([row(2)], generation=1, runtime=first["runtime"])

    def test_oversize_source_is_skipped_not_truncated_into_false_provenance(self):
        huge = context(audience=tuple(f"{i}" + "x" * 500 for i in range(20)))
        result = build_catchup(waking(), huge, [row(1, context=huge)], now=1000,
                               high_watermark=1, generation=0)
        self.assertIsNone(result["summary"])
        self.assertEqual(result["skipped_rows"], 1)


class HandoffTests(unittest.TestCase):
    def test_optional_intent_has_no_send_side_effect_and_stable_id(self):
        result = build([row(1)])
        intent = catchup_intent(result["summary"], result["night"], context(),
                                now=1000, generation=0)
        self.assertEqual(intent.purpose, "wake_catchup")
        self.assertEqual(intent.status.value, "pending")
        self.assertEqual(intent.expires_at, 1300)
        self.assertEqual(intent.evidence[0].kind, ContentKind.SUMMARY)
        self.assertEqual(intent.evidence[1].kind, ContentKind.INTERACTION)

    def test_uncommitted_watermark_cannot_make_intent(self):
        result = build([row(1)])
        self.assertIsNone(catchup_intent(result["summary"], waking(), context(),
                                        now=1000, generation=0))

    def test_missing_route_cannot_make_intent(self):
        result = build([row(1)])
        self.assertIsNone(catchup_intent(result["summary"], result["night"],
                                        context(route=None), now=1000, generation=0))

    def test_intent_rechecks_scope_revision_generation_and_deadline(self):
        result = build([row(1)])
        for ctx, at, generation in ((context(scene_id="other"), 1000, 0),
                                    (context(persona_revision="2"), 1000, 0),
                                    (context(identity_revision="2"), 1000, 0),
                                    (context(audience=("other",)), 1000, 0),
                                    (context(), 1300, 0), (context(), 1000, 1)):
            with self.subTest(ctx=ctx, at=at, generation=generation):
                self.assertIsNone(catchup_intent(result["summary"], result["night"], ctx,
                                                now=at, generation=generation))

    def test_old_wake_summary_not_reused(self):
        result = build([row(1)])
        next_wake = replace(result["night"], sleep_started_at=1010, wake_at=1100,
                            updated_at=1100, transition_deadline=1400)
        self.assertIsNone(catchup_intent(result["summary"], next_wake, context(),
                                        now=1100, generation=0))

    def test_seeded_pages_never_repeat_original_source(self):
        rng = random.Random(20261105)
        for _ in range(100):
            rows = [row(i) for i in range(1, rng.randint(5, 70))]
            policy = CatchupPolicy(max_rows=rng.randint(2, 20), max_messages=rng.randint(1, 5))
            state, runtime = waking(), None
            seen = set()
            for batch in range(policy.max_batches + 1):
                page = [r for r in rows if r["seq"] > state.unread_watermark][:policy.max_rows]
                result = build_catchup(state, context(), page, now=1000 + batch,
                                       high_watermark=rows[-1]["seq"], generation=0,
                                       runtime=runtime, policy=policy)
                if result["summary"]:
                    keys = {ref.source_id for ref in result["summary"].sources}
                    self.assertFalse(seen & keys)
                    seen |= keys
                self.assertGreaterEqual(result["night"].unread_watermark, state.unread_watermark)
                self.assertLessEqual(result["night"].unread_watermark, rows[-1]["seq"])
                state = NightState(**json.loads(canonical_json(result["night"])))
                runtime = json.loads(canonical_json(result["runtime"]))
                if not result["has_more"]:
                    break
            self.assertLessEqual(runtime["batches"], policy.max_batches)


if __name__ == "__main__":
    unittest.main()
