"""Short implementation diagnostic, not the independent 10,000-event benchmark."""

import asyncio
import hashlib
import json
import math
import sqlite3
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent))

from astrbot_plugin_livingemotion.api import LivingEmotionAPI
from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import Context, Event
from astrbot_plugin_livingemotion.runtime.background import BackgroundRuntime
from astrbot_plugin_livingemotion.runtime.projector import Projector
from astrbot_plugin_livingemotion.storage import SQLiteStore


def forbid_external(event, args):
    if event in {"socket.connect", "socket.bind", "socket.getaddrinfo", "subprocess.Popen"}:
        raise RuntimeError("offline diagnostic forbids external access")


def percentiles(values):
    ordered = sorted(values)
    return {
        f"p{percentile}_ms": round(ordered[math.ceil(len(ordered) * percentile / 100) - 1], 3)
        for percentile in (50, 95, 99)
    } if ordered else {}


async def main():
    now = 1_800_000_001.0
    config = Config()
    contexts = [Context(
        "synthetic-bot", "synthetic-persona", "synthetic-adapter", "synthetic-platform",
        "group", f"scope-{index}", f"human-{index}",
    ) for index in range(50)]
    with tempfile.TemporaryDirectory(prefix="livingemotion-f6-") as directory:
        store = SQLiteStore(Path(directory) / "diagnostic.sqlite3", config=config, clock=lambda: now)
        await store.open()
        try:
            def seed(db):
                def insert():
                    db.executemany(
                        """INSERT INTO events(event_key,scope_key,generation,event_id,producer,
                           event_type,actor_role,account_id,occurred_at,received_at,metadata_json)
                           VALUES(?,?,0,?,'sql-fixture','fixture','human',?,?,?,'{}')""",
                        ((f"fixture-{index}", contexts[index % 50].scope_key, f"fixture-{index}",
                          contexts[index % 50].account_id, now, now)
                         for index in range(10000)),
                    )
                    db.execute(
                        "INSERT INTO event_keys SELECT event_key,scope_key,generation,received_at "
                        "FROM events"
                    )
                    db.execute(
                        "INSERT INTO body_window SELECT seq,scope_key,occurred_at,? FROM events",
                        ("s" * 256,),
                    )
                store._transaction(db, insert)
            await store._run(seed)
            api = LivingEmotionAPI(
                store, config, BackgroundRuntime(store, config),
                project_event=Projector(store, lambda: config),
            )

            def event(index, phase):
                context = contexts[index % 50]
                return Event(
                    f"{phase}-{index}", "short-diagnostic", "message", context,
                    "human", now, f"{phase}-{index}", actor_id=context.account_id,
                    body="s" * 256, signals=("sadness",),
                )

            for index in range(50):
                assert (await api.ingest_event(event(index, "warmup")))["status"] == "accepted"
            run_ms, prune_ms, transaction_ms, latencies, results = [], [], [], [], []
            original_run = store._run
            original_prune = store._prune_window
            original_transaction = store._transaction

            async def timed_run(operation):
                start = time.perf_counter()
                try:
                    return await original_run(operation)
                finally:
                    run_ms.append((time.perf_counter() - start) * 1000)

            def timed_prune(*args):
                start = time.perf_counter()
                try:
                    return original_prune(*args)
                finally:
                    prune_ms.append((time.perf_counter() - start) * 1000)

            def timed_transaction(*args):
                start = time.perf_counter()
                try:
                    return original_transaction(*args)
                finally:
                    transaction_ms.append((time.perf_counter() - start) * 1000)

            store._run = timed_run
            store._prune_window = timed_prune
            store._transaction = timed_transaction

            async def producer(worker):
                for index in range(worker, 400, 20):
                    start = time.perf_counter()
                    result = await api.ingest_event(event(index, "measured"))
                    latencies.append((time.perf_counter() - start) * 1000)
                    results.append(result)

            start = time.perf_counter()
            try:
                await asyncio.gather(*(producer(worker) for worker in range(20)))
            finally:
                elapsed = time.perf_counter() - start
                store._run = original_run
                store._prune_window = original_prune
                store._transaction = original_transaction

            def check(db):
                return {
                    "events": db.execute("SELECT count(*) FROM events").fetchone()[0],
                    "event_keys": db.execute("SELECT count(*) FROM event_keys").fetchone()[0],
                    "traces": dict(db.execute(
                        "SELECT kind,count(*) FROM event_traces GROUP BY kind",
                    )),
                    "versions": dict(db.execute(
                        "SELECT kind,sum(version) FROM states GROUP BY kind",
                    )),
                    "bodies": db.execute("SELECT count(*) FROM body_window").fetchone()[0],
                    "max_scope": db.execute(
                        "SELECT max(n) FROM (SELECT count(*) n FROM body_window GROUP BY scope_key)"
                    ).fetchone()[0],
                    "synchronous": db.execute("PRAGMA synchronous").fetchone()[0],
                    "journal_mode": db.execute("PRAGMA journal_mode").fetchone()[0],
                    "integrity": db.execute("PRAGMA integrity_check").fetchone()[0],
                }

            report = {
                "boundary": "SQL-seeded full body window; 50 API warmups, 400 API samples, "
                            "50 scopes, 20 workers; not independent acceptance",
                "python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
                "seconds": round(elapsed, 3),
                "statuses": dict(Counter(item["status"] for item in results)),
                "reasons": dict(Counter(item["reason_code"] for item in results)),
                "domain_applied": sum(item.get("domain_applied", False) for item in results),
                "api_latency": percentiles(latencies),
                "store_roundtrips": len(run_ms),
                "store_roundtrip": percentiles(run_ms),
                "prune": percentiles(prune_ms),
                "transaction": percentiles(transaction_ms),
                "prune_share": round(sum(prune_ms) / sum(transaction_ms), 4),
                "counts": await store._run(check),
                "sha256": {
                    str(path): hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                    for path in map(Path, ("storage/sqlite.py", "runtime/projector.py", "api.py"))
                },
            }
            print(json.dumps(report, indent=2, sort_keys=True))
            assert report["statuses"] == {"accepted": 400}, "rejections are not performance success"
            assert report["domain_applied"] == 400
            assert report["counts"] == {
                "events": 10450, "event_keys": 10450,
                "traces": {"emotion": 450, "relationship": 450},
                "versions": {"bot": 450, "night": 450, "observation": 450, "relationship": 450},
                "bodies": 10000, "max_scope": 200, "synchronous": 2, "journal_mode": "wal",
                "integrity": "ok",
            }
        finally:
            await store.close()


if __name__ == "__main__":
    sys.addaudithook(forbid_external)
    asyncio.run(main())
