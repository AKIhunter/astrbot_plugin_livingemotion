"""Administrator private persona archives; no fabricated messaging event or route."""
import json
from ..adapters.weather import OpenMeteoWeather
from ..adapters.memory.base import material_allowed
from ..config import Config
from ..contracts import Context, SceneKind, stable_key
from ..services.experience import ExperienceService
from ..services.manual_experience import ManualExperienceService, ManualSnapshot, accepted_day
from ..storage.experiences import owner_key
from ..domain.dreaming import six_emotions
from ..contracts import BotAffect
from ..domain.emotion import decay_affect
from .projector import snapshot


class ManualExperienceRuntime:
    async def manual_persona(self):
        if self.closed or Config.from_mapping(self.native_config) != self.config:
            raise ValueError("executor_stopped")
        manager = getattr(self.host, "persona_manager", None)
        identifier = (self.config.persona_id if self.config.persona_mode == "explicit" else
                      getattr(manager, "default_persona", "") if self.config.persona_mode == "follow" else "")
        if not identifier or identifier == "[%None]":
            raise ValueError("persona_unavailable")
        persona = await manager.get_persona(identifier)
        if persona is None:
            raise ValueError("persona_unavailable")
        prompt = persona.system_prompt
        if not isinstance(prompt, str) or len(prompt) > 16000:
            raise ValueError("persona_unavailable")
        fingerprint = stable_key(identifier, prompt, persona.begin_dialogs)
        return identifier, prompt, fingerprint

    def private_archive_context(self, persona_id, fingerprint):
        # This context is never registered in source_contexts or _contexts. It cannot
        # become a QQ sending route or grant access to an external memory provider.
        return Context(
            "admin-private", persona_id, "livingemotion.console", "console", SceneKind.PRIVATE,
            "persona-archive", persona_revision=fingerprint, identity_revision="admin-private",
            audience=("admin-private",), route=None, instance_id=self.instance_id)

    async def capture_manual_experience(self, request_id, persona_id, kind):
        if kind not in ("diary", "dream"):
            raise ValueError("experience_kind_invalid")
        identifier, prompt, persona_revision = await self.manual_persona()
        if persona_id != identifier:
            raise ValueError("persona_changed")
        # 使用 LivingEmotion 自己的风格摘要，不把原生人格整段塞进请求。
        prompt = await self.persona_style(identifier, prompt)
        binding = await self.manual_model_binding(kind)
        context = self.private_archive_context(identifier, persona_revision)
        now = self.store.clock()
        day, timezone = accepted_day(now, self.config.timezone)
        materials, sources = [], {context.scope_key: (context, await self.store.get_generation(context))}
        # Only persisted, legal local sources of the configured persona. External
        # memory requires its original authorization and is deliberately skipped
        # when no live source exists; private storage remains usable.
        reader = ExperienceService(self.store, self.runtime)
        for source in await self.store.list_contexts():
            if (source.instance_id != self.instance_id or source.persona_id != identifier
                    or source.scene_kind == SceneKind.PUBLIC_COMMENT):
                continue
            generation = await self.store.get_generation(source)
            own = await reader.local_materials(source)
            selected = [m for m in own if accepted_day(m.evidence.occurred_at, timezone)[0] == day
                        and m.evidence.context.persona_id == identifier
                        and material_allowed(m, source, now)]
            if selected:
                sources[source.scope_key] = (source, generation)
                materials.extend(selected)
            if len(materials) >= 12:
                break
        await reader.close()
        materials = tuple(materials[-12:])
        selected_scopes = {m.evidence.context.scope_key for m in materials} | {context.scope_key}
        generations = tuple(v for k, v in sources.items() if k in selected_scopes)
        fingerprint = stable_key(persona_revision, self.revision, binding.fingerprint)
        from ..storage.console_data import selected_contexts
        contexts = await selected_contexts(self.store, self.instance_id,
            {"persona_id": identifier, "view_scope": "global", "context_id": "", "platform": ""})
        mood = six_emotions(BotAffect())
        if contexts:
            representative = contexts[0]
            if representative.scope_key not in {c.scope_key for c, _ in generations}:
                generations = (*generations, (representative, await self.store.get_generation(representative)))
            record = await self.store.get_state(representative, "bot")
            mood = six_emotions(decay_affect(snapshot(record, BotAffect), now=now))
            points = await self.store.emotion_history(representative, since=now - 86400, until=now)
            own = [p["emotions"] for p in points if p["emotions"] is not None
                   and accepted_day(p["at"], timezone)[0] == day]
            if own:
                mood = {k: sum(p[k] for p in own) / len(own) for k in mood}
        return ManualSnapshot(request_id, context, kind, day, timezone, now, prompt,
                              fingerprint, binding, generations, materials,
                              min(8000, self.config.experience_body_chars), self.config.home_city,
                              getattr(self.config, kind + "_retention_days"), mood,
                              json.loads(self.config.dream_theme_pool))

    async def weather_emotions(self, affect):
        """Daily six-axis overlay; underlying interaction state is never compounded."""
        from ..domain.dreaming import apply_bonus, weather_bonus
        day, zone = accepted_day(self.store.clock(), self.config.timezone)
        weather = getattr(self, "_manual_weather", None)
        report = await weather.get(self.config.home_city, day, zone) if (
            weather is not None and self.config.home_city) else None
        return apply_bonus(six_emotions(affect), weather_bonus(
            report, city=self.config.home_city, day=day, timezone=zone))

    async def manual_snapshot_current(self, snapshot):
        try:
            identifier, _, revision = await self.manual_persona()
            binding = await self.manual_model_binding(snapshot.kind)
            if identifier != snapshot.context.persona_id or stable_key(
                    revision, self.revision, binding.fingerprint) != snapshot.fingerprint:
                return False
            return all([await self.store.get_generation(c) == g for c, g in snapshot.generations])
        except Exception:
            return False

    async def commit_manual_snapshot(self, snapshot, entry):
        async with self._config_lock:
            if not await self.manual_snapshot_current(snapshot):
                raise ValueError("persona_or_model_changed")
            await self.store.commit_manual_experience(snapshot.request_id, entry)

    async def initialize_manual_experience(self):
        await self.store.recover_experience_jobs()
        self._manual_weather = OpenMeteoWeather(clock=self.store.clock)
        self.manual_experience = ManualExperienceService(
            self.store, capture=self.capture_manual_experience, current=self.manual_snapshot_current,
            commit=self.commit_manual_snapshot, weather=self._manual_weather)

    async def console_experience_generate(self, request_id, persona_id, kind, *, actor_id):
        from .console import ApplicationError
        self._open()
        self._actor(actor_id, "控制台手动生成/重写")
        await self.refresh_config()
        # 手动梦境是强制生成：睡眠时长、REM、夜间窗口、每晚次数上限一律不拦，
        # 唯一前提是「梦境生成」这个开关开着（手动链路本来也不走自动门禁）。
        if kind == "dream" and not self.config.dream_enabled:
            raise ApplicationError("validation_error", "梦境生成已在设置里关闭，请先开启梦境生成。")
        try:
            identifier, _, _ = await self.manual_persona()
            if identifier != persona_id:
                raise ValueError("persona_changed")
            previous = await self.store.experience_job(request_id, owner_key(self.instance_id, identifier))
            if previous:
                if previous["kind"] != kind:
                    raise ValueError("request_identity_conflict")
                return previous
            active = await self.store.latest_experience_job(owner_key(self.instance_id, identifier), kind)
            if active and active["status"] in ("queued", "running") and active["day"] == accepted_day(
                    self.store.clock(), self.config.timezone)[0]:
                return active
            return await self.manual_experience.submit(request_id, persona_id, kind)
        except ValueError as exc:
            if str(exc) in ("persona_changed", "request_identity_conflict"):
                raise ApplicationError("version_conflict", "人格或请求身份已变化，请刷新") from None
            raise ApplicationError("unavailable", "手动生成不可用：" + (
                str(exc) if str(exc) in ("queue_full", "persona_unavailable", "executor_stopped",
                                        "provider_budget_contract_unavailable") else "model_unavailable")) from None

    async def console_experience_task(self, request_id):
        from .console import ApplicationError
        self._open()
        await self.refresh_config()
        identifier, _, _ = await self.manual_persona()
        result = await self.store.experience_job(request_id, owner_key(self.instance_id, identifier))
        if result is None:
            raise ApplicationError("validation_error", "当前人格下没有这个生成请求")
        return result

    async def manual_experience_state(self):
        identifier, _, revision = await self.manual_persona()
        day, timezone = accepted_day(self.store.clock(), self.config.timezone)
        owner = owner_key(self.instance_id, identifier)
        state = {"persona_id": identifier, "day": day, "timezone": timezone,
                 "timezone_defaulted": not bool(self.config.timezone), "scope": "persona_private"}
        for kind in ("diary", "dream"):
            job = await self.store.latest_experience_job(owner, kind)
            daily = await self.store.daily_revision(owner, kind, day)
            state[kind] = job or {"status": "idle", "reason_code": ""}
            state[kind + "_today"] = daily
        return state
