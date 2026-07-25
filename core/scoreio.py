"""Which scored artifact a reader should trust for a run.

A suite 2.2.1 rescore lands beside the original as `scores.v221.json` and never
overwrites it, so every consumer needs one answer to "which file is current".
Answering it in each tool separately is how a leaderboard ends up ranking a
corrected run at its stale score while the published board shows the new one.

Trust is fail-closed. A sidecar is preferred only when its record proves the
rescore actually ran to completion on a verified archive: the record must
declare this suite, verify the frozen harness against a non-empty manifest,
report no missing transcripts, carry the input and judge hashes, and agree with
the sidecar it vouches for, including its hash. Anything less is ignored and
the original 2.2 artifact stands as recorded.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

CURRENT_SUITE = "2.2.1"

#: Earlier suites kept visible as recorded. A 2.2 row surviving here is one
#: whose 2.2.1 rescore was refused or failed verification.
SUPERSEDED_SUITES = ("2.1", "2.2")

RESCORE_SCORES = "scores.v221.json"
RESCORE_RECORD = "rescore_v221.json"
ORIGINAL_SCORES = "scores.json"

REQUIRED_AXES = ("TOOLS", "AGENT", "LOGIC", "MATH", "CONTEXT", "LOAD", "STABILITY")


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def rescore_is_trustworthy(run_dir: Path) -> tuple[bool, str]:
    """Whether this run's rescore may stand in for its published scores.

    Returns the reason on refusal so a caller can say why a run stayed on its
    archived value instead of silently presenting the old number.
    """
    record = _load(run_dir / RESCORE_RECORD)
    if record is None:
        return False, "no rescore record"
    if record.get("skipped"):
        return False, f"rescore refused: {record['skipped']}"

    stamp = record.get("rescore", {})
    if stamp.get("suite_version_to") != CURRENT_SUITE:
        return False, f"record targets suite {stamp.get('suite_version_to')!r}"
    if not stamp.get("judge_source_sha256"):
        return False, "record carries no judge source hashes"
    if not record.get("input_sha256"):
        return False, "record carries no input hashes"

    harness = record.get("harness_verification", {})
    if not harness.get("verified"):
        return False, "frozen harness did not verify at rescore time"
    if not harness.get("files_checked"):
        return False, "harness verification checked no files"
    if record.get("missing_transcripts"):
        return False, f"{len(record['missing_transcripts'])} transcript(s) were missing"

    source = record.get("source_run", {})
    if source.get("scoring_version") != 2:
        return False, f"source run declares scoring_version {source.get('scoring_version')!r}"
    if source.get("run_status") != "COMPLETE":
        return False, f"source run status is {source.get('run_status')!r}"
    absent = sorted(set(REQUIRED_AXES) - set(source.get("axes_present", [])))
    if absent:
        return False, f"source run is missing axes: {', '.join(absent)}"

    scores_path = run_dir / RESCORE_SCORES
    scores = _load(scores_path)
    if scores is None:
        return False, "rescore record present but scores sidecar is unreadable"
    recorded_hash = record.get("rescored_artifact_sha256", {}).get(RESCORE_SCORES)
    if not recorded_hash:
        return False, "record does not hash the sidecar it vouches for"
    if recorded_hash != _sha256(scores_path):
        return False, "sidecar does not match the hash recorded for it"

    if scores.get("suite_version") != CURRENT_SUITE:
        return False, f"sidecar declares suite {scores.get('suite_version')!r}"
    if scores.get("overall") is None:
        return False, "sidecar has no overall score"
    if scores.get("label") != record.get("label"):
        return False, "sidecar and record disagree about the label"
    if scores.get("overall") != record.get("overall", {}).get("rescored"):
        return False, "sidecar and record disagree about the overall score"
    if scores.get("grade") != record.get("grade", {}).get("rescored"):
        return False, "sidecar and record disagree about the grade"
    for axis, values in record.get("axes", {}).items():
        if scores.get("axes", {}).get(axis, {}).get("score100") != values.get("rescored"):
            return False, f"sidecar and record disagree about {axis}"
    return True, "ok"


def resolve_scores(run_dir: Path) -> tuple[dict, str] | None:
    """Return (scores, source) for a run, preferring a trustworthy rescore.

    `source` is the artifact filename, so callers can mark a row as rescored
    rather than presenting a migrated value as an original measurement.
    """
    trustworthy, _reason = rescore_is_trustworthy(run_dir)
    if trustworthy:
        scores = _load(run_dir / RESCORE_SCORES)
        if scores is not None:
            return scores, RESCORE_SCORES
    original = _load(run_dir / ORIGINAL_SCORES)
    if original is None:
        return None
    return original, ORIGINAL_SCORES


def is_current_suite(scores: dict) -> bool:
    """Whether these scores belong to the cohort the leaderboard ranks."""
    return scores.get("suite_version") == CURRENT_SUITE
