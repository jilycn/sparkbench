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
    assert materialized.logic_sample_ids == []
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
    assert len(materialized.logic_sample_ids) == 8
    assert materialized.agent_variant.startswith("records:")
    for name in (
        "math_suite.json",
        "logic_suite.json",
        "longctx_doc.txt",
        "longctx_suite.json",
        "agent_tasks.json",
    ):
        assert (tmp_path / name).is_file()
    tasks = json.loads((tmp_path / "agent_tasks.json").read_text())
    for task in tasks:
        assert (tmp_path / task["tests_file"]).is_file()
        assert (tmp_path / task["probes_file"]).is_file()


def test_agent_phase_includes_the_judge_that_produces_score_artifact(tmp_path):
    commands = sparkbench.phase_command("agent", tmp_path, tmp_path, "label", "http://example/v1", "model")
    assert len(commands) == 2
    assert commands[-1][1].endswith("judge.py")


def test_logic_phase_uses_dedicated_score_artifact(tmp_path):
    commands = sparkbench.phase_command("logic", tmp_path, tmp_path, "label", "http://example/v1", "model")
    assert len(commands) == 2
    assert commands[-1][1].endswith("logic_judge.py")
    assert sparkbench.required_phase_artifact("logic", tmp_path).name == "logic_score.json"


def test_v22_generators_are_snapshot_provenance_and_static_suites_are_not():
    assert sparkbench.SUITE_VERSION == "2.2.1"
    assert "core/gen_agent_task.py" in sparkbench.HARNESS_FILES
    assert "core/gen_logic.py" in sparkbench.HARNESS_FILES
    assert "core/gen_math.py" in sparkbench.HARNESS_FILES
    assert "core/gen_longctx.py" in sparkbench.HARNESS_FILES
    assert "suites/logic_suite.json" not in sparkbench.HARNESS_FILES
    assert "suites/math_suite.json" not in sparkbench.HARNESS_FILES
    assert "suites/math_stress.json" not in sparkbench.HARNESS_FILES
    assert "suites/longctx_suite.json" not in sparkbench.HARNESS_FILES
    assert "suites/longctx_doc.txt" not in sparkbench.HARNESS_FILES
    assert "docs/SCORING.md" in sparkbench.HARNESS_FILES
    assert "core/think_probe.py" not in sparkbench.HARNESS_FILES


def test_development_smoke_agent_variant_can_never_be_complete():
    assert sparkbench.final_run_status(False, list(sparkbench.PHASES), "smoke") == "PARTIAL"
    assert sparkbench.final_run_status(False, list(sparkbench.PHASES), None) == "COMPLETE"


def test_tool_phase_passes_reproducible_sampling_without_changing_scenarios(tmp_path, monkeypatch):
    monkeypatch.setattr(sparkbench.shutil, "which", lambda name: f"/fake/{name}")
    command = sparkbench.phase_command(
        "tools",
        tmp_path,
        tmp_path,
        "label",
        "http://example/v1",
        "model",
        seed=314,
    )[0]
    expected = {
        "--temperature": "0.6",
        "--top-p": "0.95",
        "--top-k": "20",
        "--seed": "314",
        "--trials": "1",
        "--parallel": "1",
        "--timeout": "240",
        "--max-turns": "8",
        "--reference-date": "2026-03-20",
        "--error-rate": "0.0",
    }
    for flag, value in expected.items():
        assert command[command.index(flag) + 1] == value
    assert "--short" not in command
    assert "--scenarios" not in command


def test_tool_eval_provenance_records_version_and_content_hash(tmp_path, monkeypatch):
    package = tmp_path / "tool_eval_bench"
    (package / "evals").mkdir(parents=True)
    (package / "domain").mkdir()
    (package / "evals" / "scenarios.py").write_text("SCENARIOS = ['TC-01']\n")
    (package / "evals" / "helpers.py").write_text("def score(): return 1\n")
    (package / "domain" / "tools.py").write_text("TOOLS = ['weather']\n")
    metadata = {
        "version": "9.8.7",
        "package_root": str(package),
        "suite_files": [
            "domain/tools.py",
            "evals/helpers.py",
            "evals/scenarios.py",
        ],
        "scenario_count": 1,
    }
    monkeypatch.setattr(sparkbench, "_tool_eval_metadata", lambda _tool: metadata)
    first = sparkbench.tool_eval_provenance(tmp_path / "tool-eval-bench", seed=314)
    assert first["version"] == "9.8.7"
    assert first["scenario_count"] == 1
    assert len(first["suite_hash"]) == 64
    assert first["parameters"]["--seed"] == "314"
    (package / "evals" / "scenarios.py").write_text("SCENARIOS = ['TC-01', 'TC-02']\n")
    second = sparkbench.tool_eval_provenance(tmp_path / "tool-eval-bench", seed=314)
    assert second["suite_hash"] != first["suite_hash"]


def test_tool_provenance_end_check_is_fail_closed(monkeypatch):
    recorded = {
        "cmd": "/fake/tool-eval-bench",
        "version": "1.0",
        "suite_hash": "abc",
        "parameters": {"--seed": "7"},
    }
    monkeypatch.setattr(
        sparkbench,
        "tool_eval_provenance",
        lambda _tool, seed=None: {
            "version": "1.0",
            "suite_hash": "abc",
        },
    )
    assert sparkbench.verify_tool_eval_provenance(recorded)
    monkeypatch.setattr(
        sparkbench,
        "tool_eval_provenance",
        lambda _tool, seed=None: {
            "version": "1.0",
            "suite_hash": "changed",
        },
    )
    assert not sparkbench.verify_tool_eval_provenance(recorded)
