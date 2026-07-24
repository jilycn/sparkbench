#!/usr/bin/env python3
"""Strict snapshot-local judge for the three independent agent tasks."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from sandbox import deny_reason, run_pytest, run_script
from sblib import write_json_atomic


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def _efficiency_fraction(task):
    if not task.get("converged"):
        return 0.0
    turns = task.get("turns", 99)
    base = 1.0 if turns <= 2 else 0.8 if turns == 3 else 0.6 if turns == 4 else 0.4 if turns == 5 else 0.2
    penalties = (
        task.get("invalid_tool_calls", 0)
        + task.get("http_errors", 0)
        + task.get("timeouts", 0)
        + task.get("truncated_turns", 0)
    )
    return max(0.0, base - 0.2 * penalties)


def aggregate_scores(tasks):
    """Macro-average families so no single brittle task controls the axis."""
    hidden = [
        task["hidden_passed"] / task["hidden_total"]
        if task.get("hidden_total")
        else 0.0
        for task in tasks
    ]
    probes = [
        task["probes_passed"] / task["probes_total"]
        if task.get("probes_total")
        else 0.0
        for task in tasks
    ]
    score = {
        "A1_hidden": round(_mean(hidden) * 45, 1),
        "A2_probes": round(_mean(probes) * 15, 1),
        "A3_quality": round(_mean([float(task.get("policy_safe", False)) for task in tasks]) * 5, 1),
        "A4_efficiency": round(_mean([_efficiency_fraction(task) for task in tasks]) * 5, 1),
        "detail": {"tasks": tasks},
    }
    score["total"] = round(
        sum(score[key] for key in ("A1_hidden", "A2_probes", "A3_quality", "A4_efficiency")),
        1,
    )
    return score


def _passed(output, pattern):
    match = re.search(pattern, output)
    return int(match.group(1)) if match else 0


def score_task(run_dir: Path, task: dict, metric: dict) -> dict:
    candidate = run_dir / "candidates" / task["filename"]
    result = {
        "id": task["id"],
        "family": task["family"],
        "variant": task["variant"],
        "hidden_passed": 0,
        "hidden_total": task["hidden_count"],
        "probes_passed": 0,
        "probes_total": task["probe_count"],
        "policy_safe": False,
        "turns": metric.get("turns", 0),
        "converged": metric.get("converged", False),
        "invalid_tool_calls": metric.get("invalid_tool_calls", 0),
        "http_errors": metric.get("http_errors", 0),
        "timeouts": metric.get("timeouts", 0),
        "truncated_turns": metric.get("truncated_turns", 0),
        "sandbox": metric.get("sandbox"),
        "errors": [],
    }
    if not candidate.is_file():
        result["errors"].append("candidate missing")
        return result
    reason = deny_reason(candidate.read_text())
    result["policy_safe"] = reason is None
    if reason:
        # Never invoke either runner for an AST-denied candidate.
        result["errors"].append(f"preflight denied: {reason}")
        return result
    hidden, hidden_error, hidden_mode = run_pytest(
        candidate, Path.cwd() / task["tests_file"], timeout=180
    )
    if hidden:
        result["hidden_passed"] = _passed(
            hidden.stdout + hidden.stderr, r"(\d+) passed"
        )
    if hidden_error:
        result["errors"].append(hidden_error)
    probes, probe_error, probe_mode = run_script(
        candidate, Path.cwd() / task["probes_file"], timeout=180
    )
    if probes:
        result["probes_passed"] = _passed(
            probes.stdout + probes.stderr, rf"(\d+)/{task['probe_count']}"
        )
    if probe_error:
        result["errors"].append(probe_error)
    result["sandbox"] = hidden_mode or probe_mode or result["sandbox"]
    # Correctness is determined by the final judged candidate, not a stale
    # in-loop result.
    result["converged"] = result["hidden_passed"] >= result["hidden_total"]
    return result


def main() -> None:
    run_dir = Path(sys.argv[1])
    tasks = json.loads((Path.cwd() / "agent_tasks.json").read_text())
    metrics_path = run_dir / "metrics.json"
    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
    metric_by_id = {task["id"]: task for task in metrics.get("tasks", [])}
    judged = [
        score_task(run_dir, task, metric_by_id.get(task["id"], {})) for task in tasks
    ]
    write_json_atomic(run_dir / "score.json", aggregate_scores(judged))


if __name__ == "__main__":
    main()
