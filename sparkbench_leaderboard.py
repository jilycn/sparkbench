#!/usr/bin/env python3
"""Validity-aware SparkBench v2 leaderboard; v1 artifacts are never rescored."""
from __future__ import annotations
import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent / "core"))

import argparse
import json
from pathlib import Path

from sblib import write_text_atomic

CURRENT_SUITE = "2.2"
IDENTITY_KEYS = (
    "seed",
    "math_sample_ids",
    "logic_sample_ids",
    "agent_variant",
    "context_variant",
    "tool_suite_hash",
)


def _load(path):
    return json.loads(path.read_text())


def _latest_per_label(items):
    latest = {}
    for directory, score in items:
        label = score["label"]
        if label not in latest or directory.name > latest[label][0].name:
            latest[label] = (directory, score)
    return latest


def _sample_identity(directory):
    path = directory / "manifest.json"
    if not path.exists():
        return ("missing-manifest", directory.name)
    manifest = _load(path)
    return tuple(json.dumps(manifest.get(key), sort_keys=True) for key in IDENTITY_KEYS)


def _official_cohort(items):
    cohorts = {}
    for item in items:
        cohorts.setdefault(_sample_identity(item[0]), []).append(item)
    if not cohorts:
        return [], []
    official_key = max(
        cohorts,
        key=lambda key: (
            len({score.get("label") for _, score in cohorts[key]}),
            len(cohorts[key]),
            max(directory.name for directory, _ in cohorts[key]),
        ),
    )
    official = cohorts.pop(official_key)
    exploratory = [item for cohort in cohorts.values() for item in cohort]
    return official, exploratory


def build_leaderboard(root: Path):
    complete, partial, archive_v21, legacy = [], [], [], []
    for directory in sorted(path for path in root.iterdir() if path.is_dir()):
        scores = directory / "scores.json"
        status = directory / "status.json"
        if scores.exists() and status.exists():
            score, state = _load(scores), _load(status)
            if score.get("scoring_version") == 2 and score.get("suite_version") == CURRENT_SUITE:
                (complete if state.get("run_status") == "COMPLETE" else partial).append((directory, score))
                continue
            if score.get("scoring_version") == 2 and score.get("suite_version") == "2.1":
                archive_v21.append((directory, score, state.get("run_status", "UNKNOWN")))
                continue
        old = directory / "scorecard.json"
        if old.exists():
            legacy.append((directory, _load(old)))
    comparable, exploratory = _official_cohort(complete)
    latest = _latest_per_label(comparable)
    best = {label: max((score.get("overall") or -1 for directory, score in comparable if score["label"] == label), default=None)
            for label in latest}
    ranked = sorted(latest.values(), key=lambda item: item[1].get("overall") or -1, reverse=True)
    lines = ["# SparkBench Leaderboard", "", "## Official suite 2.2 rankings", "",
             "Latest comparable COMPLETE suite 2.2 run per label. Historical best is informational only.", "",
             "| # | Recipe | Overall | Grade | Historical best | Run |", "|---|---|---:|---|---:|---|"]
    for index, (directory, score) in enumerate(ranked, 1):
        lines.append(f"| {index} | {score['label']} | **{score.get('overall')}** | {score.get('grade')} | {best[score['label']]} | {directory.name} |")
    lines += ["", "## Non-comparable v2.2 runs", "",
              "Different sampled suites are retained for inspection and never point-ranked.", ""]
    for directory, score in sorted(exploratory, key=lambda item: item[0].name):
        lines.append(f"- {score.get('label', directory.name)} — {score.get('overall', '—')} / {score.get('grade', '—')} ({directory.name})")
    lines += ["", "## Partial / per-axis", ""]
    for directory, score in sorted(partial, key=lambda item: item[0].name):
        present = ", ".join(score.get("present", [])) or "none"
        lines.append(f"- {score.get('label', directory.name)} — {present} ({directory.name})")
    lines += ["", "## Suite 2.1 archive", "",
              "Stored v2.1 results are reproduced as recorded; never rescored or ranked with suite 2.2.", "",
              "| Recipe | Overall | Grade | Status | Run |", "|---|---:|---|---|---|"]
    for directory, score, state in sorted(archive_v21, key=lambda item: item[0].name):
        lines.append(
            f"| {score.get('label', directory.name)} | {score.get('overall', '—')} | "
            f"{score.get('grade', '—')} | {state} | {directory.name} |"
        )
    lines += ["", "## Legacy (scoring v1)", "", "Preserved from v1 scorecards; never rescored or ranked with v2.", ""]
    for directory, score in sorted(legacy, key=lambda item: item[0].name):
        lines.append(f"- {score.get('label', directory.name)} — {score.get('composite', '—')} / {score.get('grade', '—')} ({directory.name})")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, nargs="?", default=Path("~/bench/sparkbench").expanduser())
    args = parser.parse_args()
    text = build_leaderboard(args.root)
    write_text_atomic(args.root / "LEADERBOARD.md", text)
    print(text, end="")


if __name__ == "__main__":
    main()
