"""Explicit, offline C51/C22 benchmark. Not collected by ordinary pytest."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time

PLUGIN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN.parent))

from astrbot_plugin_livingemotion.api import LivingEmotionAPI
from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import Context, Event
from astrbot_plugin_livingemotion.runtime.background import BackgroundRuntime
from astrbot_plugin_livingemotion.runtime.projector import Projector
from astrbot_plugin_livingemotion.storage import SQLiteStore

SOURCE_FILES = (
    "api.py", "config.py", "contracts.py", "runtime/projector.py",
    "runtime/background.py", "runtime/models.py", "storage/sqlite.py",
    "storage/schema.py", "domain/emotion.py", "domain/relationship.py",
    "domain/night.py", "docs/INTEGRATION.md",
)
NOW = 1_800_000_000.0


def no_network(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.bind"}:
        raise RuntimeError("offline_verification_network_forbidden")


def hashes():
    return {name: hashlib.sha256((PLUGIN / name).read_bytes()).hexdigest()
            for name in SOURCE_FILES}


def environment():
    def sysctl(key):
        try:
            return subprocess.check_output(
                ["sysctl", "-n", key], text=True, stderr=subprocess.DEVNULL,
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            return "unavailable"
    return {
        "os": platform.system(), "os_release": platform.release(),
        "macos": platform.mac_ver()[0], "architecture": platform.machine(),
        "cpu": sysctl("machdep.cpu.brand_string"), "logical_cpus": os.cpu_count(),
        "memory_bytes": sysctl("hw.memsize"), "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "sqlite": sqlite3.sqlite_version,
        "synthetic_only": True, "network_forbidden": True,
    }


def distribution(values):
    ordered = sorted(values)
    if not ordered:
        return {"samples": 0, "p50_ms": None, "p95_ms": None,
                "p99_ms": None, "max_ms": None}
    def percentile(q):
        return round(ordered[max(0, math.ceil(q * len(ordered)) - 1)], 6)
    return {"samples": len(ordered), "p50_ms": percentile(.50),
            "p95_ms": percentile(.95), "p99_ms": percentile(.99),
            "max_ms": round(ordered[-1], 6)}


class Measurements:
    def __init__(self):
        self.success = defaultdict(list)
        self.failure = defaultdict(list)
        self.statuses = Counter()
        self.projections = 0
        self.state_writes = 0

    def record(self, method, elapsed, result):
        status = result.get("status", "missing_status")
        reason = result.get("reason_code", "missing_reason")
        successful = (
            status == "accepted" and result.get("domain_applied") is True
            if method == "ingest_event"
            else status == "ok" and result.get("reason_code") == "snapshot"
            and result.get("version", 0) > 0
        )
        self.statuses[f"{method}:{status}:{reason}"] += 1
        (self.success if successful else self.failure)[method].append(elapsed)
        if method == "ingest_event" and successful:
            self.projections += 1
            self.state_writes += len(result.get("versions", {}))

    def report(self):
        return {"successful_latency": {k: distribution(v) for k, v in self.success.items()},
                "unsuccessful_latency": {k: distribution(v) for k, v in self.failure.items()},
                "statuses": dict(self.statuses),
                "projection_successes": self.projections,
                "state_write_successes": self.state_writes}


async def ticker(stop, samples):
    interval = .005
    while not stop.is_set():
        expected = asyncio.get_running_loop().time() + interval
        await asyncio.sleep(interval)
        samples.append(max(0, (asyncio.get_running_loop().time() - expected) * 1000))


async def measure_phase(work):
    stop, lag = asyncio.Event(), []
    tick = asyncio.create_task(ticker(stop, lag))
    await asyncio.sleep(0)
    start, cpu = time.perf_counter(), time.process_time()
    try:
        report = await work()
    finally:
        elapsed = time.perf_counter() - start
        cpu_elapsed = time.process_time() - cpu
        stop.set()
        await tick
    report.update(wall_seconds=elapsed, process_cpu_seconds=cpu_elapsed,
                  event_loop_lag=distribution(lag), lag_probe_interval_ms=5)
    return report


def context(number, instance):
    return Context("synthetic-bot", "synthetic-persona", "synthetic-adapter",
                   "offline", "private", f"scene-{number}", f"human-{number}",
                   audience=("synthetic-bot", f"human-{number}"), instance_id=instance)


def event(number, scope):
    return Event(
        f"event-{number}", "offline-benchmark", "message", scope, "human",
        NOW - 60 + number / 1000_000, f"source-{number}", actor_id=scope.account_id,
        body=(f"synthetic-{number:08d} " + "state verification " * 20)[:256],
        signals=("sadness",),
    )


async def snapshot_counts(store):
    # Inspection only; never creates seed data or substitutes for the API path.
    def inspect(db):
        result = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                  for table in ("events", "event_keys", "states", "event_traces", "body_window")}
        result["trace_counts"] = dict(db.execute(
            "SELECT kind,COUNT(*) FROM event_traces GROUP BY kind"))
        result["max_scope_bodies"] = db.execute(
            "SELECT COALESCE(MAX(n),0) FROM "
            "(SELECT COUNT(*) n FROM body_window GROUP BY scope_key)").fetchone()[0]
        result["body_chars"] = db.execute(
            "SELECT COALESCE(SUM(LENGTH(body)),0) FROM body_window").fetchone()[0]
        result["max_body_chars"] = db.execute(
            "SELECT COALESCE(MAX(LENGTH(body)),0) FROM body_window").fetchone()[0]
        result["state_versions"] = dict(db.execute(
            "SELECT kind,SUM(version) FROM states GROUP BY kind"))
        result["pragmas"] = {key: db.execute(f"PRAGMA {key}").fetchone()[0] for key in (
            "journal_mode", "synchronous", "busy_timeout", "page_size", "wal_autocheckpoint",
            "cache_size",
        )}
        result["database_bytes"] = db.execute(
            "PRAGMA page_count").fetchone()[0] * result["pragmas"]["page_size"]
        return result
    return await store._run(inspect)


async def writes(api, scopes, start, total, concurrency=20):
    metrics = Measurements()
    buckets = [[] for _ in range(concurrency)]
    # Each scene has one producer in the balanced case. The hot-key case below
    # intentionally puts all producers on the same scene, without client retries.
    for index in range(total):
        scope_index = index % len(scopes)
        buckets[scope_index % concurrency].append(event(start + index, scopes[scope_index]))
    if len(scopes) == 1:
        buckets = [buckets[0][i::concurrency] for i in range(concurrency)]
    gate = asyncio.Event()
    async def worker(items):
        await gate.wait()
        for item in items:
            begin = time.perf_counter()
            result = await api.ingest_event(item)
            metrics.record("ingest_event", (time.perf_counter() - begin) * 1000, result)
    tasks = [asyncio.create_task(worker(items)) for items in buckets]
    gate.set()
    await asyncio.gather(*tasks)
    return metrics.report()


async def reads(api, scopes, total=10000):
    metrics = Measurements()
    methods = ("get_bot_state", "get_relationship", "get_observation")
    async def worker(worker_id):
        for index in range(worker_id, total, 20):
            method = methods[index % len(methods)]
            begin = time.perf_counter()
            result = await getattr(api, method)(scopes[index % len(scopes)])
            metrics.record(method, (time.perf_counter() - begin) * 1000, result)
    await asyncio.gather(*(worker(i) for i in range(20)))
    return metrics.report()


async def storage_reads(store, scopes):
    timings = defaultdict(list)
    successes = Counter()
    async def worker(worker_id):
        for index in range(worker_id, 1000, 20):
            scope = scopes[index % len(scopes)]
            begin = time.perf_counter()
            state = await store.get_state(scope, "bot")
            timings["get_state"].append((time.perf_counter() - begin) * 1000)
            successes["get_state"] += int(state is not None and state.version > 0)
            begin = time.perf_counter()
            window = await store.read_window(scope)
            timings["read_window"].append((time.perf_counter() - begin) * 1000)
            successes["read_window"] += int(len(window) == 200)
    await asyncio.gather(*(worker(i) for i in range(20)))
    return {"storage_only_latency": {k: distribution(v) for k, v in timings.items()},
            "successes": dict(successes)}


async def diagnostic(api, store, scopes):
    timings = defaultdict(list)
    original_run, original_prune = store._run, store._prune_window
    async def timed_run(operation):
        begin = time.perf_counter()
        def timed_operation(db):
            started = time.perf_counter()
            timings["lock_and_thread_wait"].append((started - begin) * 1000)
            try:
                return operation(db)
            finally:
                timings[f"sqlite_operation:{operation.__name__}"].append(
                    (time.perf_counter() - started) * 1000)
        return await original_run(timed_operation)
    def timed_prune(*args, **kwargs):
        begin = time.perf_counter()
        try:
            return original_prune(*args, **kwargs)
        finally:
            timings["window_prune_within_commit"].append(
                (time.perf_counter() - begin) * 1000)
    store._run, store._prune_window = timed_run, timed_prune
    try:
        measured = await measure_phase(lambda: writes(api, scopes, 20_000, 1000))
    finally:
        store._run, store._prune_window = original_run, original_prune
    measured["diagnostic_only_segments"] = {
        key: {**distribution(values), "total_ms": sum(values)}
        for key, values in timings.items()
    }
    def plan(db):
        return [row[3] for row in db.execute(
            "EXPLAIN QUERY PLAN DELETE FROM body_window WHERE seq NOT IN "
            "(SELECT seq FROM body_window ORDER BY seq DESC LIMIT ?)", (10000,))]
    measured["global_window_prune_query_plan"] = await store._run(plan)
    return measured


async def benchmark():
    source_before = hashes()
    evidence = {
        "schema": 1, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": environment(), "source_sha256_before": source_before,
        "methodology": {
            "boundary": "LivingEmotionAPI + real Projector + real SQLiteStore; no Application/host",
            "load": "closed-loop 20 tasks; balanced 50 scenes; one producer per scene",
            "seed_events": 10000, "measured_events": 10000, "measured_api_reads": 10000,
            "window_rows_at_measurement_start": 10000, "body_chars_each": 256,
            "percentile": "nearest rank; successful snapshots/commits only",
            "warmup": "10000 real API events, separately reported; no empty DB timing claim",
            "threshold_ms": 50, "model_calls": 0, "send_calls": 0,
            "limitations": "single process, single store, synthetic closed-loop; not production/HTTP",
        },
        "config": asdict(Config()), "failures": [],
    }
    with tempfile.TemporaryDirectory(prefix="livingemotion-perf-") as temporary:
        config = Config()
        store = SQLiteStore(Path(temporary) / "state.sqlite3", config=config, clock=lambda: NOW)
        await store.open()
        try:
            instance = await store.get_instance_id()
            scopes = [context(i, instance) for i in range(50)]
            api = LivingEmotionAPI(
                store, config, BackgroundRuntime(store, config),
                project_event=Projector(store, lambda: config), instance_id=instance,
            )
            evidence["seed"] = await measure_phase(lambda: writes(api, scopes, 0, 10000))
            evidence["before"] = await snapshot_counts(store)
            print("seed complete: 10000 API attempts", flush=True)
            evidence["api_commit"] = await measure_phase(
                lambda: writes(api, scopes, 10000, 10000))
            evidence["after_measured_commit"] = await snapshot_counts(store)
            print("measured commits complete: 10000 API attempts", flush=True)
            evidence["api_read"] = await measure_phase(lambda: reads(api, scopes))
            evidence["storage_only"] = await measure_phase(lambda: storage_reads(store, scopes))
            evidence["diagnostic"] = await diagnostic(api, store, scopes)
            evidence["hot_key"] = await measure_phase(
                lambda: writes(api, scopes[:1], 21000, 200))
            evidence["after_all"] = await snapshot_counts(store)
        finally:
            await store.close()
    failures = evidence["failures"]
    for phase in ("seed", "api_commit"):
        if evidence[phase]["projection_successes"] != 10000:
            failures.append(f"{phase}:expected_10000_successful_projections")
        if evidence[phase]["state_write_successes"] != 40000:
            failures.append(f"{phase}:expected_40000_state_writes")
    for phase in ("api_commit", "api_read"):
        data = evidence[phase]
        if data["unsuccessful_latency"]:
            failures.append(f"{phase}:unsuccessful_operations")
        for method, values in data["successful_latency"].items():
            if values["p95_ms"] > 50:
                failures.append(f"{phase}:{method}:p95_exceeds_50ms")
    if sum(v["samples"] for v in evidence["api_read"]["successful_latency"].values()) != 10000:
        failures.append("api_read:expected_10000_successful_snapshots")
    before, after = evidence["before"], evidence["after_measured_commit"]
    evidence["C22_capacity"] = {
        "status": "PASS" if before["body_window"] == after["body_window"] == 10000
        and before["max_scope_bodies"] == after["max_scope_bodies"] == 200 else "FAIL",
        "note": "capacity only; TTL/references/reconfiguration tested separately in tests/budgets",
    }
    if after["events"] - before["events"] != 10000:
        failures.append("durability:event_count_delta")
    for kind in ("emotion", "relationship"):
        if after["trace_counts"].get(kind, 0) - before["trace_counts"].get(kind, 0) != 10000:
            failures.append(f"durability:{kind}_trace_delta")
    evidence["source_sha256_after"] = hashes()
    evidence["source_changed_during_run"] = source_before != evidence["source_sha256_after"]
    if evidence["source_changed_during_run"]:
        failures.append("source_changed_during_run:recheck_relevant_paths")
    evidence["max_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    evidence["C51_status"] = "FAIL" if failures else "PASS"
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.addaudithook(no_network)
    result = asyncio.run(benchmark())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n")
    print(json.dumps({"C51": result["C51_status"], "failures": result["failures"],
                      "commit": result["api_commit"]["successful_latency"],
                      "reads": result["api_read"]["successful_latency"]}, indent=2))
    return int(result["C51_status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
