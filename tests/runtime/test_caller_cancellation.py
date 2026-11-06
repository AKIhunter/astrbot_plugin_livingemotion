import asyncio
from datetime import datetime, timezone

import pytest

from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.runtime.background import BackgroundRuntime, ModelResultUnknown


async def run_model(runtime, context, job_id, work):
    return await runtime.run_model(
        job_id, context, 0, work, purpose="behavior", input_tokens=1, output_tokens=1,
    )


async def quota_rows(store):
    return await store._run(lambda db: [
        dict(row) for row in db.execute(
            "SELECT reservation_id,status,reason_code,units FROM quota_reservations "
            "ORDER BY reservation_id"
        )
    ])


async def test_caller_cancel_waits_for_cleanup_and_worker_serves_next_job(le_store, le_context):
    runtime = BackgroundRuntime(le_store, Config(autonomy_enabled=True))
    entered, cleaning, release, cleaned = (asyncio.Event() for _ in range(4))
    next_entered = asyncio.Event()
    cancellations = 0

    async def work():
        nonlocal cancellations
        entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancellations += 1
            cleaning.set()
            await release.wait()
            cleaned.set()
            raise

    async def next_work():
        assert cleaned.is_set()
        next_entered.set()
        return "next"

    await runtime.start()
    first = asyncio.create_task(run_model(runtime, le_context, "first", work))
    second = None
    try:
        await asyncio.wait_for(entered.wait(), 2)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        await asyncio.wait_for(cleaning.wait(), 2)
        second = asyncio.create_task(run_model(runtime, le_context, "second", next_work))
        await asyncio.sleep(0)
        assert runtime.health()["workers"] == 1
        assert runtime.health()["queue_length"] == 1
        assert not next_entered.is_set()
        release.set()
        assert await asyncio.wait_for(second, 2) == "next"
        await asyncio.wait_for(runtime.join(), 2)
        assert cancellations == 1
        assert runtime.health()["pending"] == 0
        assert runtime.health()["workers"] == 1
        assert await quota_rows(le_store) == [
            {"reservation_id": "first", "status": "cancelled",
             "reason_code": "caller_cancelled", "units": 1},
            {"reservation_id": "second", "status": "succeeded",
             "reason_code": "completed", "units": 1},
        ]
    finally:
        release.set()
        await runtime.stop()
        await asyncio.gather(first, *([second] if second is not None else []),
                             return_exceptions=True)


@pytest.mark.parametrize("phase", ("generation", "reserve_before", "reserve_after",
                                   "dispatch_scheduled"))
async def test_cancel_after_dequeue_never_dispatches(
        le_store, le_context, monkeypatch, phase):
    runtime = BackgroundRuntime(le_store, Config(autonomy_enabled=True))
    paused, release = asyncio.Event(), asyncio.Event()
    original_generation = le_store.get_generation
    original_reserve = le_store.reserve_quota
    calls = 0

    async def generation(context):
        value = await original_generation(context)
        paused.set()
        await release.wait()
        return value

    async def reserve(*args, **kwargs):
        if phase == "reserve_before":
            paused.set()
            await release.wait()
        value = await original_reserve(*args, **kwargs)
        if phase == "reserve_after":
            paused.set()
            await release.wait()
        if phase == "dispatch_scheduled":
            # Runs after task creation but before the work task gets its first step.
            asyncio.get_running_loop().call_soon(caller.cancel)
        return value

    async def work():
        nonlocal calls
        calls += 1
        return "must not dispatch"

    if phase == "generation":
        monkeypatch.setattr(le_store, "get_generation", generation)
    else:
        monkeypatch.setattr(le_store, "reserve_quota", reserve)
    await runtime.start()
    caller = asyncio.create_task(run_model(runtime, le_context, "race", work))
    try:
        if phase != "dispatch_scheduled":
            await asyncio.wait_for(paused.wait(), 2)
            assert runtime.health()["queue_length"] == 0
            caller.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(caller, 2)
        release.set()
        await asyncio.wait_for(runtime.join(), 2)
        assert calls == 0
        assert runtime.health()["workers"] == 1
        assert runtime.health()["pending"] == 0
        assert runtime.health()["outcomes"][-1]["reason_code"] == "caller_cancelled"
        rows = await quota_rows(le_store)
        assert rows == ([] if phase == "generation" else [
            {"reservation_id": "race", "status": "cancelled",
             "reason_code": "caller_cancelled", "units": 1},
        ])
    finally:
        release.set()
        await runtime.stop()
        await asyncio.gather(caller, return_exceptions=True)


@pytest.mark.parametrize("result", ("return", "unknown"))
async def test_cancel_cannot_become_success_or_refund(le_store, le_context, result):
    runtime = BackgroundRuntime(
        le_store, Config(autonomy_enabled=True, model_daily_limit=1),
    )
    entered = asyncio.Event()
    calls = cancellations = 0

    async def work():
        nonlocal calls, cancellations
        calls += 1
        entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancellations += 1
            if result == "unknown":
                raise ModelResultUnknown()
            return "discarded late response"

    await runtime.start()
    caller = asyncio.create_task(run_model(runtime, le_context, "cancel", work))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        caller.cancel()
        with pytest.raises(asyncio.CancelledError):
            await caller
        await asyncio.wait_for(runtime.join(), 2)
        expected = ("unknown", "model_result_unknown") if result == "unknown" else (
            "cancelled", "caller_cancelled",
        )
        rows = await quota_rows(le_store)
        assert (rows[0]["status"], rows[0]["reason_code"]) == expected
        assert rows[0]["units"] == 1
        period = datetime.fromtimestamp(le_store.clock(), timezone.utc).date().isoformat()
        assert await le_store.quota_usage(period=period) == 1
        with pytest.raises(ValueError, match="quota_exhausted"):
            await asyncio.wait_for(run_model(runtime, le_context, "denied", work), 2)
        await asyncio.wait_for(runtime.join(), 2)
        assert calls == cancellations == 1
        assert runtime.health()["workers"] == 1
    finally:
        await runtime.stop()
        await asyncio.gather(caller, return_exceptions=True)


async def test_stop_during_caller_cleanup_waits_without_second_cancel(le_store, le_context):
    runtime = BackgroundRuntime(le_store, Config(autonomy_enabled=True))
    entered, cleaning, release, cleaned = (asyncio.Event() for _ in range(4))

    async def work():
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaning.set()
            await release.wait()
            cleaned.set()

    await runtime.start()
    caller = asyncio.create_task(run_model(runtime, le_context, "stop-cleanup", work))
    stopper = None
    try:
        await asyncio.wait_for(entered.wait(), 2)
        caller.cancel()
        with pytest.raises(asyncio.CancelledError):
            await caller
        await asyncio.wait_for(cleaning.wait(), 2)
        stopper = asyncio.create_task(runtime.stop())
        await asyncio.sleep(0)
        assert not stopper.done()
        release.set()
        await asyncio.wait_for(stopper, 2)
        await asyncio.wait_for(runtime.join(), 2)
        assert cleaned.is_set()
        assert runtime.health()["pending"] == runtime.health()["workers"] == 0
        assert await quota_rows(le_store) == [
            {"reservation_id": "stop-cleanup", "status": "cancelled",
             "reason_code": "runtime_stopped", "units": 1},
        ]
    finally:
        release.set()
        if stopper is not None:
            await stopper
        else:
            await runtime.stop()
        await asyncio.gather(caller, return_exceptions=True)
