"""Real plugin stores, synthetic bodies, no host network or provider calls."""
from dataclasses import replace
import json
from types import SimpleNamespace
import zipfile

import pytest

from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import BehaviorIntent
from astrbot_plugin_livingemotion.diagnostic_bundle import DiagnosticRecorder
from astrbot_plugin_livingemotion.runtime.diagnostics import prepare
from astrbot_plugin_livingemotion.storage.behavior_logs import simulation_record
from astrbot_plugin_livingemotion.storage.promise_store import PromiseStore


@pytest.mark.asyncio
async def test_real_sources_and_capture_do_not_export_private_fields(le_store, le_event):
    recorder = DiagnosticRecorder(le_store.path.parent, "LE", __file__,
                                  clock=le_store.clock, credentials=["synthetic-secret-for-export"])
    le_store.diagnostics = recorder
    app = SimpleNamespace(data_dir=le_store.path.parent, config=Config(), closed=False,
                          host=SimpleNamespace(get_config=lambda: {"provider": [
                              {"id": "route-1", "api_type": "openai", "api_key": "synthetic-secret-for-export"}]}),
                          diagnostics=recorder, effective_mode=lambda: "active")
    try:
        event = replace(le_event, body="private-body-sentinel")
        await le_store.register_context(event.context)
        result = await le_store.commit_event(event, 0, traces=[{
            "kind": "emotion", "before": {"pleasure": .1}, "after": {"pleasure": .2},
            "body": "private-trace-sentinel", "reason_codes": ["care"],
            "context_emotions": {"after": [{"kind": "hurt", "intensity": .2,
                                           "evidence": "private-evidence-sentinel"}]}}])
        assert result.accepted
        intent = BehaviorIntent("offline-intent", event.context, "share", le_store.clock() - .5,
                                le_store.clock() + 3600, 0)
        await le_store.create_intent(intent)
        await simulation_record(le_store, "offline-simulation", {
            "request_id": "offline-simulation", "created_at": le_store.clock() - .5,
            "status": "completed", "text": "private-simulation-sentinel"})
        promises = PromiseStore(le_store)
        created = await promises.create(event.context, description="private-promise-sentinel",
                                        note="private-note-sentinel", due_at=le_store.clock() + 300,
                                        bucket="soon")
        await promises.move(created["promise_id"], status="running")
        app.diagnostics.clock = lambda: le_store.clock() + 1
        _, snapshot, sources = prepare(app)
        bundle = recorder.export(snapshot, sources)
        try:
            with zipfile.ZipFile(bundle.path) as archive:
                contents = {name: archive.read(name).decode() for name in archive.namelist()}
            combined = "\n".join(contents.values())
            for secret in ("private-body-sentinel", "private-trace-sentinel",
                           "private-simulation-sentinel", "private-promise-sentinel",
                           "private-note-sentinel", "synthetic-secret-for-export",
                           "private-evidence-sentinel"):
                assert secret not in combined
            assert '"api_type": "openai"' in contents["settings.json"]
            manifest = json.loads(contents["manifest.json"])
            assert manifest["files"]["events.jsonl"]["records"] == 1
            assert manifest["files"]["emotion.jsonl"]["records"] == 1
            assert manifest["skipped"] == []
            assert '"intensity": 0.2' in contents["emotion.jsonl"]
            assert '"simulated": true' in contents["behavior.jsonl"]
            assert '"simulated": false' in contents["behavior.jsonl"]
            assert '"status": "running"' in contents["promises.jsonl"]
            assert '"operation": "event"' in contents["runtime.jsonl"]
            assert '"operation": "promise_transition"' in contents["runtime.jsonl"]
        finally:
            bundle.close()
    finally:
        recorder.close()
        le_store.diagnostics = None


@pytest.mark.asyncio
async def test_diagnostics_do_not_validate_business_clock_after_commit(le_store, le_context):
    await le_store.register_context(le_context)
    original_run, original_clock = le_store._run, le_store.clock
    def failed_clock():
        raise AssertionError("business clock must not be read after commit")
    def failed_recorder(*_):
        raise RuntimeError("synthetic diagnostic failure")
    recorder = SimpleNamespace(record=failed_recorder, dropped=0)
    le_store.diagnostics = recorder
    async def commit_then_break_clock(operation):
        result = await original_run(operation)
        le_store.clock = failed_clock
        return result
    le_store._run = commit_then_break_clock
    try:
        intent = BehaviorIntent("clock-intent", le_context, "share",
                                original_clock() - 1, original_clock() + 3600, 0)
        assert (await le_store.create_intent(intent))["status"] == "created"
        le_store.clock = original_clock
        result = await le_store.transition_intent(
            le_context, intent.intent_id, 0, expected_status="pending",
            status="cancelled", reason_code="offline_cancel")
        assert result["status"] == "updated"
        assert recorder.dropped == 2
    finally:
        le_store._run, le_store.clock = original_run, original_clock
        le_store.diagnostics = None
