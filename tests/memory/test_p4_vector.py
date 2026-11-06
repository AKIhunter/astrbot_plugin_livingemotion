"""Real temporary SQLite, asynchronous deletion races, and bounded local recall."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace

import pytest
from astrbot_plugin_livingemotion.adapters.memory import LocalVectorMemory, MemoryGateway
from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import ActorRole, Event, stable_key
from astrbot_plugin_livingemotion.runtime.background import BackgroundRuntime
from astrbot_plugin_livingemotion.runtime.memory import AutoMemoryIngestor, build_memory_backend
from astrbot_plugin_livingemotion.storage import SQLiteStore

from .fakes import context, own, request


class Embedding:
    def __init__(self):
        self.model, self.dimension = "model-a", 2
        self.started, self.release = asyncio.Event(), asyncio.Event()
        self.release.set()
        self.calls, self.closed = 0, False

    async def binding(self):
        return SimpleNamespace(
            fingerprint=self.model, dimension=self.dimension, embed=self.embed,
            namespace_for=lambda dimension: stable_key(self.model, dimension),
        )

    async def embed(self, text):
        self.calls += 1
        self.started.set()
        await self.release.wait()
        return [1.0] + [0.0] * (self.dimension - 1)

    async def close(self):
        self.closed = True


@pytest.fixture
async def vector(tmp_path):
    clock = [150.0]
    store = SQLiteStore(tmp_path / "vector.sqlite3", clock=lambda: clock[0])
    await store.open()
    embedding = Embedding()
    backend = LocalVectorMemory(store, embedding, write_enabled=True, max_records=3)
    await backend.open()
    try:
        yield backend, embedding, clock
    finally:
        await backend.close()
        await store.close()


async def test_p4_vector_remember_recall_validate_forget_and_restart(vector):
    backend, embedding, _ = vector
    assert (await backend.remember(request(), own())).accepted
    gateway = MemoryGateway(backend, clock=backend.store.clock)
    result = await gateway.recall(request())
    assert result.materials[0].text == own().text
    assert result.materials[0].evidence.provider == "local_vector"
    assert (await backend.remember(request(), own())).reason_code == "duplicate"
    assert not (await backend.remember(request(), replace(own(), text="conflict"))).accepted
    reopened = LocalVectorMemory(backend.store, embedding, write_enabled=True)
    await reopened.open()
    assert (await reopened.recall(request())).materials == result.materials
    await backend.forget(context(), own().evidence.source_id)
    assert not (await gateway.validate_evidence(request(), result.materials)).valid
    assert not (await gateway.recall(request())).materials
    await gateway.close()


@pytest.mark.parametrize("change", [
    {"platform": "bili"}, {"account_id": "other"}, {"persona_id": "other"},
    {"scene_id": "other"}, {"persona_revision": "new"}, {"identity_revision": "new"},
    {"audience": ("other",)}, {"bot_id": "other"}, {"adapter_id": "other"},
])
async def test_p4_vector_source_authority_isolation(vector, change):
    backend, _, _ = vector
    await backend.remember(request(), own())
    result = await backend.recall(request())
    assert result.materials
    target = request(context(**change))
    assert not (await backend.recall(target)).materials
    assert not await backend.validate(target, result.materials)


@pytest.mark.parametrize("operation", ["source", "scope", "host_clear", "expiry"])
async def test_p4_vector_late_embedding_never_resurrects_deleted_sources(vector, operation):
    backend, embedding, clock = vector
    embedding.release.clear()
    task = asyncio.create_task(backend.remember(request(), own()))
    await embedding.started.wait()
    if operation == "source":
        await backend.forget(context(), own().evidence.source_id)
    elif operation == "scope":
        await backend.forget(context())
    elif operation == "host_clear":
        result = await backend.store.clear_scope(context(), 0, reason_code="test_clear")
        assert result.accepted
    else:
        clock[0] = 201
    embedding.release.set()
    assert not (await task).accepted
    assert not (await backend.recall(request())).materials
    rows = await backend.store._run(
        lambda db: db.execute("SELECT count(*) FROM le_memory_text").fetchone()[0])
    assert rows == 0


async def test_p4_vector_model_dimension_namespace_and_original_ttl(vector):
    backend, embedding, clock = vector
    await backend.remember(request(), own())
    old = (await backend.recall(request())).materials
    embedding.model, embedding.dimension = "model-b", 3
    assert not (await backend.recall(request())).materials
    assert not await backend.validate(request(), old)
    await backend.remember(request(), own())
    assert (await backend.recall(request())).materials
    rows = await backend.store._run(
        lambda db: db.execute("SELECT namespace,dimension FROM le_memory_vectors").fetchall())
    assert len(rows) == 2 and {row[1] for row in rows} == {2, 3}
    clock[0] = 201
    assert not (await backend.recall(request())).materials
    rows = await backend.store._run(
        lambda db: db.execute("SELECT count(*) FROM le_memory_vectors").fetchone()[0])
    assert rows == 0


async def test_p4_vector_delete_during_use_time_validation_fails_closed(vector):
    backend, embedding, _ = vector
    await backend.remember(request(), own())
    result = await backend.recall(request())
    original = embedding.binding
    calls = 0

    async def delete_at_second_binding():
        nonlocal calls
        calls += 1
        if calls == 2:
            await backend.forget(context(), own().evidence.source_id)
        return await original()
    embedding.binding = delete_at_second_binding
    assert not await backend.validate(request(), result.materials)


async def test_p4_vector_capacity_and_unconfigured_backend(vector):
    backend, _, _ = vector
    for index in range(5):
        await backend.remember(request(), own(source_id=str(index), occurred_at=100 + index))
    rows = await backend.store._run(
        lambda db: db.execute("SELECT count(*) FROM le_memory_text").fetchone()[0])
    assert rows == 3
    cfg = SimpleNamespace(livingmemory_enabled=True, memory_read=True)
    external = await build_memory_backend(backend.store, None, lambda name: None, cfg)
    assert external.capabilities().mode == "external"
    assert not external.capabilities().recall  # never falls back to local duplication
    local = await build_memory_backend(backend.store, None, lambda name: None, Config())
    assert "embedding_not_configured" in local.capabilities().reason_codes


async def test_p4_ingestion_async_human_and_bot_submission_no_model_charge(vector):
    backend, embedding, _ = vector
    config = SimpleNamespace(enabled=True, mode="active", memory_write=True,
                             livingmemory_enabled=False, embedding_provider_id="native")
    runtime = BackgroundRuntime(backend.store, Config())
    await runtime.start()
    ingestor = AutoMemoryIngestor(backend, runtime, config=lambda: config)
    embedding.release.clear()
    event = Event("h1", "host", "message", context(), ActorRole.HUMAN, 100, "h1",
                  actor_id=context().account_id, body="human source")
    try:
        assert (await ingestor.ingest(event, generation=0))["status"] == "queued"
        await embedding.started.wait()
        assert not runtime.health()["outcomes"]  # ingest returned before vectorization
        embedding.release.set()
        await runtime.join()
        bot = replace(event, event_id="b1", source_id="b1", actor_role=ActorRole.BOT,
                      actor_id=context().bot_id, event_type="bot_reply_submitted",
                      body="submitted bot reply, not platform delivery")
        assert (await ingestor.ingest(bot, generation=0))["status"] == "queued"
        await runtime.join()
        assert len((await backend.recall(request())).materials) == 2
        assert (await ingestor.ingest(
            replace(bot, event_type="bot_action_succeeded"), generation=0))["status"] != "queued"
        assert await backend.store.quota_usage(period="1970-01-01", pool="model") == 0
    finally:
        await ingestor.close()
        await runtime.stop()


@pytest.mark.parametrize("change", ["delete_before_worker", "disable_during_embed", "close"])
async def test_p4_ingestion_lifecycle_and_queued_delete_race(vector, change):
    backend, embedding, _ = vector
    config = SimpleNamespace(enabled=True, mode="active", memory_write=True,
                             livingmemory_enabled=False, embedding_provider_id="native")
    runtime = BackgroundRuntime(backend.store, Config())
    await runtime.start()
    ingestor = AutoMemoryIngestor(backend, runtime, config=lambda: config)
    blocker = asyncio.Event()
    if change == "delete_before_worker":
        await runtime.submit("block", context(), 0, blocker.wait)
    embedding.release.clear()
    event = Event("h1", "host", "message", context(), ActorRole.HUMAN, 100, "h1",
                  actor_id=context().account_id, body="source")
    try:
        await ingestor.ingest(event, generation=0)
        if change == "delete_before_worker":
            await backend.forget(context())
            blocker.set()
            await embedding.started.wait()
        else:
            await embedding.started.wait()
            if change == "disable_during_embed":
                config.livingmemory_enabled = True
            else:
                await ingestor.close()
        embedding.release.set()
        await runtime.join()
        assert not (await backend.recall(request())).materials
    finally:
        await ingestor.close()
        await runtime.stop()
