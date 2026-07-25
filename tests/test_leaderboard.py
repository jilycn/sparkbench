import json

from sparkbench_leaderboard import build_leaderboard


def _v2(root, name, label, status, overall=80, suite="2.2.1", identity="sample-a"):
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


def test_leaderboard_archives_superseded_suites_and_never_ranks_them(tmp_path):
    _v2(tmp_path, "new_20260712-010000", "new", "COMPLETE", 70)
    _v2(tmp_path, "old_20260712-020000", "old", "COMPLETE", 99, suite="2.1")
    text = build_leaderboard(tmp_path)
    official, archive = text.split("## Superseded-suite archive", 1)
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


def _rescore(run, *, overall, verified=True, skipped=None, suite="2.2.1"):
    """Attach a 2.2.1 rescore sidecar and record to an existing 2.2 run."""
    record = {"label": "r", "rescore": {"suite_version_to": "2.2.1"},
              "harness_verification": {"verified": verified}}
    if skipped:
        record["skipped"] = skipped
    (run / "rescore_v221.json").write_text(json.dumps(record))
    (run / "scores.v221.json").write_text(json.dumps(
        {"label": "r", "scoring_version": 2, "suite_version": suite, "overall": overall,
         "grade": "B", "axes": {"LOAD": {"score100": 80}}}))


def test_a_verified_rescore_is_ranked_instead_of_the_stale_original(tmp_path):
    # The published board and the leaderboard must not disagree about a run
    # that has been migrated.
    run = tmp_path / "r_20260712-010000"
    _v2(tmp_path, "r_20260712-010000", "r", "COMPLETE", 73.0, suite="2.2")
    _rescore(run, overall=77.4)
    text = build_leaderboard(tmp_path)
    official = text.split("## Non-comparable v2.2 runs", 1)[0]
    assert "77.4" in official
    assert "73.0" not in official


def test_a_refused_rescore_leaves_the_run_archived_rather_than_ranked(tmp_path):
    run = tmp_path / "r_20260712-010000"
    _v2(tmp_path, "r_20260712-010000", "r", "COMPLETE", 73.0, suite="2.2")
    _rescore(run, overall=77.4, skipped="run_status is 'PARTIAL', not COMPLETE")
    text = build_leaderboard(tmp_path)
    official, archive = text.split("## Superseded-suite archive", 1)
    assert "77.4" not in official
    assert "73.0" in archive


def test_an_unverified_harness_rescore_is_not_trusted(tmp_path):
    run = tmp_path / "r_20260712-010000"
    _v2(tmp_path, "r_20260712-010000", "r", "COMPLETE", 73.0, suite="2.2")
    _rescore(run, overall=77.4, verified=False)
    text = build_leaderboard(tmp_path)
    official, archive = text.split("## Superseded-suite archive", 1)
    assert "77.4" not in official
    assert "73.0" in archive
