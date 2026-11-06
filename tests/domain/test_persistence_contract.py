"""Domain-to-store contract probes using only the public storage interface."""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from astrbot_plugin_livingemotion.contracts import (
    BotAffect, Context, Event, EvidenceRef, Relationship, StateWrite, to_dict,
)
from astrbot_plugin_livingemotion.domain.emotion import apply_emotion
from astrbot_plugin_livingemotion.domain.relationship import apply_relationship
from astrbot_plugin_livingemotion.storage import SQLiteStore


def decode(record, cls):
    if record is None:
        return cls(), None, 0
    value = dict(record.value)
    runtime = value.pop("_runtime")
    if "evidence" in value:
        value["evidence"] = tuple(
            EvidenceRef(**{**ref, "context": Context.from_dict(ref["context"])})
            for ref in value["evidence"]
        )
    return cls(**value), runtime, record.version


class PersistenceContractTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "synthetic.sqlite3"
        self.now = 1000.0
        self.context = Context("bot", "persona", "adapter", "platform", "private",
                               "room", account_id="human")
        self.store = SQLiteStore(self.path, clock=lambda: self.now)
        await self.store.open()

    async def asyncTearDown(self):
        await self.store.close()

    def event(self, source="m1", signals=("care",)):
        return Event(source, "synthetic", "message", self.context, "human",
                     self.now, source, actor_id="human", signals=signals)

    async def compute(self, event):
        bot_record = await self.store.get_state(self.context, "bot")
        relationship_record = await self.store.get_state(
            self.context, "relationship", self.context.account_id)
        bot, bot_runtime, bot_version = decode(bot_record, BotAffect)
        relation, relation_runtime, relation_version = decode(relationship_record, Relationship)
        emotion = apply_emotion(bot, event, now=self.now, runtime=bot_runtime)
        relationship = apply_relationship(relation, event, now=self.now,
                                           runtime=relation_runtime)
        writes = (
            StateWrite("bot", {**to_dict(emotion["affect"]), "_runtime": emotion["runtime"]},
                       expected_version=bot_version),
            StateWrite("relationship", {
                **to_dict(relationship["relationship"]), "_runtime": relationship["runtime"],
            }, expected_version=relation_version, record_key=self.context.account_id),
        )
        return writes, relationship["contributions"]

    async def test_restart_preserves_snapshot_budget_and_deduplication(self):
        event = self.event()
        writes, contributions = await self.compute(event)
        result = await self.store.commit_event(event, 0, writes, contributions)
        self.assertTrue(result.accepted)
        await self.store.close()
        self.store = SQLiteStore(self.path, clock=lambda: self.now)
        await self.store.open()
        record = await self.store.get_state(self.context, "relationship", "human")
        state, runtime, version = decode(record, Relationship)
        self.assertEqual(state.score, 3)
        self.assertEqual(runtime["days"]["1970-01-01"], 3)
        self.assertEqual(version, 1)
        replay = apply_relationship(state, event, now=self.now, runtime=runtime)
        self.assertEqual(replay["reason_codes"], ("duplicate_event",))
        duplicate = await self.store.commit_event(event, 0, writes, contributions)
        self.assertEqual(duplicate.reason_code, "duplicate_event")
        ledger = await self.store.relationship_ledger(self.context)
        self.assertEqual(len(ledger), len(contributions))

    async def test_cas_conflict_requires_recompute_and_does_not_append_partial_ledger(self):
        first, second = self.event("m1"), self.event("m2", ("gratitude",))
        first_writes, first_rows = await self.compute(first)
        stale_writes, stale_rows = await self.compute(second)
        self.assertTrue((await self.store.commit_event(first, 0, first_writes, first_rows)).accepted)
        rejected = await self.store.commit_event(second, 0, stale_writes, stale_rows)
        self.assertEqual(rejected.reason_code, "version_conflict")
        self.assertEqual(len(await self.store.relationship_ledger(self.context)), len(first_rows))
        current_writes, current_rows = await self.compute(second)
        self.assertTrue((await self.store.commit_event(second, 0, current_writes, current_rows)).accepted)
        record = await self.store.get_state(self.context, "relationship", "human")
        state, runtime, version = decode(record, Relationship)
        self.assertEqual(state.score, 5)
        self.assertEqual(runtime["days"]["1970-01-01"], 5)
        self.assertEqual(version, 2)

    async def test_clear_generation_blocks_already_computed_domain_result(self):
        event = self.event()
        writes, contributions = await self.compute(event)
        self.assertTrue((await self.store.clear_scope(self.context, 0)).accepted)
        late = await self.store.commit_event(event, 0, writes, contributions)
        self.assertEqual(late.reason_code, "stale_generation")
        self.assertIsNone(await self.store.get_state(self.context, "bot"))
        self.assertEqual(await self.store.relationship_ledger(self.context), [])


if __name__ == "__main__":
    unittest.main()
