#!/usr/bin/env python3
"""Version- and sample-guarded SparkBench v2 comparison."""
from __future__ import annotations
import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent / "core"))

import argparse
import json
from pathlib import Path

from scoreio import resolve_scores


IDENTITY_KEYS = (
    "seed",
    "math_sample_ids",
    "logic_sample_ids",
    "agent_variant",
    "context_variant",
    "tool_suite_hash",
)


def latest_run(root: Path, label: str):
    candidates = []
    for manifest_path in root.glob("*/manifest.json"):
        resolved = resolve_scores(manifest_path.parent)
        if resolved and resolved[0].get("label") == label:
            candidates.append(manifest_path.parent)
    if not candidates:
        raise ValueError(f"no scored run for label {label!r}")
    return sorted(candidates, key=lambda path: path.name)[-1]


def _load(directory):
    """Scores a reader should trust for this run, plus its run-time manifest.

    Prefers a provenance-checked 2.2.1 rescore so a migrated run can be
    compared with future 2.2.1 runs instead of against its stale strict score.
    """
    resolved = resolve_scores(directory)
    if resolved is None:
        raise ValueError(f"no readable scores in {directory}")
    scores, source = resolved
    return {**scores, "artifact_source": source}, json.loads((directory / "manifest.json").read_text())


def compare_runs(root: Path, labels: list[str], axis: str | None = None, force=False):
    if len(labels) < 2:
        raise ValueError("at least two labels are required")
    loaded = {label: _load(latest_run(root, label)) for label in labels}
    scores = {label: value[0] for label, value in loaded.items()}
    manifests = {label: value[1] for label, value in loaded.items()}
    versions = {(score.get("scoring_version"), score.get("suite_version")) for score in scores.values()}
    version_mismatch = len(versions) != 1
    if version_mismatch and not force:
        raise ValueError("scoring_version or suite_version mismatch; use --force to inspect as NOT COMPARABLE")
    baseline = labels[0]
    sample_match = all(all(manifests[label].get(key) == manifests[baseline].get(key) for key in IDENTITY_KEYS)
                       for label in labels[1:])
    exploratory = not sample_match
    available = set().union(*(set(score.get("axes", {})) for score in scores.values()))
    axes = [axis] if axis else sorted(available)
    rows = {}
    for name in axes:
        values = {label: scores[label].get("axes", {}).get(name, {}).get("score100") for label in labels}
        deltas = {label: None if version_mismatch or exploratory or any(value is None for value in values.values())
                  else round(values[label] - values[baseline], 1) for label in labels[1:]}
        rows[name] = {"values": values, "delta": deltas.get(labels[1]), "deltas": deltas}
    return {"labels": labels, "runs": {label: str(latest_run(root, label)) for label in labels}, "rows": rows,
            "sources": {label: scores[label].get("artifact_source") for label in labels},
            "comparable": not version_mismatch and sample_match, "exploratory": exploratory,
            "not_comparable": version_mismatch, "forced": force}


def render(report):
    heading = "NOT COMPARABLE" if report["not_comparable"] else ("exploratory (different sampled suite)" if report["exploratory"] else "comparable")
    labels = report["labels"]
    delta_labels = [f"Δ {label}" for label in labels[1:]]
    migrated = [label for label, source in report.get("sources", {}).items()
                if (source or "").endswith(".v221.json")]
    lines = [f"# SparkBench comparison — {heading}", ""]
    if migrated:
        lines += [f"Rescored (migrated) values: {', '.join(migrated)}.", ""]
    lines += ["| Axis | " + " | ".join(labels + delta_labels) + " |",
             "|---|" + "---|" * (len(labels) + len(delta_labels))]
    for axis, row in report["rows"].items():
        values = ["missing" if row["values"][label] is None else f"{row['values'][label]:.1f}" for label in labels]
        deltas = ["—" if row["deltas"][label] is None else f"{row['deltas'][label]:+.1f}" for label in labels[1:]]
        lines.append("| " + axis + " | " + " | ".join(values + deltas) + " |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("labels", nargs="+")
    parser.add_argument("--axis")
    parser.add_argument("--bench-root", type=Path, default=Path("~/bench/sparkbench").expanduser())
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    report = compare_runs(args.bench_root, args.labels, args.axis, args.force)
    print(json.dumps(report, indent=2) if args.json else render(report), end="")


if __name__ == "__main__":
    main()
