"""Event-sourced SparkBench v2 stability accounting."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from sblib import write_json_atomic


EVENTS = ("timeout", "truncated", "http_error")

# v2.1: penalties scale with event RATE (per 100 completions), not raw event
# count. A long AGENT phase issues hundreds of completions; a couple of
# max_tokens truncations or wall-clock timeouts in there is routine, not
# instability. The flat per-event penalties this replaces (-40/truncated,
# -20/timeout) zeroed almost every real run regardless of length.
RATE_WEIGHTS = {"truncated": 3.0, "timeout": 6.0, "http_error": 10.0}
RUNAWAY_RATE_PCT = 5.0
RESTART_PENALTY = 60
OOM_PENALTY = 10


def collect_events(run_dir: Path):
    counts = {event: 0 for event in EVENTS}
    total = 0
    for path in sorted(run_dir.glob("trial_*/events.jsonl")):
        for line in path.read_text().splitlines():
            try:
                status = json.loads(line).get("status")
            except json.JSONDecodeError:
                continue
            if status is None:
                continue
            total += 1
            if status in counts:
                counts[status] += 1
    counts["total"] = total
    return counts


def _dmesg_count():
    try:
        result = subprocess.run(["dmesg", "--color=never"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode:
        return None
    markers = ("NV_ERR_NO_MEMORY", "oom-kill", "Out of memory", "NVRM: Xid")
    return sum(any(marker in line for marker in markers) for line in result.stdout.splitlines())


def system_snapshot(container: str | None):
    restarts = 0
    oom = False
    container_requested = container is not None
    container_observed = False
    container_id = None
    if container:
        try:
            result = subprocess.run(["docker", "inspect", container], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                data = json.loads(result.stdout)[0]
                restarts = int(data.get("RestartCount", 0))
                oom = bool(data.get("State", {}).get("OOMKilled", False))
                container_id = data.get("Id")
                container_observed = True
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, IndexError):
            container_observed = False
    return {"restarts": restarts, "oom": oom, "dmesg_count": _dmesg_count(),
            "container_requested": container_requested,
            "container_observed": container_observed,
            "container_id": container_id}


def system_delta(before, after):
    requested = bool(before.get("container_requested", before.get("container_observed")))
    observed = bool(before.get("container_observed")) and bool(after.get("container_observed"))
    before_id, after_id = before.get("container_id"), after.get("container_id")
    recreated = bool(requested and before_id and after_id and before_id != after_id)
    return {"restarts": max(0, after["restarts"] - before["restarts"]),
            "oom": bool(after["oom"] and not before["oom"]),
            "dmesg": max(0, (after["dmesg_count"] or 0) - (before["dmesg_count"] or 0)),
            "container_observed": observed,
            "observability_lost": bool(requested and not observed),
            "recreated": recreated}


def assess_stability(events, system):
    # recreated: same-name container with a different id — its RestartCount reset,
    # so the restart counter alone would miss the death. observability_lost: a
    # container was requested but could not be inspected at both boundaries; an
    # unmonitored run must not pass as stable (fail closed).
    fatal = (system.get("restarts", 0) > 0 or system.get("oom", False)
             or system.get("dmesg", 0) > 0 or system.get("recreated", False)
             or system.get("observability_lost", False))
    total = max(1, events.get("total", 0))
    rates = {key: 100.0 * events.get(key, 0) / total for key in RATE_WEIGHTS}
    runaway = any(rate > RUNAWAY_RATE_PCT for rate in rates.values())
    penalty = sum(RATE_WEIGHTS[key] * rate for key, rate in rates.items())
    penalty += RESTART_PENALTY * system.get("restarts", 0) + OOM_PENALTY * int(system.get("oom", False))
    score = max(0, round(100 - penalty, 1))
    return {"score100": score, "grade_cap": "C" if fatal else ("A-" if runaway else None),
            "fatal": fatal, "runaway": runaway, "rates": {key: round(rate, 3) for key, rate in rates.items()}}


def write_stability(run_dir: Path, before, container: str | None):
    events = collect_events(run_dir)
    after = system_snapshot(container)
    system = system_delta(before, after)
    payload = {"events": events, "system": system, "before": before, "after": after, **assess_stability(events, system)}
    write_json_atomic(run_dir / "stability.json", payload)
    return payload
