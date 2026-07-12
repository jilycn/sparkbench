import json

from sparkbench_leaderboard import build_leaderboard


def _v2(root, name, label, status, overall=80, suite="v2"):
    run = root / name
    run.mkdir()
    (run / "status.json").write_text(json.dumps({"run_status": status}))
    (run / "scores.json").write_text(json.dumps({"label": label, "scoring_version": 2, "suite_version": suite,
                                                   "overall": overall, "grade": "B", "axes": {"LOAD": {"score100": 80}}}))


def test_leaderboard_uses_latest_not_historical_best_and_lists_partial_legacy(tmp_path):
    _v2(tmp_path, "a_20260712-010000", "a", "COMPLETE", 99)
    _v2(tmp_path, "a_20260712-020000", "a", "COMPLETE", 70)
    _v2(tmp_path, "p_20260712-030000", "p", "PARTIAL")
    legacy = tmp_path / "old_20260711-000000"
    legacy.mkdir()
    (legacy / "scorecard.json").write_text(json.dumps({"label": "old", "composite": 88, "grade": "A-"}))
    text = build_leaderboard(tmp_path)
    assert "**70**" in text
    assert "99" in text  # historical best is informational only
    assert "Partial / per-axis" in text
    assert "Legacy (scoring v1)" in text
