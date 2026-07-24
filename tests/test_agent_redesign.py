import json

import agent_build_r2
import judge
from judge import aggregate_scores, score_task


def _task(task_id, *, passed=12, probes=4, safe=True, turns=2, converged=True):
    return {
        "id": task_id,
        "hidden_passed": passed,
        "hidden_total": 12,
        "probes_passed": probes,
        "probes_total": 4,
        "policy_safe": safe,
        "turns": turns,
        "converged": converged,
        "invalid_tool_calls": 0,
        "http_errors": 0,
        "truncated_turns": 0,
    }


def test_agent_score_uses_declared_counts_and_three_equal_units():
    score = aggregate_scores([_task("records"), _task("dependencies"), _task("ledger")])
    assert score["A1_hidden"] == 45.0
    assert score["A2_probes"] == 15.0
    assert score["A3_quality"] == 5.0
    assert score["A4_efficiency"] == 5.0
    assert score["total"] == 70.0


def test_one_bad_task_is_averaged_instead_of_zeroing_the_axis():
    score = aggregate_scores(
        [_task("records"), _task("dependencies", passed=0, probes=0, safe=False, converged=False), _task("ledger")]
    )
    assert score["A1_hidden"] == 30.0
    assert score["A2_probes"] == 10.0
    assert score["A3_quality"] == 3.3
    assert score["A4_efficiency"] == 3.3
    assert score["total"] == 46.6


def test_partial_hidden_passes_use_each_tasks_declared_denominator():
    score = aggregate_scores(
        [_task("records", passed=11), _task("dependencies"), _task("ledger")]
    )
    assert score["A1_hidden"] == 43.8


def test_agent_score_artifact_has_per_task_evidence(tmp_path):
    tasks = [_task("records"), _task("dependencies"), _task("ledger")]
    score = aggregate_scores(tasks)
    path = tmp_path / "score.json"
    path.write_text(json.dumps(score))
    restored = json.loads(path.read_text())
    assert [task["id"] for task in restored["detail"]["tasks"]] == [
        "records",
        "dependencies",
        "ledger",
    ]


def test_agent_pipeline_uses_independent_workspaces_and_retains_all_candidates(
    tmp_path, monkeypatch
):
    tasks = [
        {
            "id": family,
            "family": family,
            "variant": "v",
            "filename": f"{family}_solution.py",
            "hidden_count": 12,
        }
        for family in ("records", "dependencies", "ledger")
    ]
    tasks_path = tmp_path / "agent_tasks.json"
    tasks_path.write_text(json.dumps(tasks))
    work, out = tmp_path / "work", tmp_path / "out"
    seen = []

    def fake_run_task(_cfg, _harness, task_work, task):
        seen.append(task_work)
        task_work.mkdir(parents=True)
        (task_work / task["filename"]).write_text("value = 1\n")
        return {
            "id": task["id"],
            "passed": 12,
            "total": 12,
            "converged": True,
            "sandbox": "docker",
        }, [{"task": task["id"]}]

    monkeypatch.setattr(agent_build_r2, "run_task", fake_run_task)
    monkeypatch.setattr(agent_build_r2.Config, "from_env", lambda: object())
    monkeypatch.setattr(
        agent_build_r2.sys,
        "argv",
        ["agent_build_r2.py", "label", str(work), str(tasks_path), str(out)],
    )
    agent_build_r2.main()
    assert seen == [work / family for family in ("records", "dependencies", "ledger")]
    assert sorted(path.name for path in (out / "candidates").iterdir()) == [
        "dependencies_solution.py",
        "ledger_solution.py",
        "records_solution.py",
    ]
    metrics = json.loads((out / "metrics.json").read_text())
    assert metrics["hidden_total"] == 36
    assert metrics["converged_tasks"] == 3


def test_judge_never_executes_an_ast_denied_candidate(tmp_path, monkeypatch):
    run_dir = tmp_path / "round2"
    candidates = run_dir / "candidates"
    candidates.mkdir(parents=True)
    (candidates / "records_solution.py").write_text("import os\n")
    task = {
        "id": "records-v",
        "family": "records",
        "variant": "v",
        "filename": "records_solution.py",
        "tests_file": "agent_records_tests.py",
        "probes_file": "agent_records_probes.py",
        "hidden_count": 12,
        "probe_count": 4,
    }
    monkeypatch.setattr(
        judge,
        "run_pytest",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("denied candidate executed")
        ),
    )
    monkeypatch.setattr(
        judge,
        "run_script",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("denied candidate probed")
        ),
    )
    result = score_task(run_dir, task, {})
    assert result["policy_safe"] is False
    assert result["hidden_passed"] == 0
    assert result["probes_passed"] == 0
    assert result["errors"] == ["preflight denied: denied import"]
