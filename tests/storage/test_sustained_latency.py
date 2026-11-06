"""F6 growth regressions and an explicit offline diagnostic, not C51 acceptance."""
# ruff: noqa: E402 -- the standalone diagnostic resolves its package before imports.

from __future__ import annotations

import asyncio
import cProfile
import hashlib
import json
import math
import pstats
import sys
import tempfile
import time
from collections import Counter, defaultdict
from dataclasses import fields, replace
from pathlib import Path
from types import MappingProxyType

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    sys.path.insert(0, str(ROOT.parent))

from astrbot_plugin_livingemotion.api import LivingEmotionAPI
from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.contracts import (
    Context, Event, StateWrite, canonical_json,
)
from astrbot_plugin_livingemotion.runtime.background import BackgroundRuntime
from astrbot_plugin_livingemotion.runtime.projector import Projector
from astrbot_plugin_livingemotion.storage import SQLiteStore

NOW = 1_800_000_000.0


def make_api(store):
    return LivingEmotionAPI(
        store, store.config, BackgroundRuntime(store, store.config),
        project_event=Projector(store, lambda: store.config),
    )


async def test_mature_projection_key_work_is_independent_of_history(
    le_store, le_event_factory, monkeypatch,
):
    original = Event.idempotency_key.fget
    calls = 0

    def counted(event):
        nonlocal calls
        calls += 1
        return original(event)

    monkeypatch.setattr(Event, "idempotency_key", property(counted))
    api = make_api(le_store)
    assert (await api.ingest_event(le_event_factory(0, signals=("sadness",))))["domain_applied"]
    cold_calls = calls
    for index in range(1, 200):
        assert (await api.ingest_event(
            le_event_factory(index, signals=("sadness",))
        ))["domain_applied"]
    calls = 0
    result = await api.ingest_event(le_event_factory(200, signals=("sadness",)))
    assert result["domain_applied"] and len(result["versions"]) == 4
    # Guard capacity must not multiply hashing of the same immutable event.
    assert calls <= cold_calls + 4, (cold_calls, calls)


async def test_mature_projection_matches_contract_and_does_not_mutate_input(
    le_store, le_event_factory,
):
    class ReferenceEvent(Event):
        """The untouched contract path, without call-local key reuse."""

    le_store.config = Config(emotion_model_enabled=True)
    api, projector = make_api(le_store), Projector(le_store, lambda: le_store.config)
    for index in range(201):
        event = le_event_factory(index, signals=("sadness",))
        if index in (0, 191, 192, 200):
            original = dict(vars(event))
            reference = ReferenceEvent(**{field.name: getattr(event, field.name)
                                          for field in fields(Event)})
            assert await projector(event) == await projector(reference)
            assert vars(event) == original
        assert (await api.ingest_event(event))["domain_applied"]
    _, records = await le_store.read_projection(event.context)
    assert len(records["bot"].value["_runtime"]["seen"]) == 192
    assert len(records["relationship"].value["_runtime"]["seen"]) == 192
    assert len(records["night"].value["_runtime"]["interaction"]["seen"]) == 192
    assert all(record.version == 201 for record in records.values())
    assert (await api.ingest_event(event))["status"] == "duplicate"
    assert all(record.version == 201 for record in (
        await le_store.read_projection(event.context)
    )[1].values())


async def test_projection_key_tracks_source_and_scope(le_store, le_event):
    projector = Projector(le_store, Config)
    for event in (
        le_event, replace(le_event, source_id="another-source"),
        replace(le_event, context=replace(le_event.context, scene_id="another-scene")),
        replace(le_event, context=replace(le_event.context, account_id="another-human"),
                actor_id="another-human"),
    ):
        projection = await projector(event)
        assert {trace["event_key"] for trace in projection.traces} == {event.idempotency_key}
        assert projection.generation == 0


async def test_builtin_api_computes_event_key_once_per_request(
    le_store, le_event_factory, monkeypatch,
):
    original, calls = Event.idempotency_key.fget, []

    def counted(event):
        calls.append(event.source_id)
        return original(event)

    monkeypatch.setattr(Event, "idempotency_key", property(counted))
    api = make_api(le_store)
    for index in range(2):
        event = le_event_factory(index, signals=("sadness",))
        calls.clear()
        result = await api.ingest_event(event)
        assert result["domain_applied"] and len(result["versions"]) == 4
        assert calls == [event.source_id]
        assert "idempotency_key" not in vars(event)
        assert "scope_key" not in vars(event.context)


async def test_request_key_view_does_not_escape_to_host_or_custom_projector(
    le_store, le_event,
):
    class Application:
        config = le_store.config

        async def refresh_config(self):
            pass

        async def validate_context(self, context, generation):
            assert context is le_event.context and generation == 0
            return True

        async def remember_context(self, context):
            assert context is le_event.context

        def queue_refinement(self, event, result, projection):
            assert event is le_event and result.accepted

    api = make_api(le_store)
    api._application = Application()
    assert (await api.ingest_event(le_event))["domain_applied"]

    class CustomProjector(Projector):
        async def __call__(self, event):
            assert event is le_event
            return await super().__call__(event)

    api._project_event = CustomProjector(le_store, Config)
    assert (await api.ingest_event(le_event))["status"] == "duplicate"


async def test_request_key_view_preserves_event_subclass(le_store, le_event):
    class CustomEvent(Event):
        @property
        def idempotency_key(self):
            return "custom-key"

    event = CustomEvent(**{field.name: getattr(le_event, field.name) for field in fields(Event)})
    result = await make_api(le_store).ingest_event(event)
    assert result["domain_applied"] and result["event_key"] == "custom-key"
    assert (await make_api(le_store).ingest_event(event))["status"] == "duplicate"


async def test_projector_reuses_converted_snapshots_without_aliasing(
    le_store, le_event, monkeypatch,
):
    from astrbot_plugin_livingemotion.contracts import BotAffect, Relationship
    from astrbot_plugin_livingemotion.runtime import projector

    original, converted = projector.to_dict, []

    def counted(value):
        converted.append(type(value))
        return original(value)

    monkeypatch.setattr(projector, "to_dict", counted)
    result = await Projector(le_store, Config)(le_event)
    assert BotAffect not in converted and Relationship not in converted
    for kind, trace_kind in (("bot", "emotion"), ("relationship", "relationship")):
        write = next(write for write in result.writes if write.kind == kind)
        trace = next(trace for trace in result.traces if trace["kind"] == trace_kind)
        assert {key: value for key, value in write.value.items()
                if key != "_runtime"} == trace["after"]
        write.value["reason_codes"].append("write-only")
        assert "write-only" not in trace["after"]["reason_codes"]
        if write.value.get("evidence"):
            write.value["evidence"][0]["context"]["audience"].append("write-only")
            assert "write-only" not in trace["after"]["evidence"][0]["context"]["audience"]


def test_plain_scalar_leaves_do_not_need_conversion_copies():
    from astrbot_plugin_livingemotion.storage.sqlite import _state_data

    leaf = {"key": "source", "at": NOW, "amount": 0.0, "body_key": None}
    assert _state_data(leaf) is leaf
    assert _state_data({"seen": [leaf]})["seen"][0] is leaf
    assert _state_data({False: 1, None: 2}) == {"False": 1, "None": 2}


def test_state_encoding_is_byte_identical_to_contract(le_context):
    from enum import Enum

    from astrbot_plugin_livingemotion.storage.sqlite import _state_json

    class Label(Enum):
        VALUE = "value"

    class Text(str):
        pass

    class Key(str):
        def __str__(self):
            return "canonical-key"

    values = [
        None, True, 17, -0.0, "ascii and \u4e2d\u6587",
        {"mixed": (1, 2.5, False, None), "labels": [Label.VALUE, Text("hello")]},
        {False: "boolean-key", 2: "number-key", None: "none-key"},
        {1: "overwritten", "1": "canonical-last-value"},
        {Key("raw-key"): Text("custom-value")},
        {"booleans": [True, False, 0, 1], "zeros": [0.0, -0.0]},
        {"context": le_context, "nested": MappingProxyType({"tuple": (le_context, 1)})},
        {"_runtime": {"seen": [{"key": str(i), "at": NOW + i / 1_000_000}
                              for i in range(192)]}},
    ]
    for value in values:
        assert _state_json(value) == canonical_json(value)


def test_native_snapshot_conversion_matches_asdict_and_keeps_custom_fallback(le_event):
    from collections.abc import Mapping
    from dataclasses import asdict, is_dataclass
    from enum import Enum
    from astrbot_plugin_livingemotion.contracts import BotAffect, EvidenceRef, to_dict

    def original(value):
        if is_dataclass(value) and not isinstance(value, type):
            return original(asdict(value))
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, Mapping):
            return {str(key): original(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [original(item) for item in value]
        return value

    reference = EvidenceRef("synthetic", "source", le_event.context, "human", "bot",
                            "interaction", le_event.occurred_at)
    affect = BotAffect(evidence=(reference,))
    for value in (le_event, affect, reference, le_event.context):
        assert to_dict(value) == original(value)
    converted = to_dict(affect)
    converted["evidence"][0]["context"]["audience"].append("changed")
    assert "changed" not in le_event.context.audience

    class Custom:
        def __deepcopy__(self, memo):
            return "copied-custom-value"

    # Unusual legacy values retain the original deepcopy semantics.
    custom = replace(affect, labels=(Custom(),))
    assert to_dict(custom) == original(custom)


async def test_pure_projection_runs_off_loop_and_cancellation_drains(le_store, le_event):
    import threading
    import pytest

    entered, release = threading.Event(), threading.Event()
    projector = Projector(le_store, Config)
    original = projector._calculate
    worker_threads = []

    def blocked(*args):
        worker_threads.append(threading.current_thread())
        entered.set()
        assert release.wait(2)
        return original(*args)

    projector._calculate = blocked
    task = asyncio.create_task(projector(le_event))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        assert worker_threads[0] is not threading.current_thread()
        task.cancel()
        read = asyncio.create_task(le_store.read_projection(le_event.context))
        await asyncio.sleep(0)
        assert not task.done() and not read.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    generation, records = await read
    assert generation == 0 and all(record is None for record in records.values())


async def test_stored_state_uses_canonical_bytes_and_keeps_limits(le_store, le_context):
    import pytest

    value = {"context": le_context, "metadata": ({1: "integer-key"}, "\u96ea"),
             "_runtime": {"seen": [{"key": str(i), "at": NOW} for i in range(192)]}}
    result = await le_store.write_states(le_context, 0, (StateWrite("bot", value),))
    assert result.accepted
    payload = await le_store._run(lambda db: db.execute(
        "SELECT value_json FROM states WHERE kind='bot'"
    ).fetchone()[0])
    assert payload == canonical_json(value)
    for invalid in (float("nan"), float("inf"), -float("inf"), "s" * 65536):
        with pytest.raises(ValueError):
            await le_store.write_states(
                le_context, 0, (StateWrite("bot", {"bad": invalid}, 1),),
            )
        assert (await le_store.get_state(le_context, "bot")).version == 1


async def test_unresolved_history_keeps_native_fields(le_store, le_context, monkeypatch):
    def broken(*args):
        raise ValueError("synthetic invalid baseline")

    monkeypatch.setattr(le_store, "_legacy_baselines", broken)
    history = await le_store.behavior_history(le_context, "2027-01-15")
    assert history == {
        "global_used": 0, "scope_used": 0, "unanswered_count": 0,
        "last_attempt_at": None, "cooldown_until": None,
        "reason_codes": ("legacy_constraints_unresolved",),
    }


async def test_existing_scope_does_not_encode_ignored_context(
    le_store, le_event_factory, monkeypatch,
):
    from astrbot_plugin_livingemotion.storage import sqlite

    original, encoded_contexts = sqlite.canonical_json, []

    def counted(value):
        if isinstance(value, Context):
            encoded_contexts.append(value)
        return original(value)

    monkeypatch.setattr(sqlite, "canonical_json", counted)
    first = le_event_factory(0)
    assert (await le_store.commit_event(first, 0)).accepted
    assert len(encoded_contexts) == 1 and encoded_contexts[0].route is None
    encoded_contexts.clear()
    later = replace(le_event_factory(1), context=replace(first.context, route="new-route"))
    assert (await le_store.commit_event(later, 0)).accepted
    context_json = await le_store._run(lambda db: db.execute(
        "SELECT context_json FROM scopes WHERE scope_key=?", (first.context.scope_key,),
    ).fetchone()[0])
    assert context_json == original(replace(first.context, route=None))
    assert not encoded_contexts, "existing scope ignores context; do not re-encode it"


def distribution(values):
    ordered = sorted(values)
    return {
        "n": len(values),
        **{f"p{q}_ms": round(ordered[math.ceil(len(ordered) * q / 100) - 1], 6)
           for q in (50, 95, 99)},
        "total_ms": round(sum(values), 6),
    } if values else {"n": 0}


def synthetic_event(index, contexts):
    context = contexts[index % len(contexts)]
    return Event(
        f"event-{index}", "offline-benchmark", "message", context, "human",
        NOW - 60 + index / 1_000_000, f"source-{index}", actor_id=context.account_id,
        body=(f"synthetic-{index:08d} " + "state verification " * 20)[:256],
        signals=("sadness",),
    )


async def run_batch(api, contexts, start, total):
    buckets = [[] for _ in range(20)]
    for index in range(start, start + total):
        buckets[index % len(contexts) % 20].append(synthetic_event(index, contexts))
    latency, statuses = [], Counter()
    applied = state_writes = 0

    async def worker(items):
        nonlocal applied, state_writes
        for event in items:
            begin = time.perf_counter()
            result = await api.ingest_event(event)
            latency.append((time.perf_counter() - begin) * 1000)
            statuses[result["status"] + ":" + result["reason_code"]] += 1
            applied += bool(result.get("domain_applied"))
            state_writes += len(result.get("versions", {}))

    start_wall, start_cpu = time.perf_counter(), time.process_time()
    await asyncio.gather(*(worker(items) for items in buckets))
    result = {
        "latency": distribution(latency), "statuses": dict(statuses),
        "domain_applied": applied, "state_writes": state_writes,
        "wall_s": time.perf_counter() - start_wall,
        "cpu_s": time.process_time() - start_cpu,
    }
    assert statuses == {"accepted:committed": total}, result
    assert applied == total and state_writes == 4 * total, result
    return result


async def inspect(store):
    def read(db):
        sizes = defaultdict(list)
        guards = defaultdict(list)
        for row in db.execute("SELECT kind,value_json FROM states"):
            sizes[row["kind"]].append(len(row["value_json"]))
            runtime = json.loads(row["value_json"]).get("_runtime", {})
            if row["kind"] == "night":
                runtime = runtime.get("interaction", {})
            guards[row["kind"]].append(len(runtime.get("seen", ())))
        return {
            "counts": {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                       for table in ("events", "event_keys", "event_traces", "states",
                                     "body_window", "relationship_ledger")},
            "versions": dict(db.execute("SELECT kind,SUM(version) FROM states GROUP BY kind")),
            "state_chars": {kind: [min(v), max(v)] for kind, v in sizes.items()},
            "guard_lengths": {kind: [min(v), max(v)] for kind, v in guards.items()},
            "max_scope_bodies": db.execute(
                "SELECT MAX(n) FROM (SELECT COUNT(*) n FROM body_window GROUP BY scope_key)"
            ).fetchone()[0],
            "pragmas": {name: db.execute(f"PRAGMA {name}").fetchone()[0]
                        for name in ("journal_mode", "synchronous", "integrity_check")},
        }
    return await store._run(read)


async def measured_batch(api, contexts, start, total):
    store = api._store
    original_run, original_thread = store._run, store._thread
    original_prune = store._prune_window
    original_projection_lock = store.projection_lock
    metrics = defaultdict(list)
    scope_busy = Counter()

    class TimedConnection:
        def __init__(self, db):
            self.db = db

        def __getattr__(self, name):
            return getattr(self.db, name)

        def commit(self):
            begin, cpu = time.perf_counter(), time.thread_time()
            try:
                return self.db.commit()
            finally:
                metrics["durable_commit_wall"].append((time.perf_counter() - begin) * 1000)
                metrics["durable_commit_cpu"].append((time.thread_time() - cpu) * 1000)

    def projection_lock(context):
        lock = original_projection_lock(context)
        scope_busy[str(lock.busy)] += 1
        return lock

    async def timed_run(operation):
        begin = time.perf_counter()

        def timed(db):
            entered, cpu = time.perf_counter(), time.thread_time()
            metrics["lock_and_thread_wait"].append((entered - begin) * 1000)
            try:
                return operation(TimedConnection(db))
            finally:
                metrics["operation:" + operation.__name__].append(
                    (time.perf_counter() - entered) * 1000
                )
                metrics["operation_cpu:" + operation.__name__].append(
                    (time.thread_time() - cpu) * 1000
                )
        return await original_run(timed)

    async def timed_thread(operation):
        submitted = time.perf_counter()
        finished = None

        def timed():
            nonlocal finished
            metrics["thread_dispatch"].append((time.perf_counter() - submitted) * 1000)
            try:
                return operation()
            finally:
                finished = time.perf_counter()
        try:
            return await original_thread(timed)
        finally:
            if finished is not None:
                metrics["loop_resume"].append((time.perf_counter() - finished) * 1000)

    def timed_prune(*args):
        begin = time.perf_counter()
        try:
            return original_prune(*args)
        finally:
            metrics["prune"].append((time.perf_counter() - begin) * 1000)

    store._run, store._thread, store._prune_window = timed_run, timed_thread, timed_prune
    store.projection_lock = projection_lock
    try:
        result = await run_batch(api, contexts, start, total)
    finally:
        store._run, store._thread, store._prune_window = (
            original_run, original_thread, original_prune,
        )
        store.projection_lock = original_projection_lock
    result["segments"] = {name: distribution(values) for name, values in metrics.items()}
    result["scope_lock_busy"] = dict(scope_busy)
    return result


async def profile_batches(api, contexts, start):
    # Python 3.12 reserves one monitoring profiler ID process-wide.
    loop_profile, sql_profile = cProfile.Profile(), cProfile.Profile()
    try:
        loop_profile.enable()
        await run_batch(api, contexts, start, 40)
    finally:
        loop_profile.disable()
    original_run = api._store._run

    async def profiled_run(operation):
        return await original_run(lambda db: sql_profile.runcall(operation, db))

    api._store._run = profiled_run
    try:
        await run_batch(api, contexts, start + 40, 40)
    finally:
        api._store._run = original_run
    for label, profile in (("event_loop", loop_profile), ("storage_worker", sql_profile)):
        print(label, flush=True)
        stats = pstats.Stats(profile, stream=sys.stdout).strip_dirs()
        stats.sort_stats("cumulative").print_stats(35)
        stats.sort_stats("tottime").print_stats(25)
        stats.print_callers("to_dict|_state_data|finite|scope_key|account_key")


async def diagnostic():
    paths = ("storage/sqlite.py", "runtime/projector.py", "api.py")
    before = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in paths}
    with tempfile.TemporaryDirectory(prefix="livingemotion-f6-growth-") as directory:
        store = SQLiteStore(Path(directory) / "state.sqlite3", clock=lambda: NOW)
        await store.open()
        try:
            instance = await store.get_instance_id()
            contexts = [Context(
                "synthetic-bot", "synthetic-persona", "synthetic-adapter", "offline",
                "private", f"scene-{i}", f"human-{i}",
                audience=("synthetic-bot", f"human-{i}"), instance_id=instance,
            ) for i in range(50)]
            api = make_api(store)
            for label, start, count in (
                ("cold", 0, 400), ("growth", 400, 9600), ("mature", 10000, 400),
            ):
                report = await measured_batch(api, contexts, start, count)
                print(json.dumps({"phase": label, **report, "state": await inspect(store)},
                                 sort_keys=True), flush=True)
            # Separate intrusive profiles: never mix these timings into the distributions.
            await profile_batches(api, contexts, 10400)
            after = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                     for name in paths}
            assert before == after, "source changed during diagnostic"
            print(json.dumps({"sha256": after, "final": await inspect(store)}, sort_keys=True))
        finally:
            await store.close()


def forbid_external(event, args):
    if event in {"socket.connect", "socket.bind", "socket.getaddrinfo",
                 "socket.sendto", "subprocess.Popen"}:
        raise RuntimeError("offline diagnostic forbids external access")


if __name__ == "__main__":
    sys.addaudithook(forbid_external)
    asyncio.run(diagnostic())
