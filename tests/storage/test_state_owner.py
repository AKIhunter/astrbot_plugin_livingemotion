"""Source isolation and conservative state mode transactions."""

import asyncio
from dataclasses import replace

from astrbot_plugin_livingemotion.api import LivingEmotionAPI
from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import StateWrite, NightState, to_dict
from astrbot_plugin_livingemotion.contracts import canonical_json
from astrbot_plugin_livingemotion.runtime.background import BackgroundRuntime
from astrbot_plugin_livingemotion.runtime.projector import Projector


async def api(store):
    config = Config(night_policy_version=2, timezone="UTC")
    store.config = config
    return LivingEmotionAPI(store, config, BackgroundRuntime(store, config),
                            project_event=Projector(store, lambda: config))


async def test_shared_numbers_never_share_sources(le_store, le_event):
    facade = await api(le_store)
    context = le_event.context
    other = replace(context, scene_kind="group", scene_id="other")
    await le_store.initialize_state_mode(context, shared=True)
    await le_store.initialize_state_mode(other, shared=True)
    event = replace(le_event, signals=("care",))
    assert (await facade.ingest_event(event))["status"] == "accepted"
    private = await le_store.get_state(context, "bot")
    group = await le_store.get_state(other, "bot")
    assert group.value["pleasure"] == private.value["pleasure"] > 0
    assert group.value["evidence"] == [] and group.value["reason_codes"] == []
    assert await le_store.read_window(other) == []
    assert await le_store.get_state(other, "observation", other.account_id) is None
    assert group.owner == private.owner
    assert other.scope_key != context.scope_key
    assert (await facade.ingest_event(replace(event, context=other, source_id="group")))["status"] == (
        "accepted"
    )


async def test_two_modes_have_real_storage_and_stale_projection_cannot_write(le_store, le_event):
    facade = await api(le_store)
    context = le_event.context
    owner = await le_store.initialize_state_mode(context, shared=False)
    assert (await facade.ingest_event(le_event))["status"] == "accepted"
    projection = await facade._project_event(replace(le_event, source_id="late"))
    result = await le_store.switch_state_mode(
        context, shared=True, expected_revision=owner.revision, actor_id="operator",
    )
    assert result["status"] == "accepted"
    stale = await le_store.commit_event(replace(le_event, source_id="late"), 0, projection.writes)
    assert stale.reason_code == "stale_state_mode"
    assert len(await le_store.read_window(context)) == 1
    assert (await le_store.get_state(context, "bot")).owner.mode == "shared"
    other = replace(context, scene_id="another")
    await le_store.initialize_state_mode(other)
    assert (await facade.ingest_event(replace(le_event, context=other, source_id="other")))[
        "status"
    ] == "accepted"
    assert (await le_store.get_state(other, "bot")).version == (
        await le_store.get_state(context, "bot")
    ).version


async def test_switch_back_keeps_minimum_energy_and_longest_sleep_and_quota(le_store, le_context):
    le_store.config = Config(night_policy_version=2, timezone="UTC")
    owner = await le_store.initialize_state_mode(le_context, shared=False)
    record = await le_store.get_state(le_context, "night")
    now = le_store.clock()
    sleeping = NightState(
        phase="asleep", policy_version=2, display_state="deep_sleep", energy=7.2,
        energy_units=72, updated_at=now, sleep_started_at=now - 100, wake_at=now + 7200,
        cycle_id="cycle", cycle_kind="night", cycle_started_at=now - 100,
    )
    assert (await le_store.write_states(le_context, 0, (
        StateWrite("night", to_dict(sleeping), record.version, owner=owner),
    ))).accepted
    assert (await le_store.reserve_quota("budget", le_context, 0, period="day", purpose="behavior",
                                        limit=1))["status"] == "reserved"
    for shared in (True, False, True):
        old = le_store.state_owner(le_context)
        result = await le_store.switch_state_mode(
            le_context, shared=shared, expected_revision=old.revision, actor_id="operator",
        )
        assert result["status"] == "accepted"
        state = (await le_store.get_state(le_context, "night")).value
        assert state["energy"] <= 7.2 and state["wake_at"] >= now + 7200
        assert state["display_state"] == "deep_sleep"
        assert await le_store.quota_usage(period="day") == 1
    conflict = await le_store.switch_state_mode(
        le_context, shared=False, expected_revision=0, actor_id="operator",
    )
    assert conflict["reason_code"] == "state_revision_conflict"


async def test_clear_one_source_invalidates_shared_writes_from_other_source(le_store, le_event):
    facade = await api(le_store)
    context = le_event.context
    other = replace(context, scene_id="another")
    await le_store.initialize_state_mode(context, shared=True)
    await le_store.initialize_state_mode(other, shared=True)
    assert (await facade.ingest_event(le_event))["status"] == "accepted"
    projection = await facade._project_event(replace(le_event, context=other, source_id="late"))
    assert (await le_store.clear_scope(context, 0)).accepted
    result = await le_store.commit_event(
        replace(le_event, context=other, source_id="late"), 0, projection.writes,
    )
    assert result.reason_code == "stale_owner_generation"
    assert (await le_store.get_state(other, "bot")).value["evidence"] == []


async def test_personas_and_instances_never_share(le_store, le_event):
    facade = await api(le_store)
    contexts = [le_event.context, replace(le_event.context, persona_id="different"),
                replace(le_event.context, instance_id="different")]
    for context in contexts:
        await le_store.initialize_state_mode(context, shared=True)
    assert (await facade.ingest_event(replace(le_event, signals=("care",))))["status"] == "accepted"
    for context in contexts[1:]:
        assert (await le_store.get_state(context, "bot")).value["pleasure"] == 0


async def test_shared_twenty_concurrent_events_commit_without_retries(le_store, le_event):
    facade = await api(le_store)
    contexts = [replace(le_event.context, scene_id=f"scene-{i}") for i in range(20)]
    for context in contexts:
        await le_store.initialize_state_mode(context, shared=True)
    results = await asyncio.gather(*(facade.ingest_event(
        replace(le_event, context=c, source_id=f"source-{i}")) for i, c in enumerate(contexts)))
    assert all(result["status"] == "accepted" for result in results)
    record = await le_store.get_state(contexts[0], "night")
    assert record.version == 21


def test_old_mapping_keeps_scene_and_v1_new_config_defaults_shared():
    assert not Config.from_mapping({"enabled": True}).persona_shared_state
    assert Config.from_mapping({"enabled": True}).night_policy_version == 1
    assert Config().persona_shared_state


async def test_projector_native_json_encoding_preserves_canonical_bytes(le_store, le_event):
    from astrbot_plugin_livingemotion.storage.sqlite import _state_json
    facade = await api(le_store)
    await le_store.initialize_state_mode(le_event.context, shared=True)
    projection = await facade._project_event(le_event)
    for write in projection.writes:
        assert _state_json(write.value) == canonical_json(write.value)
    for trace in projection.traces:
        assert _state_json(trace) == canonical_json(trace)
