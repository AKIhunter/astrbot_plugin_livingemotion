"""Run the original full-load methodology against both initialized v2 modes."""
# ruff: noqa: E402

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import runpy
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent))

from astrbot_plugin_livingemotion.api import LivingEmotionAPI
from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.runtime.background import BackgroundRuntime
from astrbot_plugin_livingemotion.runtime.projector import Projector
from astrbot_plugin_livingemotion.storage import SQLiteStore

BASE = runpy.run_path(str(ROOT / "tests/performance/bench_local_state.py"))
SOURCES = (
    "config.py", "contracts.py", "domain/emotion.py", "domain/relationship.py", "domain/night.py",
    "runtime/projector.py", "runtime/night.py",
    "runtime/state_scope.py", "storage/sqlite.py", "storage/schema.py", "storage/state_scope.py",
    "storage/night.py", "api.py",
)


def hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES}


async def run_mode(shared):
    with tempfile.TemporaryDirectory(prefix="livingemotion-p2-") as temporary:
        config = Config(night_policy_version=2, timezone="UTC", persona_shared_state=shared)
        store = SQLiteStore(Path(temporary) / "state.sqlite", config=config,
                            clock=lambda: BASE["NOW"])
        await store.open()
        try:
            instance = await store.get_instance_id()
            contexts = [BASE["context"](i, instance) for i in range(50)]
            for context in contexts:
                await store.initialize_state_mode(context, shared=shared)
            api = LivingEmotionAPI(
                store, config, BackgroundRuntime(store, config),
                project_event=Projector(store, lambda: config), instance_id=instance,
            )
            seeded = await BASE["measure_phase"](lambda: BASE["writes"](api, contexts, 0, 10000))
            before = await BASE["snapshot_counts"](store)
            measured = await BASE["measure_phase"](
                lambda: BASE["writes"](api, contexts, 10000, 10000))
            after = await BASE["snapshot_counts"](store)
            reads = await BASE["measure_phase"](lambda: BASE["reads"](api, contexts))
            integrity = await store._run(lambda db: db.execute("PRAGMA integrity_check").fetchone()[0])
            return {"mode": "shared" if shared else "scene", "seed": seeded,
                    "api_commit": measured, "api_read": reads, "before": before, "after": after,
                    "integrity": integrity}
        finally:
            await store.close()


async def main(output):
    before = hashes()
    modes = []
    for shared in (False, True):
        result = await run_mode(shared)
        modes.append(result)
        print(json.dumps({
            "mode": result["mode"],
            "commits": result["api_commit"]["successful_latency"],
            "reads": result["api_read"]["successful_latency"],
            "successes": result["api_commit"]["projection_successes"],
        }), flush=True)
    failures = []
    for mode in modes:
        prefix = mode["mode"]
        for phase in ("seed", "api_commit"):
            if mode[phase]["projection_successes"] != 10000:
                failures.append(prefix + ":" + phase + ":commit_count")
            if mode[phase]["state_write_successes"] != 40000:
                failures.append(prefix + ":" + phase + ":state_count")
        for phase in ("api_commit", "api_read"):
            if mode[phase]["unsuccessful_latency"]:
                failures.append(prefix + ":" + phase + ":unsuccessful_operations")
            for method, values in mode[phase]["successful_latency"].items():
                if values["p95_ms"] > 50:
                    failures.append(prefix + ":" + method + ":p95_exceeds_50ms")
        if mode["before"]["body_window"] != 10000 or mode["after"]["body_window"] != 10000:
            failures.append(prefix + ":body_capacity")
        if mode["after"]["max_scope_bodies"] != 200:
            failures.append(prefix + ":scope_capacity")
        if mode["after"]["events"] - mode["before"]["events"] != 10000:
            failures.append(prefix + ":event_durability")
        if mode["after"]["pragmas"]["synchronous"] != 2 or mode["integrity"] != "ok":
            failures.append(prefix + ":durability")
    after = hashes()
    if before != after:
        failures.append("source_changed_during_run")
    report = {
        "status": "FAIL" if failures else "PASS", "failures": failures, "modes": modes,
        "source_sha256_before": before, "source_sha256_after": after,
        "methodology": "Each mode: 10000 real API warmups; 10000 measured events with full "
                       "10000-row body window, 50 real scopes, 20 closed-loop tasks; "
                       "10000 API reads; nearest-rank p95 <=50ms; WAL/FULL unchanged. "
                       "No model, no sender, no network. Single local process, not production.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n")
    print(json.dumps({"status": report["status"], "failures": failures}))
    return int(bool(failures))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.addaudithook(BASE["no_network"])
    raise SystemExit(asyncio.run(main(args.output)))
