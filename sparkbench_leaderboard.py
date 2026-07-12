#!/usr/bin/env python3
"""Auto-generate LEADERBOARD.md from every scorecard under ~/bench/sparkbench/.
Keeps only the newest run per label. Usage: sparkbench_leaderboard.py [results_root]"""
import glob, json, os, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/bench/sparkbench")
cards = {}
for f in sorted(glob.glob(os.path.join(ROOT, "*", "scorecard.json"))):
    c = json.load(open(f))
    ts = os.path.basename(os.path.dirname(f)).rsplit("_", 1)[-1]
    prev = cards.get(c["label"])
    if not prev or ts > prev["_ts"]:
        c["_ts"] = ts
        c["_dir"] = os.path.basename(os.path.dirname(f))
        cards[c["label"]] = c

GRADE_ORDER = {"A+": 7, "A": 6, "A-": 5, "B+": 4, "B": 3, "C": 2, "D": 1}
ranked = sorted(cards.values(),
                key=lambda c: (GRADE_ORDER.get(c["grade"], 0), c["composite"]),
                reverse=True)

CATS = ["TOOLS", "AGENT", "REASON", "CONTEXT", "LOAD", "STABILITY"]
L = ["# SparkBench Leaderboard", "",
     "Ranked by grade, then composite. Stability caps: runaway → max B, crash/OOM → max C.", "",
     "| # | Recipe | Overall | Grade | " + " | ".join(CATS) + " | SPEED | Run |",
     "|---|---|---|---|" + "---|" * len(CATS) + "---|---|"]
for i, c in enumerate(ranked, 1):
    def cell(k):
        p = c["parts"].get(k, {})
        return f"**{p.get('score100','-')}** {p.get('raw','')}"
    cats = " | ".join(cell(k) for k in CATS)
    sp = c.get("speed") or {}
    cap = " ⚠capped" if c.get("grade_capped_by_stability") else ""
    speed = f"{sp.get('tg_tps','-')} t/s · ttft {sp.get('ttft_ms','-')}ms"
    L.append(f"| {i} | {c['label']} | **{c['composite']}** | {c['grade']}{cap} | {cats} "
             f"| {speed} | {c['_dir']} |")
L.append("")
L.append("## Flags")
for c in ranked:
    fl = c.get("flags") or []
    L.append(f"- **{c['label']}**: " + ("; ".join(fl) if fl else "clean"))
out = os.path.join(ROOT, "LEADERBOARD.md")
open(out, "w").write("\n".join(L) + "\n")
print("\n".join(L))
print(f"\n-> {out}", file=sys.stderr)
