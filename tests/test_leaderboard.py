import json

from sparkbench_leaderboard import build_leaderboard


def _v2(root, name, label, status, overall=80, suite="2.2", identity="sample-a"):
    run = root / name
    run.mkdir()
    (run / "status.json").write_text(json.dumps({"run_status": status}))
    (run / "scores.json").write_text(json.dumps({"label": label, "scoring_version": 2, "suite_version": suite,
                                                   "overall": overall, "grade": "B", "axes": {"LOAD": {"score100": 80}}}))
    (run / "manifest.json").write_text(json.dumps({
        "seed": 7,
        "math_sample_ids": [identity],
        "logic_sample_ids": [identity],
        "agent_variant": identity,
        "context_variant": identity,
        "tool_suite_hash": identity,
    }))


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


def test_leaderboard_archives_v21_and_never_ranks_it_with_v22(tmp_path):
    _v2(tmp_path, "new_20260712-010000", "new", "COMPLETE", 70, suite="2.2")
    _v2(tmp_path, "old_20260712-020000", "old", "COMPLETE", 99, suite="2.1")
    text = build_leaderboard(tmp_path)
    official, archive = text.split("## Suite 2.1 archive", 1)
    assert "new" in official
    assert "old" not in official
    assert "old" in archive
    assert "99" in archive


def test_leaderboard_does_not_rank_a_different_v22_sample_cohort(tmp_path):
    _v2(tmp_path, "a_20260712-010000", "a", "COMPLETE", 70, identity="common")
    _v2(tmp_path, "b_20260712-020000", "b", "COMPLETE", 80, identity="common")
    _v2(tmp_path, "x_20260712-030000", "x", "COMPLETE", 99, identity="different")
    text = build_leaderboard(tmp_path)
    official, exploratory = text.split("## Non-comparable v2.2 runs", 1)
    assert "| a |" in official and "| b |" in official
    assert "| x |" not in official
    assert "x" in exploratory
