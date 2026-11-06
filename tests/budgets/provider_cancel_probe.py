"""Explicit host-only supplement; not selected by ordinary CI filename patterns."""

import asyncio

from astrbot_plugin_livingemotion.runtime.models import OpenAIBinding


async def test_direct_runtime_caller_cancel_reaches_provider(rig, wire, record_property):
    wire.mode = "blocked"
    binding = OpenAIBinding(wire.provider)

    async def work():
        return await binding.generate("Synthetic persona.", "Synthetic input.", 1024, 30)

    task = asyncio.create_task(rig.model("direct-runtime-cancel", work))
    await asyncio.wait_for(wire.entered.wait(), 3)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await asyncio.sleep(.05)
    wire.release.set()
    await rig.runtime.join()
    rows = await rig.rows()
    record_property("measurements", {
        "wire_calls": len(wire.requests), "transport_cancellations": wire.cancelled,
        "persisted_outcomes": rows, "shared_provider_unchanged": wire.unchanged(),
    })
    assert len(wire.requests) == wire.cancelled == 1
    assert rows[0]["status"] == "cancelled" and rows[0]["units"] == 1
    assert wire.unchanged()
