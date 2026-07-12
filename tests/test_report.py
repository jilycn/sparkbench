import json

from sparkbench_report import build_report


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def _complete_run(tmp_path):
    _write(tmp_path / "status.json", {"run_status": "COMPLETE"})
    _write(tmp_path / "manifest.json", {"scoring_version": 2, "suite_version": "v2"})
    _write(tmp_path / "stability.json", {"score100": 100, "grade_cap": None})
    trial = tmp_path / "trial_1"
    (trial / "tools.log").parent.mkdir(parents=True, exist_ok=True)
    (trial / "tools.log").write_text("Score: 90 / 100\n")
    _write(trial / "round2" / "score.json", {"A1_hidden": 45, "A2_probes": 15, "A3_quality": 5, "A4_efficiency": 5, "B_logic": 30})
    _write(trial / "round3" / "score3.json", {"C_math": 30, "D_longctx": 30})
    _write(trial / "round3" / "load.json", {"score100": 80, "p50_s": 2, "p95_s": 10, "p99_s": 12, "throughput_tok_s": 5})
    return tmp_path


def test_complete_profile_has_all_axes_weights_and_grade(tmp_path):
    report = build_report(_complete_run(tmp_path))
    assert report["overall"] == 94.7
    assert report["grade"] == "A"
    assert sum(axis["weight"] for axis in report["axes"].values()) == 100
    assert report["legacy_reason"]["score100"] == 100


def test_partial_has_axes_but_no_overall_or_stability(tmp_path):
    run = _complete_run(tmp_path)
    _write(run / "status.json", {"run_status": "PARTIAL"})
    report = build_report(run)
    assert report["overall"] is None
    assert report["grade"] is None
    assert "STABILITY" not in report["present"]


def test_load_only_fixture_omits_missing_math_and_context_from_present_axes(tmp_path):
    run = tmp_path
    _write(run / "status.json", {"run_status": "PARTIAL"})
    _write(run / "manifest.json", {"scoring_version": 2, "suite_version": "v2"})
    trial = run / "trial_1"
    _write(trial / "round3" / "score3.json", {"C_math": 0, "D_longctx": 0,
                                                   "detail": {"math": {"missing": "math_answers.json"},
                                                              "longctx": {"missing": "longctx_answers.json"}}})
    _write(trial / "round3" / "load.json", {"score100": 100})
    report = build_report(run)
    assert report["present"] == ["LOAD"]
    assert set(report["skipped"]) >= {"MATH", "CONTEXT"}


def test_fatal_cap_is_applied(tmp_path):
    run = _complete_run(tmp_path)
    _write(run / "stability.json", {"score100": 100, "grade_cap": "C"})
    assert build_report(run)["grade"] == "C"


def test_trials_require_three_clean_low_spread_runs_for_verified_repeatability(tmp_path):
    run = _complete_run(tmp_path)
    for number, load in ((2, 81), (3, 79)):
        trial = run / f"trial_{number}"
        (trial / "tools.log").parent.mkdir(parents=True)
        (trial / "tools.log").write_text("Score: 90 / 100\n")
        _write(trial / "round2" / "score.json", {"A1_hidden": 45, "A2_probes": 15, "A3_quality": 5, "A4_efficiency": 5, "B_logic": 30})
        _write(trial / "round3" / "score3.json", {"C_math": 30, "D_longctx": 30})
        _write(trial / "round3" / "load.json", {"score100": load})
    assert build_report(run)["trials"]["repeatability"] == "verified"
