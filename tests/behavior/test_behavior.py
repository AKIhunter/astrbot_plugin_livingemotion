"""Synthetic transports + real SQLite. No provider or platform connection."""

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from astrbot_plugin_livingemotion.adapters.behavior_sender import AstrBotBehaviorSender
from astrbot_plugin_livingemotion.contracts import (
    Availability, BehaviorIntent, BotAffect, ContentKind, Context, Event, EvidenceRef,
    NightState, Relationship, StateWrite, stable_key, to_dict,
)
from astrbot_plugin_livingemotion.ports.memory import Material, RecallResult, ValidationResult
from astrbot_plugin_livingemotion.services.behavior import (
    BehaviorHistory, BehaviorPolicy, BehaviorService, BehaviorSnapshot,
    SendReceipt, SendRequest,
)
from astrbot_plugin_livingemotion.storage import SQLiteStore


class BehaviorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "behavior.sqlite3"
        self.now = datetime(2026, 11, 5, 12, tzinfo=timezone.utc).timestamp()
        self.store = SQLiteStore(self.path, clock=lambda: self.now)
        await self.store.open()
        self.config = BehaviorPolicy(autonomy_enabled=True, timezone="UTC")
        self.snapshots = {}
        self.catalog = {}
        self.model_requests = []
        self.platform_calls = []
        self.services = []
        self.identity_ok = True
        self.evidence_ok = True
        self.on_model = None
        self.on_send = None
        self.on_validate = None
        self.outcome = "confirmed"
        self.context = await self.add_context("room")
        self.service = self.new_service()

    async def asyncTearDown(self):
        for service in self.services:
            await service.close()
        await self.store.close()

    async def add_context(self, room, **changes):
        context = Context(
            "bot", "native", "synthetic-adapter", "synthetic-instance", "private", room,
            "human", audience=("human", "bot"),
            route=f"synthetic-instance:FriendMessage:{room}", **changes,
        )
        self.snapshots[context.scope_key] = BehaviorSnapshot(
            context, BotAffect(social_need=.8), Relationship(score=700),
            NightState(), "Synthetic native persona", True, "loaded-1",
        )
        self.config = replace(self.config, whitelist=self.config.whitelist | {context.scope_key})
        await self.event(context, f"seed-{room}")
        return context

    async def event(self, context=None, source="new-human", role="human", event_type="message"):
        context = context or self.context
        generation = await self.store.get_generation(context)
        return await self.store.commit_event(Event(
            source, "synthetic", event_type, context, role, self.now, source,
            actor_id=context.account_id if role == "human" else context.bot_id,
            body="Synthetic source material.",
        ), generation)

    async def current(self, context):
        return self.snapshots.get(context.scope_key)

    async def validate_identity(self, context):
        return self.identity_ok

    async def validate_evidence(self, request, materials):
        if self.on_validate:
            await self.on_validate(request, materials)
        return ValidationResult(self.evidence_ok, materials if self.evidence_ok else ())

    async def model(self, request):
        self.model_requests.append(request)
        if self.on_model:
            return await self.on_model(request)
        return "Synthetic generated text."

    async def sender(self, request):
        if self.on_send:
            await self.on_send(request)
        if not await request.authorize():
            return SendReceipt(request.intent_id, request.context.route, "rejected")
        self.platform_calls.append(request)
        if self.outcome is None:
            return None
        if self.outcome == "partial":
            return SendReceipt(request.intent_id, request.context.route, "confirmed",
                               f"ack-{request.intent_id}", 1, 2)
        return SendReceipt(
            request.intent_id, request.context.route, self.outcome,
            f"ack-{request.intent_id}" if self.outcome == "confirmed" else None,
            1 if self.outcome == "confirmed" else 0,
        )

    async def history(self, context, period, exclude_intent_id):
        """Test-only catalogue stands in for foundation's missing read index.

        All statuses, watermarks and quota totals come from public SQLite APIs.
        The catalogue is retained by the harness across reopen, not production state.
        """
        global_used = await self.store.quota_usage(period=period, pool="send", purpose="behavior")
        scope_used, unanswered, attempts = 0, 0, []
        watermark = await self.store.human_watermark(context)
        for intent_id, original in self.catalog.items():
            row = await self.store.get_intent(original, intent_id)
            if not row:
                continue
            day = datetime.fromtimestamp(row["created_at"], timezone.utc).date().isoformat()
            reserved = bool(row["reservation_id"])
            if intent_id == exclude_intent_id:
                if reserved and day == period:
                    global_used -= 1
                continue
            if original.scope_key != context.scope_key:
                continue
            if reserved and day == period:
                scope_used += 1
            if row["status"] in ("sending", "succeeded", "unknown"):
                attempts.append(row["updated_at"])
                old_watermark = row["value"].get("human_watermark", watermark)
                if watermark <= old_watermark:
                    unanswered += 1
        return BehaviorHistory(global_used, scope_used, max(attempts, default=None), unanswered)

    def new_service(self, *, store=None, **changes):
        args = dict(
            current=self.current, validate_identity=self.validate_identity,
            validate_evidence=self.validate_evidence, model=self.model, sender=self.sender,
            history=self.history, policy=lambda: self.config, clock=lambda: self.now,
        )
        args.update(changes)
        service = BehaviorService(store or self.store, **args)
        self.services.append(service)
        return service

    async def execute(self, intent_id="i", context=None, *, service=None, purpose="proactive"):
        context = context or self.context
        self.catalog[intent_id] = context
        return await (service or self.service).execute(context, intent_id=intent_id, purpose=purpose)

    async def succeeded_events(self, context=None):
        return [row for row in await self.store.read_window(context or self.context)
                if row["metadata_json"]["event_type"] == "bot_action_succeeded"]

    async def restart(self):
        for service in self.services:
            await service.close()
        await self.store.close()
        self.store = SQLiteStore(self.path, clock=lambda: self.now)
        await self.store.open()
        result = await self.store.recover_inflight()
        self.service = self.new_service()
        return result

    async def test_default_disabled_and_preview_is_read_only(self):
        self.config = BehaviorPolicy()
        before = await self.store.health()
        result = await self.service.preview_behavior(self.context)
        self.assertFalse(result.eligible)
        self.assertIn("autonomy_disabled", result.reason_codes)
        self.assertEqual((result.model_calls, result.sends), (0, 0))
        self.assertEqual((await self.store.health())["counts"], before["counts"])
        self.assertEqual(self.model_requests, [])
        self.assertEqual(self.platform_calls, [])

    async def test_control_paths_retain_content_and_generation_emotion(self):
        from astrbot_plugin_livingemotion.domain.emotion import decay_affect
        for purpose in ("catchup", "closing", "dream_wake"):
            affect = BotAffect(pleasure=.8, arousal=.8, updated_at=self.now)
            old = await self.store.get_state(self.context, "bot")
            self.assertTrue((await self.store.write_states(self.context, 0, [
                StateWrite("bot", to_dict(affect), old.version if old else 0)])).accepted)
            expected = ",".join(decay_affect(affect, now=self.now).labels)

            async def generate():
                old = await self.store.get_state(self.context, "bot")
                await self.store.write_states(self.context, 0, [
                    StateWrite("bot", to_dict(BotAffect(pleasure=-.8, updated_at=self.now)),
                               old.version)])
                return "控制消息正文"

            async def permit(*args):
                return True

            result = await self.service.execute_control(
                self.context, intent_id=purpose, purpose=purpose, generate=generate,
                authorize=permit, on_submit=permit, generation=0, revision="loaded-1")
            self.assertEqual(result, "confirmed")
            row = await self.store.get_intent(self.context, purpose)
            self.assertEqual(row["value"]["content"], "控制消息正文")
            self.assertEqual(row["value"]["emotion_snapshot"], expected)
            self.assertEqual(row["value"]["transport_receipt"]["status"], "confirmed")
            self.assertTrue(row["value"]["transport_receipt"]["receipt_id"])
        counts = await self.store.send_statistics(self.context, "2026-11-05")
        self.assertEqual(counts["global"]["confirmed"], 3)
        self.assertEqual(counts["global"]["consumed"], 3)

    async def test_control_unknown_still_keeps_body_and_does_not_count_confirmed(self):
        self.outcome = None
        async def permit(*args):
            return True
        async def text():
            return "结果未知也保留正文"
        result = await self.service.execute_control(
            self.context, intent_id="unknown-control", purpose="closing", generate=text,
            authorize=permit, on_submit=permit, generation=0, revision="loaded-1")
        self.assertEqual(result, "unknown")
        row = await self.store.get_intent(self.context, "unknown-control")
        self.assertEqual(row["value"]["content"], "结果未知也保留正文")
        self.assertTrue(row["value"]["emotion_snapshot"])
        counts = await self.store.send_statistics(self.context, "2026-11-05")
        self.assertEqual(counts["global"]["confirmed"], 0)
        self.assertEqual(counts["global"]["unknown"], 1)

    async def test_eligible_preview_does_not_retrieve_generate_or_write(self):
        async def forbidden(*args):
            self.fail("preview invoked a side-effect dependency")
        service = self.new_service(materials=forbidden, model=forbidden, sender=forbidden)
        before = (await self.store.health())["counts"]
        evaluation = await service.evaluate(self.context)
        self.assertTrue(evaluation.eligible)
        self.assertGreater(evaluation.score, .35)
        self.assertTrue((await service.preview_behavior(self.context)).eligible)
        self.assertEqual((await self.store.health())["counts"], before)

    async def test_all_policy_hard_vetoes_precede_scoring(self):
        base = self.config
        cases = (
            ({"enabled": False}, "plugin_disabled"),
            ({"mode": "observe_only"}, "observe_only"),
            ({"conflict": True}, "owner_conflict"),
            ({"autonomy_enabled": False}, "autonomy_disabled"),
            ({"timezone": None}, "timezone_required"),
            ({"whitelist": frozenset()}, "not_whitelisted"),
            ({"muted_scopes": frozenset((self.context.scope_key,))}, "muted"),
            ({"active_hours": ((0, 60),)}, "outside_active_hours"),
            ({"dnd": (720, 780)}, "do_not_disturb"),
        )
        for changes, reason in cases:
            with self.subTest(reason=reason):
                self.config = replace(base, **changes)
                result = await self.service.evaluate(self.context)
                self.assertIn(reason, result.reason_codes)
                self.assertIsNone(result.score)
        self.assertEqual(self.model_requests, [])

    async def test_groups_need_separate_switch(self):
        group = replace(self.context, scene_kind="group")
        self.config = replace(self.config, whitelist=frozenset((group.scope_key,)))
        self.snapshots[group.scope_key] = replace(
            self.snapshots[self.context.scope_key], context=group,
        )
        preview = await self.service.preview_behavior(group)
        self.assertIn("group_autonomy_disabled", preview.reason_codes)
        self.config = replace(self.config, group_autonomy_enabled=True)
        self.assertTrue((await self.service.preview_behavior(group)).eligible)

    async def test_explicit_timezone_dnd_boundaries_and_overnight_active_hours(self):
        self.config = replace(self.config, timezone="Asia/Shanghai")
        for hour, minute, blocked in ((0, 59, False), (1, 0, True), (7, 59, True), (8, 0, False)):
            self.now = datetime(2026, 11, 5, hour, minute, tzinfo=timezone.utc).timestamp() - 28800
            result = await self.service.evaluate(self.context)
            self.assertEqual("do_not_disturb" in result.reason_codes, blocked)
        self.config = replace(self.config, active_hours=((1320, 60),))
        self.now = datetime(2026, 11, 5, 15, tzinfo=timezone.utc).timestamp()
        self.assertTrue((await self.service.evaluate(self.context)).eligible)
        self.now += 3600
        self.assertTrue((await self.service.evaluate(self.context)).eligible)
        self.now += 3600
        self.assertFalse((await self.service.evaluate(self.context)).eligible)

    async def test_missing_persistent_history_fails_closed(self):
        service = self.new_service(history=None)
        result = await self.execute(service=service)
        self.assertIn("behavior_history_unavailable", result.reason_codes)
        self.assertEqual(self.model_requests, [])

    async def test_missing_or_forged_route_is_rejected(self):
        for route, verified in ((None, True), ("123456", False)):
            context = replace(self.context, route=route)
            self.snapshots[context.scope_key] = replace(
                self.snapshots[context.scope_key], context=context, route_verified=verified,
            )
            result = await self.execute(str(route), context)
            self.assertIn("unverified_route", result.reason_codes)
        self.assertEqual(self.platform_calls, [])

    async def test_sleep_energy_and_availability_callback(self):
        original = self.snapshots[self.context.scope_key]
        for night, reason in ((NightState(phase="asleep"), "sleeping"),
                              (NightState(phase="settling"), "sleeping"),
                              (NightState(energy=19), "low_energy"), (None, "availability_unavailable")):
            self.snapshots[self.context.scope_key] = replace(original, night=night)
            self.assertIn(reason, (await self.service.evaluate(self.context)).reason_codes)
        async def availability(context):
            return Availability(True)
        service = self.new_service(availability=availability)
        self.assertTrue((await service.evaluate(self.context)).eligible)
        async def sleeping(context):
            return Availability(False, ("sleeping",))
        self.assertIn("unavailable", (
            await self.new_service(availability=sleeping).evaluate(self.context)
        ).reason_codes)

    async def test_success_requires_confirmation_and_persists_real_event(self):
        result = await self.execute()
        self.assertEqual(result.status, "succeeded")
        self.assertTrue(result.receipt_recorded)
        self.assertEqual((result.model_calls, result.sender_calls), (1, 1))
        row = await self.store.get_intent(self.context, "i")
        self.assertEqual(row["status"], "succeeded")
        events = await self.succeeded_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["metadata_json"]["actor_role"], "bot")
        self.assertEqual(events[0]["metadata_json"]["source_id"], "ack-i")
        self.assertTrue(events[0]["metadata_json"]["evidence"])
        self.assertEqual(await self.store.quota_usage(period="2026-11-05", pool="send"), 1)
        self.assertEqual(self.model_requests[0].snapshot.persona_prompt, "Synthetic native persona")

    async def test_log_keeps_generation_emotion_after_current_affect_changes(self):
        original = self.snapshots[self.context.scope_key]
        self.snapshots[self.context.scope_key] = replace(
            original, affect=replace(original.affect, labels=("happy", "excited")))
        async def change_mood(request):
            self.snapshots[self.context.scope_key] = replace(
                original, affect=replace(original.affect, labels=("sad",)))
            self.now += 3
            return "Synthetic generated text."
        self.on_model = change_mood
        result = await self.execute()
        self.assertEqual(result.status, "succeeded")
        row = await self.store.get_intent(self.context, "i")
        self.assertEqual(row["value"]["emotion_snapshot"], "happy,excited")
        self.assertEqual(row["attempted_at"], row["created_at"] + 3)
        self.assertEqual(self.snapshots[self.context.scope_key].affect.labels, ("sad",))
        self.assertEqual(self.model_requests[0].snapshot.affect.labels, ("happy", "excited"))

    async def test_typed_wake_intent_preserves_watermark_generation_and_deadline(self):
        watermark = await self.store.human_watermark(self.context)
        proposal = BehaviorIntent("wake", self.context, "wake_catchup", self.now - 1,
                                  self.now + 60, 0, human_watermark=watermark)
        self.catalog[proposal.intent_id] = self.context
        result = await self.service.execute_intent(proposal)
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(self.model_requests[0].intent, proposal)
        self.assertEqual((await self.store.get_intent(self.context, "wake"))["expires_at"],
                         proposal.expires_at)
        self.assertEqual(await self.store.quota_usage(
            period="2026-11-05", pool="send", purpose="behavior",
        ), 1)

    async def test_typed_old_wake_intent_is_not_rebased_onto_new_human_watermark(self):
        proposal = BehaviorIntent(
            "wake", self.context, "wake_catchup", self.now, self.now + 60, 0,
            human_watermark=await self.store.human_watermark(self.context),
        )
        await self.event(source="human-after-summary")
        result = await self.service.execute_intent(proposal)
        self.assertEqual(result.reason_codes, ("new_human_message",))
        self.assertEqual(self.model_requests, [])
        self.assertEqual(self.platform_calls, [])

    async def test_no_materials_means_no_model_and_no_send(self):
        async def empty(request):
            return RecallResult()
        result = await self.execute(service=self.new_service(materials=empty))
        self.assertEqual(result.status, "cancelled")
        self.assertIn("no_qualified_materials", result.reason_codes)
        self.assertEqual(self.model_requests, [])
        self.assertEqual(self.platform_calls, [])

    async def test_model_errors_and_invalid_output_consume_quota_not_success(self):
        async def broken(request):
            raise RuntimeError("synthetic")
        self.on_model = broken
        result = await self.execute("broken")
        self.assertEqual(result.status, "failed")
        self.on_model = lambda request: asyncio.sleep(0, result="")
        self.assertEqual((await self.execute("empty")).status, "failed")
        self.assertEqual(self.platform_calls, [])
        self.assertEqual(await self.succeeded_events(), [])
        self.assertEqual(await self.store.quota_usage(period="2026-11-05", pool="send"), 2)

    async def test_model_timeout_has_no_dispatch(self):
        self.config = replace(self.config, model_timeout_seconds=.01)
        self.on_model = lambda request: asyncio.sleep(10, result="late")
        result = await self.execute()
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.reason_codes, ("model_unavailable",))
        self.assertEqual(self.platform_calls, [])

    async def test_none_partial_and_timeout_are_unknown_without_success_evidence(self):
        for index, outcome in enumerate((None, "partial", "timeout")):
            context = await self.add_context(f"unknown-{index}")
            self.outcome = outcome
            if outcome == "timeout":
                self.config = replace(self.config, send_timeout_seconds=.01)
                loop = asyncio.get_running_loop()
                tick = loop.time()
                release = asyncio.Event()

                async def timeout_sender(request):
                    nonlocal tick
                    self.assertTrue(await request.authorize())
                    self.platform_calls.append(request)
                    # Expire only after real authorization and synthetic dispatch.
                    tick += .02
                    # A later release makes a missing timeout fail, not hang.
                    loop.call_at(tick, release.set)
                    await release.wait()

                service = self.new_service(sender=timeout_sender)
                with patch.object(loop, "time", lambda: tick):
                    result = await self.execute(f"i-{index}", context, service=service)
                self.assertEqual(result.reason_codes, ("send_unavailable",))
            else:
                service = self.service
                result = await self.execute(f"i-{index}", context, service=service)
            self.assertEqual(result.status, "unknown")
            self.assertFalse(result.receipt_recorded)
            self.assertEqual(await self.succeeded_events(context), [])
            self.assertEqual((await self.store.get_intent(context, f"i-{index}"))["status"],
                             "unknown")
            self.assertEqual((await self.execute(f"i-{index}", context, service=service)).status,
                             "unknown")
        self.assertEqual(len(self.model_requests), 3)
        self.assertEqual(len(self.platform_calls), 3)
        self.assertEqual(await self.store.quota_usage(period="2026-11-05", pool="send"), 3)

    async def test_timeout_during_authorization_is_unknown_without_dispatch(self):
        self.config = replace(self.config, send_timeout_seconds=.01)
        loop = asyncio.get_running_loop()
        tick = loop.time()
        authorizing = asyncio.Event()
        guard_waiting = asyncio.Event()
        authorized = asyncio.Event()
        release = asyncio.Event()

        async def pending_validation(request, materials):
            nonlocal tick
            if authorizing.is_set():
                guard_waiting.set()
                # Expire inside the real guard, before authorization can finish.
                tick += .02
                loop.call_at(tick, release.set)
                await release.wait()

        async def timeout_sender(request):
            authorizing.set()
            self.assertTrue(await request.authorize())
            authorized.set()
            self.platform_calls.append(request)

        self.on_validate = pending_validation
        service = self.new_service(sender=timeout_sender)
        with patch.object(loop, "time", lambda: tick):
            result = await self.execute(service=service)
        self.assertTrue(guard_waiting.is_set())
        self.assertFalse(authorized.is_set())
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason_codes, ("send_unavailable",))
        self.assertFalse(result.receipt_recorded)
        self.assertEqual((result.model_calls, result.sender_calls), (1, 1))
        self.assertEqual((await self.store.get_intent(self.context, "i"))["status"], "unknown")
        self.assertEqual(await self.succeeded_events(), [])
        self.assertEqual((await self.execute(service=service)).status, "unknown")
        self.assertEqual(len(self.model_requests), 1)
        self.assertEqual(self.platform_calls, [])
        self.assertEqual(await self.store.quota_usage(period="2026-11-05", pool="send"), 1)

    async def test_explicit_send_rejection_is_failed_not_succeeded(self):
        self.outcome = "rejected"
        self.assertEqual((await self.execute()).status, "failed")
        self.assertEqual(await self.succeeded_events(), [])

    async def test_malformed_and_uncorrelated_receipts_are_unknown(self):
        self.config = replace(self.config, global_daily_limit=100)
        cases = (
            {"route": "other"}, {"intent_id": "other"}, {"receipt_id": None},
            {"confirmed_parts": True}, {"confirmed_parts": 2}, {"total_parts": 0},
            {"status": "unknown"}, {"status": "rejected", "confirmed_parts": 1},
        )
        for index, fields in enumerate(cases):
            context = await self.add_context(f"bad-ack-{index}")
            async def sender(request, fields=fields):
                self.assertTrue(await request.authorize())
                return replace(SendReceipt(
                    request.intent_id, request.context.route, "confirmed", "synthetic-ack", 1,
                ), **fields)
            result = await self.execute(
                f"bad-ack-{index}", context, service=self.new_service(sender=sender),
            )
            self.assertEqual(result.status, "unknown", fields)
            self.assertEqual(await self.succeeded_events(context), [])

    async def test_unmatched_or_unguarded_ack_cannot_produce_success(self):
        async def unguarded(request):
            return SendReceipt(request.intent_id, request.context.route, "confirmed", "ack", 1)
        result = await self.execute(service=self.new_service(sender=unguarded))
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason_codes, ("sender_guard_not_used",))
        self.assertEqual(await self.succeeded_events(), [])

    async def test_twenty_same_intents_have_one_attempt_across_service_instances(self):
        other = self.new_service()
        results = await asyncio.gather(*(
            self.execute("same", service=other if index % 2 else self.service)
            for index in range(20)
        ))
        self.assertEqual({result.status for result in results}, {"succeeded"})
        self.assertEqual(len(self.model_requests), 1)
        self.assertEqual(len(self.platform_calls), 1)
        self.assertEqual(len(await self.succeeded_events()), 1)

    async def test_concurrent_different_intents_same_scope_respect_cooldown(self):
        results = await asyncio.gather(*(self.execute(f"i-{n}") for n in range(10)))
        self.assertEqual(sum(result.status == "succeeded" for result in results), 1)
        self.assertEqual(len(self.platform_calls), 1)
        self.assertIn("cooldown", results[-1].reason_codes)

    async def test_two_sqlite_connections_share_one_execution_lane(self):
        other_store = SQLiteStore(self.path, clock=lambda: self.now)
        await other_store.open()
        try:
            other = self.new_service(store=other_store)
            results = await asyncio.gather(
                self.execute("connection-a"), self.execute("connection-b", service=other),
            )
            self.assertEqual(sum(result.status == "succeeded" for result in results), 1)
            self.assertEqual(len(self.platform_calls), 1)
        finally:
            await other.close()
            await other_store.close()

    async def test_global_six_and_scope_two_share_all_purposes(self):
        self.config = replace(self.config, cooldown_seconds=0)
        results = [await self.execute(f"scope-{n}", purpose=purpose)
                   for n, purpose in enumerate(("proactive", "wake_catchup", "another"))]
        self.assertEqual([result.status for result in results], ["succeeded", "succeeded", "rejected"])
        self.assertIn("scope_quota_exhausted", results[-1].reason_codes)
        contexts = [await self.add_context(f"global-{n}") for n in range(12)]
        results = await asyncio.gather(*(
            self.execute(f"global-{n}", context) for n, context in enumerate(contexts)
        ))
        self.assertEqual(sum(result.status == "succeeded" for result in results), 4)
        self.assertEqual(len(self.platform_calls), 6)
        self.assertEqual(await self.store.quota_usage(period="2026-11-05", pool="send"), 6)

    async def test_failed_generation_budget_survives_restart(self):
        async def fail(request):
            raise RuntimeError("synthetic")
        self.on_model = fail
        await self.execute("failed-1")
        await self.execute("failed-2")
        await self.restart()
        self.on_model = None
        self.assertIn("scope_quota_exhausted", (await self.execute("new")).reason_codes)
        self.assertEqual(await self.store.quota_usage(period="2026-11-05", pool="send"), 2)

    async def test_real_quota_transaction_rejects_even_with_stale_history_callback(self):
        for n in range(2):
            await self.store.reserve_quota(
                f"existing-{n}", self.context, 0, period="2026-11-05",
                purpose="behavior", pool="send", limit=6, scope_limit=2,
            )
        async def stale(context, period, exclude):
            return BehaviorHistory()
        result = await self.execute(service=self.new_service(history=stale))
        self.assertEqual(result.status, "cancelled")
        self.assertEqual(result.reason_codes, ("quota_exhausted",))
        self.assertEqual(self.model_requests, [])

    async def test_cooldown_and_unanswered_backoff_survive_restart_and_midnight(self):
        await self.execute("first")
        await self.restart()
        self.assertIn("cooldown", (await self.execute("too-soon")).reason_codes)
        self.now += 7200
        await self.execute("second")
        self.now += 86400
        await self.restart()
        result = await self.execute("next-day")
        self.assertIn("unanswered_backoff", result.reason_codes)
        await self.event(source="human-replies")
        self.assertEqual((await self.execute("after-human")).status, "succeeded")

    async def test_unknowns_count_conservatively_toward_unanswered_backoff(self):
        self.outcome = "partial"
        self.assertEqual((await self.execute("partial")).status, "unknown")
        self.now += 7200
        self.outcome = None
        self.assertEqual((await self.execute("unconfirmed")).status, "unknown")
        self.now += 86400
        await self.restart()
        self.assertIn("unanswered_backoff", (await self.execute("new")).reason_codes)
        self.assertEqual(len(self.platform_calls), 2)

    async def test_generation_crossing_midnight_cancels_old_day_reservation(self):
        self.now = datetime(2026, 11, 5, 23, 59, tzinfo=timezone.utc).timestamp()
        async def midnight(request):
            self.now += 120
            return "Stale day content."
        self.on_model = midnight
        result = await self.execute("before")
        self.assertEqual(result.status, "cancelled")
        self.assertIn("quota_period_changed", result.reason_codes)
        self.assertEqual(self.platform_calls, [])
        self.on_model = None
        self.assertEqual((await self.execute("after")).status, "succeeded")
        self.assertEqual(await self.store.quota_usage(period="2026-11-05", pool="send"), 1)
        self.assertEqual(await self.store.quota_usage(period="2026-11-06", pool="send"), 1)

    async def test_human_arrival_during_generation_cancels_but_other_scope_does_not(self):
        other = await self.add_context("other")
        async def new_human(request):
            await self.event(source="new-human")
            return "Old content."
        self.on_model = new_human
        result = await self.execute("cancel")
        self.assertEqual(result.status, "cancelled")
        self.assertIn("new_human_message", result.reason_codes)
        async def other_human(request):
            await self.event(other, "other-human")
            return "Current content."
        self.on_model = other_human
        self.assertEqual((await self.execute("keep")).status, "succeeded")

    async def test_bot_preface_and_tool_receipts_never_self_cancel(self):
        watermark = await self.store.human_watermark(self.context)
        async def bot_and_tool(request):
            await self.event(source="bot-prefix", role="bot", event_type="message")
            await self.event(source="tool", role="unknown", event_type="tool_result")
            return "Final text."
        self.on_model = bot_and_tool
        result = await self.execute()
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(await self.store.human_watermark(self.context), watermark)

    async def test_generation_revision_route_audience_or_lifecycle_change_cancels(self):
        changes = (
            {"persona_revision": "new"}, {"persona_id": "different"},
            {"identity_revision": "unbound"}, {"route": "some-other-route"},
            {"audience": ("new-audience",)}, {"account_id": "new-account"},
        )
        for n, fields in enumerate(changes):
            context = await self.add_context(f"changed-{n}")
            async def change(request, context=context, fields=fields):
                snapshot = self.snapshots[context.scope_key]
                self.snapshots[context.scope_key] = replace(
                    snapshot, context=replace(snapshot.context, **fields),
                )
                return "Must be discarded."
            self.on_model = change
            result = await self.execute(f"change-{n}", context)
            self.assertEqual(result.status, "cancelled")
        self.assertEqual(self.platform_calls, [])

    async def test_persona_prompt_and_lifecycle_epoch_change_cancel(self):
        for index, fields in enumerate(({"persona_prompt": "updated"},
                                         {"lifecycle_revision": "reloaded"})):
            context = await self.add_context(f"epoch-{index}")
            async def change(request, context=context, fields=fields):
                self.snapshots[context.scope_key] = replace(
                    self.snapshots[context.scope_key], **fields,
                )
                return "Old text."
            self.on_model = change
            self.assertEqual((await self.execute(f"epoch-{index}", context)).status, "cancelled")
        self.assertEqual(self.platform_calls, [])

    async def test_unbinding_discards_whole_generation_not_only_citations(self):
        async def unbind(request):
            self.identity_ok = False
            self.evidence_ok = False
            return "Secret old-account content."
        self.on_model = unbind
        result = await self.execute()
        self.assertEqual(result.status, "cancelled")
        self.assertEqual(self.platform_calls, [])

    async def test_evidence_revoked_without_context_change_cancels(self):
        async def revoke(request):
            self.evidence_ok = False
            return "Revoked material."
        self.on_model = revoke
        result = await self.execute()
        self.assertEqual(result.status, "cancelled")
        self.assertEqual(result.reason_codes, ("evidence_invalid",))

    async def test_material_scope_kind_holder_and_summary_provenance_are_enforced(self):
        self.config = replace(self.config, global_daily_limit=100)
        changes = (
            {"context": {"bot_id": "other"}}, {"context": {"persona_id": "other"}},
            {"context": {"scene_id": "other"}}, {"context": {"platform": "other"}},
            {"context": {"adapter_id": "other"}}, {"context": {"account_id": "other"}},
            {"context": {"audience": ("stranger",)}}, {"holder_id": "other"},
            {"kind": ContentKind.DREAM}, {"kind": ContentKind.DIARY},
            {"kind": ContentKind.SUMMARY},
        )
        for index, changeset in enumerate(changes):
            context = await self.add_context(f"material-{index}")
            async def materials(request, changeset=changeset):
                ref = EvidenceRef(
                    "synthetic", "evidence-id", request.context, "human", "bot",
                    ContentKind.INTERACTION, self.now,
                )
                fields = dict(changeset)
                if "context" in fields:
                    fields["context"] = replace(request.context, **fields["context"])
                return RecallResult((Material(replace(ref, **fields), "Synthetic."),))
            result = await self.execute(
                f"material-{index}", context, service=self.new_service(materials=materials),
            )
            self.assertEqual(result.status, "cancelled", changeset)
        self.assertEqual(self.model_requests, [])
        self.assertEqual(self.platform_calls, [])

    async def test_expired_material_after_generation_is_not_sent(self):
        async def materials(request):
            ref = EvidenceRef("synthetic", "expiring", request.context, "human", "bot",
                              ContentKind.FACT, self.now, expires_at=self.now + 1)
            return RecallResult((Material(ref, "Synthetic expiring material."),))
        async def model(request):
            self.now += 2
            return "Stale evidence."
        self.on_model = model
        result = await self.execute(service=self.new_service(materials=materials))
        self.assertEqual(result.reason_codes, ("evidence_invalid",))
        self.assertEqual(self.platform_calls, [])

    async def test_input_and_output_limits_are_enforced(self):
        self.config = replace(self.config, max_input_chars=1)
        result = await self.execute("large-input")
        self.assertEqual(result.reason_codes, ("model_input_too_large",))
        self.assertEqual(self.model_requests, [])
        self.config = replace(self.config, max_input_chars=12000, max_output_chars=1)
        result = await self.execute("large-output")
        self.assertEqual(result.reason_codes, ("model_output_invalid",))
        self.assertEqual(self.platform_calls, [])

    async def test_clock_rollback_and_expired_intent_cancel_after_generation(self):
        for index, (delta, reason) in enumerate(((-1, "clock_reversed"), (301, "expired_intent"))):
            context = await self.add_context(f"time-{index}")
            async def model(request, delta=delta):
                self.now += delta
                return "Stale clock."
            self.on_model = model
            result = await self.execute(f"time-{index}", context)
            self.assertEqual(result.status, "cancelled")
            self.assertIn(reason, result.reason_codes)
        self.assertEqual(self.platform_calls, [])

    async def test_final_rechecks_sleep_energy_and_policy(self):
        changes = (
            ("sleep", "snapshot", {"night": NightState(phase="asleep")}, "sleeping"),
            ("energy", "snapshot", {"night": NightState(energy=0)}, "low_energy"),
            ("mute", "policy", {}, "muted"),
            ("whitelist", "policy", {}, "not_whitelisted"),
            ("disabled", "policy", {"autonomy_enabled": False}, "autonomy_disabled"),
        )
        for name, target, fields, reason in changes:
            context = await self.add_context(name)
            base = self.config
            async def update(request, context=context, name=name, target=target, fields=fields):
                if target == "snapshot":
                    self.snapshots[context.scope_key] = replace(
                        self.snapshots[context.scope_key], **fields,
                    )
                elif name == "mute":
                    self.config = replace(self.config, muted_scopes=frozenset((context.scope_key,)))
                elif name == "whitelist":
                    self.config = replace(self.config, whitelist=frozenset())
                else:
                    self.config = replace(self.config, **fields)
                return "Now forbidden."
            self.on_model = update
            result = await self.execute(name, context)
            self.assertEqual(result.status, "cancelled")
            self.assertIn(reason, result.reason_codes)
            self.config = base
        self.assertEqual(self.platform_calls, [])

    async def test_final_quota_and_cooldown_history_are_rechecked(self):
        original = self.history
        changed = False
        async def history(context, period, exclude):
            if changed:
                return BehaviorHistory(6, 2, self.now, 2)
            return await original(context, period, exclude)
        async def update(request):
            nonlocal changed
            changed = True
            return "Disallowed."
        self.on_model = update
        result = await self.execute(service=self.new_service(history=history))
        self.assertEqual(result.status, "cancelled")
        self.assertIn("global_quota_exhausted", result.reason_codes)
        self.assertEqual(self.platform_calls, [])

    async def test_sender_wait_requires_another_guard(self):
        async def human_in_sender(request):
            await self.event(source="after-sending-cas")
        self.on_send = human_in_sender
        result = await self.execute()
        self.assertEqual(result.status, "failed")
        self.assertIn("new_human_message", result.reason_codes)
        self.assertEqual(self.platform_calls, [])

    async def test_last_async_refresh_cannot_hide_sleep_or_human_or_dnd_change(self):
        for mode in ("sleep", "human", "dnd"):
            self.now = datetime(2026, 11, 5, 0, 59, 59, tzinfo=timezone.utc).timestamp()
            context = await self.add_context(f"last-refresh-{mode}")
            service = self.new_service()
            async def after_claim(request, context=context, mode=mode, service=service):
                calls = 0
                async def refresh(current_context):
                    nonlocal calls
                    calls += 1
                    if calls == 3:
                        if mode == "sleep":
                            self.snapshots[context.scope_key] = replace(
                                self.snapshots[context.scope_key], night=NightState(phase="asleep"),
                            )
                        elif mode == "human":
                            await self.event(context, f"last-human-{mode}")
                        else:
                            self.now += 2
                    return self.snapshots[current_context.scope_key]
                service.current = refresh
            self.on_send = after_claim
            with self.subTest(mode=mode):
                result = await self.execute(f"last-{mode}", context, service=service)
                self.assertNotEqual(result.status, "succeeded")
        self.assertEqual(self.platform_calls, [])

    async def test_non_boolean_identity_authorization_is_not_accepted(self):
        async def malformed(context):
            return "false"
        result = await self.execute(service=self.new_service(validate_identity=malformed))
        self.assertIn("identity_invalid", result.reason_codes)
        self.assertEqual(self.platform_calls, [])

    async def test_clear_during_generation_prevents_late_write_and_send(self):
        async def clear(request):
            await self.store.clear_scope(self.context, 0)
            return "Cleared."
        self.on_model = clear
        result = await self.execute()
        self.assertEqual(result.status, "cancelled")
        self.assertEqual(await self.store.get_generation(self.context), 1)
        self.assertEqual(await self.store.read_window(self.context), [])
        self.assertEqual(self.platform_calls, [])
        self.assertEqual(await self.store.quota_usage(period="2026-11-05", pool="send"), 1)

    async def test_close_cancels_and_drains_model_before_store_close(self):
        started = asyncio.Event()
        stopped = asyncio.Event()
        async def waiting(request):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()
        self.on_model = waiting
        task = asyncio.create_task(self.execute())
        await asyncio.wait_for(started.wait(), 2)
        await self.service.close()
        self.assertTrue(stopped.is_set())
        self.assertTrue(task.cancelled())
        self.assertEqual((await self.store.get_intent(self.context, "i"))["status"], "cancelled")
        self.assertEqual(self.platform_calls, [])

    async def test_close_during_send_marks_unknown_and_never_resumes(self):
        started = asyncio.Event()
        async def sending(request):
            self.assertTrue(await request.authorize())
            self.platform_calls.append(request)
            started.set()
            await asyncio.Event().wait()
        service = self.new_service(sender=sending)
        task = asyncio.create_task(self.execute(service=service))
        await asyncio.wait_for(started.wait(), 2)
        await service.close()
        self.assertTrue(task.cancelled())
        self.assertEqual((await self.store.get_intent(self.context, "i"))["status"], "unknown")
        await self.restart()
        self.assertEqual((await self.execute()).status, "unknown")
        self.assertEqual(len(self.platform_calls), 1)
        self.assertEqual(await self.succeeded_events(), [])

    async def test_crash_windows_recover_without_replaying_side_effects(self):
        for index, stage in enumerate(("pending", "reserved", "generating", "sending")):
            context = await self.add_context(stage)
            intent_id = f"crash-{index}"
            self.catalog[intent_id] = context
            intent = BehaviorIntent(
                intent_id, context, "proactive", self.now, self.now + 300, 0,
                human_watermark=await self.store.human_watermark(context),
            )
            await self.store.create_intent(intent)
            if stage != "pending":
                q = stable_key("behavior-send", intent_id)
                await self.store.reserve_quota(
                    q, context, 0, period="2026-11-05", purpose="behavior",
                    pool="send", limit=6, scope_limit=2,
                )
                states = ("pending", "reserved", "generating", "sending")
                for old, new in zip(states, states[1:]):
                    await self.store.transition_intent(
                        context, intent_id, 0, expected_status=old, status=new,
                        reason_code="synthetic_crash", reservation_id=q,
                    )
                    if new == stage:
                        break
        recovered = await self.restart()
        self.assertEqual(recovered, {"unknown": 1, "cancelled": 3})
        for intent_id, context in self.catalog.items():
            result = await self.execute(intent_id, context)
            self.assertIn(result.status, ("unknown", "cancelled"))
        self.assertEqual(self.platform_calls, [])
        self.assertEqual(self.model_requests, [])

    async def test_success_event_commit_failure_is_reported_without_resend(self):
        async def fail(event, generation):
            raise RuntimeError("synthetic database unavailable")
        result = await self.execute(service=self.new_service(record_success=fail))
        self.assertEqual(result.status, "succeeded")
        self.assertFalse(result.receipt_recorded)
        self.assertIn("success_event_not_recorded", result.reason_codes)
        await self.restart()
        await self.execute()
        self.assertEqual(len(self.platform_calls), 1)

    async def test_storage_failure_after_dispatch_stops_executor_and_restart_never_resends(self):
        original = self.store.transition_intent
        async def fail_success(*args, **kwargs):
            if kwargs["status"] == "succeeded":
                raise RuntimeError("synthetic storage failure after confirmed dispatch")
            return await original(*args, **kwargs)
        self.store.transition_intent = fail_success
        result = await self.execute()
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason_codes, ("behavior_storage_fault",))
        self.assertIn("behavior_storage_fault", (await self.execute("next")).reason_codes)
        await self.restart()
        self.assertEqual((await self.execute()).status, "unknown")
        self.assertEqual(len(self.platform_calls), 1)
        self.assertEqual(await self.succeeded_events(), [])

    async def test_bounded_queue_rejects_without_model_or_intent(self):
        self.config = replace(self.config, max_pending=1)
        started = asyncio.Event()
        release = asyncio.Event()
        async def waiting(request):
            started.set()
            await release.wait()
            return "Synthetic."
        self.on_model = waiting
        task = asyncio.create_task(self.execute("first"))
        await asyncio.wait_for(started.wait(), 2)
        result = await self.execute("overflow")
        self.assertEqual(result.reason_codes, ("behavior_queue_full",))
        self.assertIsNone(await self.store.get_intent(self.context, "overflow"))
        release.set()
        await task

    async def test_seeded_interleavings_preserve_at_most_one_and_no_stale_sends(self):
        randomizer = random.Random(20261105)
        self.config = replace(self.config, global_daily_limit=100)
        actions = ["human", "bot", "tool", "identity", "clear", "none"] * 4
        randomizer.shuffle(actions)
        for index, action in enumerate(actions):
            context = await self.add_context(f"seeded-{index}")
            async def interleave(request, context=context, action=action, index=index):
                await asyncio.sleep(0)
                if action in ("human", "bot", "tool"):
                    await self.event(
                        context, f"interleave-{index}",
                        "unknown" if action == "tool" else action,
                        "tool_result" if action == "tool" else "message",
                    )
                elif action == "identity":
                    snapshot = self.snapshots[context.scope_key]
                    self.snapshots[context.scope_key] = replace(
                        snapshot, context=replace(context, identity_revision="revoked"),
                    )
                elif action == "clear":
                    await self.store.clear_scope(context, 0)
                return "Seeded output."
            self.on_model = interleave
            before = len(self.platform_calls)
            results = await asyncio.gather(*(
                self.execute(f"seeded-{index}", context) for _ in range(3)
            ))
            sent = len(self.platform_calls) - before
            self.assertEqual(sent, int(action in ("bot", "tool", "none")), (index, action, results))
            self.assertLessEqual(sent, 1)


class HostSenderTests(unittest.IsolatedAsyncioTestCase):
    async def test_host_bool_none_and_true_never_claim_confirmation(self):
        context = Context("bot", "p", "adapter", "platform", "private", "room",
                          route="platform:FriendMessage:room")
        for raw in (True, None, False):
            calls = []
            async def send(route, chain):
                calls.append((route, chain))
                return raw
            async def recorded(context):
                return context.route
            async def authorize():
                return True
            sender = AstrBotBehaviorSender(send, make_chain=lambda text: [text],
                                           recorded_route=recorded)
            result = await sender(SendRequest("i", context, "Synthetic", authorize))
            self.assertEqual(result.status, "rejected" if raw is False else "unknown")
            self.assertEqual(calls, [(context.route, ["Synthetic"])])

    async def test_route_is_never_synthesized_or_fallen_back_to_id(self):
        context = Context("bot", "p", "adapter", "platform", "private", "12345", route="12345")
        async def forbidden(*args):
            self.fail("unrecorded route sent")
        async def recorded(context):
            return None
        sender = AstrBotBehaviorSender(forbidden, make_chain=lambda text: text,
                                       recorded_route=recorded)
        result = await sender(SendRequest("i", context, "Synthetic", forbidden))
        self.assertEqual(result.status, "rejected")


if __name__ == "__main__":
    unittest.main()
