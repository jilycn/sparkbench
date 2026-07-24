#!/usr/bin/env python3
"""Rescore STABILITY for pre-v2.1 COMPLETE runs using the corrected rate-scaled formula.

Recomputes score100/grade_cap/fatal/runaway/rates from the same already-recorded event
counts plus a freshly-derived request total. Hardened per the 2026-07-23 Codex review:

- the original stability.json is preserved as stability.json.pre-v21 (never overwritten
  if it already exists — first backup wins);
- the rewritten stability.json carries a `rescore` metadata block (timestamp, formula
  source commit, sha256 of the original artifact);
- writes are atomic (tmp file + os.replace);
- dependent artifacts (scores.json / scorecard.md) are regenerated via
  sparkbench_report so a run directory is never left internally inconsistent.

Run manifests are never touched — recipe/config/harness provenance stays exactly as
recorded at run time. Published boards must mark rescored rows (see RESULTS.md note 5).
"""
import datetime
import hashlib
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, "core")
from stability import assess_stability

REPO = pathlib.Path(__file__).resolve().parent

RUNS = [
    "codernext_nvfp4_20260714-011702",
    "deepseek_v4_flash_iq3_20260714-020034",
    "m1_unsloth_std_v2b_20260713-234019",
    "m3_svc_fp8_nomtp_v2_20260713-082030",
    "q122b_dflash_20260712-220343",
    "q36_nvfp4_mlponly_20260715-201812",
    "q36_nvfp4_mtp_20260715-075915",
    "q3next_80b_20260712-231753",
]
root = pathlib.Path.home() / "bench" / "sparkbench"


def formula_commit():
    try:
        out = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return "unknown"


def atomic_write(path: pathlib.Path, text: str):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def regenerate_report(run_dir: pathlib.Path):
    subprocess.run([sys.executable, str(REPO / "sparkbench_report.py"), str(run_dir)],
                   check=True, capture_output=True, text=True)


commit = formula_commit()
for name in RUNS:
    d = root / name
    stability_path = d / "stability.json"
    original_text = stability_path.read_text()
    old = json.loads(original_text)

    backup = d / "stability.json.pre-v21"
    if not backup.exists():
        atomic_write(backup, original_text)

    events = dict(old["events"])
    total = 0
    for p in sorted(d.glob("trial_*/events.jsonl")):
        for line in p.read_text().splitlines():
            try:
                status = json.loads(line).get("status")
            except json.JSONDecodeError:
                continue
            if status is not None:
                total += 1
    events["total"] = total
    new = assess_stability(events, old["system"])
    payload = dict(old)
    payload["events"] = events
    payload.update(new)
    payload["rescore"] = {
        "formula": "v2.1 rate-scaled",
        "formula_commit": commit,
        "rescored_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "original_sha256": hashlib.sha256(original_text.encode()).hexdigest(),
        "original_backup": backup.name,
    }
    atomic_write(stability_path, json.dumps(payload))
    regenerate_report(d)
    print(f"{name}: score100 {old.get('score100')} -> {new['score100']} "
          f"(total={total}); scores.json/scorecard.md regenerated")
