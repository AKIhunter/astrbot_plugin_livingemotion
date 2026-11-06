"""Retained ledger reads use synthetic SQLite data and no host/model calls."""

from dataclasses import replace

import pytest

from astrbot_plugin_livingemotion.adapters.identity import IdentityAdapter
from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import Event, StateWrite
from astrbot_plugin_livingemotion.runtime.projector import Projector
from astrbot_plugin_livingemotion.runtime.relationship_projection import (
    CONTEXT_LIMIT, read_relationship_projection,
)
from astrbot_plugin_livingemotion.storage import SQLiteStore
from astrbot_plugin_livingemotion.tests.memory import fakes


@pytest.fixture
async def projection_case(tmp_path):
    now = [150.0]
    store = SQLiteStore(tmp_path / "synthetic-projection.db", clock=lambda: now[0])
    await store.open()
    provider = fakes.Provider()
    identities = IdentityAdapter(lambda: provider)
    target = fakes.context(audience=("qq:alice", "qq:bot"))
    event = fakes.Event(target)
    identity = await identities.resolve(target, event=event)
    first = identity.context
    second = replace(first, platform="bili", account_id="linked", scene_id="linked",
                     audience=("bili:linked", "qq:bot"))
    projector = Projector(store, lambda: Config())
    for number, source in enumerate((first, second)):
        await store.register_context(source)
        normalized = Event(str(number), "identity-test", "message", source, "human", now[0],
                           str(number), actor_id=source.account_id)
        projection = await projector(normalized)
        assert (await store.commit_event(
            normalized, await store.get_generation(source), projection.writes,
            projection.contributions, traces=projection.traces,
        )).accepted
    try:
        yield store, now, provider, identities, identity, event, first, second
    finally:
        await store.close()


async def test_read_reprojects_after_body_and_events_expire_without_copying(projection_case):
    store, now, provider, identities, identity, event, first, second = projection_case
    before = [await store.relationship_ledger(source) for source in (first, second)]
    versions = [(await store.get_state(source, "relationship", source.account_id)).version
                for source in (first, second)]
    now[0] += 31 * 86400
    await store.cleanup()
    await store.close()
    store = SQLiteStore(store.path, clock=lambda: now[0])
    await store.open()
    try:
        assert (await store.health())["counts"]["events"] == 0
        result = await read_relationship_projection(store, identities, identity, event=event)
        assert result.score == 1
        provider.bound, provider.revision = False, provider.revision + 1
        assert await read_relationship_projection(store, identities, identity, event=event) is None
        current = await identities.resolve(first, event=event)
        result = await read_relationship_projection(store, identities, current, event=event)
        assert result.score == 0.5
        assert result.identity_revision == current.context.identity_revision
        assert [await store.relationship_ledger(source) for source in (first, second)] == before
        assert [(await store.get_state(source, "relationship", source.account_id)).version
                for source in (first, second)] == versions
    finally:
        await store.close()


@pytest.mark.parametrize("change", ["revision", "provider_loss", "clear"])
async def test_authority_or_generation_change_during_read_discards_result(
    projection_case, monkeypatch, change,
):
    store, _, provider, identities, identity, event, _, second = projection_case
    read = store.relationship_ledger

    async def changed(source):
        rows = await read(source)
        if source.account_key == second.account_key:
            if change == "revision":
                provider.revision += 1
            elif change == "provider_loss":
                identities.provider = lambda: None
            else:
                assert (await store.clear_scope(
                    source, await store.get_generation(source), reason_code="synthetic_clear",
                )).accepted
        return rows

    monkeypatch.setattr(store, "relationship_ledger", changed)
    assert await read_relationship_projection(store, identities, identity, event=event) is None


async def test_no_registry_source_is_inferred_from_bound_account(projection_case, monkeypatch):
    store, _, _, identities, identity, event, first, _ = projection_case

    async def current_only(*, limit):
        return [replace(first, route=None)]

    monkeypatch.setattr(store, "list_contexts", current_only)
    result = await read_relationship_projection(store, identities, identity, event=event)
    assert result.score == 0.5


async def test_truncated_context_inventory_is_not_reported_as_complete(
    projection_case, monkeypatch,
):
    store, _, _, identities, identity, event, first, _ = projection_case

    async def truncated(*, limit):
        assert limit == CONTEXT_LIMIT
        return [replace(first, account_id=f"synthetic-{n}") for n in range(limit)]

    monkeypatch.setattr(store, "list_contexts", truncated)
    assert await read_relationship_projection(store, identities, identity, event=event) is None


async def test_local_baseline_is_never_added_to_other_accounts(projection_case):
    store, _, _, identities, identity, event, first, _ = projection_case
    record = await store.get_state(first, "relationship", first.account_id)
    assert (await store.write_states(first, record.generation, (
        StateWrite("relationship", {**record.value, "score": 900.0},
                   record.version, first.account_id),
    ))).accepted
    result = await read_relationship_projection(store, identities, identity, event=event)
    assert result.score == 900
    assert not result.evidence_complete
    assert result.reason_codes == ("relationship_baseline_not_aggregatable",)


async def test_manual_freeze_survives_projection_without_changing_sources(projection_case):
    store, _, _, identities, identity, event, first, _ = projection_case
    record = await store.get_state(first, "relationship", first.account_id)
    assert (await store.correct_relationship(
        first, record.generation, expected_version=record.version,
        actor_id="synthetic-admin", reason="synthetic-freeze", frozen=True,
    )).accepted
    result = await read_relationship_projection(store, identities, identity, event=event)
    assert result.score == 1
    assert result.frozen


async def test_unbound_read_still_checks_final_identity(projection_case, monkeypatch):
    store, _, provider, identities, identity, event, first, _ = projection_case
    provider.bound = False
    provider.revision += 1
    current = await identities.resolve(first, event=event)
    read = store.get_state

    async def changed(*args, **kwargs):
        value = await read(*args, **kwargs)
        provider.revision += 1
        return value

    monkeypatch.setattr(store, "get_state", changed)
    assert await read_relationship_projection(store, identities, current, event=event) is None
