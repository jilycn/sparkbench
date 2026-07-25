import hashlib
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
    official, exploratory = text.split("## Non-comparable suite 2.2.1 runs", 1)
    assert "| a |" in official and "| b |" in official
    assert "| x |" not in official
    assert "x" in exploratory


def _rescore(run, *, overall, verified=True, skipped=None, suite="2.2.1", files_checked=3):
    """Attach a rescore that the trust resolver should accept.

    Built to satisfy every check rather than the minimum, so a test that
    exercises refusal has to remove something specific. A helper that writes
    only the fields trust happens to read is how a fail-open resolver survives
    its own test suite.
    """
    axes = {name: {"score100": 80.0} for name in
            ("TOOLS", "AGENT", "LOGIC", "MATH", "CONTEXT", "LOAD", "STABILITY")}
    scores = {"label": "r", "scoring_version": 2, "suite_version": suite,
              "overall": overall, "grade": "B", "axes": axes}
    (run / "scores.v221.json").write_text(json.dumps(scores))
    digest = hashlib.sha256((run / "scores.v221.json").read_bytes()).hexdigest()
    record = {
        "label": "r",
        "rescore": {"suite_version_to": "2.2.1",
                    "judge_source_sha256": {"core/judgelib.py": "0" * 64}},
        "harness_verification": {"verified": verified, "files_checked": files_checked},
        "missing_transcripts": [],
        "source_run": {"scoring_version": 2, "run_status": "COMPLETE",
                       "axes_present": sorted(axes)},
        "axes": {name: {"published": 0.0, "rescored": 80.0}
                 for name in ("LOGIC", "MATH", "CONTEXT")},
        "overall": {"published": 73.0, "rescored": overall},
        "grade": {"published": "B", "rescored": "B"},
        "input_sha256": {"harness/logic_suite.json": "1" * 64},
        "rescored_artifact_sha256": {"scores.v221.json": digest},
    }
    if skipped:
        record["skipped"] = skipped
    (run / "rescore_v221.json").write_text(json.dumps(record))


def test_a_verified_rescore_is_ranked_instead_of_the_stale_original(tmp_path):
    # The published board and the leaderboard must not disagree about a run
    # that has been migrated.
    run = tmp_path / "r_20260712-010000"
    _v2(tmp_path, "r_20260712-010000", "r", "COMPLETE", 73.0, suite="2.2")
    _rescore(run, overall=77.4)
    text = build_leaderboard(tmp_path)
    official = text.split("## Non-comparable suite 2.2.1 runs", 1)[0]
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


def test_a_rescore_whose_sidecar_was_edited_after_the_fact_is_not_trusted(tmp_path):
    # The record hashes the sidecar it vouches for, so a later edit to the
    # sidecar invalidates the vouch rather than riding on it.
    run = tmp_path / "r_20260712-010000"
    _v2(tmp_path, "r_20260712-010000", "r", "COMPLETE", 73.0, suite="2.2")
    _rescore(run, overall=77.4)
    tampered = json.loads((run / "scores.v221.json").read_text())
    tampered["overall"] = 99.9
    (run / "scores.v221.json").write_text(json.dumps(tampered))

    text = build_leaderboard(tmp_path)
    official, archive = text.split("## Superseded-suite archive", 1)
    assert "99.9" not in official
    assert "73.0" in archive


def test_a_rescore_missing_a_transcript_is_not_trusted(tmp_path):
    run = tmp_path / "r_20260712-010000"
    _v2(tmp_path, "r_20260712-010000", "r", "COMPLETE", 73.0, suite="2.2")
    _rescore(run, overall=77.4)
    record = json.loads((run / "rescore_v221.json").read_text())
    record["missing_transcripts"] = ["trial_1/raw/logic-l1.txt"]
    (run / "rescore_v221.json").write_text(json.dumps(record))

    text = build_leaderboard(tmp_path)
    official, archive = text.split("## Superseded-suite archive", 1)
    assert "77.4" not in official
    assert "73.0" in archive


def test_the_board_names_which_rows_are_migrated(tmp_path):
    run = tmp_path / "r_20260712-010000"
    _v2(tmp_path, "r_20260712-010000", "r", "COMPLETE", 73.0, suite="2.2")
    _rescore(run, overall=77.4)
    _v2(tmp_path, "o_20260712-020000", "o", "COMPLETE", 81.0)

    official = build_leaderboard(tmp_path).split("## Non-comparable", 1)[0]
    rescored_row = next(line for line in official.splitlines() if "| r |" in line)
    original_row = next(line for line in official.splitlines() if "| o |" in line)
    assert "rescored" in rescored_row
    assert "original" in original_row
