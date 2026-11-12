"""Synthetic host boundary, real Generation/Runtime/API/Projector/SQLite."""

import asyncio
import copy
from dataclasses import replace
from datetime import datetime, timezone
import inspect
import json
from types import SimpleNamespace

from astrbot_plugin_livingemotion.api import LivingEmotionAPI
from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import BehaviorIntent, Context, Event
from astrbot_plugin_livingemotion.runtime.background import BackgroundRuntime
from astrbot_plugin_livingemotion.runtime.models import Generation
from astrbot_plugin_livingemotion.runtime.projector import Projector
from astrbot_plugin_livingemotion.runtime.refinement import Refinement
from astrbot_plugin_livingemotion.storage import SQLiteStore

NOW = datetime(2026, 11, 5, 23, 30, tzinfo=timezone.utc).timestamp()
PURPOSES = ("emotion", "behavior", "diary", "dream")


def scope(number=0):
    return Context("synthetic-bot", "synthetic-persona", "synthetic-adapter",
                   "offline", "private", f"synthetic-human-{number}",
                   f"synthetic-human-{number}",
                   audience=("synthetic-bot", f"synthetic-human-{number}"),
                   instance_id="synthetic-instance")


class Rig:
    def __init__(self, path, **changes):
        self.path = path
        self.now = NOW
        self.config = replace(
            Config(), emotion_model_enabled=True, autonomy_enabled=True,
            diary_enabled=True, dream_enabled=True, timezone="UTC", diary_at="00:00",
            **changes,
        )
        self.store = None
        self.runtime = None

    @property
    def day(self):
        return datetime.fromtimestamp(self.now, timezone.utc).date().isoformat()

    async def open(self):
        self.store = SQLiteStore(self.path, config=self.config, clock=lambda: self.now)
        await self.store.open()
        await self.store.recover_inflight()
        self.runtime = BackgroundRuntime(self.store, self.config)
        self.api = LivingEmotionAPI(
            self.store, self.config, self.runtime,
            project_event=Projector(self.store, lambda: self.config),
            instance_id="synthetic-instance",
        )
        await self.runtime.start()

    async def close(self):
        if self.runtime:
            await self.runtime.stop()
        if self.store:
            await self.store.close()

    async def reopen(self, **changes):
        await self.close()
        self.config = replace(self.config, **changes)
        await self.open()

    async def ingest(self, number, context=None, *, body="synthetic interaction",
                     occurred_at=None):
        event = Event(
            f"synthetic-event-{number}", "offline-test", "message", context or scope(),
            "human", self.now - 1 if occurred_at is None else occurred_at,
            f"synthetic-source-{number}", actor_id=(context or scope()).account_id,
            body=body, signals=("sadness",),
        )
        result = await self.api.ingest_event(event)
        assert result["status"] == "accepted" and result["domain_applied"] is True, result
        return event

    async def rows(self):
        return await self.store._run(lambda db: [
            dict(row) for row in db.execute(
                "SELECT purpose,pool,status,COUNT(*) n,SUM(units) units "
                "FROM quota_reservations GROUP BY purpose,pool,status"
            )
        ])

    async def bodies(self):
        return await self.store._run(lambda db: dict(db.execute(
            "SELECT COUNT(*) count,COALESCE(MAX(LENGTH(body)),0) max_chars,"
            "COALESCE(SUM(LENGTH(body)),0) total_chars FROM body_window"
        ).fetchone()))

    async def model(self, job, work, purpose="behavior", context=None, **budgets):
        context = context or scope()
        return await self.runtime.run_model(
            job, context, await self.store.get_generation(context), work, purpose=purpose,
            input_tokens=budgets.get("input_tokens", self.config.model_input_tokens),
            output_tokens=budgets.get("output_tokens", self.config.model_output_tokens),
        )


class Wire:
    def __init__(self):
        import httpx
        from astrbot.core.provider.sources.openai_source import ProviderOpenAIOfficial
        from openai import AsyncOpenAI

        self.requests = []
        self.mode = "ok"
        self.text = "ok"
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = 0
        provider_config = {
            "id": "synthetic-provider", "type": "openai_chat_completion",
            "model": "qwen-offline-fixture", "key": ["synthetic-key-a", "synthetic-key-b"],
            "api_base": "https://offline.invalid/v1",
            "custom_extra_body": {
                "messages": [{"role": "user", "content": "uncounted synthetic override"}],
                "model": "synthetic-override", "n": 9, "max_tokens": 99999,
                "max_completion_tokens": 99999, "tools": [{"type": "function"}],
                "enable_thinking": True, "temperature": 0.2,
            },
        }
        # Real constructor and text_chat/_query/SDK serialization; only transport is a stub.
        self.provider = ProviderOpenAIOfficial(provider_config, {})
        self.unused_client = self.provider.client
        self.provider.client = AsyncOpenAI(
            api_key="synthetic-key-a", base_url="https://offline.invalid/v1",
            max_retries=4, timeout=73,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(self.handle)),
        )
        self.provider.default_params = inspect.signature(
            self.provider.client.chat.completions.create).parameters.keys()
        self.original_config = copy.deepcopy(self.provider.provider_config)
        self.original_client = self.provider.client

    async def handle(self, request):
        import httpx

        self.requests.append(json.loads(request.content))
        self.entered.set()
        if self.mode == "blocked":
            try:
                await self.release.wait()
            except asyncio.CancelledError:
                self.cancelled += 1
                raise
        if self.mode == "timeout":
            raise httpx.ReadTimeout("synthetic timeout", request=request)
        if self.mode == "error":
            return httpx.Response(503, json={"error": {"message": "synthetic failure"}})
        text = self.text
        if self.mode == "entry":
            data = json.loads(self.requests[-1]["messages"][-1]["content"])
            text = json.dumps({"body": "Synthetic subjective entry.",
                               "source_ids": [data["materials"][0]["source_id"]]})
        return httpx.Response(200, json={
            "id": "synthetic-completion", "object": "chat.completion", "created": 1,
            "model": "qwen-offline-fixture",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })

    def unchanged(self):
        return (self.provider.provider_config == self.original_config
                and self.provider.client is self.original_client
                and self.provider.client.max_retries == 4
                and self.provider.client.timeout == 73
                and len(self.provider.api_keys) == 2)


class App(Generation, Refinement):
    """Host identity/persona authorization are synthetic, not under test."""

    def __init__(self, rig, wire):
        self.store, self.runtime, self.config = rig.store, rig.runtime, rig.config
        self._revision, self._services = "synthetic-revision", {}
        self._admin, self.closed, self.memory = object(), False, None
        self.instance_id = "synthetic-instance"
        self.lookups = []

        async def provider(pid):
            self.lookups.append(pid)
            return wire.provider

        async def current_id(route):
            return "synthetic-provider"

        async def current(context):
            return SimpleNamespace(persona=SimpleNamespace(prompt="Synthetic persona."))

        self.host = SimpleNamespace(
            provider_manager=SimpleNamespace(get_provider_by_id=provider),
            get_current_chat_provider_id=current_id,
        )
        self.bridge = SimpleNamespace(current=current)

    async def validate_context(self, context, generation=None):
        return (context.instance_id == self.instance_id
                and (generation is None
                     or generation == await self.store.get_generation(context)))

    def effective_mode(self, context=None):
        return "active"

    async def night_guard(self, context, night):
        return True

    async def behavior_request(self, number=0, *, persona="Synthetic persona.",
                               output_tokens=1024):
        context = scope()
        return SimpleNamespace(
            intent=BehaviorIntent(
                f"synthetic-intent-{number}", context, "behavior", NOW, NOW + 60,
                await self.store.get_generation(context),
                human_watermark=await self.store.human_watermark(context),
            ),
            snapshot=SimpleNamespace(persona_prompt=persona), materials=(),
            max_output_tokens=output_tokens,
        )
