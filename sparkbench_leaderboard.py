#!/usr/bin/env python3
"""Validity-aware SparkBench v2 leaderboard; v1 artifacts are never rescored."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sblib import write_text_atomic


def _load(path):
    return json.loads(path.read_text())


def _latest_per_label(items):
    latest = {}
    for directory, score in items:
        label = score["label"]
        if label not in latest or directory.name > latest[label][0].name:
            latest[label] = (directory, score)
    return latest


def build_leaderboard(root: Path):
    complete, partial, legacy = [], [], []
    for directory in sorted(path for path in root.iterdir() if path.is_dir()):
        scores = directory / "scores.json"
        status = directory / "status.json"
        if scores.exists() and status.exists():
            score, state = _load(scores), _load(status)
            if score.get("scoring_version") == 2:
                (complete if state.get("run_status") == "COMPLETE" else partial).append((directory, score))
                continue
        old = directory / "scorecard.json"
        if old.exists():
            legacy.append((directory, _load(old)))
    latest = _latest_per_label(complete)
    best = {label: max((score.get("overall") or -1 for directory, score in complete if score["label"] == label), default=None)
            for label in latest}
    ranked = sorted(latest.values(), key=lambda item: item[1].get("overall") or -1, reverse=True)
    lines = ["# SparkBench Leaderboard", "", "## Official v2 rankings", "",
             "Latest comparable COMPLETE v2 run per label. Historical best is informational only.", "",
             "| # | Recipe | Overall | Grade | Historical best | Run |", "|---|---|---:|---|---:|---|"]
    for index, (directory, score) in enumerate(ranked, 1):
        lines.append(f"| {index} | {score['label']} | **{score.get('overall')}** | {score.get('grade')} | {best[score['label']]} | {directory.name} |")
    lines += ["", "## Partial / per-axis", ""]
    for directory, score in sorted(partial, key=lambda item: item[0].name):
        present = ", ".join(score.get("present", [])) or "none"
        lines.append(f"- {score.get('label', directory.name)} — {present} ({directory.name})")
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
