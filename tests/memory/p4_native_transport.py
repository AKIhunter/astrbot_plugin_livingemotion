"""Explicit offline lane: actual native source methods and synthetic SDK transports.

Run with ASTRBOT_HOST_SOURCE=<frozen host source> pytest tests/memory/p4_native_transport.py.
Only upstream transport/decorator/base dependencies are fixtures, never source methods.
"""

import asyncio
import importlib.util
import logging
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from astrbot_plugin_livingemotion.adapters.embedding import NativeEmbedding


@pytest.fixture
def native(monkeypatch):
    root = Path(os.environ["ASTRBOT_HOST_SOURCE"])
    prefix = "astrbot.core.provider"
    for name in ("astrbot", "astrbot.core", prefix, prefix + ".sources"):
        module = ModuleType(name)
        module.__path__ = []
        module.logger = logging.getLogger("p4-offline")
        monkeypatch.setitem(sys.modules, name, module)

    class Base:
        def __init__(self, config, settings):
            self.provider_config = config
            self.request_headers = {"X-Test": "offline"}

        def set_model(self, model):
            self.model = model

        def get_model(self):
            # Actual OpenAI native base keeps model_name separate from the
            # self.model used by its request method.
            return getattr(self, "model_name", "")

    base = ModuleType(prefix + ".provider")
    base.EmbeddingProvider = Base
    monkeypatch.setitem(sys.modules, base.__name__, base)
    entities = ModuleType(prefix + ".entities")
    entities.ProviderType = SimpleNamespace(EMBEDDING="embedding")
    monkeypatch.setitem(sys.modules, entities.__name__, entities)
    register = ModuleType(prefix + ".register")
    register.register_provider_adapter = lambda *a, **k: lambda cls: cls
    monkeypatch.setitem(sys.modules, register.__name__, register)
    calls = []

    class Client:
        def __init__(self, **options):
            self.options = options
            self.embeddings = self

        def with_options(self, **options):
            calls.append(("options", options))
            return Client(**options)

        async def create(self, **kwargs):
            calls.append(("openai", kwargs))
            return SimpleNamespace(data=[SimpleNamespace(embedding=[3.0, 4.0])])

    openai = ModuleType("openai")
    openai.AsyncOpenAI = Client
    monkeypatch.setitem(sys.modules, "openai", openai)
    httpx = ModuleType("httpx")
    httpx.AsyncClient = lambda **kwargs: None
    monkeypatch.setitem(sys.modules, "httpx", httpx)

    class DashTransport:
        @staticmethod
        def call(**kwargs):
            calls.append(("dashscope", kwargs))
            return SimpleNamespace(status_code=200, output={
                "embeddings": [{"text_index": 0, "embedding": [3.0, 4.0]}],
            })
    dashscope = ModuleType("dashscope")
    dashscope.TextEmbedding = dashscope.MultiModalEmbedding = DashTransport
    monkeypatch.setitem(sys.modules, "dashscope", dashscope)
    classes = {}
    for name, classname in (
        ("openai_embedding_source", "OpenAIEmbeddingProvider"),
        ("dashscope_embedding_source", "DashScopeEmbeddingProvider"),
    ):
        path = root / "astrbot/core/provider/sources" / (name + ".py")
        spec = importlib.util.spec_from_file_location(prefix + ".sources." + name, path)
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, spec.name, module)
        spec.loader.exec_module(module)
        classes[name] = getattr(module, classname)
    return classes, calls


@pytest.mark.parametrize("kind", ["openai", "dashscope"])
async def test_p4_actual_native_embedding_methods_offline(native, kind):
    classes, calls = native
    config = {
        "id": "native", "embedding_api_key": "synthetic-not-a-key",
        "embedding_api_base": ("https://api.openai.com/v1" if kind == "openai"
                               else "https://dashscope.aliyuncs.com/api/v1"),
        "embedding_model": "text-embedding-3-small" if kind == "openai" else "text-embedding-v4",
        "embedding_dimensions": 2,
    }
    provider = classes[kind + "_embedding_source"](config, {})

    async def get_provider(pid):
        return provider
    adapter = NativeEmbedding(SimpleNamespace(
        provider_manager=SimpleNamespace(get_provider_by_id=get_provider)), "native")
    binding = await adapter.binding()
    assert await binding.embed("offline body") == (0.6, 0.8)
    assert await binding.embed("offline body") == (0.6, 0.8)
    sent = [value for transport, value in calls if transport == kind]
    assert len(sent) == 1
    assert sent[0]["model"] == config["embedding_model"]
    assert sent[0]["input"] == ("offline body" if kind == "openai" else ["offline body"])
    if kind == "openai":
        assert sent[0]["dimensions"] == 2
        assert [v for transport, v in calls if transport == "options"] == [
            {"max_retries": 0, "timeout": 5.0},
        ]
        assert "max_retries" not in provider.client.options
    else:
        assert sent[0]["dimension"] == 2
        assert sent[0]["base_address"] == config["embedding_api_base"]
    namespace = binding.namespace
    # Restarting the adapter does not change the persisted model namespace.
    second = NativeEmbedding(adapter.host, "native")
    assert (await second.binding()).namespace == namespace
    provider.model = "changed-model"
    with pytest.raises(ValueError, match="embedding_provider_changed"):
        await binding.embed("offline body")
    await adapter.close()
    await second.close()


async def test_p4_embedding_singleflight_timeout_and_provider_reload(native):
    classes, _calls = native
    provider = classes["openai_embedding_source"]({
        "id": "native", "embedding_api_key": "synthetic",
        "embedding_model": "text-embedding-3-small", "embedding_dimensions": 2,
    }, {})
    release = asyncio.Event()
    entered = asyncio.Event()

    async def blocked(**kwargs):
        entered.set()
        await release.wait()
        return SimpleNamespace(data=[SimpleNamespace(embedding=[3.0, 4.0])])
    provider.client.create = blocked
    provider.client.with_options = lambda **kwargs: provider.client

    async def get_provider(pid):
        return provider
    adapter = NativeEmbedding(SimpleNamespace(
        provider_manager=SimpleNamespace(get_provider_by_id=get_provider)), "native", timeout=0.02)
    binding = await adapter.binding()
    tasks = [asyncio.create_task(binding.embed("same")) for _ in range(2)]
    await entered.wait()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    assert all(isinstance(item, ValueError) and str(item) == "embedding_timeout" for item in results)
    assert not adapter._inflight and not adapter._cache
    await adapter.close()
