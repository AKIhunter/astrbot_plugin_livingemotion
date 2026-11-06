import asyncio
import sqlite3
from dataclasses import replace

import pytest
from astrbot_plugin_livingemotion.adapters.memory import (
    LivingMemoryAdapter,
    LocalLiteMemory,
    MemoryGateway,
)
from astrbot_plugin_livingemotion.ports.memory import MemoryMode

from .fakes import Event, Provider, context, own, request


async def test_none_keeps_own_material_without_long_term_calls():
    gateway = MemoryGateway(clock=lambda: 150)
    assert gateway.capabilities().mode == MemoryMode.NONE
    result = await gateway.recall(request(), available=(own(),))
    assert result.materials == (own(),) and result.reused
    assert (await gateway.recall(request())).materials == ()
    assert not (await gateway.append_experience(request(), own(), idempotency_key="x")).accepted


async def test_local_explicit_text_persists_and_expires(tmp_path):
    path = tmp_path / "local.sqlite3"
    backend = LocalLiteMemory(path, clock=lambda: 150)
    assert (await backend.remember(request(), own())).reason_code == "stored"
    assert (await backend.remember(request(), own())).reason_code == "duplicate"
    assert not (await backend.remember(request(), replace(own(), text="changed"))).accepted
    reopened = LocalLiteMemory(path, clock=lambda: 150)
    gateway = MemoryGateway(reopened, clock=lambda: 150)
    result = await gateway.recall(request())
    assert result.materials[0].text == own().text
    assert result.materials[0].evidence.source_ids == ("message-1",)
    assert not (await gateway.recall(request(request_id="other", query="coffee"))).materials
    reopened.clock = lambda: 201
    gateway.clock = lambda: 201
    assert not (await gateway.validate_evidence(request(), result.materials)).valid
    assert not (await gateway.recall(request())).materials
    with sqlite3.connect(path) as db:
        # Cleanup is triggered by local operations, independently of gateway cache.
        await reopened.fetch(request(), None)
        assert db.execute("SELECT count(*) FROM explicit_text").fetchone()[0] == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"expires_at": None},
        {"expires_at": 10000000},
        {"source_ids": ()},
        {"kind": "dream"},
        {"kind": "summary"},
        {"provider": "livingmemory"},
    ],
)
async def test_local_rejects_implicit_unbounded_or_subjective_facts(tmp_path, changes):
    backend = LocalLiteMemory(tmp_path / "local.sqlite3", clock=lambda: 150)
    assert not (await backend.remember(request(), own(**changes))).accepted


async def test_local_bounds_delete_and_cache_invalidation(tmp_path):
    backend = LocalLiteMemory(
        tmp_path / "local.sqlite3", clock=lambda: 150, max_records=3, per_scope=2
    )
    for index in range(4):
        await backend.remember(request(), own(source_id=str(index), occurred_at=100 + index))
    gateway = MemoryGateway(backend, clock=lambda: 150)
    result = await gateway.recall(request())
    assert len(result.materials) == 2
    await backend.forget(context(), result.materials[0].evidence.source_id)
    assert not (await gateway.validate_evidence(request(), result.materials)).valid
    assert not (await gateway.recall(request())).materials


@pytest.mark.parametrize(
    "change",
    [
        {"bot_id": "another-bot"},
        {"persona_id": "another-persona"},
        {"adapter_id": "another-adapter"},
        {"platform": "bili"},
        {"scene_id": "another"},
        {"scene_kind": "group"},
        {"account_id": "another"},
        {"persona_revision": "changed"},
        {"identity_revision": "changed"},
        {"audience": ("mallory",)},
        {"audience": ()},
    ],
)
async def test_source_isolation_matrix(tmp_path, change):
    backend = LocalLiteMemory(tmp_path / "local.sqlite3", clock=lambda: 150)
    await backend.remember(request(), own())
    gateway = MemoryGateway(backend, clock=lambda: 150)
    changed = request(context(**change))
    assert not (await gateway.recall(changed)).materials
    assert not (await gateway.validate_evidence(changed, (own(),))).valid


async def test_live_guard_invalidates_entire_generation_and_bound_self_requires_guard():
    ctx = context(identity_revision="livingmemory:7")
    current = True

    async def guard(*args):
        return current

    gateway = MemoryGateway(clock=lambda: 150, context_guard=guard)
    result = await gateway.recall(request(ctx), available=(own(ctx),))
    assert result.materials
    current = False
    final = await gateway.validate_evidence(request(ctx), result.materials)
    assert not final.valid and not final.materials
    unguarded = MemoryGateway(clock=lambda: 150)
    assert not (await unguarded.validate_evidence(request(ctx), (own(ctx),))).valid


async def external_runtime(**kwargs):
    provider = Provider()
    backend = LivingMemoryAdapter(lambda: provider, **kwargs)
    event = Event()
    identity = await backend.identity.resolve(context(), event=event)
    req = request(identity.context)
    gateway = MemoryGateway(backend, clock=lambda: 150)
    return provider, backend, event, req, gateway


async def test_external_real_public_contract_and_final_validation():
    provider, _, event, req, gateway = await external_runtime()
    result = await gateway.recall(req, event=event)
    assert len(result.materials) == 1
    ref = result.materials[0].evidence
    assert ref.provider == "livingmemory" and ref.holder_id == "qq:bot"
    assert ref.subject_id == "qq:alice" and ref.kind == "summary"
    assert ref.context == req.context and ref.sensitive and ref.authorization
    assert "#window:1:3" in ref.source_ids[0]
    assert (await gateway.validate_evidence(req, result.materials, event=event)).valid
    provider.revision += 1
    final = await gateway.validate_evidence(req, result.materials, event=event)
    assert not final.valid and not final.materials
    assert not (await gateway.recall(req, event=event)).materials
    assert provider.calls == 1


async def test_request_purpose_single_flight_and_available_reuse():
    provider, _, event, req, gateway = await external_runtime()
    provider.release.clear()
    first = asyncio.create_task(gateway.recall(req, event=event))
    await provider.started.wait()
    second = asyncio.create_task(gateway.recall(req, event=event))
    await asyncio.sleep(0)
    provider.release.set()
    a, b = await asyncio.gather(first, second)
    assert a.materials == b.materials and b.reused and provider.calls == 1
    reused = await gateway.recall(req, event=event, available=a.materials)
    assert reused.reused and provider.calls == 1
    conflict = await gateway.recall(replace(req, query="changed"), event=event)
    assert conflict.reason_codes == ("request_purpose_conflict",)
    await gateway.recall(replace(req, purpose="proactive"), event=event)
    assert provider.calls == 2


async def test_unbind_during_recall_or_validation_rejects_all_material():
    provider, _, event, req, gateway = await external_runtime()
    provider.release.clear()
    task = asyncio.create_task(gateway.recall(req, event=event))
    await provider.started.wait()
    provider.revision += 1
    provider.bound = False
    provider.release.set()
    assert not (await task).materials
    provider, _, event, req, gateway = await external_runtime()
    result = await gateway.recall(req, event=event)
    provider.change_during_validation = True
    assert not (await gateway.validate_evidence(req, result.materials, event=event)).valid


async def test_provider_filtering_reload_and_forged_receipt_fail_closed():
    provider, backend, event, req, gateway = await external_runtime()
    result = await gateway.recall(req, event=event)
    changed = replace(result.materials[0], text="forged")
    assert not (await gateway.validate_evidence(req, (changed,), event=event)).valid
    provider.allow = False
    assert not (await gateway.validate_evidence(req, result.materials, event=event)).valid
    provider.allow = True
    backend.provider = lambda: Provider()
    assert not (await gateway.validate_evidence(req, result.materials, event=event)).valid


@pytest.mark.parametrize(
    "field",
    [
        "source_account",
        "owner_account",
        "subject_accounts",
        "source_session_id",
        "persona_id",
        "audience",
        "sensitivity",
        "_identity_revision",
        "source_window",
        "create_time",
    ],
)
async def test_incomplete_external_provenance_is_never_filled_from_query(field):
    provider, _, event, req, gateway = await external_runtime()
    rows = await provider.search_memories_for_event("tea", event, persona_id=req.context.persona_id)
    del rows[0].metadata[field]
    provider.rows = rows
    result = await gateway.recall(req, event=event)
    assert not result.materials
    assert "external_provenance_incomplete_or_out_of_scope" in result.reason_codes


@pytest.mark.parametrize(
    "read,export", [(True, False), (False, True), (False, False), (True, True)]
)
async def test_external_read_write_independence_and_background_degradation(read, export):
    provider, backend, event, req, gateway = await external_runtime(
        read_enabled=read,
        export_enabled=export,
    )
    assert backend.capabilities().recall is read
    assert not backend.capabilities().append_experience
    assert not (await gateway.recall(req)).materials
    assert provider.calls == 0
    assert not (await gateway.recall(req, event=Event(synthetic=True))).materials
    assert provider.calls == 0
    await gateway.recall(replace(req, request_id="foreground"), event=event)
    assert provider.calls == int(read)
    assert not (await backend.append(req, own(), "key")).accepted
    assert (await gateway.recall(request(), available=(own(),))).materials


async def test_provider_timeout_and_gateway_close_leave_no_running_request():
    provider, _, event, req, gateway = await external_runtime(timeout=0.01)
    provider.release.clear()
    result = await gateway.recall(req, event=event)
    assert result.reason_codes == ("external_provider_unavailable",)
    assert not gateway._inflight
    provider, _, event, req, gateway = await external_runtime()
    provider.release.clear()
    task = asyncio.create_task(gateway.recall(req, event=event))
    await provider.started.wait()
    await gateway.close()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not gateway._inflight and not gateway._cache


async def test_discovery_failure_keeps_own_material_and_reports_unavailable():
    def broken():
        raise RuntimeError("discovery is unavailable")

    backend = LivingMemoryAdapter(broken)
    gateway = MemoryGateway(backend, clock=lambda: 150)
    assert not backend.capabilities().recall
    assert (await gateway.recall(request(), available=(own(),))).materials
    result = await gateway.recall(request(), event=Event())
    assert result.reason_codes == ("external_provider_unavailable",)


async def test_read_switch_off_invalidates_cached_evidence():
    _, backend, event, req, gateway = await external_runtime()
    result = await gateway.recall(req, event=event)
    backend.read_enabled = False
    assert not (await gateway.validate_evidence(req, result.materials, event=event)).valid
    assert not (await gateway.recall(req, event=event)).materials


async def test_external_metadata_change_invalidates_whole_generation():
    provider, _, event, req, gateway = await external_runtime()
    result = await gateway.recall(req, event=event)

    async def changed(rows):
        rows[0].metadata["audience"] = "public"
        return rows

    provider.validate_identity_results = changed
    final = await gateway.validate_evidence(req, result.materials, event=event)
    assert not final.valid and not final.materials


async def test_caller_cancellation_does_not_start_duplicate_retrieval():
    provider, _, event, req, gateway = await external_runtime()
    provider.release.clear()
    task = asyncio.create_task(gateway.recall(req, event=event))
    await provider.started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    replacement = asyncio.create_task(gateway.recall(req, event=event))
    provider.release.set()
    assert (await replacement).materials
    assert provider.calls == 1
    await gateway.close()


async def test_inflight_limit_denies_other_request_without_extra_provider_call():
    provider, backend, event, req, _ = await external_runtime()
    gateway = MemoryGateway(backend, max_requests=1, clock=lambda: 150)
    provider.release.clear()
    task = asyncio.create_task(gateway.recall(req, event=event))
    await provider.started.wait()
    busy = await gateway.recall(replace(req, request_id="second"), event=event)
    assert busy.reason_codes == ("memory_busy",) and provider.calls == 1
    provider.release.set()
    await task
    await gateway.close()


@pytest.mark.parametrize("limit", [0, True, float("nan"), 1.5])
def test_memory_cache_limit_is_finite_integer(limit):
    with pytest.raises(ValueError):
        MemoryGateway(max_requests=limit)
