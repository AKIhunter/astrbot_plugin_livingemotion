from dataclasses import replace

import pytest

from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import EvidenceRef, Experience
from budget_support import scope


async def test_small_scope_global_limits_real_projection(rig, record_property):
    await rig.reopen(window_per_scope=3, window_global=5)
    for i in range(16):
        await rig.ingest(i, scope(i // 4))
    counts = await rig.store._run(lambda db: [
        row[0] for row in db.execute("SELECT COUNT(*) FROM body_window GROUP BY scope_key")])
    stats = await rig.bodies()
    record_property("measurements", {**stats, "per_scope_counts": counts,
                                      "successful_event_projections": 16})
    assert stats["count"] == 5 and max(counts) <= 3
    await rig.reopen()
    assert await rig.bodies() == stats


async def test_body_8000_and_lower_config_limit(rig, record_property):
    for i, n in enumerate((7999, 8000, 8001)):
        await rig.ingest(i, body="x" * n)
    lengths = [len(row["body"]) for row in await rig.store.read_window(scope())]
    await rig.reopen(body_max_chars=17)
    await rig.ingest(10, scope(1), body="y" * 100)
    smaller = [len(row["body"]) for row in await rig.store.read_window(scope(1))]
    record_property("measurements", {"default_lengths": lengths, "smaller_lengths": smaller})
    assert lengths == [7999, 8000, 8000] and smaller == [17]


async def test_ttl_from_occurrence_not_ingest_and_exact_boundary(rig, record_property):
    cutoff = rig.now - 7 * 86400
    for i, timestamp in enumerate((cutoff - 1, cutoff, cutoff + 1, rig.now - 1)):
        await rig.ingest(i, occurred_at=timestamp)
    before = await rig.bodies()
    rig.now += 1
    visible = await rig.store.read_window(scope())
    await rig.store.cleanup()
    after = await rig.bodies()
    record_property("measurements", {"before": before, "after": after,
                                      "read_visible": len(visible)})
    assert before["count"] == 2 and len(visible) == after["count"] == 1
    await rig.reopen()
    assert (await rig.bodies())["count"] == 1


async def test_pinned_experience_reference_does_not_extend_source_body(rig, record_property):
    event = await rig.ingest(0)
    ref = EvidenceRef("livingemotion", event.idempotency_key, scope(), scope().account_id,
                      scope().bot_id, "interaction", event.occurred_at,
                      expires_at=event.occurred_at + 7 * 86400,
                      source_ids=(event.source_id,))
    experience = Experience("synthetic-diary", scope(), "diary", rig.day, rig.now,
                            "Synthetic summary, not a source body.", (ref,),
                            rig.now + 30 * 86400, pinned=True)
    assert (await rig.store.save_experience(experience, 0))["status"] == "created"
    rig.now = event.occurred_at + 7 * 86400
    assert await rig.store.read_window(scope()) == []
    await rig.store.cleanup()
    await rig.reopen()
    saved = await rig.store.load_experience(experience.experience_id)
    record_property("measurements", {"remaining_source_bodies": (await rig.bodies())["count"],
                                      "experience_retained": saved is not None,
                                      "source_reference_retained": bool(saved and saved[0].evidence)})
    assert (await rig.bodies())["count"] == 0
    assert saved is not None and saved[0].evidence[0].source_id == ref.source_id


async def test_lower_scope_limit_cleanup_prunes_inactive_scopes(rig, record_property):
    for i in range(12):
        await rig.ingest(i, scope(i // 4))
    await rig.reopen(window_per_scope=2)
    await rig.store.cleanup()
    counts = await rig.store._run(lambda db: [
        row[0] for row in db.execute("SELECT COUNT(*) FROM body_window GROUP BY scope_key")])
    record_property("measurements", {"configured_per_scope": 2,
                                      "persisted_per_scope_counts": counts,
                                      "read_limit": len(await rig.store.read_window(scope()))})
    assert counts and max(counts) <= 2, "cleanup retained inactive scopes above lowered limit"


async def test_lower_global_limit_cleanup(rig, record_property):
    for i in range(12):
        await rig.ingest(i, scope(i // 4))
    await rig.reopen(window_global=5)
    await rig.store.cleanup()
    record_property("measurements", await rig.bodies())
    assert (await rig.bodies())["count"] == 5


async def test_lower_ttl_cleanup_inactive_sources(rig, record_property):
    await rig.ingest(0, occurred_at=rig.now - 2 * 86400)
    await rig.ingest(1, scope(1))
    assert (await rig.bodies())["count"] == 2
    await rig.reopen(window_days=1)
    await rig.store.cleanup()
    record_property("measurements", await rig.bodies())
    assert (await rig.bodies())["count"] == 1
    assert await rig.store.read_window(scope()) == []


@pytest.mark.parametrize("field,value", (
    ("window_days", 8), ("window_per_scope", 201), ("window_global", 10001),
    ("body_max_chars", 8001),
))
def test_window_hard_maxima_cannot_be_raised(field, value):
    with pytest.raises(ValueError, match="exceeds safety maximum"):
        replace(Config(), **{field: value})
