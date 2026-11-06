"""Portable checks of evidence gate behavior, not replacement product assertions."""

import pytest

import host_environment
from run_evidence import Evidence, EXPECTED, LANES, PROVIDER, RUNTIME, WINDOW


def complete(path):
    evidence = Evidence()
    evidence.selected = [f"{path}::test_synthetic_{i}" for i in range(EXPECTED[path])]
    evidence.cases = {
        node: {"status": "passed", "measurements": {},
               "phases": {"setup": "passed", "call": "passed", "teardown": "passed"}}
        for node in evidence.selected
    }
    return evidence


def test_collection_reduction_is_not_pass():
    evidence = complete(RUNTIME)
    del evidence.cases[evidence.selected.pop()]
    assert "collection_count_mismatch:" + RUNTIME in evidence.integrity_failures((RUNTIME,))


def test_skipped_call_is_not_pass():
    evidence = complete(RUNTIME)
    row = evidence.cases[evidence.selected[0]]
    row["status"], row["phases"]["call"] = "skipped", "skipped"
    assert "not_all_phases_passed:" + evidence.selected[0] in evidence.integrity_failures((RUNTIME,))


def test_setup_failure_is_not_pass():
    evidence = complete(RUNTIME)
    evidence.cases[evidence.selected[0]]["phases"] = {"setup": "failed", "teardown": "passed"}
    assert "not_all_phases_passed:" + evidence.selected[0] in evidence.integrity_failures((RUNTIME,))


def test_unexecuted_selected_case_is_not_pass():
    evidence = complete(RUNTIME)
    del evidence.cases[evidence.selected[0]]
    assert "selected_tests_not_all_executed" in evidence.integrity_failures((RUNTIME,))


def test_deselection_is_counted_separately():
    evidence = complete(RUNTIME)
    node = evidence.selected.pop()
    evidence.deselected.append(node)
    del evidence.cases[node]
    assert evidence.integrity_failures((RUNTIME,)) == []
    assert len(evidence.selected) == 14 and len(evidence.deselected) == 1


@pytest.mark.parametrize("counts,accepted", (
    ([2, 2, 2], True), ([1, 2, 2], False), ([2, 2], False), ([2, 2, 3], False),
))
def test_f9_requires_three_scopes_with_two_physical_rows(counts, accepted):
    evidence = complete(WINDOW)
    node = evidence.selected.pop()
    row = evidence.cases.pop(node)
    node = WINDOW + "::test_lower_scope_limit_cleanup_prunes_inactive_scopes"
    evidence.selected.append(node)
    row["measurements"]["persisted_per_scope_counts"] = counts
    evidence.cases[node] = row
    failures = evidence.integrity_failures((WINDOW,))
    assert ("inactive_scope_physical_counts_not_2_2_2" not in failures) is accepted


def test_host_must_be_explicit_even_on_a_developer_machine(monkeypatch):
    monkeypatch.delenv("ASTRBOT_HOST_SOURCE", raising=False)
    with pytest.raises(RuntimeError, match="host_source_required"):
        host_environment.configure_host()


def test_invalid_explicit_host_fails(tmp_path):
    with pytest.raises(RuntimeError, match="invalid_host_source"):
        host_environment.configure_host(tmp_path)


def test_missing_dependency_metadata_is_explicit(monkeypatch):
    def missing(name):
        raise host_environment.PackageNotFoundError(name)

    monkeypatch.setattr(host_environment, "version", missing)
    assert host_environment.packages(("openai",)) == {"openai": None}


def test_provider_is_explicit_and_not_in_portable_lane():
    assert PROVIDER in LANES["all"] and PROVIDER in LANES["f8"]
    assert PROVIDER not in LANES["portable"]
