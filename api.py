"""R9 v1 in-process facade. No HTTP/admin trust is inferred from call arguments."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from .config import Config
from .domain.relationship import initial_relationship
from .contracts import (
    API_VERSION,
    SCHEMA_VERSION,
    BotAffect,
    Context,
    Event,
    NightState,
    Relationship,
    RelationshipContribution,
    SceneKind,
    StateWrite,
    stable_key,
    to_dict,
)
from .runtime.background import BackgroundRuntime
from .runtime.projector import Projector, projection_event
from .storage import SQLiteStore, StoreClosed

ProjectEvent = Callable[
    [Event], Awaitable[tuple[Sequence[StateWrite], Sequence[RelationshipContribution]]]
]


class LivingEmotionAPI:
    api_version = API_VERSION

    def __init__(self, store: SQLiteStore, config: Config, runtime: BackgroundRuntime,
                 *, project_event: ProjectEvent | None = None, instance_id: str | None = None,
                 application=None):
        self._store = store
        self._config = config
        self._runtime = runtime
        self._project_event = project_event
        self._instance_id = instance_id
        self._active = True
        self._application = application

    def stop_accepting(self) -> None:
        self._active = False

    async def _sync(self):
        if self._application is not None and self._active:
            await self._application.refresh_config()

    @staticmethod
    def _context(context: Context | Mapping[str, Any]) -> Context:
        return context if isinstance(context, Context) else Context.from_dict(context)

    @staticmethod
    def _result(status: str, reason: str, **data: Any) -> dict[str, Any]:
        return {"api_version": API_VERSION, "status": status, "reason_code": reason, **data}

    async def get_capabilities(self, context=None) -> dict[str, Any]:
        await self._sync()
        mode = (self._application.effective_mode(self._context(context) if context is not None else None) if self._application
                else self._config.mode if self._config.enabled and self._active else "disabled")
        return self._result(
            "ok", "capabilities", schema_version=SCHEMA_VERSION,
            operations=["get_capabilities", "resolve_producer_context", "ingest_event", "get_bot_state",
                        "get_current_emotion",
                        "get_observation", "get_relationship", "get_availability",
                        "preview_behavior", "get_health"],
            mode=mode, memory_mode=self._config.memory_mode,
            instance_id=self._instance_id,
            persistent_idempotency=True, domain_ready=self._project_event is not None,
            autonomous_executor=self._application is not None, model_generation=self._application is not None,
            scene_kinds=[kind.value for kind in SceneKind],
            reason_codes=[] if self._project_event else ["domain_not_connected"],
        )

    async def resolve_producer_context(self, source: Mapping[str, Any]) -> dict[str, Any]:
        """Trusted plugin producers supply source facts, never routes or host IDs."""
        await self._sync()
        if not self._active or not self._config.enabled:
            return self._result("unavailable", "plugin_disabled")
        if self._instance_id is None:
            return self._result("unavailable", "instance_unavailable")
        required = {"producer", "bot_account", "adapter_id", "platform", "scene_kind",
                    "scene_id", "account_id", "persona_id", "persona_revision"}
        try:
            if set(source) != required:
                raise ValueError("producer fields")
            if any(not isinstance(source[name], str) or not source[name].strip()
                   or len(source[name]) > 512 for name in required):
                raise ValueError("source missing")
            kind = SceneKind(source["scene_kind"])
            if kind not in (SceneKind.PRIVATE, SceneKind.PUBLIC_COMMENT):
                raise ValueError("producer scene unsupported")
            if kind == SceneKind.PRIVATE and source["scene_id"] != source["account_id"]:
                raise ValueError("private scene mismatch")
            audience = (("public:" + stable_key(source["platform"], source["scene_id"]),)
                        if kind == SceneKind.PUBLIC_COMMENT else (
                            source["platform"] + ":" + source["bot_account"],
                            source["platform"] + ":" + source["account_id"],
                        ))
            context = Context(
                instance_id=self._instance_id,
                bot_id="producer:" + stable_key(self._instance_id, source["producer"],
                                                source["platform"], source["bot_account"]),
                persona_id=source["persona_id"], persona_revision=source["persona_revision"],
                adapter_id=source["adapter_id"], platform=source["platform"],
                scene_kind=kind, scene_id=source["scene_id"], account_id=source["account_id"],
                identity_revision="source:" + stable_key(source["platform"], source["account_id"]),
                audience=audience, route=None,
            )
            return self._result("ok", "producer_context", data=to_dict(context))
        except (ValueError, TypeError, KeyError):
            return self._result("rejected", "invalid_producer_context")

    async def ingest_event(self, event: Event | Mapping[str, Any]) -> dict[str, Any]:
        await self._sync()
        if not self._active or not self._config.enabled:
            return self._result("rejected", "plugin_disabled")
        try:
            parsed = event if isinstance(event, Event) else Event.from_dict(event)
            if self._instance_id is not None and parsed.context.instance_id != self._instance_id:
                return self._result("rejected", "instance_mismatch")
            lock = self._store.projection_lock(parsed.context)
            # Waiting events keep their pre-clear generation. An uncontended built-in
            # projector acquires the lock without yielding, then reads one snapshot.
            generation = (await self._store.get_generation(parsed.context)
                          if lock.busy or not isinstance(self._project_event, Projector)
                          else None)
            async with lock:
                return await self._commit_projected(parsed, generation)
        except (TypeError, ValueError, KeyError):
            return self._result("rejected", "invalid_event")
        except StoreClosed:
            return self._result("rejected", "store_closed")
        except Exception:
            return self._result("rejected", "processing_failed")

    async def _commit_projected(self, parsed: Event, generation: int | None) -> dict[str, Any]:
        # Only the built-in path shares this request's immutable key view. Host
        # callbacks and custom projectors continue receiving the caller's event.
        request_event = (projection_event(parsed) if type(self._project_event) is Projector
                         else parsed)
        for _ in range(3):
            writes, contributions = (), ()
            traces = ()
            if self._project_event is not None:
                projection = await self._project_event(request_event)
                snapshot_generation = getattr(projection, "generation", None)
                if generation is None:
                    if type(snapshot_generation) is not int or snapshot_generation < 0:
                        raise ValueError("projection generation missing")
                    generation = snapshot_generation
                if snapshot_generation is not None and snapshot_generation != generation:
                    return self._result("rejected", "stale_generation")
                if hasattr(projection, "writes"):
                    writes, contributions, traces = (
                        projection.writes, projection.contributions, projection.traces,
                    )
                else:
                    writes, contributions = projection
            if not self._active:
                return self._result("rejected", "plugin_stopped")
            if self._application is not None:
                if not self._application.config.enabled:
                    return self._result("rejected", "plugin_disabled")
                if parsed.context.route and not await self._application.validate_context(
                    parsed.context, generation,
                ):
                    return self._result("rejected", "context_changed")
            result = await self._store.commit_event(
                request_event, generation, writes, contributions, traces=traces,
            )
            if result.reason_code != "version_conflict":
                if self._application and result.accepted:
                    await self._application.remember_context(parsed.context)
                    if self._project_event is not None:
                        self._application.queue_refinement(parsed, result, projection)
                return {"api_version": API_VERSION, **to_dict(result),
                        "domain_applied": self._project_event is not None and result.accepted}
        return self._result("rejected", "version_conflict")

    async def _snapshot(self, context: Context | Mapping[str, Any], kind: str,
                        default: Any) -> dict[str, Any]:
        await self._sync()
        if not self._active or not self._config.enabled:
            return self._result("unavailable", "plugin_disabled")
        try:
            scope = self._context(context)
            if self._instance_id is not None and scope.instance_id != self._instance_id:
                return self._result("rejected", "instance_mismatch")
            if kind in ("observation", "relationship") and not scope.account_id:
                return self._result("rejected", "missing_account")
            record = await self._store.get_state(
                scope, kind, scope.account_id if kind in ("observation", "relationship") else "",
            )
            value = to_dict(default) if record is None else {
                key: val for key, val in record.value.items() if not key.startswith("_")
            }
            # Old/custom partial projections have no domain timestamp; do not
            # invent elapsed time or expand their legacy payload shape.
            if kind == "bot" and (record is None or {
                "pleasure", "arousal", "stress", "social_need", "updated_at",
            }.issubset(value)):
                from .runtime.projector import current_affect
                value = to_dict(current_affect(record, now=self._store.clock()))
            if kind == "relationship" and self._application is not None:
                relationship = await self._application.current_relationship(scope, record=record)
                if relationship is None:
                    return self._result("unavailable", "context_changed")
                value = to_dict(relationship)
            if kind == "relationship" and value is not None:
                value["normalized"] = value.get("score", 0) / 1000.0
            if kind == "observation" and value is not None:
                if value.get("expires_at", 0) <= self._store.clock():
                    value = None
            return self._result(
                "ok", "snapshot" if record is not None else "baseline",
                type=kind, data=value, context=to_dict(scope),
                generation=record.generation if record else await self._store.get_generation(scope),
                version=record.version if record else 0,
                reason_codes=[] if self._project_event else ["domain_not_connected"],
            )
        except (TypeError, ValueError, KeyError):
            return self._result("rejected", "invalid_context")
        except StoreClosed:
            return self._result("unavailable", "store_closed")
        except Exception:
            return self._result("unavailable", "storage_failed")

    async def get_bot_state(self, context: Context | Mapping[str, Any]) -> dict[str, Any]:
        return await self._snapshot(context, "bot", BotAffect())

    async def get_current_emotion(self, context=None, *, event=None) -> dict[str, Any]:
        """Numeric read facade for other plugins; no text, evidence or identity fields."""
        await self._sync()
        if not self._active or not self._config.enabled:
            return self._result("unavailable", "plugin_disabled")
        try:
            app = self._application
            if event is not None:
                if app is None:
                    return self._result("unavailable", "native_bridge_unavailable")
                source, _ = await app.bridge.normalize(event, self._store.clock())
                scope = source.context
            else:
                scope = self._context(context)
            if self._instance_id is not None and scope.instance_id != self._instance_id:
                return self._result("rejected", "instance_mismatch")
            # Shared private state is never exposed to a public-comment producer.
            if scope.scene_kind == SceneKind.PUBLIC_COMMENT:
                return self._result("unavailable", "public_comment_no_emotion")
            generation = await self._store.get_generation(scope)
            if app is not None and not await app.validate_context(scope, generation):
                return self._result("unavailable", "context_changed")
            from .runtime.projector import current_affect
            from .runtime.state_scope import source_affect
            from .domain.dreaming import six_emotions
            record = await self._store.get_state(scope, "bot")
            state = current_affect(record, now=self._store.clock())
            state = source_affect(state, scope)
            emotions = await app.weather_emotions(state) if app else six_emotions(state)
            if app is not None and not await app.validate_context(scope, generation):
                return self._result("unavailable", "context_changed")
            latest = await self._store.get_state(scope, "bot")
            if (latest.version if latest else 0) != (record.version if record else 0):
                return self._result("unavailable", "state_changed")
            dominant = max(emotions, key=emotions.get)
            dominant = dominant if emotions[dominant] >= .25 else "calm"
            mode = app.effective_mode(scope) if app else self._config.mode
            return self._result("ok", "current_emotion", data={
                "emotions": emotions, "dominant": dominant, "labels": list(state.labels),
                "affect": {k: getattr(state, k) for k in (
                    "pleasure", "arousal", "stress", "social_need")},
                "updated_at": state.updated_at, "sampled_at": self._store.clock(),
                "version": record.version if record else 0, "generation": generation,
                "mode": mode, "may_influence_reply": mode == "active",
            })
        except (TypeError, ValueError, KeyError, AttributeError):
            return self._result("rejected", "invalid_context")
        except StoreClosed:
            return self._result("unavailable", "store_closed")
        except Exception:
            return self._result("unavailable", "emotion_read_failed")

    async def get_observation(self, context: Context | Mapping[str, Any]) -> dict[str, Any]:
        return await self._snapshot(context, "observation", None)

    async def get_relationship(self, context: Context | Mapping[str, Any]) -> dict[str, Any]:
        return await self._snapshot(
            context, "relationship", initial_relationship(),
        )

    async def get_availability(self, context: Context | Mapping[str, Any]) -> dict[str, Any]:
        await self._sync()
        if not self._active or not self._config.enabled:
            return self._result("unavailable", "plugin_disabled")
        try:
            scope = self._context(context)
            if self._instance_id and scope.instance_id != self._instance_id:
                return self._result("rejected", "instance_mismatch")
            if scope.scene_kind == SceneKind.PUBLIC_COMMENT:
                return self._result("ok", "public_comment_no_route", available=False,
                                    block_chat=False, reason_codes=["public_comment_no_route"])
            if self._application:
                availability = await self._application.availability(scope)
                return self._result("ok", "night_state", **to_dict(availability))
        except (ValueError, TypeError, KeyError):
            return self._result("rejected", "invalid_context")
        snapshot = await self._snapshot(context, "night", NightState())
        if snapshot["status"] != "ok":
            return snapshot
        phase = snapshot["data"].get("phase", "awake")
        sleeping = self._config.night_enabled and phase in ("settling", "asleep", "waking")
        return self._result(
            "ok", "night_state", available=not sleeping,
            block_chat=sleeping and self._config.night_block_chat,
            reason_codes=["sleeping"] if sleeping else [], version=snapshot["version"],
            generation=snapshot["generation"],
        )

    async def preview_behavior(self, context: Context | Mapping[str, Any]) -> dict[str, Any]:
        await self._sync()
        if self._application:
            try:
                preview = await self._application.behavior.preview_behavior(self._context(context))
                return self._result("ok", "behavior_preview", **to_dict(preview))
            except (ValueError, TypeError):
                return self._result("rejected", "invalid_context")
        availability = await self.get_availability(context)
        if availability["status"] != "ok":
            return availability
        return self._result(
            "ok", "executor_not_connected", eligible=False, model_calls=0, sends=0,
            reason_codes=["executor_not_connected"]
            + ([] if self._config.autonomy_enabled else ["autonomy_disabled"])
            + (["observe_only"] if self._config.mode == "observe_only" else [])
            + availability["reason_codes"],
        )

    async def get_health(self) -> dict[str, Any]:
        await self._sync()
        if not self._active:
            return self._result("stopped", "plugin_stopped")
        try:
            storage = await self._store.health()
            return self._result("ok", "ready", storage=storage,
                                runtime=self._runtime.health(),
                                reason_codes=[] if self._project_event else ["domain_not_connected"])
        except Exception:
            return self._result("unavailable", "storage_failed")
