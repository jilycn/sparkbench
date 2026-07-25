import json
from pathlib import Path

import rescore_v221


def weighted_total(axes: dict) -> float:
    """The driver's arithmetic: round each weighted axis, then sum."""
    return round(sum(round(value * rescore_v221.WEIGHTS[name] / 100, 1)
                     for name, value in axes.items()), 1)


def build_run(root: Path, *, logic_body: str, published_logic: float = 0.0) -> Path:
    """Minimal 2.2 run archive: one trial, one item per rescored phase."""
    run = root / "fake-recipe_20260725-000000"
    trial = run / "trial_1"
    (run / "harness").mkdir(parents=True)
    (trial / "round2").mkdir(parents=True)
    (trial / "round3").mkdir(parents=True)
    (trial / "raw").mkdir(parents=True)

    (run / "harness" / "logic_suite.json").write_text(json.dumps(
        [{"id": "l1", "family": "assignment", "answer": {"A": 1}}]))
    (run / "harness" / "math_suite.json").write_text(json.dumps(
        [{"id": "m1", "difficulty": "easy", "answer": 4, "numeric": True}]))
    (run / "harness" / "longctx_suite.json").write_text(json.dumps(
        [{"id": "c1", "answer": "blue"}]))

    (trial / "raw" / "logic-l1.txt").write_text(logic_body)
    (trial / "raw" / "math-m1.txt").write_text('{"answer": 4}')
    (trial / "raw" / "ctx-c1.txt").write_text('{"answer": "blue"}')
    (trial / "round2" / "logic_answers.json").write_text(json.dumps({"l1": {"request_id": "logic-l1"}}))
    (trial / "round3" / "math_answers.json").write_text(json.dumps({"m1": {"request_id": "math-m1"}}))
    (trial / "round3" / "longctx_answers.json").write_text(json.dumps({"c1": {"request_id": "ctx-c1"}}))

    # Published artifacts as the 2.2 judge would have left them.
    (trial / "round2" / "logic_score.json").write_text(json.dumps(
        {"correct": 0, "total": 1, "score100": 0.0,
         "detail": {"l1": "wrong (got None, want {'A': 1})"}}))
    (trial / "round3" / "score3.json").write_text(json.dumps(
        {"C_math": 1, "D_longctx": 3, "detail": {"math": {"m1": "OK"}, "longctx": {"c1": "OK"}}}))
    axes = {"TOOLS": 100.0, "AGENT": 100.0, "LOGIC": published_logic, "MATH": 3.3,
            "CONTEXT": 10.0, "LOAD": 100.0, "STABILITY": 100.0}
    (run / "scores.json").write_text(json.dumps({
        "label": "fake-recipe", "suite_version": "2.2", "overall": weighted_total(axes),
        "axes": {name: {"raw": f"{value}/100", "score100": value,
                        "weight": rescore_v221.WEIGHTS[name],
                        "weighted": round(value * rescore_v221.WEIGHTS[name] / 100, 1)}
                 for name, value in axes.items()}}))
    (run / "scorecard.md").write_text("# fake\n")
    return run


def test_rescore_writes_sidecars_and_never_touches_the_originals(tmp_path):
    run = build_run(tmp_path, logic_body='{\n  "A": 1\n}')
    before = {path: path.read_bytes() for path in run.rglob("*") if path.is_file()}

    record = rescore_v221.rescore_run(run)

    assert record is not None
    for path, content in before.items():
        assert path.read_bytes() == content, f"{path} was modified"
    assert (run / "scores.v221.json").is_file()
    assert (run / "trial_1" / "round2" / "logic_score.v221.json").is_file()
    assert (run / "trial_1" / "round3" / "score3.v221.json").is_file()


def test_rescore_record_carries_the_evidence_a_reader_needs(tmp_path):
    run = build_run(tmp_path, logic_body='{\n  "A": 1\n}')

    record = rescore_v221.rescore_run(run)

    assert record["moved"] is True
    assert record["axes"]["LOGIC"] == {"published": 0.0, "rescored": 100.0}
    assert record["original_artifact_sha256"]["scores.json"]
    assert record["transcript_sha256"]["trial_1/raw/logic-l1.txt"]
    assert record["rescore"]["judge_commit"]
    assert "not hash sealed" in record["rescore"]["provenance_warning"]
    changed = [item for item in record["changed_items"] if item["id"] == "l1"]
    assert changed and changed[0]["was"].startswith("wrong (got None")
    assert changed[0]["now"] == "OK"
    assert changed[0]["kind"] == "score_change"
    assert record["change_counts"] == {"score_change": 1, "explanation_only": 0}


def test_a_run_whose_answers_were_already_compliant_does_not_move(tmp_path):
    run = build_run(tmp_path, logic_body='{"A": 1}', published_logic=100.0)
    (run / "trial_1" / "round2" / "logic_score.json").write_text(json.dumps(
        {"correct": 1, "total": 1, "score100": 100.0, "detail": {"l1": "OK"}}))

    record = rescore_v221.rescore_run(run)

    assert record["moved"] is False
    assert record["changed_items"] == []


def test_runs_from_other_suites_are_skipped(tmp_path):
    run = build_run(tmp_path, logic_body='{"A": 1}')
    scores = json.loads((run / "scores.json").read_text())
    scores["suite_version"] = "2.1"
    (run / "scores.json").write_text(json.dumps(scores))

    assert rescore_v221.rescore_run(run) is None
    assert not (run / "scores.v221.json").exists()
