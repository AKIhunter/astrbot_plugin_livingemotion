"""Public frozen storage-port checks, not production storage wiring."""

from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from astrbot_plugin_livingemotion.contracts import (
    Context, Event, NightState, StateWrite, to_dict,
)
from astrbot_plugin_livingemotion.domain.night import (
    ReplyReceipt, advance_night, apply_interaction, apply_reply_receipt, begin_sleep,
)
from astrbot_plugin_livingemotion.services.catchup import build_catchup, catchup_intent
from astrbot_plugin_livingemotion.storage import SQLiteStore


class PersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "synthetic.sqlite3"
        self.now = 1_800_000_000.0
        self.context = Context("bot", "persona", "adapter", "platform", "private", "room",
                               account_id="human", audience=("human",),
                               route="verified:synthetic:room")
        self.store = SQLiteStore(self.path, clock=lambda: self.now)
        await self.store.open()

    async def asyncTearDown(self):
        await self.store.close()
        self.tmp.cleanup()

    async def restart(self):
        await self.store.close()
        self.store = SQLiteStore(self.path, clock=lambda: self.now)
        await self.store.open()

    def event(self, source="m1"):
        return Event(source, "local", "message", self.context, "human", self.now, source,
                     actor_id="human", body="synthetic")

    async def test_settling_reply_and_offline_wake_survive_restart(self):
        state = begin_sleep(NightState(updated_at=self.now), self.context, now=self.now,
                            wake_at=self.now + 60, request_id="request1")
        result = await self.store.write_states(self.context, 0, [StateWrite("night", to_dict(state))])
        self.assertTrue(result.accepted)
        await self.restart()
        saved = await self.store.get_state(self.context, "night")
        self.now += 1
        state = apply_reply_receipt(
            NightState(**saved.value), ReplyReceipt(self.context, "succeeded", self.now, "request1"),
            now=self.now,
        )
        result = await self.store.write_states(self.context, 0, [
            StateWrite("night", to_dict(state), expected_version=saved.version)
        ])
        self.assertTrue(result.accepted)
        self.now += 100000
        await self.restart()
        saved = await self.store.get_state(self.context, "night")
        state = advance_night(NightState(**saved.value), now=self.now, recovering=True)
        self.assertEqual(state.phase.value, "waking")
        self.assertEqual(state.transition_deadline, self.now + 300)

    async def test_catchup_watermark_and_sources_commit_together(self):
        await self.store.commit_event(self.event(), 0)
        high = await self.store.human_watermark(self.context)
        rows = await self.store.read_window(self.context, after_seq=0, limit=200)
        state = NightState(phase="waking", updated_at=self.now, sleep_started_at=self.now - 100,
                           wake_at=self.now, transition_deadline=self.now + 300)
        result = build_catchup(state, self.context, rows, now=self.now,
                               high_watermark=high, generation=0)
        payload = {**to_dict(result["night"]), "_catchup": result["runtime"]}
        saved = await self.store.write_states(self.context, 0, [StateWrite("night", payload)])
        self.assertTrue(saved.accepted)
        await self.restart()
        record = await self.store.get_state(self.context, "night")
        value = dict(record.value)
        runtime = value.pop("_catchup")
        state = NightState(**value)
        self.assertEqual(runtime["summary"]["sources"][0]["source_ids"], ["m1"])
        self.assertEqual(state.unread_watermark, high)
        repeated = build_catchup(state, self.context, rows, now=self.now,
                                 high_watermark=high, generation=0, runtime=runtime)
        self.assertIsNone(repeated["summary"])

    async def test_cas_conflict_and_clear_reject_stale_catchup(self):
        state = NightState(updated_at=self.now)
        first = await self.store.write_states(self.context, 0, [StateWrite("night", to_dict(state))])
        self.assertTrue(first.accepted)
        stale = await self.store.write_states(self.context, 0, [StateWrite("night", to_dict(state))])
        self.assertEqual(stale.reason_code, "version_conflict")
        await self.store.clear_scope(self.context, 0)
        stale = await self.store.write_states(self.context, 0, [
            StateWrite("night", to_dict(state), expected_version=1)
        ])
        self.assertEqual(stale.reason_code, "stale_generation")
        self.assertIsNone(await self.store.get_state(self.context, "night"))

    async def test_interaction_energy_runtime_and_event_are_atomic(self):
        event = self.event()
        result = apply_interaction(NightState(updated_at=self.now), event, context=self.context,
                                   now=self.now)
        payload = {**to_dict(result["night"]), "_interaction": result["runtime"]}
        saved = await self.store.commit_event(event, 0, [StateWrite("night", payload)])
        self.assertTrue(saved.accepted)
        await self.restart()
        record = await self.store.get_state(self.context, "night")
        duplicate = await self.store.commit_event(event, 0, [
            StateWrite("night", {**record.value, "energy": 0}, expected_version=record.version)
        ])
        self.assertEqual(duplicate.status, "duplicate")
        after = await self.store.get_state(self.context, "night")
        self.assertEqual(after.value["energy"], 99.8)
        self.assertEqual(after.version, record.version)

    async def test_intent_has_single_persistent_key(self):
        await self.store.commit_event(self.event(), 0)
        rows = await self.store.read_window(self.context)
        high = await self.store.human_watermark(self.context)
        state = NightState(phase="waking", updated_at=self.now, sleep_started_at=self.now - 100,
                           wake_at=self.now, transition_deadline=self.now + 300)
        result = build_catchup(state, self.context, rows, now=self.now, high_watermark=high,
                               generation=0)
        intent = catchup_intent(result["summary"], result["night"], self.context,
                                now=self.now, generation=0)
        first = await self.store.create_intent(intent)
        second = await self.store.create_intent(replace(intent, created_at=self.now + 1))
        self.assertEqual(first["status"], "created")
        self.assertEqual(second["status"], "duplicate")


if __name__ == "__main__":
    unittest.main()
