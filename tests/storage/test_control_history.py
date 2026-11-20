"""Persist the control clock; never retrofit present feelings onto historical samples."""
import sqlite3
from dataclasses import replace

import pytest

from astrbot_plugin_livingemotion.contracts import BotAffect, StateWrite, to_dict
from astrbot_plugin_livingemotion.domain.dreaming import six_emotions
from astrbot_plugin_livingemotion.domain.emotion import decay_affect
from astrbot_plugin_livingemotion.storage import SQLiteStore
from astrbot_plugin_livingemotion.storage.schema import MIGRATIONS, migrate


def test_v8_migration_preserves_history_and_marks_control_missing():
    db = sqlite3.connect(":memory:")
    try:
        migrate(db, MIGRATIONS[:8])
        before = ("old", 0, 300, -.6, .7, .6, .3, 0, .3, 0, .3, 1)
        db.execute("INSERT INTO emotion_samples VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", before)
        db.commit()
        migrate(db)
        assert db.execute("PRAGMA user_version").fetchone()[0] == 9
        assert db.execute("SELECT * FROM emotion_samples").fetchone() == (*before, None, None)
        migrate(db)
        assert db.execute("SELECT COUNT(*) FROM emotion_samples").fetchone()[0] == 1
    finally:
        db.close()


@pytest.mark.parametrize("shared", [False, True])
@pytest.mark.parametrize("control", [.2, .8])
async def test_control_history_survives_restart_and_new_control(tmp_path, le_context, shared, control):
    start, clock = 1800000000, [1800000000]
    path = tmp_path / "control.sqlite3"
    affect = BotAffect(pleasure=-.6, arousal=.7, stress=.6, social_need=.3,
                      control=control, control_at=start - 1800, updated_at=start,
                      baseline_refined=True)
    store = SQLiteStore(path, clock=lambda: clock[0])
    await store.open()
    try:
        owner = await store.initialize_state_mode(le_context, shared=shared)
        old = await store.get_state(le_context, "bot")
        assert (await store.write_states(le_context, 0, [
            StateWrite("bot", to_dict(affect), old.version if old else 0, owner=owner)])).accepted
        points = await store.emotion_history(le_context, since=start, until=start + 3600)
        assert all(p["emotions"] == six_emotions(decay_affect(affect, now=p["at"]))
                   and p["control_basis"] == "recorded_decay" for p in points)
    finally:
        await store.close()
    reopened = SQLiteStore(path, clock=lambda: clock[0])
    await reopened.open()
    try:
        assert await reopened.emotion_history(
            le_context, since=start, until=start + 3600) == points
        clock[0] += 3600
        owner = reopened.state_owner(le_context)
        old = await reopened.get_state(le_context, "bot")
        changed = replace(affect, control=1-control, control_at=clock[0], updated_at=clock[0])
        assert (await reopened.write_states(le_context, 0, [
            StateWrite("bot", to_dict(changed), old.version, owner=owner)])).accepted
        new = await reopened.emotion_history(le_context, since=start, until=clock[0])
        assert new[:-1] == points[:-1]
        assert new[-1]["emotions"] == six_emotions(changed)
    finally:
        await reopened.close()


async def test_legacy_control_history_is_neutral_and_explicit(le_store, le_context):
    now = int(le_store.clock() // 300) * 300
    await le_store.get_generation(le_context)
    await le_store._run(lambda db: db.execute(
        """INSERT INTO emotion_samples(owner_key,generation,at,pleasure,arousal,stress,social_need,
           baseline_pleasure,baseline_arousal,baseline_stress,baseline_social_need,baseline_refined)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (le_context.scope_key, 0, now, -.6, .7, .6, .3, 0, .3, 0, .3, 1)))
    points = await le_store.emotion_history(le_context, since=now, until=now)
    assert points[0]["emotions"] == six_emotions(
        BotAffect(pleasure=-.6, arousal=.7, stress=.6, social_need=.3))
    assert points[0]["basis"] == "recorded_decay"
    assert points[0]["control_basis"] == "legacy_control_unknown"


@pytest.mark.parametrize("shared", [False, True])
async def test_control_uses_existing_shared_or_scene_ownership(le_store, le_context, shared):
    owner = await le_store.initialize_state_mode(le_context, shared=shared)
    old = await le_store.get_state(le_context, "bot")
    state = BotAffect(control=.8, control_at=le_store.clock(), updated_at=le_store.clock())
    assert (await le_store.write_states(le_context, 0, [
        StateWrite("bot", to_dict(state), old.version if old else 0, owner=owner)])).accepted
    other = replace(le_context, scene_id="other-chat", account_id="other-human")
    await le_store.initialize_state_mode(other, shared=shared)
    record = await le_store.get_state(other, "bot")
    assert (record.value["control"] if record else .5) == (.8 if shared else .5)
