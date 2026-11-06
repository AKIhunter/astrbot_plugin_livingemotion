"""Controlled time/randomness with real SQLite; no model or transport."""

import asyncio
from dataclasses import replace

import pytest

from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import BotAffect, Relationship, SceneKind
from astrbot_plugin_livingemotion.domain.proactivity import (
    choose_motive, initiative_probability, motives,
)
from astrbot_plugin_livingemotion.storage.proactivity import (
    claim_opportunity, finish_opportunity, read_schedule,
)
from astrbot_plugin_livingemotion.storage import SQLiteStore


@pytest.mark.parametrize("patch", [
    {"behavior_random_min_minutes": 100, "behavior_random_max_minutes": 90},
    {"behavior_random_max_minutes": 10081}, {"behavior_idle_minutes": 0},
    {"behavior_idle_minutes": 1441}, {"behavior_style": "spam"},
    {"behavior_emotional_share": "true"}, {"behavior_random_min_minutes": True},
])
def test_invalid_initiative_settings(patch):
    with pytest.raises(ValueError):
        Config(**patch)


def test_relationship_controls_emotional_share_and_motive_rotation():
    affect, relation = BotAffect(stress=.7, social_need=.8), Relationship(score=800)
    choices = motives(affect, relation, SceneKind.PRIVATE, absent_seconds=4 * 86400)
    assert {c.key for c in choices} == {
        "memory_followup", "care_checkin", "light_chat", "emotional_share", "reconnect",
    }
    for scene, rel, enabled in (
        (SceneKind.GROUP, relation, True),
        (SceneKind.PRIVATE, replace(relation, score=599), True),
        (SceneKind.PRIVATE, replace(relation, trust=.2), True),
        (SceneKind.PRIVATE, replace(relation, boundary=.8), True),
        (SceneKind.PRIVATE, replace(relation, evidence_complete=False), True),
        (SceneKind.PRIVATE, relation, False),
    ):
        assert "emotional_share" not in {
            c.key for c in motives(affect, rel, scene, emotional_share=enabled)
        }
    first = choose_motive(choices, 0)
    assert choose_motive(choices, 0, previous=first.key).key != first.key
    assert choose_motive(choices, 1).key == choices[-1].key
    assert (initiative_probability(.7, 0, "gentle")
            < initiative_probability(.7, 0, "balanced")
            < initiative_probability(.7, 0, "lively"))
    assert initiative_probability(.7, 1, "balanced") < initiative_probability(.7, 0, "balanced")


@pytest.mark.asyncio
async def test_durable_single_claim_overlap_reopen_and_unknown(tmp_path, le_context):
    clock = [1800000000.]
    path = tmp_path / "opportunities.sqlite3"
    store = SQLiteStore(path, clock=lambda: clock[0])
    await store.open()
    args = dict(signature="config1", delay=120, lateness=300, deadline=100)
    try:
        await store.register_context(le_context)
        assert await claim_opportunity(store, le_context, **args) is None
        clock[0] += 120
        claims = await asyncio.gather(*[
            claim_opportunity(store, le_context, **args) for _ in range(20)
        ])
        claim, = [claim for claim in claims if claim]
        assert (await read_schedule(store, le_context))["next_at"] == clock[0] + 120
        assert await finish_opportunity(store, le_context, claim, outcome="unknown", reason="unknown")
        assert not await finish_opportunity(store, le_context, claim, outcome="succeeded", reason="fake")
    finally:
        await store.close()
    reopened = SQLiteStore(path, clock=lambda: clock[0])
    await reopened.open()
    try:
        state = await read_schedule(reopened, le_context)
        assert state["last_outcome"] == "unknown"
        assert await claim_opportunity(reopened, le_context, **args) is None
        assert (await read_schedule(reopened, le_context))["next_at"] == state["next_at"]
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_missed_stuck_reverse_config_and_clear_never_replay(le_store, le_context):
    clock = [1800000001.]
    le_store.clock = lambda: clock[0]
    args = dict(signature="first", delay=60, lateness=90, deadline=30)
    await le_store.register_context(le_context)
    await claim_opportunity(le_store, le_context, **args)
    clock[0] += 200
    assert await claim_opportunity(le_store, le_context, **args) is None
    assert (await read_schedule(le_store, le_context))["last_reason"] == "missed_opportunity"
    clock[0] += 60
    old = await claim_opportunity(le_store, le_context, **args)
    assert old
    clock[0] += 31
    assert await claim_opportunity(le_store, le_context, **args) is None
    assert (await read_schedule(le_store, le_context))["last_reason"] == "opportunity_interrupted"
    assert not await finish_opportunity(le_store, le_context, old, outcome="succeeded", reason="late")
    clock[0] -= 1
    assert await claim_opportunity(le_store, le_context, **args) is None
    assert (await read_schedule(le_store, le_context))["last_reason"] == "clock_reversed"
    await claim_opportunity(le_store, le_context, **{**args, "signature": "second"})
    await claim_opportunity(le_store, le_context, **args)
    clock[0] += 60
    new = await claim_opportunity(le_store, le_context, **args)
    assert new and new["run_id"] != old["run_id"]
    await le_store.clear_scope(le_context, 0)
    assert not await finish_opportunity(le_store, le_context, new, outcome="unknown", reason="old")
    assert await claim_opportunity(le_store, le_context, **args) is None
    state = await read_schedule(le_store, le_context)
    assert state["generation"] == 1 and state["recent_topics"] == []
