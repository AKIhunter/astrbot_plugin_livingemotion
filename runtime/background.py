"""No autonomous scheduling: workers sleep until explicit bounded work exists."""

from __future__ import annotations

import asyncio
import contextvars
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ..config import Config
from ..contracts import Context
from ..storage import SQLiteStore


class ModelResultUnknown(TimeoutError):
    """A dispatched request has no usable confirmed result; never retry it."""


@dataclass(frozen=True)
class _Job:
    job_id: str
    context: Context
    generation: int
    purpose: str
    work: Callable[[], Awaitable[Any]]
    model: bool
    completion: asyncio.Future | None = None
    execution_context: contextvars.Context | None = None
    # 手动生成（管理员显式点按钮）不受每日模型预算拦住；用量照记，便于观察。
    exempt_quota: bool = False
    # 日记/梦境等长任务可单独放宽；None 表示沿用全局 model_timeout_seconds。
    timeout_seconds: float | None = None


class BackgroundRuntime:
    def __init__(self, store: SQLiteStore, config: Config):
        self.store = store
        self.config = config
        self._queue: asyncio.Queue[_Job] = asyncio.Queue(maxsize=config.queue_size)
        self._tasks: list[asyncio.Task[None]] = []
        self._pending: set[str] = set()
        self._outcomes: deque[dict[str, str]] = deque(maxlen=100)
        self._accepting = False

    async def start(self) -> None:
        if self._tasks or not self.config.enabled:
            return
        self._accepting = True
        self._tasks = [asyncio.create_task(self._worker(), name=f"livingemotion-worker-{i}")
                       for i in range(self.config.model_concurrency)]

    async def submit(self, job_id: str, context: Context, generation: int,
                     work: Callable[[], Awaitable[Any]], *, purpose: str = "local",
                     model: bool = False, input_tokens: int = 0,
                     output_tokens: int = 0, completion=None,
                     exempt_quota: bool = False,
                     timeout_seconds: float | None = None) -> dict[str, str]:
        if not self._accepting:
            return {"status": "rejected", "reason_code": "runtime_stopped"}
        if model and self.config.mode != "active":
            return {"status": "rejected", "reason_code": "observe_only"}
        if not job_id or job_id in self._pending:
            return {"status": "rejected", "reason_code": "duplicate_job"}
        enabled = {"emotion": self.config.emotion_model_enabled,
                   "feeling": self.config.enabled,
                   "dream": self.config.dream_enabled, "diary": self.config.diary_enabled,
                   "behavior": self.config.autonomy_enabled,
                   "catchup": getattr(self.config, "catchup_enabled", False),
                   "closing": getattr(self.config, "closing_enabled", False)}
        if model and not enabled.get(purpose, False):
            return {"status": "rejected", "reason_code": "model_disabled"}
        if (type(input_tokens) is not int or type(output_tokens) is not int
                or input_tokens < 0 or output_tokens < 0
                or input_tokens > self.config.model_input_tokens
                or output_tokens > self.config.model_output_tokens):
            return {"status": "rejected", "reason_code": "token_limit"}
        if model and output_tokens == 0:
            return {"status": "rejected", "reason_code": "missing_token_budget"}
        if timeout_seconds is not None and (
                type(timeout_seconds) not in (int, float)
                or not 0 < timeout_seconds <= 600):
            return {"status": "rejected", "reason_code": "invalid_timeout"}
        try:
            self._queue.put_nowait(_Job(job_id, context, generation, purpose, work, model,
                                       completion, contextvars.copy_context(),
                                       bool(exempt_quota), timeout_seconds))
        except asyncio.QueueFull:
            return {"status": "rejected", "reason_code": "queue_full"}
        self._pending.add(job_id)
        # Queued is not durable acceptance; only commit_event may say accepted.
        return {"status": "queued", "reason_code": "queued"}

    async def run_model(self, job_id, context, generation, work, *, purpose,
                        input_tokens, output_tokens, timeout_seconds=None):
        completion = asyncio.get_running_loop().create_future()
        result = await self.submit(
            job_id, context, generation, work, purpose=purpose, model=True,
            input_tokens=input_tokens, output_tokens=output_tokens, completion=completion,
            timeout_seconds=timeout_seconds,
        )
        if result["status"] != "queued":
            raise ValueError(result["reason_code"])
        return await completion

    async def _run_work(self, job: _Job) -> Any:
        async def invoke():
            # Cancellation can arrive after task creation, before its first step.
            if job.completion is not None and job.completion.cancelled():
                raise asyncio.CancelledError
            return await job.work()

        work = asyncio.create_task(invoke(), context=job.execution_context)

        def cancel_work(completion):
            if completion.cancelled() and not work.done() and not work.cancelling():
                work.cancel()

        if job.completion is not None:
            job.completion.add_done_callback(cancel_work)
        try:
            # Own cancellation here so stop cannot interrupt caller-triggered cleanup.
            value = await asyncio.wait_for(
                asyncio.shield(work),
                timeout=job.timeout_seconds or self.config.model_timeout_seconds,
            )
            if job.completion is not None and job.completion.cancelled():
                raise asyncio.CancelledError
            return value
        finally:
            if job.completion is not None:
                job.completion.remove_done_callback(cancel_work)
            if not work.done():
                if not work.cancelling():
                    work.cancel()
                await asyncio.gather(work, return_exceptions=True)

    async def _worker(self) -> None:
        while self._accepting:
            job = await self._queue.get()
            reserved = False
            status, reason = "failed", "job_failed"
            try:
                if job.completion is not None and job.completion.cancelled():
                    status, reason = "cancelled", "caller_cancelled"
                    continue
                generation = await self.store.get_generation(job.context)
                if job.completion is not None and job.completion.cancelled():
                    status, reason = "cancelled", "caller_cancelled"
                    continue
                if generation != job.generation:
                    status, reason = "cancelled", "stale_generation"
                    continue
                if job.model:
                    # Charge at actual dispatch; queued work cannot reset midnight quotas.
                    period = datetime.fromtimestamp(self.store.clock(), timezone.utc).date().isoformat()
                    # 手动生成不设上限（仍写一条预留，便于事后看用量）。
                    limit = (max(self.config.model_daily_limit, 10 ** 6)
                             if job.exempt_quota else self.config.model_daily_limit)
                    result = await self.store.reserve_quota(
                        job.job_id, job.context, job.generation, period=period,
                        purpose=job.purpose, limit=limit,
                        global_limit=limit,
                        min_interval_seconds=(self.config.emotion_interval_seconds
                                              if job.purpose == "emotion" else 0),
                    )
                    reserved = result["status"] == "reserved"
                    # Let the reservation settle before cancellation; never lose a charge.
                    if job.completion is not None and job.completion.cancelled():
                        status, reason = "cancelled", "caller_cancelled"
                        continue
                    if not reserved:
                        status, reason = "rejected", result["reason_code"]
                        continue
                value = await self._run_work(job)
                status, reason = "succeeded", "completed"
                if job.completion is not None and not job.completion.done():
                    job.completion.set_result(value)
            except asyncio.CancelledError:
                status = "cancelled"
                if asyncio.current_task().cancelling():
                    reason = "runtime_stopped"
                    raise
                reason = ("caller_cancelled" if job.completion is not None
                          and job.completion.cancelled() else "task_cancelled")
            except ModelResultUnknown:
                status, reason = "unknown", "model_result_unknown"
            except asyncio.TimeoutError:
                status, reason = "unknown" if job.model else "failed", "task_timeout"
            except ValueError as exc:
                code = str(exc)
                status, reason = "failed", (code if code in (
                    "context_changed", "provider_changed", "model_unavailable",
                    "provider_budget_contract_unsupported",
                ) else "job_failed")
            except Exception:
                # Never retain exception strings or model/private text in ordinary health.
                status, reason = "failed", "job_failed"
            finally:
                try:
                    if reserved:
                        await self.store.finish_quota(job.job_id, status=status, reason_code=reason)
                finally:
                    self._outcomes.append({"job_id": job.job_id, "status": status,
                                           "reason_code": reason})
                    self._pending.discard(job.job_id)
                    if job.completion is not None and not job.completion.done():
                        job.completion.set_exception(ValueError(reason))
                    self._queue.task_done()

    async def join(self) -> None:
        await self._queue.join()

    async def stop(self) -> None:
        self._accepting = False
        tasks, self._tasks = self._tasks, []
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        while not self._queue.empty():
            job = self._queue.get_nowait()
            self._outcomes.append({"job_id": job.job_id, "status": "cancelled",
                                   "reason_code": "runtime_stopped"})
            self._pending.discard(job.job_id)
            if job.completion is not None and not job.completion.done():
                job.completion.cancel()
            self._queue.task_done()

    def health(self) -> dict[str, Any]:
        return {"accepting": self._accepting, "queue_length": self._queue.qsize(),
                "workers": sum(not task.done() for task in self._tasks),
                "pending": len(self._pending), "outcomes": list(self._outcomes)}
