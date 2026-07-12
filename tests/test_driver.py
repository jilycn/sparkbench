import json
from pathlib import Path

import pytest

import sparkbench


def test_snapshot_is_hashable_and_source_edits_do_not_change_it(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "suite.json").write_text('{"answer": 1}')
    (source / "runner.py").write_text("print('ok')")
    manifest = sparkbench.snapshot_harness(source, tmp_path / "run", ["suite.json", "runner.py"], seed=7)
    (source / "suite.json").write_text('{"answer": 2}')
    assert (tmp_path / "run" / "harness" / "suite.json").read_text() == '{"answer": 1}'
    assert sparkbench.verify_snapshot(tmp_path / "run" / "harness", manifest["files"])


def test_snapshot_hash_mismatch_is_detected(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "runner.py").write_text("print('ok')")
    manifest = sparkbench.snapshot_harness(source, tmp_path / "run", ["runner.py"], seed=7)
    copied = tmp_path / "run" / "harness" / "runner.py"
    copied.chmod(0o644)
    copied.write_text("changed")
    assert not sparkbench.verify_snapshot(tmp_path / "run" / "harness", manifest["files"])


def test_materialization_is_explicit_static_seam(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "math_suite.json").write_text("[]")
    materialized = sparkbench.materialize_dynamic_inputs(source, tmp_path / "staging", seed=11)
    assert materialized == []
    assert (tmp_path / "staging").is_dir()


def test_phase_selector_rejects_unknown_phase():
    assert sparkbench.parse_phases("math,logic") == ["math", "logic"]
    with pytest.raises(ValueError):
        sparkbench.parse_phases("math,nope")


def test_status_is_written_atomically(tmp_path):
    sparkbench.write_status(tmp_path, {"run_status": "PARTIAL", "phases": {"math": "failed"}})
    assert json.loads((tmp_path / "status.json").read_text())["run_status"] == "PARTIAL"
