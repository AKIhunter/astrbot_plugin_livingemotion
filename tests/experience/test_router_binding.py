"""Offline checks for multi_api_router bindings; no network or real model."""

import asyncio
from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.runtime.background import ModelResultUnknown
from astrbot_plugin_livingemotion.runtime.models import (
    Generation, ModelUnavailable, RouterBinding,
)


def router(identifier="multi_api_router:upstream_12", model="deepseek-v4-pro-202606",
           text="ok", delay=0.0):
    class MultiApiRouterProvider:
        def __init__(self):
            self.calls = []

        def meta(self):
            return SimpleNamespace(id=identifier)

        def get_model(self):
            return model

        async def text_chat(self, **kwargs):
            self.calls.append(kwargs)
            if delay:
                await asyncio.sleep(delay)
            return SimpleNamespace(role="assistant", completion_text=text)

    return MultiApiRouterProvider()


async def test_router_binding_forwards_budget_without_openai_contract():
    provider = router()
    binding = RouterBinding(provider)
    assert binding.count("sys", "data") == len(b"data") + len(b"sys") + 256
    assert await binding.generate("sys", "data", 64, 1) == "ok"
    call = provider.calls[0]
    assert call["prompt"] == "data" and call["system_prompt"] == "sys"
    assert call["contexts"] == [] and call["func_tool"] is None
    assert call["max_tokens"] == 64 and call["request_max_retries"] == 1


async def test_router_binding_only_accepts_pinned_upstreams():
    with pytest.raises(ModelUnavailable) as unpinned:
        RouterBinding(router(identifier="multi_api_router"))
    assert str(unpinned.value) == "provider_budget_contract_unsupported"
    with pytest.raises(ModelUnavailable) as empty:
        RouterBinding(router(model=""))
    assert str(empty.value) == "model_unavailable"


async def test_router_binding_timeout_and_output_validation():
    with pytest.raises((asyncio.TimeoutError, TimeoutError)):
        await RouterBinding(router(delay=0.05)).generate("sys", "data", 8, 0.001)
    with pytest.raises(ModelResultUnknown, match="model_output_invalid"):
        await RouterBinding(router(text="x" * 9)).generate("sys", "data", 8, 1)


async def test_select_model_binding_dispatches_router_provider():
    provider = router()
    generation = Generation()
    generation.config = SimpleNamespace(
        provider_id="", fallback_provider_id="",
        diary_provider_id="multi_api_router:upstream_12",
    )
    generation.host = SimpleNamespace(
        provider_manager=SimpleNamespace(get_provider_by_id=lambda _pid: provider))
    binding = await generation._select_model_binding("diary")
    assert isinstance(binding, RouterBinding)


async def test_select_model_binding_rejects_unpinned_router():
    provider = router(identifier="multi_api_router", model="automatic")
    generation = Generation()
    generation.config = SimpleNamespace(
        provider_id="", fallback_provider_id="",
        diary_provider_id="multi_api_router",
    )
    generation.host = SimpleNamespace(
        provider_manager=SimpleNamespace(get_provider_by_id=lambda _pid: provider))
    with pytest.raises(ModelUnavailable) as unavailable:
        await generation._select_model_binding("diary")
    assert str(unavailable.value) == "provider_budget_contract_unsupported"
