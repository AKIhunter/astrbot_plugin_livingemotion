"""V1 lexical read compatibility without migration or mutations of the old DB."""

import sqlite3
from dataclasses import replace
from types import SimpleNamespace

import pytest
from astrbot_plugin_livingemotion.adapters.memory import LocalVectorMemory, MemoryGateway
from astrbot_plugin_livingemotion.adapters.memory.legacy import LegacyExplicitReader
from astrbot_plugin_livingemotion.adapters.memory.local_lite import LocalLiteMemory
from astrbot_plugin_livingemotion.runtime.memory import build_memory_backend
from astrbot_plugin_livingemotion.storage import SQLiteStore

from .fakes import context, own, request
from .test_p4_vector import Embedding


@pytest.fixture
async def legacy(tmp_path):
    clock = [150.0]
    path = tmp_path / "explicit_memory.sqlite3"
    old = LocalLiteMemory(path, clock=lambda: clock[0])
    assert (await old.remember(request(), own())).accepted
    store = SQLiteStore(tmp_path / "livingemotion.sqlite3", clock=lambda: clock[0])
    await store.open()
    config = SimpleNamespace(memory_read=True, memory_mode="none")
    backend = await build_memory_backend(store, None, lambda name: None, config)
    snapshot = (path.read_bytes(), path.stat().st_mtime_ns)
    try:
        yield backend, old, clock
    finally:
        assert (path.read_bytes(), path.stat().st_mtime_ns) == snapshot
        await backend.close()
        await store.close()


async def test_p4_legacy_read_without_embedding_does_not_claim_vectors(legacy):
    backend, _, _ = legacy
    assert backend.capabilities().recall
    gateway = MemoryGateway(backend, clock=backend.store.clock)
    result = await gateway.recall(request())
    assert len(result.materials) == 1
    assert result.materials[0].text == own().text
    assert result.materials[0].evidence.provider == "local_lite"
    assert result.materials[0].evidence.expires_at == own().evidence.expires_at
    assert "embedding_not_configured" in result.reason_codes
    assert (await gateway.validate_evidence(request(), result.materials)).valid
    assert not (await backend.recall(request(query="unmatched"))).materials
    assert not (await backend.remember(request(), own())).accepted
    counts = await backend.store._run(lambda db: [
        db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("le_memory_text", "le_memory_vectors")
    ])
    assert counts == [0, 0]
    await gateway.close()


@pytest.mark.parametrize("changes", [
    {"account_id": "other"}, {"persona_id": "other"}, {"bot_id": "other"},
    {"scene_id": "other"}, {"platform": "bili"}, {"instance_id": "other"},
    {"identity_revision": "new"}, {"persona_revision": "new"},
    {"audience": ("unauthorized",)},
])
async def test_p4_legacy_context_and_authority_isolation(legacy, changes):
    backend, _, _ = legacy
    material = (await backend.recall(request())).materials
    other = request(context(**changes))
    assert not (await backend.recall(other)).materials
    assert not await backend.validate(other, material)


@pytest.mark.parametrize("operation", ["source", "scope", "host_clear", "expiry"])
async def test_p4_legacy_deletion_expiry_and_restart(legacy, operation):
    backend, _, clock = legacy
    old = (await backend.recall(request())).materials
    if operation == "source":
        await backend.forget(context(), own().evidence.source_id)
    elif operation == "scope":
        await backend.forget(context())
    elif operation == "host_clear":
        assert (await backend.store.clear_scope(
            context(), 0, reason_code="p4_legacy_test",
        )).accepted
    else:
        clock[0] = 200
    assert not await backend.validate(request(), old)
    assert not (await backend.recall(request())).materials
    restarted = LocalVectorMemory(backend.store, None, legacy_path=backend.legacy.path)
    await restarted.open()
    assert not (await restarted.recall(request())).materials
    assert not await restarted.validate(request(), old)
    await restarted.close()


async def test_p4_legacy_delete_at_final_validation_boundary(legacy):
    backend, _, _ = legacy
    materials = (await backend.recall(request())).materials
    original = backend.data._run

    async def erase_before_snapshot(operation):
        # forget calls VectorStore._run too; avoid reinjecting into that transaction.
        backend.data._run = original
        await backend.forget(context(), own().evidence.source_id)
        return await original(operation)
    backend.data._run = erase_before_snapshot
    assert not await backend.validate(request(), materials)


async def test_p4_legacy_read_switch_does_not_get_bypassed(legacy):
    backend, _, _ = legacy
    materials = (await backend.recall(request())).materials
    backend.read_enabled = False
    assert not backend.capabilities().recall
    assert not (await backend.recall(request())).materials
    assert not await backend.validate(request(), materials)


async def test_p4_legacy_vector_combination_preserves_old_provenance(legacy):
    backend, _, _ = legacy
    embedding = Embedding()
    backend.embedding, backend.write_enabled = embedding, True
    await backend.remember(request(), own(source_id="new"))
    result = await backend.recall(request())
    assert [item.evidence.provider for item in result.materials] == [
        "local_lite", "local_vector",
    ]
    assert await backend.validate(request(), result.materials)
    await backend.forget(context(), own().evidence.source_id)
    assert [item.evidence.provider for item in (await backend.recall(request())).materials] == [
        "local_vector",
    ]


async def test_p4_legacy_no_file_creation_or_external_fallback(tmp_path, monkeypatch):
    store = SQLiteStore(tmp_path / "livingemotion.sqlite3", clock=lambda: 150)
    await store.open()
    try:
        backend = await build_memory_backend(
            store, None, lambda name: None, SimpleNamespace(memory_read=True),
        )
        assert not (await backend.recall(request())).materials
        assert not (tmp_path / "explicit_memory.sqlite3").exists()
        await backend.close()

        def forbidden(*args):
            raise AssertionError("external must not read local legacy")
        monkeypatch.setattr(LegacyExplicitReader, "_rows", forbidden)
        external = await build_memory_backend(
            store, None, lambda name: None,
            SimpleNamespace(livingmemory_enabled=True, memory_read=True),
        )
        assert external.capabilities().mode == "external"
        assert not (await external.fetch(request(), None)).materials
    finally:
        await store.close()


async def test_p4_legacy_changed_body_is_rejected(tmp_path):
    path = tmp_path / "explicit_memory.sqlite3"
    old = LocalLiteMemory(path, clock=lambda: 150)
    await old.remember(request(), own())
    store = SQLiteStore(tmp_path / "livingemotion.sqlite3", clock=lambda: 150)
    await store.open()
    backend = await build_memory_backend(
        store, None, lambda name: None, SimpleNamespace(memory_read=True),
    )
    try:
        materials = (await backend.recall(request())).materials
        with sqlite3.connect(path) as db:
            db.execute("UPDATE explicit_text SET body='changed after recall'")
        assert not await backend.validate(request(), materials)
        assert not await backend.validate(request(), (replace(materials[0], text="forged"),))
    finally:
        await backend.close()
        await store.close()
