"""Random idle opportunities feed the existing guarded autonomous executor."""

import asyncio
import random

from ..contracts import BehaviorIntent, stable_key
from ..domain.proactivity import choose_motive, initiative_probability, motives
from ..storage.proactivity import claim_opportunity, finish_opportunity, last_activity


class Proactivity:
    async def host_proactive_state(self) -> dict:
        """宿主是否已经有一条主动聊天任务；结果缓存五分钟。

        只读探测，不改宿主任何数据。检测不到宿主目录也按"没有"处理，
        不影响独立部署的场景。
        """
        if not bool(getattr(self.config, "proactive_native_yield", True)):
            return {"present": False, "count": 0, "jobs": [], "reason": "yield_disabled"}
        from .proactive_arbiter import cached, refresh

        state = cached(getattr(self, "data_dir", ""))
        if state.get("reason") == "not_probed_yet":
            # 首次调用才真读一次；之后五分钟内都用缓存。
            state = await asyncio.to_thread(refresh, getattr(self, "data_dir", ""))
        return state

    async def maybe_proact(self, context):
        from .proactive_arbiter import yielding_jobs

        # 修复全天让行：只保护同一目标的定时问候前后各15分钟，
        # 其他会话/时段继续原来的随机机会和发送前校验。
        host = await self.host_proactive_state()
        now = self.store.clock()
        yielding = yielding_jobs(host, context, now)
        if yielding:
            logged = getattr(self, "_native_yield_logged", set())
            if context.scope_key not in logged:
                self._native_yield_logged = logged | {context.scope_key}
                import logging

                logging.getLogger("astrbot_plugin_livingemotion.promise").warning(
                    "[LE-behavior] 宿主任务 %s target=%s，前后15分钟随机主动让行",
                    [job.get("id") for job in yielding], context.scene_id)
            return
        self._native_yield_logged = getattr(self, "_native_yield_logged", set()) - {
            context.scope_key}
        policy = self.behavior_policy()
        if (self.behavior._policy_reasons(context, policy, now)
                or len(self._actions) >= self.config.queue_size):
            return
        # Group members share one opportunity, and overlapping ticks claim it
        # transactionally. Random draws never invoke a provider.
        rng = getattr(self, "_proactive_random", None) or random.SystemRandom()
        signature = stable_key(self.config, context.persona_revision)
        deadline = 120 + self.config.model_timeout_seconds
        claim = await claim_opportunity(
            self.store, context, signature=signature,
            delay=rng.randint(self.config.behavior_random_min_minutes,
                              self.config.behavior_random_max_minutes) * 60,
            lateness=max(300, self.config.scheduler_seconds * 2), deadline=deadline,
        )
        if claim is None:
            return
        if len(self._actions) >= self.config.queue_size:
            await finish_opportunity(
                self.store, context, claim, outcome="skipped", reason="behavior_queue_full",
            )
            return

        async def work():
            mode = ""
            result = None
            outcome, reason = "skipped", "opportunity_cancelled"
            try:
                async with asyncio.timeout(deadline):
                    generation = await self.store.get_generation(context)
                    if generation != claim["generation"]:
                        reason = "stale_generation"
                        return
                    watermark = await self.store.human_watermark(context)
                    activity = await last_activity(self.store, context)
                    latest = max(activity or 0, self._participation.get(context.scope_key, 0))
                    if (latest > self.store.clock()
                            or self.store.clock() - latest < self.config.behavior_idle_minutes * 60
                            or any(c.scope_key == context.scope_key
                                   for c in self._reply_contexts.values())):
                        reason = "conversation_active"
                        return
                    evaluation = await self.behavior.evaluate(context)
                    if not evaluation.eligible:
                        reason = ", ".join(evaluation.reason_codes)
                        return
                    history = await self.behavior_history(
                        context, self.behavior._period(policy, self.store.clock()), None,
                    )
                    if rng.random() >= initiative_probability(
                            evaluation.score, history.unanswered_count, self.config.behavior_style):
                        reason = "random_skip"
                        return
                    snapshot = await self.current_snapshot(context)
                    if snapshot is None:
                        reason = "context_changed"
                        return
                    mode = choose_motive(
                        motives(snapshot.affect, snapshot.relationship, context.scene_kind,
                                emotional_share=self.config.behavior_emotional_share,
                                absent_seconds=self.store.clock() - (activity or self.store.clock())),
                        rng.random(), previous=claim.get("last_mode", ""),
                    ).key
                    intent = BehaviorIntent(
                        claim["run_id"], context, "proactive:" + mode,
                        claim["started_at"], min(claim["deadline"],
                                                claim["started_at"] + policy.intent_ttl_seconds),
                        generation, human_watermark=watermark,
                    )
                    result = await self.behavior.execute_intent(intent)
                    outcome, reason = result.status, ", ".join(result.reason_codes)
            except TimeoutError:
                outcome, reason = "skipped", "opportunity_timeout"
            except asyncio.CancelledError:
                raise
            except Exception:
                outcome, reason = "failed", "opportunity_dependency_unavailable"
            finally:
                # The intent ledger remains authoritative for delivery, including
                # unknown. This record only describes the scheduling opportunity.
                intent = await self.store.get_intent(context, claim["run_id"])
                if intent and intent["status"] in ("unknown", "succeeded"):
                    outcome, reason = intent["status"], intent["reason_code"]
                await finish_opportunity(
                    self.store, context, claim, outcome=outcome, reason=reason,
                )
        self.spawn_action(work())
