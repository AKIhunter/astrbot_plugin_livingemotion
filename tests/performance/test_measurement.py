import importlib.util
from pathlib import Path


def load_benchmark():
    spec = importlib.util.spec_from_file_location(
        "local_state_benchmark", Path(__file__).with_name("bench_local_state.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_percentiles_use_nearest_rank():
    benchmark = load_benchmark()
    stats = benchmark.distribution(list(range(1, 101)))
    assert stats == {"samples": 100, "p50_ms": 50, "p95_ms": 95,
                     "p99_ms": 99, "max_ms": 100}
    assert benchmark.distribution([])["p95_ms"] is None


def test_rejections_and_baselines_never_count_as_fast_successes():
    benchmark = load_benchmark()
    metrics = benchmark.Measurements()
    metrics.record("ingest_event", 1, {"status": "rejected", "reason_code": "version_conflict"})
    metrics.record("ingest_event", 2, {"status": "accepted", "domain_applied": False})
    metrics.record("get_bot_state", 1, {"status": "ok", "reason_code": "baseline", "version": 0})
    metrics.record("ingest_event", 70, {
        "status": "accepted", "reason_code": "committed", "domain_applied": True,
        "versions": {"bot:": 1},
    })
    report = metrics.report()
    assert report["successful_latency"]["ingest_event"]["p95_ms"] == 70
    assert report["successful_latency"]["ingest_event"]["samples"] == 1
    assert report["projection_successes"] == report["state_write_successes"] == 1
    assert report["unsuccessful_latency"]["ingest_event"]["samples"] == 2
