"""Evidence integrity tests; no product behavior is replaced."""

import json
import subprocess
from types import SimpleNamespace

import pytest

from astrbot_plugin_livingemotion.tests.verification import check_source_overlap as overlap
from astrbot_plugin_livingemotion.tests.verification import run_checks as runner


@pytest.fixture
def evidence_runner(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "OUTPUT", tmp_path)
    monkeypatch.setattr(runner, "hashes", lambda: {"synthetic.py": "fixed"})
    monkeypatch.setattr(runner, "environment", lambda: {"synthetic": True})
    monkeypatch.setattr(runner.platform, "platform", lambda: "synthetic-platform")
    monkeypatch.setattr(runner.sys, "argv", ["run_checks.py", "probes", "--label", "unit"])
    return tmp_path


def test_runner_preserves_existing_label(evidence_runner, monkeypatch):
    record = evidence_runner / "unit.json"
    record.write_text('{"historical":true}', encoding="utf-8")

    def forbidden(*args, **kwargs):
        raise AssertionError("existing evidence must not execute again")

    monkeypatch.setattr(runner.subprocess, "run", forbidden)
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2
    assert record.read_text(encoding="utf-8") == '{"historical":true}'


def test_runner_timeout_still_records_partial_output(evidence_runner, monkeypatch):
    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 240, output=b"synthetic partial output")

    monkeypatch.setattr(runner.subprocess, "run", timeout)
    assert runner.main() == 124
    record = json.loads((evidence_runner / "unit.json").read_text())
    assert record["timed_out"] and record["exit_code"] == 124
    assert record["changed_during_run"] == [] and not record["junit"]["available"]
    assert "synthetic partial output" in (evidence_runner / "unit.log").read_text()


def test_runner_invalid_xml_cannot_look_successful(evidence_runner, monkeypatch):
    def complete(command, **kwargs):
        (evidence_runner / "unit.xml").write_text("<unfinished", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="synthetic output", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", complete)
    assert runner.main() == 125
    record = json.loads((evidence_runner / "unit.json").read_text())
    assert record["junit"] == {"available": False, "error": "invalid_junit_xml"}


def test_runner_collection_record_is_distinct(evidence_runner, monkeypatch):
    monkeypatch.setattr(
        runner.sys, "argv", ["run_checks.py", "probes", "--label", "unit", "--collect-only"],
    )

    def complete(command, **kwargs):
        assert "--collect-only" in command
        (evidence_runner / "unit.xml").write_text(
            '<testsuites><testsuite tests="0"/></testsuites>', encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="collected synthetic", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", complete)
    assert runner.main() == 0
    record = json.loads((evidence_runner / "unit.json").read_text())
    assert record["collect_only"] and record["junit"]["cases"] == []


def test_junit_outcomes_are_not_collapsed_to_pass(tmp_path):
    path = tmp_path / "report.xml"
    path.write_text(
        '<testsuites><testsuite tests="4">'
        '<testcase name="ok"/><testcase name="bad"><failure/></testcase>'
        '<testcase name="environment"><error/></testcase>'
        '<testcase name="unrun"><skipped/></testcase>'
        '</testsuite></testsuites>', encoding="utf-8",
    )
    assert [case["outcome"] for case in runner.junit_summary(path)["cases"]] == [
        "passed", "failure", "error", "skipped",
    ]


def test_delivery_manifest_rejects_paths_outside_root(tmp_path, monkeypatch):
    monkeypatch.setattr(overlap, "ROOT", tmp_path / "plugin")
    overlap.ROOT.mkdir()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"files": ["../manifest.json"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid_delivery_path"):
        overlap.delivery_files(manifest)


def test_overlap_signatures_do_not_include_literal_body(tmp_path):
    private = "SYNTHETIC_PRIVATE_MARKER " * 8
    path = tmp_path / "synthetic.py"
    path.write_text(f"VALUE = {private!r}\n", encoding="utf-8")
    result = overlap.signatures(path, tmp_path)
    assert len(result["long_literals"]) == 1
    assert "SYNTHETIC_PRIVATE_MARKER" not in json.dumps(result)


def test_delivery_candidate_keeps_only_reviewed_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(overlap, "ROOT", tmp_path)
    selected = ["main.py", "docs/verification-final.md", *overlap.REVIEWED_EVIDENCE]
    excluded = [
        ".venv-ci/private.py", ".ci-work/copy.py", "tests/__pycache__/test.pyc",
        "tests/verification/evidence/raw.json", "tests/host/final_evidence/raw.json",
        "tests/console/evidence-unreviewed.json", ".DS_Store",
    ]
    for name in selected + excluded:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic", encoding="utf-8")
    assert overlap.candidate_files() == sorted(selected)
