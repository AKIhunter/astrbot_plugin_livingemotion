"""Independent CLI-to-runtime checks, only synthetic snapshots and send stubs."""

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from astrbot_plugin_livingemotion.adapters.memory import MemoryGateway
from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import BotAffect, Event, NightState, Relationship
from astrbot_plugin_livingemotion.services.behavior import (
    BehaviorHistory, BehaviorPolicy, BehaviorService, BehaviorSnapshot, SendReceipt,
)
from astrbot_plugin_livingemotion.storage import SQLiteStore
from astrbot_plugin_livingemotion.tests.migration.test_legacy_import import (
    CLI, NOW, sample,
)


def cli(*args):
    process = subprocess.run(
        [sys.executable, str(CLI), *map(str, args)],
        text=True, capture_output=True, timeout=30,
    )
    assert process.returncode == 0, (process.returncode, process.stdout, process.stderr)
    return json.loads(process.stdout)


def import_cli(sample_value, tmp_path, selection):
    source, target, _, _ = sample_value
    selector, manifest = tmp_path / "selection.json", tmp_path / "manifest.json"
    selector.write_text(json.dumps(selection), encoding="utf-8")
    common = ["--snapshot", source, "--snapshot-confirmed",
              "--target", target, "--target-stopped"]
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    preview = cli("preview", *common, "--selection", selector, "--output", manifest)
    first = cli("import", *common, "--manifest", manifest)
    repeated = cli("import", *common, "--manifest", manifest)
    verified = cli("verify", *common, "--manifest", manifest)
    assert first["inserted"] == len(selection["rows"])
    assert repeated["inserted"] == 0
    assert verified["status"] == "verified"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    return preview


@pytest.mark.parametrize("restriction", ["cooldown", "scope_quota", "global_quota", "unanswered"])
@pytest.mark.parametrize("proven", [False, True], ids=["unresolved", "proven"])
def test_imported_behavior_restriction_blocks_after_restart(sample, tmp_path, restriction, proven):
    source, target, selection, context = sample
    day = datetime.fromtimestamp(NOW, timezone.utc).date().isoformat()
    session = {
        "last_at": NOW - 200 if restriction == "cooldown" else NOW - 10000,
        "next_ok_at": NOW + 800 if restriction == "cooldown" else NOW - 1,
        "unanswered": 2 if restriction == "unanswered" else 0,
        "sent_today": 2 if restriction == "scope_quota" else 0, "day": day,
    }
    global_value = {"sent_today": 6 if restriction == "global_quota" else 0, "day": day}
    with sqlite3.connect(source) as db:
        db.execute("UPDATE kv SET v=? WHERE k='proactive.sessions'",
                   (json.dumps({"old-session": session}),))
        db.execute("UPDATE kv SET v=? WHERE k='proactive.global'", (json.dumps(global_value),))
    db.close()

    async def seed():
        store = SQLiteStore(target, clock=lambda: NOW)
        await store.open()
        try:
            assert (await store.commit_event(Event(
                "before-import", "verification", "message", context, "human", NOW - 400,
                "before-import", actor_id=context.account_id, body="Synthetic eligible material.",
            ), 0)).accepted
        finally:
            await store.close()

    asyncio.run(seed())
    selection = {**selection, "rows": [
        row for row in selection["rows"]
        if row["key"].get("k") in ("proactive.sessions", "proactive.global")
    ]}
    if proven:
        selection["rows"] = [
            {**row, "context_id": context.account_key, "constraint_binding": {
                "timezone": "UTC", "quota_scope": (
                    "instance" if row["key"]["k"] == "proactive.global" else "scope"
                ),
            }} for row in selection["rows"]
        ]
    preview = import_cli(sample, tmp_path, selection)
    if not proven:
        assert preview["activation_blockers"]

    async def restart_and_execute():
        # This is the real behavior service and real SQL history, not the author's catalogue.
        now = [NOW]
        store = SQLiteStore(target, config=Config(timezone="UTC"), clock=lambda: now[0])
        await store.open()
        await store.recover_inflight()
        gateway = MemoryGateway(clock=lambda: now[0])
        sends, calls = [], []

        async def current(_context):
            return BehaviorSnapshot(
                context, BotAffect(social_need=.8), Relationship(score=700),
                NightState(), "Synthetic native persona.", True, "verification-restart",
            )

        async def valid(_context):
            return True

        async def history(ctx, period, exclude):
            return BehaviorHistory(**await store.behavior_history(ctx, period, exclude))

        async def model(request):
            calls.append(request.intent.intent_id)
            return "Synthetic generated message."

        async def sender(request):
            if not await request.authorize():
                return SendReceipt(request.intent_id, request.context.route, "rejected")
            sends.append(request.intent_id)
            return SendReceipt(request.intent_id, request.context.route, "confirmed",
                               "synthetic-receipt", 1, 1)

        service = BehaviorService(
            store, current=current, validate_identity=valid,
            validate_evidence=gateway.validate_evidence, model=model, sender=sender,
            history=history, clock=lambda: now[0],
            policy=lambda: BehaviorPolicy(
                autonomy_enabled=True, timezone="UTC", whitelist=frozenset({context.scope_key}),
                dnd=(0, 1),
            ),
        )
        try:
            before = await store.behavior_history(context, day)
            evaluation = await service.evaluate(context)
            result = await service.execute(context, intent_id=f"after-import-{restriction}")
            assert not sends and not calls and not evaluation.eligible, {
                "restriction": restriction, "history": before,
                "eligible": evaluation.eligible, "result": result.status,
                "model_calls": len(calls), "send_stub_calls": len(sends),
            }
            if proven:
                expected = {
                    "global_used": (6 if restriction == "global_quota"
                                    else 2 if restriction == "scope_quota" else 0),
                    "scope_used": 2 if restriction == "scope_quota" else 0,
                    "unanswered_count": 2 if restriction == "unanswered" else 0,
                }
                assert {key: before[key] for key in expected} == expected
                assert before["last_attempt_at"] is None, "Must not invent a native attempt"
                if restriction == "unanswered":
                    await store.commit_event(Event(
                        "after-import-human", "verification", "message", context, "human",
                        NOW, "after-import-human", actor_id=context.account_id,
                        body="Synthetic human reply after import.",
                    ), 0)
                else:
                    now[0] += 800 if restriction == "cooldown" else 86400
                released = await service.evaluate(context)
                assert released.eligible, {
                    "restriction": restriction, "after_release": released.reason_codes,
                }
                sent = await service.execute(context, intent_id=f"released-{restriction}")
                assert sent.status == "succeeded" and len(calls) == len(sends) == 1
            else:
                now[0] += 86400
                assert not (await service.evaluate(context)).eligible
                assert not sends and not calls
        finally:
            await service.close()
            await gateway.close()
            await store.close()

    asyncio.run(restart_and_execute())


def test_imported_bounded_window_does_not_keep_body_after_retention(sample, tmp_path):
    _, target, selection, context = sample
    selection = {
        **selection,
        "rows": [{"table": "msg_archive", "key": {"id": 2},
                  "context_id": context.account_key, "source_session_id": "old-session"}],
        "window": {"since": NOW - 100, "until": NOW},
    }
    import_cli(sample, tmp_path, selection)

    async def expire():
        store = SQLiteStore(target, clock=lambda: NOW + 8 * 86400)
        await store.open()
        try:
            await store.cleanup()
            assert await store.read_window(context) == []
        finally:
            await store.close()

    asyncio.run(expire())
    with sqlite3.connect(target) as db:
        retained = db.execute(
            "SELECT COUNT(*) FROM states WHERE kind='legacy_import' "
            "AND instr(value_json,?)>0", ("SYNTHETIC WINDOW",),
        ).fetchone()[0]
    db.close()
    assert retained == 0, "Selected short-term body survives 8-day cleanup in legacy_import"


def test_cli_rollback_preserves_new_event_and_requires_stopped_target(sample, tmp_path):
    _, target, selection, context = sample
    selection = {**selection, "rows": [selection["rows"][1]]}
    import_cli(sample, tmp_path, selection)

    async def new_activity():
        store = SQLiteStore(target, clock=lambda: NOW)
        await store.open()
        try:
            assert (await store.commit_event(Event(
                "new-runtime", "verification", "message", context, "human", NOW,
                "new-runtime", actor_id=context.account_id, body="New synthetic runtime record.",
            ), 0)).accepted
        finally:
            await store.close()

    asyncio.run(new_activity())
    consumers = tmp_path / "consumers.json"
    consumers.write_text(json.dumps({
        "format": 1, "consumers": {"BiliBot": {"current": "livingemotion", "restore": "congling"}},
    }), encoding="utf-8")
    before = hashlib.sha256(target.read_bytes()).hexdigest()
    result = cli("rollback-plan", "--target", target, "--target-stopped", "--consumers", consumers)
    assert result["steps"][0]["action"] == "stop_new_executor_and_consumers"
    assert result["destructive_operations"] == []
    assert result["preserved_counts"]["events"] == 1
    assert hashlib.sha256(target.read_bytes()).hexdigest() == before
    rejected = subprocess.run(
        [sys.executable, str(CLI), "rollback-plan", "--target", str(target),
         "--consumers", str(consumers)], capture_output=True, text=True, timeout=30,
    )
    assert rejected.returncode == 2
    assert json.loads(rejected.stderr)["reason_code"] == "target_must_be_stopped"
