"""Historical decay must use the baseline of that sample; migration never invents it."""
import sqlite3
from dataclasses import replace

import pytest

from astrbot_plugin_livingemotion.contracts import BotAffect, StateWrite, to_dict
from astrbot_plugin_livingemotion.domain.emotion import decay_affect
from astrbot_plugin_livingemotion.domain.dreaming import six_emotions
from astrbot_plugin_livingemotion.storage.schema import MIGRATIONS, migrate


@pytest.mark.parametrize("shared", [False, True])
async def test_dynamic_history_matches_live_decay_and_survives_new_baseline(le_store, le_context, shared):
    start = int(le_store.clock() // 300) * 300
    le_store.clock = lambda: start
    owner = await le_store.initialize_state_mode(le_context, shared=shared)
    affect = BotAffect(pleasure=.8, arousal=.7, stress=.2, social_need=.6,
        baseline_pleasure=.5, baseline_arousal=.5, baseline_stress=.1,
        baseline_social_need=.4, baseline_refined=True, updated_at=start)
    old = await le_store.get_state(le_context, "bot")
    assert (await le_store.write_states(le_context, 0, [
        StateWrite("bot", to_dict(affect), old.version if old else 0, owner=owner)])).accepted
    points = await le_store.emotion_history(le_context, since=start, until=start + 3600)
    for point in points:
        assert point["emotions"] == six_emotions(decay_affect(affect, now=point["at"]))
        assert point["basis"] == "recorded_decay"
    historical = [p for p in points if p["at"] < start + 3600]
    le_store.clock = lambda: start + 3600
    old = await le_store.get_state(le_context, "bot")
    changed = replace(affect, baseline_pleasure=-.5, updated_at=start + 3600)
    assert (await le_store.write_states(le_context, 0, [
        StateWrite("bot", to_dict(changed), old.version, owner=owner)])).accepted
    points = await le_store.emotion_history(le_context, since=start, until=start + 3600)
    assert points[:-1] == historical  # Current baseline cannot rewrite earlier samples.
    assert points[-1]["emotions"] == six_emotions(changed)


def test_v7_migration_preserves_legacy_dimensions_and_marks_baseline_missing():
    db = sqlite3.connect(":memory:")
    try:
        migrate(db, MIGRATIONS[:7])
        db.execute("INSERT INTO emotion_samples VALUES(?,?,?,?,?,?,?)",
                   ("old", 0, 300, .8, .5, .1, .4))
        db.commit()
        migrate(db)
        assert db.execute("PRAGMA user_version").fetchone()[0] == 8
        old = db.execute("SELECT * FROM emotion_samples").fetchone()
        assert old[:7] == ("old", 0, 300, .8, .5, .1, .4)
        assert old[7:] == (None,) * 5
        migrate(db)
        assert db.execute("SELECT COUNT(*) FROM emotion_samples").fetchone()[0] == 1
    finally:
        db.close()


async def test_legacy_history_exposes_missing_baseline(le_store, le_context):
    now = int(le_store.clock() // 300) * 300
    await le_store.get_generation(le_context)
    await le_store._run(lambda db: db.execute(
        """INSERT INTO emotion_samples(owner_key,generation,at,pleasure,arousal,stress,social_need)
           VALUES(?,?,?,?,?,?,?)""", (le_context.scope_key, 0, now, .8, .5, .1, .4)))
    points = await le_store.emotion_history(le_context, since=now, until=now + 300)
    assert all(point["basis"] == "legacy_baseline_unknown" for point in points)
