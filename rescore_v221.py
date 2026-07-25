#!/usr/bin/env python3
"""Re-grade archived suite 2.2 runs with the 2.2.1 judge, into sidecars only.

The suite 2.2 judge accepted an answer object only when it fitted on the last
physical line, so compliant pretty-printed answers were scored wrong. The
repair is a parser change, not a question change, so archived runs can be
re-graded from their own preserved transcripts instead of being re-benched.

Published artifacts are never modified. Every rescored value lands in a
`.v221.json` sidecar beside the original, and each run gains a
`rescore_v221.json` provenance record carrying the original artifact hashes,
the hash of every transcript read, the judge commit, the per-item changes with
their reason, and the caveat below.

Provenance caveat, recorded in every output: run transcripts were not hash
sealed when they were written. The archives are operationally trusted, but
their immutability since the run cannot be established after the fact, so
these values are a derived rescore rather than a reproduction of the original
measurement.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from statistics import median

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "core"))

from judge3 import grade_suite  # noqa: E402
from logic_judge import grade_logic  # noqa: E402
from sblib import write_json_atomic, write_text_atomic  # noqa: E402

sys.path.insert(0, str(REPO))
from sparkbench_report import build_report, markdown  # noqa: E402

BENCH_ROOT = Path.home() / "bench" / "sparkbench"
SOURCE_SUITE = "2.2"
TARGET_SUITE = "2.2.1"
WEIGHTS = {"TOOLS": 27, "AGENT": 22, "LOGIC": 10, "MATH": 8, "CONTEXT": 10, "LOAD": 13, "STABILITY": 10}
RESCORED_AXES = ("LOGIC", "MATH", "CONTEXT")
SIDECAR_SUFFIX = ".v221"

#: Judge sources whose behaviour determines every rescored value. Hashed into
#: each record so a reader can tell which parser produced the numbers even if
#: the working tree has since moved on.
JUDGE_SOURCES = ("core/judgelib.py", "core/logic_judge.py", "core/judge3.py", "rescore_v221.py")

PROVENANCE_WARNING = (
    "Derived rescore. Transcripts were not hash sealed at run time, so their "
    "immutability since the original run cannot be cryptographically established. "
    "Values are comparable with other 2.2.1 rescores and with future 2.2.1 runs, "
    "not with the strict-graded 2.2 numbers as originally published."
)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def judge_commit() -> str:
    """HEAD of the repo that supplied the repaired judge."""
    try:
        done = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True)
        return done.stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def worktree_clean() -> bool | None:
    """Whether the judge sources came from a committed tree. None if unknown."""
    try:
        done = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain"],
                              capture_output=True, text=True, check=True)
        return not done.stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return None


def judge_source_hashes() -> dict[str, str]:
    return {name: sha256_of(REPO / name) for name in JUDGE_SOURCES if (REPO / name).is_file()}


def harness_verification(run: Path, manifest: dict) -> dict:
    """Re-hash the frozen harness against the manifest recorded at run time.

    A rescore reads the run's own snapshotted suites. If that snapshot no longer
    matches what the run recorded, the questions being graded are not the
    questions that were asked, and the rescore is meaningless.
    """
    recorded = manifest.get("files", {})
    mismatched, missing = [], []
    for name, digest in recorded.items():
        path = run / "harness" / name
        if not path.is_file():
            missing.append(name)
        elif sha256_of(path) != digest:
            mismatched.append(name)
    return {"files_checked": len(recorded), "missing": sorted(missing),
            "mismatched": sorted(mismatched), "verified": not missing and not mismatched}


def ineligible_reason(run: Path, published: dict, manifest: dict, status: dict, harness: dict) -> str | None:
    """Why this run must not be rescored, or None when it may be.

    Fails closed. A rescore that silently accepts a partial or tampered run
    would publish a number nobody can stand behind.
    """
    if status.get("run_status") != "COMPLETE":
        return f"run_status is {status.get('run_status')!r}, not COMPLETE"
    if manifest.get("scoring_version") != 2:
        return f"scoring_version is {manifest.get('scoring_version')!r}, not 2"
    if manifest.get("suite_version") != SOURCE_SUITE:
        return f"suite_version is {manifest.get('suite_version')!r}, not {SOURCE_SUITE}"
    if published.get("overall") is None:
        return "published report has no overall score"
    absent = sorted(set(WEIGHTS) - set(published.get("axes", {})))
    if absent:
        return f"published report is missing axes: {', '.join(absent)}"
    if not harness["verified"]:
        return (f"frozen harness does not match the manifest "
                f"(missing {harness['missing']}, mismatched {harness['mismatched']})")
    return None


def transcript_hashes(trial: Path, answers_files: list[Path]) -> tuple[dict[str, str], list[str]]:
    """Hash every transcript the rescored phases read, and name the absent ones.

    Missing transcripts are listed explicitly rather than silently skipped: an
    item graded against a file that is not there is evidence of nothing.
    """
    hashes: dict[str, str] = {}
    missing: list[str] = []
    for answers_path in answers_files:
        if not answers_path.is_file():
            missing.append(f"{trial.name}/{answers_path.name} (answers file absent)")
            continue
        for item_id, record in json.loads(answers_path.read_text()).items():
            request_id = record.get("request_id")
            if not request_id:
                missing.append(f"{trial.name}/{item_id} (no request_id)")
                continue
            path = trial / "raw" / f"{request_id}.txt"
            if path.is_file():
                hashes[str(path.relative_to(trial.parent))] = sha256_of(path)
            else:
                missing.append(f"{trial.name}/raw/{request_id}.txt")
    return hashes, missing


def changed_items(old_detail: dict, new_detail: dict, trial_name: str, phase: str) -> list[dict]:
    """Per-item differences between the published and rescored judgements.

    Each change is tagged `score_change` or `explanation_only`. The repaired
    judge rewords every non-OK item to name its envelope, so most differences
    are wording. Without the tag, a run whose score did not move would appear
    to have been regraded from top to bottom.
    """
    changes = []
    for item_id, now in new_detail.items():
        was = old_detail.get(item_id)
        if was == now:
            continue
        kind = "score_change" if (was == "OK") != (now == "OK") else "explanation_only"
        changes.append({"trial": trial_name, "phase": phase, "id": item_id,
                        "kind": kind, "was": was, "now": now})
    return changes


def rescore_trial(run: Path, trial: Path) -> dict:
    """Re-grade one trial, returning its scores, details and compliance blocks."""
    suite = json.loads((run / "harness" / "logic_suite.json").read_text())
    logic = grade_logic(trial / "round2", suite)
    os.chdir(run / "harness")
    try:
        math = grade_suite(trial / "round3", "math_suite.json", "math_answers.json", 1)
        longctx = grade_suite(trial / "round3", "longctx_suite.json", "longctx_answers.json", 3)
    finally:
        os.chdir(REPO)
    return {
        "logic": logic,
        "math": math,
        "longctx": longctx,
        "axes": {
            "LOGIC": logic["score100"],
            "MATH": round(math.points / 30 * 100, 1),
            "CONTEXT": round(longctx.points / 30 * 100, 1),
        },
    }


def write_trial_sidecars(trial: Path, graded: dict, stamp: dict) -> dict[str, str]:
    """Write per-trial sidecars, returning the hashes of the originals they shadow."""
    originals: dict[str, str] = {}
    logic_original = trial / "round2" / "logic_score.json"
    if logic_original.is_file():
        originals[str(logic_original.relative_to(trial.parent))] = sha256_of(logic_original)
    write_json_atomic(trial / "round2" / "logic_score.v221.json", {**graded["logic"], "rescore": stamp})

    score3_original = trial / "round3" / "score3.json"
    if score3_original.is_file():
        originals[str(score3_original.relative_to(trial.parent))] = sha256_of(score3_original)
    math, longctx = graded["math"], graded["longctx"]
    write_json_atomic(trial / "round3" / "score3.v221.json", {
        "C_math": math.points,
        "D_longctx": longctx.points,
        "detail": {"math": math.detail, "longctx": longctx.detail},
        "flags": math.flags + longctx.flags,
        "math_breakdown": math.difficulty_counts,
        "format_compliance": {"math": math.compliance, "longctx": longctx.compliance},
        "rescore": stamp,
    })
    return originals


def published_detail(path: Path, key: str | None = None) -> dict:
    """Detail block from a published score artifact, empty when absent."""
    if not path.is_file():
        return {}
    data = json.loads(path.read_text())
    detail = data.get("detail", {})
    return detail.get(key, {}) if key else detail


def rescore_run(run: Path) -> dict | None:
    """Re-grade every trial of one run and write its sidecars and record.

    Returns None when the run is not a suite 2.2 archive, and a record with
    `skipped` set when it is one but fails an eligibility check.
    """
    scores_path = run / "scores.json"
    manifest_path = run / "manifest.json"
    status_path = run / "status.json"
    if not (scores_path.is_file() and manifest_path.is_file() and status_path.is_file()):
        return None
    published = json.loads(scores_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    status = json.loads(status_path.read_text())
    if manifest.get("suite_version") != SOURCE_SUITE:
        return None

    harness = harness_verification(run, manifest)
    stamp = {
        "suite_version_from": SOURCE_SUITE,
        "suite_version_to": TARGET_SUITE,
        "judge_commit": judge_commit(),
        "judge_worktree_clean": worktree_clean(),
        "judge_source_sha256": judge_source_hashes(),
        "parser": "judgelib.terminal_answer (raw_decode, line-start terminal object)",
        "rescored_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "provenance_warning": PROVENANCE_WARNING,
    }

    blocked = ineligible_reason(run, published, manifest, status, harness)
    if blocked:
        record = {"label": published.get("label", run.name), "run": run.name, "rescore": stamp,
                  "skipped": blocked, "harness_verification": harness}
        write_json_atomic(run / "rescore_v221.json", record)
        return record

    originals = {"scores.json": sha256_of(scores_path),
                 "manifest.json": sha256_of(manifest_path),
                 "status.json": sha256_of(status_path)}
    scorecard = run / "scorecard.md"
    if scorecard.is_file():
        originals["scorecard.md"] = sha256_of(scorecard)
    inputs = {f"harness/{path.name}": sha256_of(path) for path in sorted((run / "harness").glob("*_suite.json"))}

    transcripts: dict[str, str] = {}
    absent: list[str] = []
    changes: list[dict] = []
    for trial in sorted(run.glob("trial_*")):
        graded = rescore_trial(run, trial)
        originals.update(write_trial_sidecars(trial, graded, stamp))
        answers_files = [trial / "round2" / "logic_answers.json",
                         trial / "round3" / "math_answers.json",
                         trial / "round3" / "longctx_answers.json"]
        for answers_path in answers_files:
            if answers_path.is_file():
                inputs[str(answers_path.relative_to(run))] = sha256_of(answers_path)
        hashed, missing = transcript_hashes(trial, answers_files)
        transcripts.update(hashed)
        absent += missing
        changes += changed_items(published_detail(trial / "round2" / "logic_score.json"),
                                 graded["logic"]["detail"], trial.name, "LOGIC")
        changes += changed_items(published_detail(trial / "round3" / "score3.json", "math"),
                                 graded["math"].detail, trial.name, "MATH")
        changes += changed_items(published_detail(trial / "round3" / "score3.json", "longctx"),
                                 graded["longctx"].detail, trial.name, "CONTEXT")

    # Rebuild every derived field through the report builder rather than
    # patching the published one, so raw strings, medians, ranges, legacy
    # reason and grade cannot drift from the corrected scores.
    report = build_report(run, artifact_suffix=SIDECAR_SUFFIX)
    report["suite_version"] = TARGET_SUITE
    report["rescore"] = stamp
    write_json_atomic(run / "scores.v221.json", report)
    write_text_atomic(run / "scorecard.v221.md", markdown(report))

    axes = {name: value["score100"] for name, value in published["axes"].items()}
    rescored = {name: value["score100"] for name, value in report["axes"].items()}
    record = {
        "label": report["label"],
        "run": run.name,
        "rescore": stamp,
        "trials": report["trials"]["n"] if report["trials"] else 0,
        "axes": {axis: {"published": axes.get(axis), "rescored": rescored.get(axis)}
                 for axis in RESCORED_AXES},
        "overall": {"published": published["overall"], "rescored": report["overall"]},
        "grade": {"published": published.get("grade"), "rescored": report.get("grade")},
        "moved": abs((report["overall"] or 0) - published["overall"]) > 0.05,
        "change_counts": {
            "score_change": sum(1 for change in changes if change["kind"] == "score_change"),
            "explanation_only": sum(1 for change in changes if change["kind"] == "explanation_only"),
        },
        "changed_items": changes,
        "harness_verification": harness,
        "original_artifact_sha256": originals,
        "input_sha256": inputs,
        "transcript_sha256": transcripts,
        "missing_transcripts": absent,
    }
    write_json_atomic(run / "rescore_v221.json", record)
    return record


def main() -> int:
    records = []
    for run in sorted(path for path in BENCH_ROOT.iterdir() if path.is_dir()):
        record = rescore_run(run)
        if record:
            records.append(record)
    for record in records:
        if record.get("skipped"):
            print(f"SKIP  {record['label']:32s} {record['skipped']}")
            continue
        mark = "MOVED" if record["moved"] else "same "
        counts = record["change_counts"]
        print(f"{mark} {record['label']:32s} "
              f"{record['overall']['published']:5.1f} -> {record['overall']['rescored']:5.1f} "
              f"({counts['score_change']} regraded, {counts['explanation_only']} reworded)")
    print(f"\n{len(records)} run(s) rescored into sidecars. Originals untouched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
