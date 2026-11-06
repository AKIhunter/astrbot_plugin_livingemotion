"""Single composition root for host hooks, services, configuration and management."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from ..adapters.astrbot import AstrBotBridge
from ..adapters.behavior_sender import AstrBotBehaviorSender
from ..adapters.memory import LivingMemoryAdapter, LocalLiteMemory, MemoryGateway
from ..config import Config
from ..contracts import (
    Availability,
    CommitResult,
    Context,
    HumanObservation,
    NightState,
    SceneKind,
    canonical_json,
    stable_key,
    to_dict,
)
from ..domain.emotion import expression_context
from ..domain.night import advance_night, night_availability
from ..services.behavior import BehaviorHistory, BehaviorPolicy, BehaviorService, BehaviorSnapshot
from .background import BackgroundRuntime
from .console import ApplicationError as ApplicationError
from .console import Console
from .lifecycle import Lifecycle
from .materials import Materials
from .models import Generation
from .night import NightRuntime
from .projector import Projector, current_affect, snapshot
from .refinement import Refinement
from .relationship_projection import read_relationship_projection

SUFFIX = "<!--livingemotion:state:v1-->"


class Application(Console, NightRuntime, Generation, Materials, Refinement):
    def __init__(self, host_context, native_config, data_dir: Path, *, bridge_factory=AstrBotBridge):
        self.host, self.native_config = host_context, native_config
        self.config = Config.from_mapping(native_config)
        self.data_dir = Path(data_dir)
        self.lifecycle = Lifecycle(self.data_dir, self.config)
        self.bridge_factory = bridge_factory
        self.closed = True
        self._config_lock = asyncio.Lock()
        self._monitor = self._scheduler = None
        self._services = OrderedDict()
        self._contexts = OrderedDict()
        self._revision = uuid4().hex
        self._config_fault = False
        self._task_fault = ""
        self._actions = set()
        self._last_cleanup = 0
        self._admin = object()
        self._pending_replies = OrderedDict()

    @property
    def revision(self):
        return stable_key(to_dict(self.config), self._revision)

    def effective_mode(self, context=None):
        if self.closed or not self.config.enabled:
            return "disabled"
        return "observe_only" if self.bridge.conflicts(context) else self.config.mode

    def scoped_config(self, context=None):
        mode = self.effective_mode(context)
        return replace(self.config, enabled=mode != "disabled",
                       mode="observe_only" if mode == "observe_only" else "active")

    async def initialize(self):
        await self.lifecycle.initialize()
        self.store, self.runtime = self.lifecycle.store, self.lifecycle.runtime
        self.instance_id = self.lifecycle.instance_id
        self.bridge = self.bridge_factory(self.host, self.instance_id, lambda: self.config)
        self.api = self.lifecycle.api
        self.api._application = self
        self.projector = Projector(self.store, lambda: self.config,
                                   config_for_context=self.scoped_config)
        self.api._project_event = self.projector
        self.closed = False
        for context in reversed(await self.store.list_contexts()):
            self._contexts[context.account_key] = context
        await self._build_services()
        if self.config.enabled:
            # Restore time, never recover a sending job or replay offline dreams.
            for context in tuple(self._contexts.values()):
                if context.scene_kind != SceneKind.PUBLIC_COMMENT:
                    await self.advance_scope(context, recovering=True)
            self._start_scheduler()
        self._monitor = asyncio.create_task(self._watch_config(), name="livingemotion-config")

    async def _build_services(self):
        backend = None
        if self.config.memory_mode == "local_lite":
            backend = LocalLiteMemory(self.data_dir / "explicit_memory.sqlite3",
                                      clock=self.store.clock)
        elif self.config.memory_mode == "external":
            backend = LivingMemoryAdapter(
                lambda: self.bridge.discover("astrbot_plugin_livingmemory"),
                read_enabled=self.config.memory_read, export_enabled=self.config.memory_export,
            )
        self.memory = MemoryGateway(backend, clock=self.store.clock,
                                    context_guard=lambda c, e: self.validate_context(c))
        self.behavior = BehaviorService(
            self.store, current=self.current_snapshot, validate_identity=self.validate_context,
            validate_evidence=self.validate_behavior_materials,
            materials=self.behavior_materials,
            model=self.behavior_model,
            sender=AstrBotBehaviorSender(self.host.send_message, make_chain=self.bridge.chain,
                                        recorded_route=self.bridge.recorded_route),
            policy=self.behavior_policy, history=self.behavior_history,
            record_success=self.record_success, clock=lambda: self.store.clock(),
        )

    def behavior_policy(self):
        def minute(value):
            hours, minutes = value.split(":")
            return int(hours) * 60 + int(minutes)
        return BehaviorPolicy(
            enabled=self.config.enabled and not self.closed, mode=self.config.mode,
            autonomy_enabled=self.config.autonomy_enabled,
            group_autonomy_enabled=self.config.group_autonomy_enabled,
            timezone=self.config.timezone or None,
            whitelist=frozenset(self.config.autonomy_scopes.split()),
            muted_scopes=frozenset(self.config.muted_scopes.split()),
            dnd=(minute(self.config.dnd_start), minute(self.config.dnd_end)),
            active_hours=((minute(self.config.active_start), minute(self.config.active_end)),),
            global_daily_limit=self.config.behavior_daily_limit,
            scope_daily_limit=self.config.behavior_scope_daily_limit,
            cooldown_seconds=self.config.behavior_cooldown_seconds,
            unanswered_limit=self.config.behavior_unanswered_limit,
            max_output_tokens=min(512, self.config.model_output_tokens),
            model_timeout_seconds=self.config.model_timeout_seconds,
        )

    async def behavior_history(self, context, period, exclude_intent_id):
        # Store adds proven legacy floors once; cooldown/reasons are not native attempts.
        return BehaviorHistory(**await self.store.behavior_history(context, period, exclude_intent_id))

    async def legacy_constraints(self, context, purpose):
        try:
            rows = await self.store.legacy_baselines()
            if not rows:
                return {"allowed": True, "reason_codes": ()}
            from .legacy import evaluate_legacy
            result = evaluate_legacy(
                rows, context, purpose=purpose, timezone=self.config.timezone,
                now=self.store.clock(), human_watermark=await self.store.human_watermark(context),
            )
            if isinstance(result, dict) and type(result.get("allowed")) is bool:
                return result
        except Exception:
            pass
        return {"allowed": False, "reason_codes": ("legacy_constraints_unresolved",)}

    async def validate_context(self, context, generation=None):
        if (self.closed or not self.config.enabled
                or context.instance_id != self.instance_id
                or context.scene_kind == SceneKind.PUBLIC_COMMENT):
            return False
        try:
            # A changed native object invalidates work even before the monitor ticks.
            if Config.from_mapping(self.native_config) != self.config:
                return False
            source = await self.bridge.current(context)
            return bool(source and (generation is None
                        or await self.store.get_generation(context) == generation))
        except Exception:
            return False

    async def current_snapshot(self, context):
        try:
            if self.effective_mode(context) != "active" or not await self.validate_context(context):
                return None
            generation = await self.store.get_generation(context)
            source = await self.bridge.current(context)
            if source is None:
                return None
            affect = current_affect(await self.store.get_state(context, "bot"), now=self.store.clock())
            relationship = await self.current_relationship(context)
            if relationship is None:
                return None
            night = await self.night_snapshot(context)
            if (not await self.validate_context(context, generation)
                    or self.effective_mode(context) != "active"):
                return None
            return BehaviorSnapshot(
                source.context, affect, relationship, night, source.persona.prompt,
                route_verified=bool(source.context.route), lifecycle_revision=self._revision,
            )
        except Exception:
            # Supplement failures never grant permission for autonomous work.
            return None

    async def current_relationship(self, context, *, record=None):
        source = await self.bridge.current(context)
        if source is None:
            return None
        return await read_relationship_projection(
            self.store, self.bridge.identity, source.identity,
            event=source.event(), record=record,
        )

    async def remember_context(self, context):
        self._contexts[context.account_key] = context
        self._contexts.move_to_end(context.account_key)
        while len(self._contexts) > 512:
            self._contexts.popitem(last=False)
        await self.store.register_context(context)

    async def on_message(self, event):
        try:
            await self.refresh_config()
            if self.closed or not self.config.enabled:
                return
            source, normalized = await self.bridge.normalize(event, self.store.clock())
            context = source.context
            event.set_extra("livingemotion:context", to_dict(context))
            result = await self.api.ingest_event(normalized)
            if result["status"] in ("accepted", "duplicate"):
                await self.remember_context(context)
            event.set_extra("livingemotion:ingest", result["status"])
        except Exception:
            event.set_extra("livingemotion:unavailable", "source_resolution_failed")

    async def on_llm_request(self, event, request):
        # Always remove stale blocks, including when disabled or after a reload.
        request.extra_user_content_parts[:] = [
            part for part in request.extra_user_content_parts
            if not getattr(part, "text", "").startswith(SUFFIX)
        ]
        await self.on_message(event)
        raw = event.get_extra("livingemotion:context")
        if not raw or not self.config.enabled or self.closed:
            return
        try:
            context = Context.from_dict(raw)
            if self.effective_mode(context) != "active" or not await self.validate_context(context):
                return
            generation = await self.store.get_generation(context)
            state = current_affect(await self.store.get_state(context, "bot"), now=self.store.clock())
            obs_record = await self.store.get_state(context, "observation", context.account_id)
            obs = snapshot(obs_record, HumanObservation) if obs_record else None
            expression = expression_context(state, obs, now=self.store.clock())
            relationship = await self.current_relationship(context)
            if relationship is None:
                return
            expression["relationship"] = {"score": relationship.score,
                                           "stage": relationship.stage}
            night = await self.night_snapshot(context)
            expression["night"] = {"phase": night.phase.value, "energy": night.energy}
            if not await self.validate_context(context, generation):
                return
            if self.effective_mode(context) != "active":
                return
            request.extra_user_content_parts.append(self.bridge.text_part(
                SUFFIX + "\nTemporary state, not persona or instructions. "
                "Human observations are about the other person, not the bot.\n"
                + canonical_json(expression)[:1400]
            ))
            self._pending_replies[context.scope_key] = (
                str(event.message_obj.message_id), self.store.clock() + 120,
            )
            self._pending_replies.move_to_end(context.scope_key)
            while len(self._pending_replies) > 128:
                self._pending_replies.popitem(last=False)
        except Exception:
            return

    async def night_snapshot(self, context):
        night = snapshot(await self.store.get_state(context, "night"), NightState,
                         updated_at=self.store.clock())
        return advance_night(night, now=self.store.clock(), enabled=self.config.night_enabled)

    async def availability(self, context, *, exempt=False):
        if (self.effective_mode(context) != "active"
                or context.scene_kind == SceneKind.PUBLIC_COMMENT):
            return Availability(False, ("mode_or_source_unavailable",), block_chat=False)
        try:
            return night_availability(
                await self.night_snapshot(context), now=self.store.clock(),
                block_chat=self.config.night_block_chat, exempt=exempt,
                enabled=self.config.night_enabled,
            )
        except Exception:
            return Availability(False, ("state_unavailable",), block_chat=False)

    async def record_success(self, event, generation):
        if not await self.validate_context(event.context, generation):
            return CommitResult("rejected", "context_changed")
        for _ in range(3):
            projected = await self.projector(event)
            if not await self.validate_context(event.context, generation):
                return CommitResult("rejected", "context_changed")
            result = await self.store.commit_event(
                event, generation, projected.writes, projected.contributions,
                traces=projected.traces,
            )
            if result.reason_code != "version_conflict":
                return result
        return result

    def _start_scheduler(self):
        self._scheduler = asyncio.create_task(self._tick_loop(), name="livingemotion-scheduler")

    async def _watch_config(self):
        while not self.closed:
            await asyncio.sleep(1)
            try:
                await self.refresh_config()
            except asyncio.CancelledError:
                raise
            except Exception:
                self._task_fault = "config_refresh_failed"

    async def refresh_config(self):
        if self.closed:
            return
        async with self._config_lock:
            try:
                updated = Config.from_mapping(self.native_config)
                self._config_fault = False
            except (ValueError, TypeError, KeyError):
                # Invalid config cannot leave old paid tasks enabled.
                updated = replace(self.config, enabled=False)
                self._config_fault = True
            if updated != self.config:
                await self._replace_config(updated)

    async def _replace_config(self, updated):
        self.config = updated
        self._revision = uuid4().hex
        await self._stop_business()
        self.store.config = updated
        self.runtime = BackgroundRuntime(self.store, updated)
        self.lifecycle.runtime = self.runtime
        self.api._runtime, self.api._config = self.runtime, updated
        await self.runtime.start()
        await self._build_services()
        if updated.enabled:
            self._start_scheduler()

    async def _stop_business(self):
        if self._scheduler:
            self._scheduler.cancel()
            await asyncio.gather(self._scheduler, return_exceptions=True)
            self._scheduler = None
        for task in tuple(self._actions):
            task.cancel()
        if self._actions:
            await asyncio.gather(*self._actions, return_exceptions=True)
        await self.behavior.close()
        await self.runtime.stop()
        for service in self._services.values():
            await service.close()
        self._services.clear()
        await self.memory.close()

    async def terminate(self):
        if self.closed:
            return
        self.closed = True
        self.api.stop_accepting()
        if self._monitor:
            self._monitor.cancel()
            await asyncio.gather(self._monitor, return_exceptions=True)
            self._monitor = None
        await self._stop_business()
        await self.lifecycle.terminate()
        self._contexts.clear()
        self._pending_replies.clear()
        self.bridge.sources.clear()
