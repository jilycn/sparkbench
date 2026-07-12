#!/usr/bin/env python3
"""sparkbench aggregator: unify tool-eval + round2 + round3 artifacts into one scorecard.

Usage: sparkbench_report.py --label NAME --tooleval FILE --round2 DIR --round3 DIR --out DIR

Composite (100):
  TOOLS   tool-eval score/100          x 30
  AGENT   round2 A (A1+A2+A3+A4)/70    x 25
  REASON  (round2 B/30 + round3 C/30)/60 x 20
  CONTEXT round3 D/30                  x 15
  LOAD    round3 E/20                  x 10
Stability flags cap the grade: runaway -> max B, crash/OOM -> max C.
Speed sidebar parsed from tool-eval throughput table (tg t/s, ttft @ d0 c1).
"""
import argparse, json, os, re, sys

ap = argparse.ArgumentParser()
ap.add_argument("--label", required=True)
ap.add_argument("--tooleval")
ap.add_argument("--round2")
ap.add_argument("--round3")
ap.add_argument("--out", required=True)
a = ap.parse_args()

card = {"label": a.label, "parts": {}, "flags": [], "speed": {}, "composite": 0.0, "grade": None}

def flag(msg):
    card["flags"].append(msg)

# ---- TOOLS + speed ----
if a.tooleval and os.path.exists(a.tooleval):
    txt = open(a.tooleval, errors="replace").read()
    m = re.search(r"Score:\s*(\d+)\s*/\s*(\d+)", txt)
    if m:
        raw, mx = int(m.group(1)), int(m.group(2))
        npass = len(re.findall(r"\u2705 PASS", txt))
        npart = len(re.findall(r"PARTIAL", txt))
        nfail = len(re.findall(r"\u274c FAIL", txt))
        ntot = npass + npart + nfail
        scen = f" \u00b7 {npass}/{ntot} pass" + (f", {npart} partial" if npart else "") if ntot else ""
        card["parts"]["TOOLS"] = {"raw": f"{raw}/{mx}{scen}", "pts": round(raw / mx * 27, 1), "max": 27}
    for cm in re.finditer(r"CRITICAL[^\n]*", txt):
        flag("tool-eval: " + cm.group(0)[:120])
    sp = re.search(r"d0 c1\s+([\d,]+) pp t/s\s+([\d.]+) tg t/s\s+ttft=(\d+)ms", txt)
    if sp:
        card["speed"] = {"pp_tps": int(sp.group(1).replace(",", "")),
                         "tg_tps": float(sp.group(2)), "ttft_ms": int(sp.group(3))}
else:
    card["parts"]["TOOLS"] = {"raw": "missing", "pts": 0, "max": 27}

# ---- AGENT + half of REASON from round2 ----
r2_logic = 0.0
if a.round2 and os.path.exists(os.path.join(a.round2, "score.json")):
    s2 = json.load(open(os.path.join(a.round2, "score.json")))
    agent_raw = s2["A1_hidden"] + s2["A2_probes"] + s2["A3_quality"] + s2["A4_efficiency"]
    card["parts"]["AGENT"] = {"raw": f"{round(agent_raw,1)}/70", "pts": round(agent_raw / 70 * 22, 1), "max": 22}
    r2_logic = s2["B_logic"]
    mpath = os.path.join(a.round2, "metrics.json")
    if os.path.exists(mpath):
        m2 = json.load(open(mpath))
        trunc = sum(1 for f in m2.get("finish_reasons", []) if f == "length")
        if trunc: flag(f"round2 agent: {trunc} runaway/truncated turn(s)")
        if m2.get("http_errors"): flag(f"round2 agent: {m2['http_errors']} HTTP errors")
        if m2.get("invalid_tool_calls"): flag(f"round2 agent: {m2['invalid_tool_calls']} invalid tool calls")
else:
    card["parts"]["AGENT"] = {"raw": "missing", "pts": 0, "max": 22}

# ---- round3: rest of REASON + CONTEXT + LOAD ----
r3_math = 0.0
if a.round3 and os.path.exists(os.path.join(a.round3, "score3.json")):
    s3 = json.load(open(os.path.join(a.round3, "score3.json")))
    r3_math = s3["C_math"]
    card["parts"]["CONTEXT"] = {"raw": f"{s3['D_longctx']}/30", "pts": round(s3["D_longctx"] / 30 * 13, 1), "max": 13}
    card["parts"]["LOAD"] = {"raw": f"{s3['E_concurrency']}/20", "pts": round(s3["E_concurrency"] / 20 * 10, 1), "max": 10}
    for f in s3.get("flags", []):
        flag("round3: " + f)
    tf = s3.get("detail", {}).get("think_forensics")
    if tf: card["think_forensics"] = tf
else:
    card["parts"]["CONTEXT"] = {"raw": "missing", "pts": 0, "max": 13}
    card["parts"]["LOAD"] = {"raw": "missing", "pts": 0, "max": 10}

reason_raw = r2_logic + r3_math
card["parts"]["REASON"] = {"raw": f"{round(reason_raw,1)}/60", "pts": round(reason_raw / 60 * 18, 1), "max": 18}

# ---- STABILITY: scored from events during THIS run ----
ev = {"runaways": 0, "timeouts": 0, "http_errors": 0, "invalid_tool_calls": 0,
      "container_restarts": 0, "oom_events": 0, "server_down_after": False}
if a.round2 and os.path.exists(os.path.join(a.round2, "metrics.json")):
    m2 = json.load(open(os.path.join(a.round2, "metrics.json")))
    ev["runaways"] += sum(1 for f in m2.get("finish_reasons", []) if f == "length")
    ev["http_errors"] += m2.get("http_errors", 0)
    ev["invalid_tool_calls"] += m2.get("invalid_tool_calls", 0)
if a.round3 and os.path.exists(os.path.join(a.round3, "score3.json")):
    s3f = json.load(open(os.path.join(a.round3, "score3.json"))).get("flags", [])
    ev["runaways"] += sum(1 for f in s3f if "RUNAWAY" in f)
    ev["timeouts"] += sum(1 for f in s3f if "timed out" in f.lower())
    ev["http_errors"] += sum(1 for f in s3f if "HTTP" in f and "RUNAWAY" not in f)
if a.round3 and os.path.exists(os.path.join(a.round3, "conc_results.json")):
    ev["http_errors"] += json.load(open(os.path.join(a.round3, "conc_results.json"))).get("http_errors", 0)
sys_p = os.path.join(a.out, "stability_sys.json")
if os.path.exists(sys_p):
    sysd = json.load(open(sys_p))
    ev["container_restarts"] = sysd.get("container_restarts", 0)
    ev["oom_events"] = sysd.get("oom_events", 0)
    ev["server_down_after"] = not sysd.get("server_up_after", True)
stab = 100 - 40*ev["runaways"] - 20*ev["timeouts"] - 15*ev["http_errors"] \
       - 10*ev["invalid_tool_calls"] - 60*ev["container_restarts"] - 10*ev["oom_events"] \
       - (60 if ev["server_down_after"] else 0)
stab = max(0, stab)
if ev["container_restarts"]:
    flag(f"system: {ev['container_restarts']} container restart(s) — crash")
if ev["server_down_after"]:
    flag("system: server down after run — crash")
if ev["oom_events"]:
    flag(f"system: {ev['oom_events']} NVRM memory-pressure warning(s)")
card["parts"]["STABILITY"] = {"raw": f"{stab}/100 events={sum(v for k,v in ev.items() if k!='server_down_after')}",
                              "pts": round(stab / 100 * 10, 1), "max": 10}
card["stability_events"] = ev

# ---- per-category 0-100 score ----
for p in card["parts"].values():
    p["score100"] = round(p["pts"] / p["max"] * 100, 1) if p["max"] else 0

# ---- composite + grade with stability caps ----
card["composite"] = round(sum(p["pts"] for p in card["parts"].values()), 1)
c = card["composite"]
grade = ("A+" if c >= 95 else "A" if c >= 90 else "A-" if c >= 85 else
         "B+" if c >= 80 else "B" if c >= 70 else "C" if c >= 60 else "D")
GRADES = ["D", "C", "B", "B+", "A-", "A", "A+"]
cap = None
if any("crash" in f.lower() or "oom" in f.lower() for f in card["flags"]):
    cap = "C"
elif any("runaway" in f.lower() or "RUNAWAY" in f for f in card["flags"]):
    cap = "B"
if cap and GRADES.index(grade) > GRADES.index(cap):
    grade = cap
    card["grade_capped_by_stability"] = True
card["grade"] = grade

os.makedirs(a.out, exist_ok=True)
json.dump(card, open(os.path.join(a.out, "scorecard.json"), "w"), indent=2)

# ---- markdown ----
L = [f"# sparkbench scorecard — {a.label}", ""]
L.append("| Category | Raw | Score /100 | Weight | Weighted |")
L.append("|---|---|---|---|---|")
for k in ("TOOLS", "AGENT", "REASON", "CONTEXT", "LOAD", "STABILITY"):
    p = card["parts"][k]
    L.append(f"| {k} | {p['raw']} | **{p['score100']}** | {p['max']}% | {p['pts']} |")
if card["speed"]:
    sp = card["speed"]
    L.append(f"| SPEED | {sp.get('tg_tps','?')} tg t/s · ttft {sp.get('ttft_ms','?')}ms · pp {sp.get('pp_tps','?')} t/s | — | not scored | factor |")
L.append(f"| **OVERALL** | | | | **{card['composite']}/100 — grade {card['grade']}**"
         + (" (capped by stability)" if card.get("grade_capped_by_stability") else "") + " |")
L.append("")
L.append("Flags: " + ("; ".join(card["flags"]) if card["flags"] else "none — clean run"))
open(os.path.join(a.out, "scorecard.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
