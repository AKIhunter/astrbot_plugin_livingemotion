"""Absolute-time night scheduler. Every mutation is version/generation guarded."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from ..contracts import NightPhase, NightState, SceneKind, StateWrite, stable_key, to_dict
from ..domain.night import (
    advance_night,
    apply_reply_receipt,
    begin_sleep,
    finish_waking,
    wake_night,
)
from ..services.catchup import CatchupPolicy, build_catchup, catchup_intent
from .projector import snapshot


class NightRuntime:
    def sleep_window(self, now):
        config = self.config
        if not config.timezone or not config.night_schedule_enabled:
            return None
        tz = ZoneInfo(config.timezone)
        current = datetime.fromtimestamp(now, tz)
        start = datetime.combine(current.date(), time.fromisoformat(config.sleep_at), tz)
        end = datetime.combine(current.date(), time.fromisoformat(config.wake_at), tz)
        if end <= start:
            if current < end:
                start -= timedelta(days=1)
            else:
                end += timedelta(days=1)
        return (start.timestamp(), end.timestamp()) if start <= current < end else None

    async def advance_scope(self, context, *, recovering=False, action=None):
        if context.scene_kind == SceneKind.PUBLIC_COMMENT or not self.config.enabled:
            return None
        generation = await self.store.get_generation(context)
        for _ in range(3):
            now = self.store.clock()
            record = await self.store.get_state(context, "night")
            night = snapshot(record, NightState, updated_at=now)
            runtime = dict(record.value.get("_runtime", {})) if record else {}
            night = advance_night(night, now=now, enabled=self.config.night_enabled,
                                  recovering=recovering)
            if action == "night.wake":
                night = wake_night(night, now=now, reason="manual",
                                   enabled=self.config.night_enabled)
            elif action == "night.sleep":
                night = begin_sleep(night, context, now=now, wake_at=now + 8 * 3600,
                                    manual=True, enabled=self.config.night_enabled)
            elif not recovering and self.effective_mode(context) == "active":
                window = self.sleep_window(now)
                if window and runtime.get("schedule_key") != str(window[0]):
                    # Mark the window once, including when settling cannot complete.
                    runtime["schedule_key"] = str(window[0])
                    pending = self._pending_replies.get(context.scope_key)
                    message_id = pending[0] if pending and pending[1] > now else None
                    night = begin_sleep(night, context, now=now, wake_at=window[1],
                                        message_id=message_id, enabled=self.config.night_enabled)
            rows = []
            watermark = await self.store.human_watermark(context)
            policy = CatchupPolicy(max_rows=min(200, self.config.window_per_scope))
            if night.phase == NightPhase.WAKING:
                rows = await self.store.read_window(
                    context, after_seq=night.unread_watermark, limit=policy.max_rows,
                )
            catchup = build_catchup(
                night, context, rows, now=now, high_watermark=watermark,
                generation=generation, runtime=runtime.get("catchup", {}), policy=policy,
            )
            night, runtime["catchup"] = catchup["night"], catchup["runtime"]
            intent = None
            if (not recovering and catchup["summary"] is not None
                    and not catchup["has_more"] and self.config.autonomy_enabled):
                intent = catchup_intent(catchup["summary"], night, context,
                                        now=now, generation=generation)
            if night.phase == NightPhase.WAKING and not catchup["has_more"]:
                night = finish_waking(night, now=now, enabled=self.config.night_enabled)
            if self.closed or not self.config.enabled:
                return None
            if action and not await self.validate_context(context, generation):
                return None
            result = await self.store.write_states(context, generation, (
                StateWrite("night", {**to_dict(night), "_runtime": runtime},
                           record.version if record else 0),
            ))
            if result.accepted:
                if intent and self.effective_mode(context) == "active":
                    self.spawn_action(self.behavior.execute_intent(intent))
                return night
            if result.reason_code != "version_conflict":
                return None
        return None

    async def night_guard(self, context, original):
        if self.effective_mode(context) != "active" or not self.config.night_enabled:
            return False
        current = await self.night_snapshot(context)
        return (current.phase == NightPhase.ASLEEP and current.sleep_stage == "REM"
                and current.sleep_started_at == original.sleep_started_at
                and await self.validate_context(context))

    async def confirm_reply(self, receipt):
        """Trusted transport-confirmation port, not a model or HTTP callback."""
        context = receipt.context
        generation = await self.store.get_generation(context)
        for _ in range(3):
            if not await self.validate_context(context, generation):
                return False
            record = await self.store.get_state(context, "night")
            if record is None:
                return False
            night = apply_reply_receipt(snapshot(record, NightState), receipt,
                                        now=self.store.clock(), enabled=self.config.night_enabled)
            result = await self.store.write_states(context, generation, (
                StateWrite("night", {**record.value, **to_dict(night)}, record.version),
            ))
            if result.reason_code != "version_conflict":
                return result.accepted

    def spawn_action(self, work):
        async def bounded():
            try:
                return await work
            except asyncio.CancelledError:
                raise
            except Exception:
                self._task_fault = "background_action_failed"
        task = asyncio.create_task(bounded(), name="livingemotion-action")
        self._actions.add(task)
        task.add_done_callback(self._actions.discard)
        return task

    async def _tick_loop(self):
        while not self.closed and self.config.enabled:
            await asyncio.sleep(self.config.scheduler_seconds)
            try:
                await self.tick()
                self._task_fault = ""
            except asyncio.CancelledError:
                raise
            except Exception:
                self._task_fault = "scheduler_tick_failed"

    async def tick(self):
        if self.closed or not self.config.enabled:
            return
        now = self.store.clock()
        for context in tuple(self._contexts.values()):
            if context.scene_kind == SceneKind.PUBLIC_COMMENT:
                continue
            night = await self.advance_scope(context)
            if (self.effective_mode(context) != "active"
                    or not await self.validate_context(context)):
                continue
            source = await self.bridge.current(context)
            if self.config.diary_enabled or self.config.dream_enabled:
                try:
                    experience = await self.experience_service(context)
                    if self.config.diary_enabled:
                        await experience.queue_diary(context, persona_text=source.persona.prompt)
                    if self.config.dream_enabled and night:
                        await experience.queue_dream(
                            context, night, persona_text=source.persona.prompt,
                        )
                except ValueError:
                    self._task_fault = "provider_budget_contract_unavailable"
            if self.config.autonomy_enabled and len(self._actions) < self.config.queue_size:
                # One logical attempt per cooldown slot; never resume an old intent.
                intent_id = "scheduled:" + stable_key(
                    context.scope_key, int(now // self.behavior_policy().cooldown_seconds),
                )
                self.spawn_action(self.behavior.execute(context, intent_id=intent_id))
        if now - self._last_cleanup >= 3600:
            await self.store.cleanup()
            self._last_cleanup = now

    async def mark_request_read(self, event):
        raw = event.get_extra("livingemotion:context")
        source_id = str(getattr(event.message_obj, "message_id", "") or "")
        if not raw or not self.config.enabled:
            return
        from ..contracts import Context
        context = Context.from_dict(raw)
        if not await self.validate_context(context):
            return
        generation = await self.store.get_generation(context)
        for _ in range(3):
            record = await self.store.get_state(context, "night")
            if record is None:
                return
            night = snapshot(record, NightState)
            rows = await self.store.read_window(context, after_seq=night.unread_watermark, limit=1)
            # Confirm only the contiguous message actually consumed by this request.
            if not rows or rows[0]["metadata_json"]["source_id"] != source_id:
                return
            updated = replace(night, unread_watermark=rows[0]["seq"])
            result = await self.store.write_states(context, generation, (
                StateWrite("night", {**record.value, **to_dict(updated)}, record.version),
            ))
            if result.reason_code != "version_conflict":
                return
