"""Event-sourced SparkBench v2 stability accounting."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from sblib import write_json_atomic


EVENTS = ("timeout", "truncated", "http_error")


def collect_events(run_dir: Path):
    counts = {event: 0 for event in EVENTS}
    for path in sorted(run_dir.glob("trial_*/events.jsonl")):
        for line in path.read_text().splitlines():
            try:
                status = json.loads(line).get("status")
            except json.JSONDecodeError:
                continue
            if status in counts:
                counts[status] += 1
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
    container_observed = container is not None
    if container:
        try:
            result = subprocess.run(["docker", "inspect", container], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                data = json.loads(result.stdout)[0]
                restarts = int(data.get("RestartCount", 0))
                oom = bool(data.get("State", {}).get("OOMKilled", False))
            else:
                container_observed = False
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, IndexError):
            container_observed = False
    return {"restarts": restarts, "oom": oom, "dmesg_count": _dmesg_count(), "container_observed": container_observed}


def system_delta(before, after):
    return {"restarts": max(0, after["restarts"] - before["restarts"]),
            "oom": bool(after["oom"] and not before["oom"]),
            "dmesg": max(0, (after["dmesg_count"] or 0) - (before["dmesg_count"] or 0)),
            "container_observed": before["container_observed"] and after["container_observed"]}


def assess_stability(events, system):
    fatal = system.get("restarts", 0) > 0 or system.get("oom", False) or system.get("dmesg", 0) > 0
    runaway = events.get("truncated", 0) > 0
    score = max(0, 100 - 40 * events.get("truncated", 0) - 20 * events.get("timeout", 0)
                - 15 * events.get("http_error", 0) - 60 * system.get("restarts", 0) - 10 * int(system.get("oom", False)))
    return {"score100": score, "grade_cap": "C" if fatal else ("A-" if runaway else None),
            "fatal": fatal, "runaway": runaway}


def write_stability(run_dir: Path, before, container: str | None):
    events = collect_events(run_dir)
    after = system_snapshot(container)
    system = system_delta(before, after)
    payload = {"events": events, "system": system, "before": before, "after": after, **assess_stability(events, system)}
    write_json_atomic(run_dir / "stability.json", payload)
    return payload
