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
    assert materialized.files == []
    assert materialized.math_sample_ids == []
    assert (tmp_path / "staging").is_dir()


def test_phase_selector_rejects_unknown_phase():
    assert sparkbench.parse_phases("math,logic") == ["math", "logic"]
    with pytest.raises(ValueError):
        sparkbench.parse_phases("math,nope")


def test_status_is_written_atomically(tmp_path):
    sparkbench.write_status(tmp_path, {"run_status": "PARTIAL", "phases": {"math": "failed"}})
    assert json.loads((tmp_path / "status.json").read_text())["run_status"] == "PARTIAL"


def test_real_materialization_stages_sampled_math_context_and_hidden_agent_inputs(tmp_path):
    root = Path(__file__).parents[1]
    materialized = sparkbench.materialize_dynamic_inputs(root, tmp_path, seed=14)
    assert len(materialized.math_sample_ids) == 30
    assert materialized.agent_variant in {"precedence", "shortcircuit", "closures"}
    for name in ("math_suite.json", "longctx_doc.txt", "longctx_suite.json", "agent_hidden_tests.py",
                 "agent_edge_probes.py", "agent_task.json"):
        assert (tmp_path / name).is_file()


def test_agent_phase_includes_the_judge_that_produces_score_artifact(tmp_path):
    commands = sparkbench.phase_command("agent", tmp_path, tmp_path, "label", "http://example/v1", "model")
    assert len(commands) == 2
    assert commands[-1][1].endswith("judge.py")
