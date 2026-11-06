"""Both public facades, with no production events or private-engine access."""

from copy import deepcopy
from dataclasses import replace

import pytest
from astrbot_plugin_livingemotion.adapters.memory import LivingMemoryAdapter, MemoryGateway

from .fakes import Event, Provider, context, request


class RequeryProvider(Provider):
    validate_identity_results = None

    @property
    def engine(self):
        raise AssertionError("private_engine_forbidden")


async def rig(profile):
    provider = Provider() if profile == "validate" else RequeryProvider()
    backend = LivingMemoryAdapter(lambda: provider)
    event = Event()
    identity = await backend.identity.resolve(context(), event=event)
    req = request(identity.context)
    gateway = MemoryGateway(backend, clock=lambda: 150)
    return provider, backend, event, req, gateway


@pytest.mark.parametrize("profile", ["validate", "event_requery"])
async def test_p4_profiles_use_current_event_and_reject_background(profile):
    provider, backend, event, req, gateway = await rig(profile)
    assert backend.capabilities().recall
    assert not backend.capabilities().background_recall
    assert not (await gateway.recall(req)).materials
    assert provider.calls == 0
    result = await gateway.recall(replace(req, request_id="live"), event=event)
    assert len(result.materials) == 1
    assert await backend.validate(req, result.materials, event)
    assert not await backend.validate(req, result.materials, None)
    assert not await backend.validate(req, result.materials, Event(synthetic=True))
    assert not await backend.validate(replace(req, query="changed"), result.materials, event)
    assert not await backend.validate(replace(req, limit=5), result.materials, event)
    await gateway.close()


@pytest.mark.parametrize("change", ["id", "body", "source", "deleted", "identity", "reload"])
async def test_p4_requery_requires_same_candidate_body_and_all_sources(change):
    provider, backend, event, req, gateway = await rig("event_requery")
    result = await gateway.recall(req, event=event)
    assert result.materials and provider.calls == 2  # query + use-time requery
    rows = await provider.search_memories_for_event("tea", event, persona_id=req.context.persona_id)
    provider.rows = deepcopy(rows)
    if change == "id":
        provider.rows[0].doc_id = 2
    elif change == "body":
        provider.rows[0].content += " changed"
    elif change == "source":
        provider.rows[0].metadata["source_window"]["end_index"] += 1
    elif change == "deleted":
        provider.rows = []
    elif change == "identity":
        provider.revision += 1
    else:
        backend.provider = lambda: RequeryProvider()
    assert not (await gateway.validate_evidence(req, result.materials, event=event)).valid
    await gateway.close()


async def test_p4_requery_identity_changes_during_final_query():
    provider, backend, event, req, gateway = await rig("event_requery")
    result = await gateway.recall(req, event=event)
    original = provider.search_memories_for_event

    async def changed(*args, **kwargs):
        rows = await original(*args, **kwargs)
        provider.revision += 1
        return rows
    provider.search_memories_for_event = changed
    assert not await backend.validate(req, result.materials, event)
    await gateway.close()
