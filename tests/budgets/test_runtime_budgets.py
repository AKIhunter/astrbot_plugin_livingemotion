import asyncio
from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys

import pytest

from astrbot_plugin_livingemotion.runtime.background import ModelResultUnknown
from budget_support import PURPOSES, scope


async def test_default_one_worker_queue_100(rig, record_property):
    await rig.reopen(model_daily_limit=200)
    entered, release = asyncio.Event(), asyncio.Event()
    calls = active = peak = 0

    async def work():
        nonlocal calls, active, peak
        calls += 1
        active += 1
        peak = max(peak, active)
        entered.set()
        try:
            await release.wait()
        finally:
            active -= 1

    first = await rig.runtime.submit("first", scope(), 0, work, model=True,
                                     purpose="behavior", input_tokens=4096, output_tokens=1024)
    await asyncio.wait_for(entered.wait(), 2)
    queued = [await rig.runtime.submit(
        f"queued-{i}", scope(i + 1), 0, work, model=True,
        purpose="behavior", input_tokens=4096, output_tokens=1024,
    ) for i in range(101)]
    before = rig.runtime.health()
    release.set()
    await asyncio.wait_for(rig.runtime.join(), 10)
    record_property("measurements", {
        "workers": before["workers"], "queue_length": before["queue_length"],
        "pending": before["pending"], "dispatched": calls, "peak_active": peak,
        "queued": sum(x["status"] == "queued" for x in queued),
        "queue_full": sum(x["reason_code"] == "queue_full" for x in queued),
        "daily_limit_for_queue_isolation": 200,
    })
    assert first["status"] == "queued"
    assert before["workers"] == peak == 1
    assert before["queue_length"] == 100 and before["pending"] == 101
    assert [x["status"] for x in queued] == ["queued"] * 100 + ["rejected"]
    assert queued[-1]["reason_code"] == "queue_full" and calls == 101


@pytest.mark.parametrize("purpose", PURPOSES)
async def test_token_boundaries_each_purpose(rig, purpose, record_property):
    calls = 0

    async def work():
        nonlocal calls
        calls += 1
        return "ok"

    for i, (tokens, output, reason) in enumerate((
        (4097, 1, "token_limit"), (1, 1025, "token_limit"),
        (True, 1, "token_limit"), (1, -1, "token_limit"),
        (1, 0, "missing_token_budget"),
    )):
        with pytest.raises(ValueError, match=reason):
            await rig.model(f"invalid-{i}", work, purpose, input_tokens=tokens,
                            output_tokens=output)
    assert await rig.model("boundary", work, purpose) == "ok"
    await rig.runtime.join()
    record_property("measurements", {"rejected_before_dispatch": 5, "calls": calls})
    assert calls == 1 and await rig.store.quota_usage(period=rig.day) == 1


async def test_global_48_shared_by_purpose_scope_and_restart(rig, record_property):
    calls = 0

    async def work():
        nonlocal calls
        calls += 1
        if calls % 2:
            raise RuntimeError("synthetic failure")
        return "ok"

    for i in range(48):
        try:
            await rig.model(f"daily-{i}", work, PURPOSES[i % 4], scope(i))
        except ValueError as exc:
            assert str(exc) == "job_failed"
    await rig.runtime.join()
    before = await rig.rows()
    await rig.reopen()
    await rig.store.clear_scope(scope(), 0)
    await rig.store.cleanup()
    with pytest.raises(ValueError, match="quota_exhausted"):
        await rig.model("after-reopen-clear", work, context=scope())
    await rig.runtime.join()
    usage = await rig.store.quota_usage(period=rig.day)
    record_property("measurements", {"calls_before_next_day": calls, "usage": usage,
                                      "persisted_outcomes": before})
    assert calls == usage == 48
    assert sum(r["n"] for r in before if r["status"] == "failed") == 24
    rig.now += 86400
    with pytest.raises(ValueError, match="job_failed"):
        await rig.model("next-day", work, context=scope(99))
    assert calls == 49


async def test_emotion_interval_survives_clear_restart_and_midnight(rig, record_property):
    calls = 0

    async def work():
        nonlocal calls
        calls += 1
        return "ok"

    rig.now += 1799
    await rig.model("emotion-first", work, "emotion")
    await rig.runtime.join()
    await rig.reopen()
    await rig.store.clear_scope(scope(), 0)
    rig.now += 2
    with pytest.raises(ValueError, match="quota_cooldown"):
        await rig.model("emotion-midnight", work, "emotion")
    rig.now += 597
    with pytest.raises(ValueError, match="quota_cooldown"):
        await rig.model("emotion-599", work, "emotion")
    rig.now += 1
    await rig.model("emotion-600", work, "emotion")
    record_property("measurements", {"calls": calls, "blocked_elapsed_seconds": [2, 599],
                                      "allowed_elapsed_seconds": 600})
    assert calls == 2


@pytest.mark.parametrize("mode", ("timeout", "unknown", "failure", "stop"))
async def test_terminal_outcomes_no_retry_and_no_refund(rig, mode, record_property):
    await rig.reopen(model_timeout_seconds=1, model_daily_limit=1)
    entered = asyncio.Event()
    calls = cancelled = 0

    async def work():
        nonlocal calls, cancelled
        calls += 1
        entered.set()
        if mode == "unknown":
            raise ModelResultUnknown()
        if mode == "failure":
            raise RuntimeError("synthetic failure")
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled += 1
            raise

    task = asyncio.create_task(rig.model("terminal", work))
    await asyncio.wait_for(entered.wait(), 2)
    if mode == "stop":
        await rig.runtime.stop()
    await asyncio.gather(task, return_exceptions=True)
    await rig.runtime.join()
    outcomes = await rig.rows()
    await rig.reopen()
    with pytest.raises(ValueError, match="quota_exhausted"):
        await rig.model("second", work)
    record_property("measurements", {"calls": calls, "work_cancelled": cancelled,
                                      "persisted_outcomes": outcomes})
    expected = {"timeout": "unknown", "unknown": "unknown", "failure": "failed",
                "stop": "cancelled"}[mode]
    assert calls == 1 and outcomes[0]["status"] == expected


async def test_queued_caller_cancel_never_dispatches(rig, record_property):
    entered, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def work():
        nonlocal calls
        calls += 1
        entered.set()
        await release.wait()
        return "ok"

    first = asyncio.create_task(rig.model("active", work))
    await asyncio.wait_for(entered.wait(), 2)
    second = asyncio.create_task(rig.model("queued", work))
    async def wait_queued():
        while rig.runtime.health()["queue_length"] != 1:
            await asyncio.sleep(0)
    await asyncio.wait_for(wait_queued(), 2)
    second.cancel()
    await asyncio.gather(second, return_exceptions=True)
    release.set()
    await first
    await rig.runtime.join()
    record_property("measurements", {"calls": calls, "outcomes": rig.runtime.health()["outcomes"]})
    assert calls == 1
    assert rig.runtime.health()["outcomes"][-1]["reason_code"] == "caller_cancelled"


async def test_active_caller_cancel_stops_work(rig, record_property):
    entered, release = asyncio.Event(), asyncio.Event()
    calls = cancelled = 0

    async def work():
        nonlocal calls, cancelled
        calls += 1
        entered.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            cancelled += 1
            raise
        return "synthetic result"

    task = asyncio.create_task(rig.model("active-cancel", work))
    await asyncio.wait_for(entered.wait(), 2)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await asyncio.sleep(.05)
    release.set()
    await rig.runtime.join()
    rows = await rig.rows()
    record_property("measurements", {"calls": calls, "work_cancelled": cancelled,
                                      "persisted_outcomes": rows})
    assert calls == 1 and cancelled == 1, "active caller cancellation did not reach work"
    assert rows[0]["status"] == "cancelled"


async def test_actual_dispatched_crash_keeps_reservation(rig, record_property):
    await rig.close()
    script = Path(__file__).with_name("crash_worker.py")
    completed = await asyncio.to_thread(
        subprocess.run, [sys.executable, str(script), str(rig.path)],
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        cwd=rig.path.parent, capture_output=True, timeout=10,
    )
    assert completed.returncode == 0, "synthetic crash worker failed"
    rig.config = replace(rig.config, model_daily_limit=1)
    await rig.open()
    calls = 0

    async def work():
        nonlocal calls
        calls += 1

    with pytest.raises(ValueError, match="quota_exhausted"):
        await rig.model("after-crash", work)
    rows = await rig.rows()
    record_property("measurements", {"post_restart_calls": calls, "persisted_outcomes": rows})
    assert calls == 0 and rows[0]["status"] == "unknown" and rows[0]["units"] == 1


async def test_idle_runtime_has_no_calls_or_quota(rig):
    await asyncio.sleep(.02)
    assert rig.runtime.health()["queue_length"] == 0
    assert rig.runtime.health()["outcomes"] == []
    assert await rig.rows() == []
