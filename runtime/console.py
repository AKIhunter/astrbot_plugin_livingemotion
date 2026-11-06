"""Management DTOs. Authentication belongs to the product HTTP handlers."""

from __future__ import annotations

import inspect
from dataclasses import fields
from uuid import uuid4

from ..config import Config
from ..contracts import HumanObservation, SceneKind, to_dict
from ..services.experience import dream_view
from .projector import current_affect, snapshot


class ApplicationError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message
        self.status_code = {"validation_error": 400, "unauthorized": 401, "forbidden": 403,
                            "version_conflict": 409, "unavailable": 503}[code]
        super().__init__(message)


def dimensions(value):
    return {"pleasure": (value.pleasure + 1) / 2, "arousal": value.arousal,
            "stress": value.stress, "social_need": value.social_need}


class Console:
    def _context(self, context_id, *, optional=False):
        if not isinstance(context_id, str) or len(context_id) > 128:
            raise ApplicationError("validation_error", "Invalid context")
        if not context_id and optional:
            return next(reversed(self._contexts.values()), None)
        context = self._contexts.get(context_id)
        if context is None:
            raise ApplicationError("validation_error", "Unknown context")
        return context

    def _open(self):
        if self.closed:
            raise ApplicationError("unavailable", "Plugin stopped")

    @staticmethod
    def _actor(actor_id, reason):
        if (not isinstance(actor_id, str) or not actor_id.strip() or len(actor_id) > 512
                or not isinstance(reason, str) or not reason.strip() or len(reason) > 1000):
            raise ApplicationError("validation_error", "An authenticated actor and reason are required")

    def config_dto(self):
        enums = {"mode": ["active", "observe_only"], "memory_mode": ["none", "local_lite", "external"],
                 "persona_mode": ["follow", "explicit", "none"]}
        def section(name):
            for prefix, group in (("persona", "persona"), ("memory", "memory"),
                                  ("night", "night"), ("sleep", "night"), ("wake", "night"),
                                  ("diary", "experience"), ("dream", "experience"),
                                  ("autonomy", "behavior"), ("group", "behavior")):
                if name.startswith(prefix):
                    return group
            return "emotion"
        return {
            "revision": self.revision, "source": "AstrBot native plugin configuration",
            "values": to_dict(self.config),
            "fields": [
                {"key": f.name, "label": f.name, "section": section(f.name),
                 "type": ("enum" if f.name in enums else "boolean" if type(f.default) is bool
                          else "integer" if type(f.default) is int else "string"),
                 **({"options": [{"value": v, "label": v} for v in enums[f.name]]}
                    if f.name in enums else {})}
                for f in fields(Config)
            ],
        }

    async def console_state(self, context_id=""):
        self._open()
        await self.refresh_config()
        context = self._context(context_id, optional=True)
        memory = self.memory.capabilities()
        state = {
            "api_version": 1, "context_id": context.account_key if context else "",
            "contexts": [{"id": c.account_key,
                          "label": f"{c.platform} / {c.scene_kind.value} / {c.scene_id} / {c.account_id}"}
                         for c in reversed(self._contexts.values())],
            "updated_at": self.store.clock(), "mode": self.effective_mode(context),
            "revision": self.revision, "config": self.config_dto(),
            "capabilities": ["config.write", "behavior.preview"],
            "health": [
                {"name": "runtime", "status": "ok" if self.config.enabled else "unavailable",
                 "reason": "ready" if self.config.enabled else "disabled"},
                {"name": "configuration", "status": "degraded" if self._config_fault else "ok",
                 "reason": "invalid_native_config" if self._config_fault else "native"},
                {"name": "ownership", "status": "degraded" if self.bridge.conflicts(context) else "ok",
                 "reason": "congling_scope_conflict" if self.bridge.conflicts(context) else "exclusive"},
                {"name": "background", "status": "degraded" if self._task_fault else "ok",
                 "reason": self._task_fault or "idle"},
                {"name": "reply_confirmation", "status": "unavailable",
                 "reason": "unsupported：当前宿主无可靠回复确认；收尾 120 秒超时取消，"
                           "不将 after-sent/bool/None 视为发送成功。"},
            ],
            "memory": {"mode": self.config.memory_mode, "provider": self.config.memory_mode,
                       "can_read": memory.recall, "can_write": memory.append_experience,
                       "capabilities": [], "reason": ", ".join(memory.reason_codes)},
            "experience": {"diary_enabled": self.config.diary_enabled,
                           "dream_enabled": self.config.dream_enabled,
                           "reason": "Explicitly enabled generation only"},
            "actions": [],
        }
        if context is None:
            return state
        bot_record = await self.store.get_state(context, "bot")
        bot = current_affect(bot_record, now=self.store.clock())
        obs_record = await self.store.get_state(context, "observation", context.account_id)
        obs = snapshot(obs_record, HumanObservation) if obs_record else None
        generation = await self.store.get_generation(context)
        relation = await self.current_relationship(context)
        night = await self.night_snapshot(context)
        availability = await self.availability(context)
        source = self.bridge.source(context)
        preview = await self.behavior.preview_behavior(context)
        model_ready = False
        try:
            await self.model_binding(context)
            model_ready = True
        except (ValueError, ImportError):
            pass
        active = self.effective_mode(context) == "active" and context.scene_kind != SceneKind.PUBLIC_COMMENT
        if relation is not None and not await self.validate_context(context, generation):
            relation = None
        state.update({
            "persona": {"id": context.persona_id, "name": context.persona_id,
                        "source": "AstrBot native", "revision": context.persona_revision,
                        "description": source.persona.prompt if source else ""},
            "bot_state": {"dimensions": dimensions(bot), "label": ", ".join(bot.labels),
                          "reason": ", ".join(bot.reason_codes), "updated_at": bot.updated_at,
                          "version": bot_record.version if bot_record else 0, "source": "livingEmotion"},
            "observation": ({"subject": obs.subject_id, "label": ", ".join(obs.labels),
                             "confidence": obs.confidence, "observed_at": obs.occurred_at,
                             "expires_at": obs.expires_at, "source": "human observation"}
                            if obs and obs.expires_at > self.store.clock() else None),
            "relationship": ({"stage": relation.stage, "raw": relation.score,
                             "normalized": relation.normalized, "scale": "0-1000",
                             "source_completeness": "complete" if relation.evidence_complete else "partial",
                             "identity_revision": context.identity_revision,
                             "reason": ", ".join(relation.reason_codes)}
                             if relation is not None else None),
            "availability": {"available": availability.available, "state": night.phase.value,
                             "block_chat": availability.block_chat,
                             "reasons": list(availability.reason_codes)},
            "night": {"state": night.phase.value, "stage": night.sleep_stage,
                      "energy": night.energy / 100, "sleep_at": night.sleep_started_at,
                      "wake_at": night.wake_at, "reason": ""},
            "behavior": {"enabled": self.config.autonomy_enabled,
                         "reason": ", ".join(preview.reason_codes), "candidates": []},
            "actions": [
                {"id": name, "enabled": enabled,
                 "reason": "" if enabled else "Current mode, provider or policy does not permit this action"}
                for name, enabled in (
                    ("night.sleep", active and self.config.night_enabled),
                    ("night.wake", self.config.enabled and self.config.night_enabled),
                    ("diary.generate", active and self.config.diary_enabled and model_ready),
                    ("dream.generate", active and self.config.dream_enabled and model_ready
                     and night.phase.value == "asleep" and night.sleep_stage == "REM"),
                    ("behavior.send", active and model_ready and preview.eligible),
                )
            ],
        })
        return state

    async def console_records(self, context_id, kind, page=1, page_size=10, query=""):
        self._open()
        context = self._context(context_id)
        try:
            result = await self.store.query_records(
                context, kind, page=page, page_size=page_size, query=query,
            )
        except ValueError:
            raise ApplicationError("validation_error", "Invalid record query") from None
        items = []
        for row in result["items"]:
            value = row["value"]
            item = {"id": row["id"], "created_at": row["created_at"],
                    "status": row.get("status", "recorded"),
                    "reason": row.get("reason_code", ""), "source": "livingEmotion",
                    "context": context.account_key}
            if kind == "emotion":
                item.update({k: v for k, v in value.items()
                             if k in ("before", "after", "reason_codes", "label")})
                for name in ("before", "after"):
                    raw = item.get(name)
                    if isinstance(raw, dict) and "pleasure" in raw:
                        item[name] = {**raw, "pleasure": (raw["pleasure"] + 1) / 2}
            elif kind == "behavior":
                item.update(candidate=value.get("purpose", ""), intent_id=row["id"],
                            result=row["status"], vetoes=value.get("reason_codes", []))
            else:
                loaded = await self.store.load_experience(row["id"])
                if loaded is None:
                    continue
                entry, _ = loaded
                item.update(title=entry.period, body=entry.body, visibility="private",
                            clarity=entry.clarity, pinned=entry.pinned,
                            sources=[{"kind": ref.kind.value, "label": ref.kind.value,
                                      "source_id": ref.source_id} for ref in entry.evidence])
                if kind == "dream":
                    view = dream_view(entry, now=self.store.clock())
                    item.update(body=view.get("body", ""), clarity=view["clarity"])
            items.append(item)
        return {"api_version": 1, **result, "items": items}

    async def update_config(self, patch, *, expected_revision, reason, actor_id, context_id=""):
        self._open()
        self._actor(actor_id, reason)
        await self.refresh_config()
        if context_id:
            self._context(context_id)
        async with self._config_lock:
            if expected_revision != self.revision:
                raise ApplicationError("version_conflict", "Configuration changed; refresh first")
            if not isinstance(patch, dict) or not patch or set(patch) - set(to_dict(self.config)):
                raise ApplicationError("validation_error", "Unknown or empty configuration patch")
            try:
                updated = Config.from_mapping({**to_dict(self.config), **patch})
            except (ValueError, TypeError, KeyError):
                raise ApplicationError("validation_error", "Invalid configuration value") from None
            old = dict(self.native_config)
            self.native_config.update(patch)
            try:
                saved = self.native_config.save_config()
                if inspect.isawaitable(saved):
                    await saved
            except Exception:
                self.native_config.clear()
                self.native_config.update(old)
                raise ApplicationError("unavailable", "Native configuration could not be saved") from None
            await self._replace_config(updated)
            await self.store.append_audit(action="config.update", actor_id=actor_id,
                                          reason=reason, value={"fields": sorted(patch)})
        return await self.console_state(context_id)

    async def console_preview(self, context_id):
        self._open()
        context = self._context(context_id)
        result = await self.behavior.preview_behavior(context)
        return {"api_version": 1, "eligible": result.eligible,
                "reasons": list(result.reason_codes), "candidates": [],
                "model_calls": 0, "sends": 0}

    async def console_action(self, context_id, action, *, expected_revision, reason,
                             actor_id, confirmed):
        self._open()
        self._actor(actor_id, reason)
        if confirmed is not True:
            raise ApplicationError("validation_error", "Explicit confirmation is required")
        state = await self.console_state(context_id)
        if expected_revision != self.revision:
            raise ApplicationError("version_conflict", "Configuration changed; refresh first")
        if not any(a["id"] == action and a["enabled"] for a in state["actions"]):
            raise ApplicationError("forbidden", "Action is unavailable")
        context = self._context(context_id)
        request_id = uuid4().hex
        if action.startswith("night."):
            result = await self.advance_scope(context, action=action)
            if result is None:
                raise ApplicationError("version_conflict", "Night state changed")
            result = {"status": "accepted", "reason": "night_state_committed"}
        elif action == "behavior.send":
            self.spawn_action(self.behavior.execute(context, intent_id="manual:" + request_id))
            result = {"status": "queued", "reason": "behavior_queued"}
        else:
            service = await self.experience_service(context)
            source = await self.bridge.current(context)
            if source is None:
                raise ApplicationError("unavailable", "Source changed")
            result = (await service.queue_diary(context, persona_text=source.persona.prompt)
                      if action == "diary.generate" else await service.queue_dream(
                          context, await self.night_snapshot(context),
                          persona_text=source.persona.prompt))
        await self.store.append_audit(action=action, actor_id=actor_id, reason=reason,
                                      context=context, value={"request_id": request_id,
                                                              "status": result["status"]})
        return {"api_version": 1, "request_id": request_id, **result}

    async def correct_relationship(self, context_id, *, expected_version, reason, actor_id,
                                   score=None, frozen=None):
        self._open()
        self._actor(actor_id, reason)
        context = self._context(context_id)
        result = await self.store.correct_relationship(
            context, await self.store.get_generation(context), expected_version=expected_version,
            actor_id=actor_id, reason=reason, score=score, frozen=frozen,
        )
        return {"api_version": 1, **to_dict(result)}

    async def clear_context(self, context_id, *, expected_generation, reason, actor_id):
        self._open()
        self._actor(actor_id, reason)
        result = await self.store.clear_scope(
            self._context(context_id), expected_generation, actor_id=actor_id, reason_code=reason,
        )
        return {"api_version": 1, **to_dict(result)}

    async def pin_experience(self, context_id, entry_id, *, pinned, reason, actor_id):
        self._open()
        self._actor(actor_id, reason)
        context = self._context(context_id)
        from .models import _pin_actor
        token = _pin_actor.set((actor_id, reason))
        try:
            service = await self.experience_service(context, need_model=False)
            result = await service.set_pin(entry_id, context, self._admin, pinned=pinned)
            return {"api_version": 1, **result}
        finally:
            _pin_actor.reset(token)
