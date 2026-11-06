"""Absolute-time night scheduler. Every mutation is version/generation guarded."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from ..contracts import (
    Availability, NightPhase, NightState, SceneKind, SleepState, StateWrite, stable_key, to_dict,
)
from ..domain.night import (
    SleepCycle,
    advance_night,
    advance_life,
    apply_reply_receipt,
    begin_sleep,
    chat_wake,
    chat_wake_eligible,
    finish_waking,
    life_policy,
    night_availability,
    start_life_reply,
    submit_life_reply,
    wake_night,
)
from ..services.catchup import CatchupPolicy, build_catchup, catchup_intent
from .projector import snapshot


class NightRuntime:
    def _night_v2(self):
        return getattr(self.config, "night_policy_version", 1) == 2 and bool(self.config.timezone)

    async def _pending_life_state(self, context):
        """A missing timezone must not replay v1 energy math over persisted v2."""
        record = await self.store.get_state(context, "night")
        return bool(record and record.value.get("policy_version") == 2)

    def _night_random(self, low, high):
        # Injectable inclusive source; no process-local sleep/wake result cache.
        import random
        source = getattr(self, "night_random", None)
        return (source or random.randint)(low, high)

    def night_timeline(self, now, *, state=None):
        """Preview absolute dates without drawing a new lie-in for an old cycle."""
        config = self.config
        tz = ZoneInfo(config.timezone)
        current = datetime.fromtimestamp(now, tz)
        start = datetime.combine(current.date(), time.fromisoformat(config.fatigue_start), tz)
        if current < start:
            start -= timedelta(days=1)
        deep = datetime.combine(start.date(), time.fromisoformat(config.deep_sleep_at), tz)
        wake = datetime.combine(start.date(), time.fromisoformat(config.wake_at), tz)
        if deep <= start:
            deep += timedelta(days=1)
        if wake <= deep:
            wake += timedelta(days=1)
        # Timestamps, not wall-clock subtraction, establish actual DST order.
        midpoint = (start.timestamp() + deep.timestamp()) / 2
        identifier = stable_key("night", start.timestamp(), config.timezone)
        lie = state.lie_in_minutes if state and state.cycle_id == identifier else None
        target = wake.timestamp() + (lie or 0) * 60
        return {
            "cycle_id": identifier, "start": start.timestamp(), "drowsy": midpoint,
            "deep": deep.timestamp(), "base_wake": wake.timestamp(), "wake": target,
            "lie_in_minutes": lie,
        }

    def _life_cycle(self, state, now):
        config = self.config
        if not config.night_enabled or not config.night_schedule_enabled:
            return None
        timeline = self.night_timeline(now, state=state)
        if (state.wake_at is not None and state.wake_at > now and state.cycle_id
                and not (state.cycle_kind == "nap" and timeline["start"] <= now
                         < timeline["wake"])):
            return None
        # A persisted night target remains authoritative past fatigue_end.
        if timeline["start"] <= now < timeline["wake"]:
            lie = timeline["lie_in_minutes"]
            if lie is None:
                lie = self._night_random(config.lie_in_min_minutes, config.lie_in_max_minutes)
            return SleepCycle(
                timeline["cycle_id"], "night", timeline["start"],
                timeline["base_wake"] + lie * 60, timeline["deep"], timeline["drowsy"],
                timeline["base_wake"], lie,
            )
        if config.nap_enabled:
            tz = ZoneInfo(config.timezone)
            current = datetime.fromtimestamp(now, tz)
            start = datetime.combine(current.date(), time.fromisoformat(config.nap_start), tz)
            end = datetime.combine(current.date(), time.fromisoformat(config.nap_end), tz)
            if end <= start:
                if current < end:
                    start -= timedelta(days=1)
                else:
                    end += timedelta(days=1)
            if start <= current < end:
                return SleepCycle(stable_key("nap", start.timestamp(), config.timezone),
                                  "nap", start.timestamp(), end.timestamp())
        return None

    def _fatigue_windows(self, start, now):
        tz = ZoneInfo(self.config.timezone)
        day = datetime.fromtimestamp(start, tz).date() - timedelta(days=1)
        last = datetime.fromtimestamp(now, tz).date()
        # Long-offline recovery is capped only in work, not time: before the last
        # week rates saturate at a bound, and no old actions are replayed.
        if (last - day).days > 370:
            day = last - timedelta(days=370)
        windows = []
        while day <= last:
            left = datetime.combine(day, time.fromisoformat(self.config.fatigue_start), tz)
            right = datetime.combine(day, time.fromisoformat(self.config.fatigue_end), tz)
            if right <= left:
                right += timedelta(days=1)
            if right.timestamp() >= start and left.timestamp() <= now:
                windows.append((left.timestamp(), right.timestamp()))
            day += timedelta(days=1)
        return tuple(windows)

    def _advance_life(self, state, now, runtime=None):
        return advance_life(
            state, now=now, cycle=None if (runtime or {}).get("manual_wake_until", 0) > now
            else self._life_cycle(state, now),
            fatigue_windows=self._fatigue_windows(state.updated_at, now),
            policy=life_policy(self.config),
            allow_sleep=bool(self.config.allow_sleep and self.config.night_enabled),
        )

    async def initialize_state_scope(self, context):
        return await self.store.initialize_state_mode(
            context, shared=getattr(self.config, "persona_shared_state", False),
        )

    async def night_snapshot(self, context):
        if self._night_v2():
            result = await self.advance_scope(context)
            if result is None:
                raise ValueError("night_state_unavailable")
            return result
        night = snapshot(await self.store.get_state(context, "night"), NightState,
                         updated_at=self.store.clock())
        if night.policy_version == 2:
            return night
        return advance_night(night, now=self.store.clock(), enabled=self.config.night_enabled)

    async def availability(self, context, *, exempt=False):
        if self.effective_mode(context) != "active" or context.scene_kind == SceneKind.PUBLIC_COMMENT:
            return Availability(False, ("mode_or_source_unavailable",))
        try:
            state = await self.night_snapshot(context)
        except Exception:
            return Availability(False, ("state_unavailable",), block_chat=False)
        if self._night_v2() or state.policy_version == 2:
            allowed = (not self.config.allow_sleep or not self.config.night_enabled
                       or self._night_v2() and state.display_state in
                       (SleepState.AWAKE, SleepState.GROGGY))
            # Exempt is not a chat-wake bypass for deep sleep; authenticated
            # manual wake changes the state via advance_scope(action=night.wake).
            reason = (f"night_{state.display_state.value}" if self._night_v2()
                      else "night_timezone_required")
            return Availability(allowed, (reason,), not allowed)
        return night_availability(state, now=self.store.clock(),
                                  block_chat=self.config.night_block_chat, exempt=exempt,
                                  enabled=self.config.night_enabled)

    async def reply_started(self, context, reply_id, *, expected_generation=None):
        if not self._night_v2():
            if (await self._pending_life_state(context) and self.config.allow_sleep
                    and self.config.night_enabled):
                return {"allowed": False, "status": "rejected",
                        "reason_code": "night_timezone_required", "ticket": None}
            return {"allowed": True, "status": "accepted", "reason_code": "night_v1",
                    "ticket": None}
        if self.effective_mode(context) != "active" or not await self.validate_context(context):
            return {"allowed": False, "status": "rejected", "reason_code": "context_changed"}

        def transform(state, runtime, now, attempt):
            state, changes = self._advance_life(state, now, runtime)
            state, allowed = start_life_reply(state, policy=life_policy(self.config))
            return state, changes, {"allowed": allowed,
                                    "reason_code": "reply_started" if allowed else "sleep_blocks_reply"}
        return await self.store.night_operation(
            context, transform, operation="reply_started", reply_id=reply_id,
            expected_generation=expected_generation,
        )

    async def reply_submitted(self, context, reply_id, *, ticket=None):
        """First final result enters host output, NOT evidence of delivery."""
        if not self._night_v2():
            if (await self._pending_life_state(context) and self.config.allow_sleep
                    and self.config.night_enabled):
                return {"allowed": False, "status": "rejected",
                        "reason_code": "night_timezone_required"}
            return {"allowed": True, "status": "accepted", "reason_code": "night_v1"}
        if self.effective_mode(context) != "active" or not await self.validate_context(context):
            return {"allowed": False, "status": "rejected", "reason_code": "context_changed"}

        def transform(state, runtime, now, attempt):
            state, changes = self._advance_life(state, now, runtime)
            deadline = state.wake_window_deadline
            valid = (
                state.display_state != SleepState.DEEP_SLEEP
                and (deadline is None or now < deadline)
                and (not attempt["wake_session"] or attempt["wake_session"] == state.wake_session)
                and attempt["cycle_id"] == state.cycle_id
            )
            if not valid:
                return state, changes, {"allowed": False, "reason_code": "reply_submission_expired"}
            state, charge = submit_life_reply(
                state, now=now, policy=life_policy(self.config),
                allow_sleep=bool(self.config.allow_sleep and self.config.night_enabled),
            )
            return state, (*changes, *charge), {"allowed": True, "reason_code": "reply_submitted"}
        return await self.store.night_operation(
            context, transform, operation="reply_submitted", reply_id=reply_id, ticket=ticket,
        )

    async def wake_attempt(self, context, event):
        if not self._night_v2():
            return {"allowed": False, "status": "rejected", "reason_code": "night_v1"}
        if self.effective_mode(context) != "active" or not await self.validate_context(context):
            return {"allowed": False, "status": "rejected", "reason_code": "context_changed"}

        def transform(state, runtime, now, attempt):
            state, changes = self._advance_life(state, now, runtime)
            if not now - 7200 <= event.occurred_at <= now:
                return state, changes, {"allowed": False, "reason_code": "wake_event_expired"}
            dice = (self._night_random(0, 9), self._night_random(0, 9)) if (
                state.wake_score is None and state.energy < 10
                and chat_wake_eligible(state, event, policy=life_policy(self.config))
            ) else (0, 0)
            state, allowed, reason = chat_wake(state, event, policy=life_policy(self.config),
                                              dice=dice)
            if allowed or reason == "wake_roll_failed":
                changes = (*changes, {"occurred_at": now, "category": "wake",
                                     "before_units": state.energy_units,
                                     "after_units": state.energy_units, "reason_code": reason})
            return state, changes, {"allowed": allowed, "reason_code": reason}
        return await self.store.night_operation(context, transform, operation="wake", event=event)

    async def begin_reply(self, context, attempt_id):
        return bool((await self.reply_started(context, attempt_id))["allowed"])

    async def submit_reply(self, context, submission_id, *, attempt_id=None):
        # submission_id must be the stable logical reply ID, not a chunk/TTS ID.
        identifier = attempt_id or submission_id
        ticket = await self.store.reply_ticket(context, identifier) if self._night_v2() else None
        return bool((await self.reply_submitted(context, identifier, ticket=ticket))["allowed"])

    async def try_chat_wake(self, context, event_key, is_private, native_at_bot):
        if type(is_private) is not bool or type(native_at_bot) is not bool:
            return False
        if is_private != (context.scene_kind == SceneKind.PRIVATE):
            return False
        event = await self.store.archived_event(context, event_key)
        if event is None:
            return False
        if native_at_bot and context.scene_kind == SceneKind.GROUP:
            event = replace(event, signals=(*event.signals, "native_bot_mention"))
        return bool((await self.wake_attempt(context, event))["allowed"])

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
        if self._night_v2():
            if action and not await self.validate_context(context):
                return None
            def transform(state, runtime, now, attempt):
                state, changes = self._advance_life(state, now, runtime)
                if action == "night.wake":
                    state = replace(
                        state, display_state=SleepState.AWAKE, phase=NightPhase.AWAKE,
                        wake_at=now, cycle_id=None, sleep_started_at=None, sleep_stage=None,
                        deep_sleep_at=None, drowsy_at=None, wake_score=None, wake_failures=0,
                        wake_session=None, wake_replies_used=0, wake_reply_limit=0,
                        first_reply_submitted_at=None, wake_window_deadline=None,
                        reason_codes=("manual_wake",),
                    )
                    # Suppress re-entering this planned cycle after admin wake.
                    runtime["manual_wake_until"] = self.night_timeline(now)["base_wake"]
                elif action == "night.sleep":
                    runtime.pop("manual_wake_until", None)
                    cycle = SleepCycle(stable_key("manual", now), "manual", now, now + 8 * 3600)
                    state = replace(state, wake_at=None)
                    state, added = advance_life(state, now=now, cycle=cycle,
                                               policy=life_policy(self.config),
                                               allow_sleep=self.config.allow_sleep)
                    changes = (*changes, *added)
                elif runtime.get("manual_wake_until", 0) > now:
                    state = replace(state, display_state=SleepState.AWAKE, phase=NightPhase.AWAKE,
                                    wake_at=None, cycle_id=None, cycle_started_at=None,
                                    deep_sleep_at=None, drowsy_at=None, sleep_started_at=None,
                                    sleep_stage=None)
                if action:
                    changes = (*changes, {
                        "occurred_at": now, "category": "manual",
                        "before_units": state.energy_units, "after_units": state.energy_units,
                        "reason_code": action,
                    })
                return state, changes, {"allowed": True, "reason_code": action or "night_clock"}
            result = await self.store.night_operation(
                context, transform, operation="manual" if action else "tick",
            )
            return result.get("night") if result["status"] == "accepted" else None
        generation = await self.store.get_generation(context)
        for _ in range(3):
            now = self.store.clock()
            record = await self.store.get_state(context, "night")
            night = snapshot(record, NightState, updated_at=now)
            if night.policy_version == 2:
                # Keep absolute windows, energy units and attempts intact until
                # the configured life policy can resume them.
                return night
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
                           record.version if record else 0,
                           owner=record.owner if record else self.store.state_owner(context)),
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
        if self._night_v2():
            return False
        context = receipt.context
        generation = await self.store.get_generation(context)
        for _ in range(3):
            if not await self.validate_context(context, generation):
                return False
            record = await self.store.get_state(context, "night")
            if record is None:
                return False
            if record.value.get("policy_version") == 2:
                return False
            night = apply_reply_receipt(snapshot(record, NightState), receipt,
                                        now=self.store.clock(), enabled=self.config.night_enabled)
            result = await self.store.write_states(context, generation, (
                StateWrite("night", {**record.value, **to_dict(night)}, record.version,
                           owner=record.owner),
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
        proactive_scopes = set()
        proactive_contexts = {c.scope_key: c for c in self._contexts.values()}
        for context in tuple(self._contexts.values()):
            if context.scene_kind == SceneKind.PUBLIC_COMMENT:
                continue
            closing = getattr(self, "maybe_close_conversation", None)
            if closing is not None and self.effective_mode(context) == "active":
                await closing(context)
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
                if (context.scope_key not in proactive_scopes
                        and context == proactive_contexts[context.scope_key]):
                    proactive_scopes.add(context.scope_key)
                    await self.maybe_proact(context)
        if now - self._last_cleanup >= 3600:
            await self.store.cleanup()
            self._last_cleanup = now

    async def mark_request_read(self, event):
        if self._night_v2():
            return
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
            if night.policy_version == 2:
                return
            rows = await self.store.read_window(context, after_seq=night.unread_watermark, limit=1)
            # Confirm only the contiguous message actually consumed by this request.
            if not rows or rows[0]["metadata_json"]["source_id"] != source_id:
                return
            updated = replace(night, unread_watermark=rows[0]["seq"])
            result = await self.store.write_states(context, generation, (
                StateWrite("night", {**record.value, **to_dict(updated)}, record.version,
                           owner=record.owner),
            ))
            if result.reason_code != "version_conflict":
                return
