"""Native provider classes with mock wire/SDK transport, never a paid API."""

import json
from types import SimpleNamespace
from unittest.mock import patch


async def native_transports(core, e, *, final=False):
    import httpx
    from openai import AsyncOpenAI
    from astrbot.core import astrbot_config
    from astrbot.core.provider.sources.openai_source import ProviderOpenAIOfficial
    from astrbot.core.provider.sources.openai_embedding_source import OpenAIEmbeddingProvider
    from astrbot.core.provider.sources.dashscope_embedding_source import DashScopeEmbeddingProvider

    wires, fault = [], [False]

    def wire(request):
        payload = json.loads(request.content)
        wires.append({"path": request.url.path, "payload": payload})
        if fault[0]:
            return httpx.Response(500, json={"error": {
                "type": "synthetic_fault", "message": "Synthetic transport failure.",
            }})
        if request.url.path.endswith("/embeddings"):
            return httpx.Response(200, json={
                "object": "list", "model": "retro-embedding",
                "data": [{"object": "embedding", "index": 0, "embedding": [3.0, 4.0]}],
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            })
        return httpx.Response(200, json={
            "id": "retro-response", "object": "chat.completion", "created": 1,
            "model": "retro-chat",
            "choices": [{"index": 0, "message": {
                "role": "assistant", "content": "Synthetic.",
            }, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })

    providers = []
    client = httpx.AsyncClient(transport=httpx.MockTransport(wire), trust_env=False)
    try:
        chat = ProviderOpenAIOfficial(
            {"id": "retro-openai", "type": "openai_chat_completion", "key": ["synthetic-not-a-key"],
             "api_base": "http://127.0.0.1:1/v1", "model": "retro-chat",
             "custom_extra_body": {"max_tokens": 999, "n": 2}},
            astrbot_config["provider_settings"],
        )
        providers.append(chat)
        await chat.client.close()
        chat.client = AsyncOpenAI(
            api_key="synthetic-not-a-key", base_url="http://127.0.0.1:1/v1",
            http_client=client, max_retries=0,
        )
        if final:
            from retro_common import product
            before_config = json.dumps(chat.provider_config, sort_keys=True)
            binding = product("runtime.models").OpenAIBinding(chat)
            result = await binding.generate("Synthetic system.", "Synthetic input.", 64, 2)
            e.check("transport.product_chat_response", result == "Synthetic.")
            payload = wires[-1]["payload"]
            e.check("transport.product_wire_budget", payload.get("max_tokens") == 64
                    and payload.get("n") == 1)
            e.check("transport.product_host_provider_unchanged",
                    json.dumps(chat.provider_config, sort_keys=True) == before_config)
            before = len(wires)
            fault[0] = True
            try:
                await binding.generate("Synthetic.", "Synthetic.", 64, 2)
            except product("runtime.background").ModelResultUnknown:
                e.check("transport.product_unknown_fail_closed", True)
            else:
                e.check("transport.product_unknown_fail_closed", False)
            finally:
                fault[0] = False
            e.check("transport.product_unknown_not_retried", len(wires) == before + 1)
        else:
            result = await chat.text_chat(prompt="Synthetic input.", system_prompt="")
            e.check("transport.native_openai_chat", result.completion_text == "Synthetic.",
                    layer="native_provider_mock_http_transport")
        embedding = OpenAIEmbeddingProvider(
            {"id": "retro-embedding", "type": "openai_embedding",
             "embedding_api_key": "synthetic-not-a-key",
             "embedding_api_base": "http://127.0.0.1:1/v1",
             "embedding_model": "retro-embedding", "embedding_dimensions": 2},
            astrbot_config["provider_settings"],
        )
        providers.append(embedding)
        await embedding.client.close()
        embedding.client = chat.client
        vector = await embedding.get_embedding("Synthetic.")
        e.check("transport.native_openai_embedding", vector == [3.0, 4.0],
                layer="native_provider_mock_http_transport")
        dash = DashScopeEmbeddingProvider(
            {"id": "retro-dash", "type": "dashscope_embedding",
             "embedding_api_key": "synthetic-not-a-key",
             "embedding_api_base": "http://127.0.0.1:1/api/v1",
             "embedding_model": "text-embedding-v4", "embedding_dimensions": 2},
            astrbot_config["provider_settings"],
        )
        calls = []

        def sdk(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                status_code=200, output={"embeddings": [
                    {"text_index": 0, "embedding": [3.0, 4.0]},
                ]},
            )

        with patch(
            "astrbot.core.provider.sources.dashscope_embedding_source.TextEmbedding.call",
            side_effect=sdk,
        ):
            vector = await dash.get_embedding("Synthetic.")
        e.check("transport.native_dashscope_sdk", vector == [3.0, 4.0]
                and len(calls) == 1 and calls[0]["base_address"].startswith("http://127.0.0.1"),
                layer="native_provider_mock_sdk_transport")
        if final:
            await product_embedding(core, embedding, dash, sdk, wires, e)
        e.report["transport_wire_paths"] = [entry["path"] for entry in wires]
        e.report["transport_sdk_calls"] = len(calls)
    finally:
        for provider in providers:
            if getattr(provider, "client", None):
                await provider.client.close()
        await client.aclose()


async def product_embedding(core, embedding, dash, sdk, wires, e):
    from retro_common import product
    module = product("adapters.embedding")
    registered = {}
    for provider in (embedding, dash):
        pid = provider.provider_config["id"]
        registered[pid] = core.provider_manager.inst_map.get(pid)
        core.provider_manager.inst_map[pid] = provider
    try:
        for label, provider in (("openai", embedding), ("dashscope", dash)):
            owner = module.NativeEmbedding(core.star_context, provider.provider_config["id"],
                                           timeout=2)
            try:
                binding = await owner.binding()
                before = len(wires)
                with patch(
                    "astrbot.core.provider.sources.dashscope_embedding_source.TextEmbedding.call",
                    side_effect=sdk,
                ):
                    first = await binding.embed("Synthetic adapter input.")
                    second = await binding.embed("Synthetic adapter input.")
                e.check("transport.product_" + label + "_embedding",
                        len(first) == 2 and abs(first[0] - 0.6) < 0.001
                        and abs(first[1] - 0.8) < 0.001 and first == second)
                if label == "openai":
                    e.check("transport.product_embedding_cache_one_wire", len(wires) == before + 1)
                core.provider_manager.inst_map.pop(provider.provider_config["id"])
                try:
                    await binding.embed("Synthetic revoked provider.")
                except module.EmbeddingUnavailable:
                    e.check("transport.product_" + label + "_revocation_closed", True)
                else:
                    e.check("transport.product_" + label + "_revocation_closed", False)
            finally:
                await owner.close()
    finally:
        for pid, previous in registered.items():
            if previous is None:
                core.provider_manager.inst_map.pop(pid, None)
            else:
                core.provider_manager.inst_map[pid] = previous
