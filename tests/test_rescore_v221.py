import hashlib
import json
from pathlib import Path

import rescore_v221

PHASES = ["tools", "agent", "logic", "math", "context", "load"]


def weighted_total(axes: dict) -> float:
    """The driver's arithmetic: round each weighted axis, then sum."""
    return round(sum(round(value * rescore_v221.WEIGHTS[name] / 100, 1)
                     for name, value in axes.items()), 1)


def build_run(root: Path, *, logic_body: str, published_logic: float = 0.0) -> Path:
    """A complete, eligible suite 2.2 archive with one item per rescored phase."""
    run = root / "fake-recipe_20260725-000000"
    trial = run / "trial_1"
    harness = run / "harness"
    harness.mkdir(parents=True)
    (trial / "round2").mkdir(parents=True)
    (trial / "round3").mkdir(parents=True)
    (trial / "raw").mkdir(parents=True)

    suites = {
        "logic_suite.json": [{"id": "l1", "family": "assignment", "answer": {"A": 1}}],
        "math_suite.json": [{"id": "m1", "difficulty": "easy", "answer": 4, "numeric": True}],
        "longctx_suite.json": [{"id": "c1", "answer": "blue"}],
    }
    for name, suite in suites.items():
        (harness / name).write_text(json.dumps(suite))

    (trial / "raw" / "logic-l1.txt").write_text(logic_body)
    (trial / "raw" / "math-m1.txt").write_text('{"answer": 4}')
    (trial / "raw" / "ctx-c1.txt").write_text('{"answer": "blue"}')
    (trial / "round2" / "logic_answers.json").write_text(json.dumps({"l1": {"request_id": "logic-l1"}}))
    (trial / "round3" / "math_answers.json").write_text(json.dumps({"m1": {"request_id": "math-m1"}}))
    (trial / "round3" / "longctx_answers.json").write_text(json.dumps({"c1": {"request_id": "ctx-c1"}}))

    # Non-rescored phase artifacts, so build_report can produce every axis.
    (trial / "tools.log").write_text("Score: 100 / 100\n")
    (trial / "round2" / "score.json").write_text(json.dumps({"A1_hidden": 70}))
    (trial / "round3" / "load.json").write_text(json.dumps({"score100": 100.0}))
    (run / "stability.json").write_text(json.dumps({"score100": 100.0, "grade_cap": None, "fatal": False}))

    # Published artifacts as the strict 2.2 judge would have left them.
    (trial / "round2" / "logic_score.json").write_text(json.dumps(
        {"correct": int(published_logic > 0), "total": 1, "score100": published_logic,
         "detail": {"l1": "OK" if published_logic else "wrong (got None, want {'A': 1})"}}))
    (trial / "round3" / "score3.json").write_text(json.dumps(
        {"C_math": 1, "D_longctx": 3, "detail": {"math": {"m1": "OK"}, "longctx": {"c1": "OK"}}}))

    axes = {"TOOLS": 100.0, "AGENT": 100.0, "LOGIC": published_logic, "MATH": 3.3,
            "CONTEXT": 10.0, "LOAD": 100.0, "STABILITY": 100.0}
    (run / "scores.json").write_text(json.dumps({
        "label": "fake-recipe", "scoring_version": 2, "suite_version": "2.2",
        "run_status": "COMPLETE", "overall": weighted_total(axes), "grade": "B",
        "axes": {name: {"raw": f"{value}/100", "score100": value,
                        "weight": rescore_v221.WEIGHTS[name],
                        "weighted": round(value * rescore_v221.WEIGHTS[name] / 100, 1)}
                 for name, value in axes.items()}}))
    (run / "scorecard.md").write_text("# fake\n")
    (run / "status.json").write_text(json.dumps({"run_status": "COMPLETE"}))
    (run / "manifest.json").write_text(json.dumps({
        "label": "fake-recipe", "scoring_version": 2, "suite_version": "2.2", "phases": PHASES,
        "files": {name: hashlib.sha256((harness / name).read_bytes()).hexdigest() for name in suites},
    }))
    return run


def test_rescore_writes_sidecars_and_never_touches_the_originals(tmp_path):
    run = build_run(tmp_path, logic_body='{\n  "A": 1\n}')
    before = {path: path.read_bytes() for path in run.rglob("*") if path.is_file()}

    record = rescore_v221.rescore_run(run)

    assert record is not None and not record.get("skipped")
    for path, content in before.items():
        assert path.read_bytes() == content, f"{path} was modified"
    assert (run / "scores.v221.json").is_file()
    assert (run / "scorecard.v221.md").is_file()
    assert (run / "trial_1" / "round2" / "logic_score.v221.json").is_file()
    assert (run / "trial_1" / "round3" / "score3.v221.json").is_file()


def test_the_rescored_report_is_internally_consistent(tmp_path):
    # A corrected score100 next to a stale raw string or median is how a
    # sidecar misleads someone reading it a month later.
    run = build_run(tmp_path, logic_body='{\n  "A": 1\n}')

    rescore_v221.rescore_run(run)

    report = json.loads((run / "scores.v221.json").read_text())
    logic = report["axes"]["LOGIC"]
    assert logic["score100"] == 100.0
    assert logic["raw"] == "100.0/100"
    assert logic["weighted"] == 10.0
    assert report["trials"]["per_axis_median"]["LOGIC"] == 100.0
    assert report["trials"]["per_trial"][0]["LOGIC"] == 100.0
    assert report["suite_version"] == "2.2.1"
    assert report["overall"] == round(sum(axis["weighted"] for axis in report["axes"].values()), 1)
    assert report["legacy_reason"]["score100"] == round((100.0 * 10 + 3.3 * 8) / 18, 1)


def test_rescore_record_carries_the_evidence_a_reader_needs(tmp_path):
    run = build_run(tmp_path, logic_body='{\n  "A": 1\n}')

    record = rescore_v221.rescore_run(run)

    assert record["moved"] is True
    assert record["axes"]["LOGIC"] == {"published": 0.0, "rescored": 100.0}
    assert record["original_artifact_sha256"]["scores.json"]
    assert record["original_artifact_sha256"]["manifest.json"]
    assert record["input_sha256"]["harness/logic_suite.json"]
    assert record["input_sha256"]["trial_1/round2/logic_answers.json"]
    assert record["transcript_sha256"]["trial_1/raw/logic-l1.txt"]
    assert record["missing_transcripts"] == []
    assert record["harness_verification"]["verified"] is True
    assert record["rescore"]["judge_source_sha256"]["core/judgelib.py"]
    assert "not hash sealed" in record["rescore"]["provenance_warning"]
    changed = [item for item in record["changed_items"] if item["id"] == "l1"]
    assert changed and changed[0]["was"].startswith("wrong (got None")
    assert changed[0]["now"] == "OK"
    assert changed[0]["kind"] == "score_change"
    assert record["change_counts"] == {"score_change": 1, "explanation_only": 0}


def test_a_run_whose_answers_were_already_compliant_does_not_move(tmp_path):
    run = build_run(tmp_path, logic_body='{"A": 1}', published_logic=100.0)

    record = rescore_v221.rescore_run(run)

    assert record["moved"] is False
    assert record["changed_items"] == []


def test_a_partial_run_is_refused_rather_than_rescored(tmp_path):
    run = build_run(tmp_path, logic_body='{\n  "A": 1\n}')
    (run / "status.json").write_text(json.dumps({"run_status": "PARTIAL"}))

    record = rescore_v221.rescore_run(run)

    assert "not COMPLETE" in record["skipped"]
    assert not (run / "scores.v221.json").exists()


def test_a_harness_that_no_longer_matches_its_manifest_is_refused(tmp_path):
    # The rescore grades against the run's own snapshotted questions. If those
    # have changed, the questions being graded are not the ones that were asked.
    run = build_run(tmp_path, logic_body='{\n  "A": 1\n}')
    (run / "harness" / "logic_suite.json").write_text(json.dumps(
        [{"id": "l1", "family": "assignment", "answer": {"A": 999}}]))

    record = rescore_v221.rescore_run(run)

    assert "frozen harness" in record["skipped"]
    assert not (run / "scores.v221.json").exists()


def test_runs_from_other_suites_are_skipped(tmp_path):
    run = build_run(tmp_path, logic_body='{"A": 1}')
    manifest = json.loads((run / "manifest.json").read_text())
    manifest["suite_version"] = "2.1"
    (run / "manifest.json").write_text(json.dumps(manifest))

    assert rescore_v221.rescore_run(run) is None
    assert not (run / "scores.v221.json").exists()
