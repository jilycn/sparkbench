#!/usr/bin/env python3
"""Profile-first, versioned SparkBench v2 report generator."""
from __future__ import annotations
import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent / "core"))

import argparse
import json
import re
from pathlib import Path

from sblib import write_json_atomic, write_text_atomic


WEIGHTS = {"TOOLS": 27, "AGENT": 22, "LOGIC": 10, "MATH": 8, "CONTEXT": 10, "LOAD": 13, "STABILITY": 10}
GRADE_ORDER = ["D", "C", "B", "B+", "A-", "A", "A+"]


def _median(values):
    values = sorted(values)
    middle = len(values) // 2
    return values[middle] if len(values) % 2 else round((values[middle - 1] + values[middle]) / 2, 1)


def _axis(score, raw, weight, breakdown=None):
    axis = {"raw": raw, "score100": round(score, 1), "weight": weight, "weighted": round(score * weight / 100, 1)}
    if breakdown:
        axis["breakdown"] = breakdown
    return axis


def _tool_score(path):
    if not path.exists():
        return None
    match = re.search(r"Score:\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", path.read_text(errors="replace"))
    return float(match.group(1)) / float(match.group(2)) * 100 if match else None


def _artifact(directory: Path, name: str, suffix: str) -> Path:
    """Prefer a suffixed sidecar such as score3.v221.json when one exists.

    This lets a rescore rebuild every derived field through the same code path
    that produced the original, instead of hand-patching a published report.
    Hand-patching is how a file ends up with a corrected score100 sitting next
    to a stale raw string, median, or grade.
    """
    if suffix:
        candidate = directory / f"{Path(name).stem}{suffix}.json"
        if candidate.exists():
            return candidate
    return directory / name


def _trial_axes(trial, suffix=""):
    values = {}
    tool = _tool_score(trial / "tools.log")
    if tool is not None: values["TOOLS"] = tool
    round2 = trial / "round2" / "score.json"
    if round2.exists():
        data = json.loads(round2.read_text())
        values["AGENT"] = sum(data.get(key, 0) for key in ("A1_hidden", "A2_probes", "A3_quality", "A4_efficiency")) / 70 * 100
    logic_score = _artifact(trial / "round2", "logic_score.json", suffix)
    if logic_score.exists():
        data = json.loads(logic_score.read_text())
        if "missing" not in data:
            values["LOGIC"] = data.get("score100")
    round3 = _artifact(trial / "round3", "score3.json", suffix)
    if round3.exists():
        data = json.loads(round3.read_text())
        detail = data.get("detail", {})
        if "C_math" in data and "missing" not in detail.get("math", {}):
            values["MATH"] = data["C_math"] / 30 * 100
        if "D_longctx" in data and "missing" not in detail.get("longctx", {}):
            values["CONTEXT"] = data["D_longctx"] / 30 * 100
    load = trial / "round3" / "load.json"
    if load.exists(): values["LOAD"] = json.loads(load.read_text()).get("score100")
    return {key: value for key, value in values.items() if value is not None}


def _grade(overall):
    return "A+" if overall >= 95 else "A" if overall >= 90 else "A-" if overall >= 85 else "B+" if overall >= 80 else "B" if overall >= 70 else "C" if overall >= 60 else "D"


def _cap(grade, cap):
    if cap and GRADE_ORDER.index(grade) > GRADE_ORDER.index(cap):
        return cap
    return grade


def build_report(run_dir: Path, artifact_suffix: str = ""):
    status = json.loads((run_dir / "status.json").read_text())
    manifest = json.loads((run_dir / "manifest.json").read_text())
    run_status = status["run_status"]
    if run_status == "INVALID":
        return {"label": run_dir.name, "scoring_version": manifest["scoring_version"], "suite_version": manifest["suite_version"],
                "run_status": "INVALID", "axes": {}, "present": [], "overall": None, "grade": None, "trials": None}
    trials = sorted(path for path in run_dir.glob("trial_*") if path.is_dir())
    per_trial = [_trial_axes(trial, artifact_suffix) for trial in trials]
    math_breakdowns = []
    for trial in trials:
        path = _artifact(trial / "round3", "score3.json", artifact_suffix)
        data = json.loads(path.read_text()) if path.exists() else {}
        math_breakdowns.append(data.get("math_breakdown", {}))
    math_breakdown = {}
    for difficulty in ("easy", "med", "hard"):
        entries = [value[difficulty] for value in math_breakdowns if difficulty in value]
        if len(entries) == len(trials) and entries:
            math_breakdown[difficulty] = {
                "correct": _median([entry["correct"] for entry in entries]),
                "total": entries[0]["total"],
                "score100": _median([entry["score100"] for entry in entries]),
            }
    axes = {}
    for name, weight in WEIGHTS.items():
        if name == "STABILITY": continue
        values = [trial[name] for trial in per_trial if name in trial]
        if len(values) == len(trials) and values:
            axes[name] = _axis(
                _median(values),
                f"{_median(values):.1f}/100",
                weight,
                math_breakdown if name == "MATH" else None,
            )
    stability = run_dir / "stability.json"
    if run_status == "COMPLETE" and stability.exists():
        value = json.loads(stability.read_text())
        axes["STABILITY"] = _axis(value["score100"], f"{value['score100']}/100", WEIGHTS["STABILITY"])
    phase_axes = {"tools": "TOOLS", "agent": "AGENT", "logic": "LOGIC", "math": "MATH",
                  "context": "CONTEXT", "load": "LOAD"}
    selected_axes = {phase_axes[phase] for phase in manifest.get("phases", phase_axes) if phase in phase_axes}
    axes = {name: axis for name, axis in axes.items() if name == "STABILITY" or name in selected_axes}
    # A shared judge may emit more than one score (agent/logic share round2),
    # but a partial run must never surface an unselected axis as a silent zero.
    per_trial = [{name: value for name, value in trial.items() if name in selected_axes} for trial in per_trial]
    present = list(axes)
    complete = run_status == "COMPLETE" and set(axes) == set(WEIGHTS)
    overall = round(sum(axis["weighted"] for axis in axes.values()), 1) if complete else None
    grade = _grade(overall) if overall is not None else None
    cap = json.loads(stability.read_text()).get("grade_cap") if stability.exists() else None
    if grade: grade = _cap(grade, cap)
    logic, math = axes.get("LOGIC"), axes.get("MATH")
    legacy_reason = None
    if logic and math:
        legacy_reason = {"raw": f"{logic['score100'] * .3 + math['score100'] * .3:.1f}/60", "score100": round((logic["score100"] * 10 + math["score100"] * 8) / 18, 1)}
    trial_block = None
    if trials:
        ranges = {key: round(max(values) - min(values), 1) for key in WEIGHTS if key != "STABILITY"
                  if (values := [trial[key] for trial in per_trial if key in trial])}
        fatal = bool(json.loads(stability.read_text()).get("fatal")) if stability.exists() else False
        repeatability = "unverified" if len(trials) == 1 else "preliminary" if len(trials) == 2 else \
            ("verified" if not fatal and len(ranges) == len(WEIGHTS) - 1 and max(ranges.values(), default=0) <= 5 else "unverified")
        trial_block = {"n": len(trials), "per_trial": per_trial,
                       "per_axis_median": {key: value["score100"] for key, value in axes.items() if key != "STABILITY"},
                       "per_axis_range": ranges, "repeatability": repeatability}
    skipped = [name for name in WEIGHTS if name not in axes]
    return {"label": manifest.get("label", run_dir.name), "scoring_version": manifest["scoring_version"],
            "suite_version": manifest["suite_version"], "run_status": run_status, "axes": axes, "present": present,
            "legacy_reason": legacy_reason, "trials": trial_block, "overall": overall, "grade": grade,
            "stability_cap": cap, "skipped": skipped}


def markdown(report):
    lines = [f"# SparkBench v2 profile — {report['label']}", "", f"Run status: **{report['run_status']}**", "",
             "| Axis | Score | Weight | Weighted |", "|---|---:|---:|---:|"]
    for name in WEIGHTS:
        if name in report["axes"]:
            axis = report["axes"][name]
            lines.append(f"| {name} | {axis['score100']:.1f} | {axis['weight']}% | {axis['weighted']:.1f} |")
        elif name == "STABILITY" and report["run_status"] == "PARTIAL":
            lines.append("| STABILITY | N/A (partial) | 10% | — |")
    if report["trials"]:
        lines += ["", f"Repeatability: {report['trials']['repeatability']} ({report['trials']['n']} trial(s)); medians and ranges in scores.json."]
    if report["overall"] is not None:
        lines += ["", f"**Grade (policy v2): {report['grade']} — {report['overall']}/100**"]
    else:
        lines += ["", "No overall/grade: run is partial or lacks required axes."]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    report = build_report(args.run_dir)
    if report["run_status"] == "INVALID":
        raise SystemExit("refusing to score INVALID run")
    write_json_atomic(args.run_dir / "scores.json", report)
    write_text_atomic(args.run_dir / "scorecard.md", markdown(report))


if __name__ == "__main__":
    main()
