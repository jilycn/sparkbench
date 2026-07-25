"""Which scored artifact a reader should trust for a run.

A suite 2.2.1 rescore lands beside the original as `scores.v221.json` and never
overwrites it, so every consumer needs one answer to "which file is current".
Answering it in each tool separately is how a leaderboard ends up ranking a
corrected run at its stale score while the published board shows the new one.

A rescore is preferred only when it carries provenance that checks out. An
unverified or refused rescore is ignored rather than trusted, and the original
2.2 artifact remains readable as archive evidence in either case.
"""
from __future__ import annotations

import json
from pathlib import Path

CURRENT_SUITE = "2.2.1"

#: Earlier suites kept visible as recorded. A 2.2 row surviving here is one
#: whose 2.2.1 rescore was refused or failed verification.
SUPERSEDED_SUITES = ("2.1", "2.2")

RESCORE_SCORES = "scores.v221.json"
RESCORE_RECORD = "rescore_v221.json"
ORIGINAL_SCORES = "scores.json"


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def rescore_is_trustworthy(run_dir: Path) -> tuple[bool, str]:
    """Whether this run's rescore may stand in for its published scores."""
    record = _load(run_dir / RESCORE_RECORD)
    if record is None:
        return False, "no rescore record"
    if record.get("skipped"):
        return False, f"rescore refused: {record['skipped']}"
    if not record.get("harness_verification", {}).get("verified"):
        return False, "frozen harness did not verify at rescore time"
    scores = _load(run_dir / RESCORE_SCORES)
    if scores is None:
        return False, "rescore record present but scores sidecar is unreadable"
    if scores.get("suite_version") != CURRENT_SUITE:
        return False, f"rescore sidecar declares suite {scores.get('suite_version')!r}"
    if scores.get("overall") is None:
        return False, "rescore sidecar has no overall score"
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
