"""Purpose selection and real shared-runtime quota, with offline model bindings."""

import asyncio
from collections import OrderedDict
from types import SimpleNamespace

import pytest
from astrbot_plugin_livingemotion.adapters.memory import MemoryGateway
from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import ActorRole, Event
from astrbot_plugin_livingemotion.runtime import models
from astrbot_plugin_livingemotion.runtime.background import BackgroundRuntime
from astrbot_plugin_livingemotion.storage import SQLiteStore

from .fakes import context


class Binding:
    def __init__(self, provider):
        if provider is None:
            raise models.ModelUnavailable("provider_missing")
        self.provider = provider
        self.fingerprint = provider.pid

    def count(self, system, data):
        return len(system.encode("utf-8")) + len(data.encode("utf-8")) + 256

    async def generate(self, system, data, tokens, timeout):
        self.provider.calls.append((system, data, tokens, timeout))
        self.provider.started.set()
        await self.provider.release.wait()
        return '{"body":"My own bot reflection."}'


class App(models.Generation):
    def __init__(self, store, runtime, providers):
        self.store, self.runtime, self.config = store, runtime, runtime.config
        self.providers = providers
        self.closed, self.valid = False, True
        self._revision, self._admin = "rev", object()
        self.instance_id = context().instance_id
        self._services = OrderedDict()
        self.memory = MemoryGateway(clock=store.clock)

        async def get(pid):
            return self.providers.get(pid)

        async def current(route):
            return "chat"
        self.host = SimpleNamespace(
            provider_manager=SimpleNamespace(get_provider_by_id=get),
            get_current_chat_provider_id=current,
        )

    @property
    def revision(self):
        return self._revision

    async def validate_context(self, source, generation=None):
        return self.valid and (generation is None
                               or await self.store.get_generation(source) == generation)

    def effective_mode(self, context):
        return "active" if self.valid else "disabled"

    async def legacy_constraints(self, context, purpose):
        return {"allowed": self.valid}

    async def night_guard(self, *args):
        return True


@pytest.fixture
async def model_app(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "OpenAIBinding", Binding)
    config = Config(
        diary_enabled=True, dream_enabled=True, catchup_enabled=True, closing_enabled=True,
        diary_at="00:00", timezone="UTC", model_input_tokens=16384,
        diary_provider_id="diary-native", dream_provider_id="dream-native",
        catchup_provider_id="catchup-native", closing_provider_id="closing-native",
        model_daily_limit=2,
    )
    store = SQLiteStore(tmp_path / "models.sqlite3", config=config, clock=lambda: 150)
    await store.open()
    runtime = BackgroundRuntime(store, config)
    providers = {}
    for pid in ("chat", "diary-native", "dream-native", "catchup-native", "closing-native"):
        release = asyncio.Event()
        release.set()
        providers[pid] = SimpleNamespace(
            pid=pid, calls=[], started=asyncio.Event(), release=release,
        )
    app = App(store, runtime, providers)
    await runtime.start()
    try:
        yield app
    finally:
        await app.close_generation_resources()
        await app.memory.close()
        await runtime.stop()
        await store.close()


async def test_p4_purpose_provider_selection_and_one_shared_daily_limit(model_app):
    app = model_app
    for purpose in ("diary", "dream", "catchup", "closing"):
        assert (await app.model_binding(context(), purpose=purpose)).fingerprint == purpose + "-native"
    await app.purpose_model(context(), "catchup", "rules", "full untruncated data", "catchup-1")
    await app.purpose_model(context(), "closing", "rules", "closing data", "closing-1")
    with pytest.raises(ValueError):
        await app.purpose_model(context(), "diary", "rules", "data", "diary-1")
    assert len(app.providers["catchup-native"].calls) == 1
    assert len(app.providers["closing-native"].calls) == 1
    assert not app.providers["diary-native"].calls
    reservations = await app.store._run(
        lambda db: db.execute("SELECT purpose FROM quota_reservations WHERE pool='model'").fetchall())
    assert {row[0] for row in reservations} == {"catchup", "closing"}


async def test_p4_purpose_generation_revalidates_after_provider_call(model_app):
    app = model_app
    provider = app.providers["catchup-native"]
    provider.release.clear()
    task = asyncio.create_task(app.purpose_model(
        context(), "catchup", "rules", "private synthetic data", "guarded"))
    await provider.started.wait()
    app.valid = False
    provider.release.set()
    with pytest.raises(ValueError):
        await task
    assert len(provider.calls) == 1


async def test_p4_purpose_oversize_rejected_before_dispatch(model_app):
    app = model_app
    with pytest.raises(ValueError, match="model_token_limit"):
        await app.purpose_model(context(), "catchup", "rules", "x" * 20000, "oversize")
    assert not app.providers["catchup-native"].calls
    assert not app.runtime.health()["pending"]


async def test_p4_independent_diary_dream_binding_and_unavailable_other_model(model_app):
    app = model_app
    app.providers.pop("dream-native")
    service = await app.experience_service(context())
    event = Event("h1", "host", "message", context(), ActorRole.HUMAN, 100, "h1",
                  actor_id=context().account_id, body="a synthetic real encounter")
    assert (await app.store.commit_event(event, 0)).accepted
    ticket = await service.queue_diary(context())
    assert ticket["status"] == "queued"
    await app.runtime.join()
    assert service.outcome(ticket["job_id"])["status"] == "created"
    assert len(app.providers["diary-native"].calls) == 1
    assert not app.providers["chat"].calls
    entry, _ = await app.store.load_experience(ticket["experience_id"])
    assert entry.body.startswith("日期：1970-01-01（UTC）\n城市：未配置\n天气：未获取")
    await service.close()
