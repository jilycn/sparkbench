#!/usr/bin/env python3
"""Rescore STABILITY for pre-v2.1 COMPLETE runs using the corrected rate-scaled formula.
Only touches stability.json (recomputes score100/grade_cap/fatal/runaway/rates from the same
already-recorded event counts + a freshly-derived total). Does not touch manifest.json — the
run's actual recipe/config/harness_git_commit provenance stays exactly as recorded at run time.
"""
import sys, json, pathlib

sys.path.insert(0, "core")
from stability import assess_stability

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

for name in RUNS:
    d = root / name
    old = json.loads((d / "stability.json").read_text())
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
    (d / "stability.json").write_text(json.dumps(payload))
    print(f"{name}: old score100={old.get('score100')} -> new score100={new['score100']} (total={total})")
