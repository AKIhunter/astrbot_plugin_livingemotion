"""Native embedding bindings; no credentials, model probes, or SDK retries."""

from __future__ import annotations

import asyncio
import copy
import math
from collections import OrderedDict
from dataclasses import dataclass

from ..contracts import finite, stable_key


class EmbeddingUnavailable(ValueError):
    pass


def checked_vector(value, dimension=0):
    if (not isinstance(value, (list, tuple)) or not 1 <= len(value) <= 8192
            or dimension and len(value) != dimension):
        raise EmbeddingUnavailable("embedding_dimension_invalid")
    if any(type(v) not in (float, int) or not math.isfinite(v) for v in value):
        raise EmbeddingUnavailable("embedding_vector_invalid")
    norm = math.hypot(*value)
    if not math.isfinite(norm) or norm == 0:
        raise EmbeddingUnavailable("embedding_vector_invalid")
    return tuple(float(v) / norm for v in value)


@dataclass(frozen=True)
class EmbeddingBinding:
    owner: object
    provider: object
    fingerprint: str
    index_key: str
    model: str
    dimension: int

    @property
    def namespace(self):
        return self.namespace_for(self.dimension)

    def namespace_for(self, dimension):
        return stable_key(self.index_key, dimension)

    async def embed(self, text):
        return await self.owner.embed(self, text)


class NativeEmbedding:
    """Only inspected native OpenAI/DashScope embedding classes are accepted.

    A DashScope native call may own a synchronous SDK thread after cancellation;
    its result is never consumed after our timeout or lifecycle invalidation.
    """

    def __init__(self, host, provider_id, *, timeout=5.0, max_cache=128):
        finite(timeout, "embedding_timeout", 0.001, 60)
        if type(max_cache) is not int or not 1 <= max_cache <= 1024:
            raise ValueError("embedding_cache_limit")
        self.host, self.provider_id, self.timeout = host, provider_id, timeout
        self.max_cache = max_cache
        self._cache = OrderedDict()
        self._inflight = {}
        self._dimensions = {}
        self._closed = False

    @staticmethod
    def _supported(provider):
        classes = []
        for module, name in (
            ("astrbot.core.provider.sources.openai_embedding_source", "OpenAIEmbeddingProvider"),
            ("astrbot.core.provider.sources.dashscope_embedding_source",
             "DashScopeEmbeddingProvider"),
        ):
            try:
                from importlib import import_module
                classes.append(getattr(import_module(module), name))
            except ImportError:
                continue
        return type(provider) in classes

    async def binding(self):
        if self._closed or not self.provider_id:
            raise EmbeddingUnavailable("embedding_not_configured")
        provider = await asyncio.wait_for(
            self.host.provider_manager.get_provider_by_id(self.provider_id), self.timeout,
        )
        if not self._supported(provider):
            raise EmbeddingUnavailable("embedding_provider_unsupported")
        # These exact native classes send self.model on the wire. OpenAI's
        # inherited get_model() may still expose an empty model_name.
        model = getattr(provider, "model", None)
        config = provider.provider_config
        dimension = provider.get_dim()
        if (not isinstance(model, str) or not model.strip()
                or type(dimension) is not int or not 0 <= dimension <= 8192):
            raise EmbeddingUnavailable("embedding_model_invalid")
        index_key = stable_key(self.provider_id, model, config)
        dimension = dimension or self._dimensions.get(index_key, 0)
        return EmbeddingBinding(
            self, provider, stable_key(self.provider_id, id(provider), model, config),
            index_key, model, dimension,
        )

    async def _current(self, binding):
        current = await self.binding()
        if current.fingerprint != binding.fingerprint:
            raise EmbeddingUnavailable("embedding_provider_changed")

    async def embed(self, binding, text):
        if not isinstance(text, str) or not text.strip() or len(text) > 16000:
            raise EmbeddingUnavailable("embedding_text_invalid")
        await self._current(binding)
        key = stable_key(binding.fingerprint, text)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        task = self._inflight.get(key)
        if task is None:
            if len(self._inflight) >= 8:
                raise EmbeddingUnavailable("embedding_busy")
            task = asyncio.create_task(self._embed(binding, text))
            self._inflight[key] = task
            task.add_done_callback(lambda done: done.exception() if not done.cancelled() else None)
        value = await asyncio.shield(task)
        await self._current(binding)
        self._cache[key] = value
        while len(self._cache) > self.max_cache:
            self._cache.popitem(last=False)
        return value

    async def _embed(self, binding, text):
        key = stable_key(binding.fingerprint, text)
        try:
            provider = copy.copy(binding.provider)
            provider.provider_config = copy.deepcopy(binding.provider.provider_config)
            if hasattr(provider, "client"):
                provider.client = binding.provider.client.with_options(
                    max_retries=0, timeout=self.timeout,
                )
            value = await asyncio.wait_for(provider.get_embedding(text), self.timeout)
            await self._current(binding)
            vector = checked_vector(value, binding.dimension)
            known = self._dimensions.get(binding.index_key)
            if known is not None and known != len(vector):
                raise EmbeddingUnavailable("embedding_dimension_changed")
            self._dimensions[binding.index_key] = len(vector)
            return vector
        except TimeoutError:
            raise EmbeddingUnavailable("embedding_timeout") from None
        except EmbeddingUnavailable:
            raise
        except Exception:  # noqa: BLE001 - optional host SDK failure cannot leak private text.
            raise EmbeddingUnavailable("embedding_unavailable") from None
        finally:
            self._inflight.pop(key, None)

    async def close(self):
        self._closed = True
        tasks = tuple(self._inflight.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._inflight.clear()
        self._cache.clear()
        self._dimensions.clear()
