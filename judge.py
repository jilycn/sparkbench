#!/usr/bin/env python3
"""Round-2 judge: computes the 100-pt score per SCORING.md. Fully automated.
Usage: judge.py <results_dir>  (expects interp.py, metrics.json, logic_answers.json)"""
import ast as astmod, importlib.util, json, os, re, subprocess, sys

RD = sys.argv[1]
score = {"A1_hidden": 0.0, "A2_probes": 0, "A3_quality": 0, "A4_efficiency": 0, "B_logic": 0,
         "total": 0.0, "detail": {}}

HERE = os.path.dirname(os.path.abspath(__file__))
INTERP = os.path.join(RD, "interp.py")

# ---------- A1: hidden suite (40) ----------
if os.path.exists(INTERP):
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "--no-header", "test_interp.py"],
                       cwd=RD, capture_output=True, text=True, timeout=180)
    out = r.stdout + r.stderr
    m = re.search(r"(\d+) passed", out)
    passed = int(m.group(1)) if m else 0
    total = 31
    score["A1_hidden"] = round(passed / total * 40, 1)
    score["detail"]["hidden_passed"] = f"{passed}/{total}"
else:
    score["detail"]["hidden_passed"] = "no interp.py produced"

# ---------- A2: edge probes (10) ----------
if os.path.exists(INTERP):
    r = subprocess.run([sys.executable, os.path.join(HERE, "edge_probes.py"), RD],
                       capture_output=True, text=True, timeout=120)
    m = re.search(r"(\d+)/10", r.stdout)
    score["A2_probes"] = int(m.group(1)) if m else 0
    score["detail"]["probes"] = r.stdout.strip().splitlines()

# ---------- A3: static quality (10) ----------
if os.path.exists(INTERP):
    src = open(INTERP).read()
    pts = 0
    try:
        tree = astmod.parse(src)
        calls = [n.func.id for n in astmod.walk(tree)
                 if isinstance(n, astmod.Call) and isinstance(n.func, astmod.Name)]
        no_eval = not any(c in ("eval", "exec", "compile") for c in calls)
        bare_except = any(isinstance(n, astmod.ExceptHandler) and n.type is None
                          for n in astmod.walk(tree))
        defs = sum(isinstance(n, (astmod.FunctionDef, astmod.ClassDef)) for n in astmod.walk(tree))
        pts += 3 if no_eval else 0
        pts += 2 if not bare_except else 0
        pts += 2 if defs >= 5 else 0
        score["detail"]["quality"] = {"no_eval": no_eval, "no_bare_except": not bare_except,
                                      "defs": defs, "size_kb": round(len(src) / 1024, 1)}
        # deep recursion probe (1000)
        probe = ("import sys; sys.path.insert(0,%r); from interp import run; "
                 "print(run('func c(n) { if (n == 0) { return 0; } return 1 + c(n - 1); } print(c(1000));'))" % RD)
        pr = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, timeout=60)
        deep_ok = "[1000]" in pr.stdout
        pts += 2 if deep_ok else 0
        score["detail"]["quality"]["deep_1000"] = deep_ok
        pts += 1 if len(src) <= 30 * 1024 else 0
    except SyntaxError:
        score["detail"]["quality"] = "SYNTAX ERROR in interp.py"
    score["A3_quality"] = pts

# ---------- A4: efficiency (10) ----------
mpath = os.path.join(RD, "metrics.json")
if os.path.exists(mpath):
    m = json.load(open(mpath))
    turns = m.get("turns", 99)
    if m.get("converged"):
        base = 10 if turns <= 6 else 8 if turns <= 9 else 6 if turns <= 12 else 4
    else:
        base = 0
    ded = 2 * (m.get("invalid_tool_calls", 0) + m.get("http_errors", 0)
               + sum(1 for f in m.get("finish_reasons", []) if f == "length"))
    score["A4_efficiency"] = max(0, base - ded)
    score["detail"]["efficiency"] = {"turns": turns, "converged": m.get("converged"),
                                     "deductions": ded}

# ---------- B: logic (30) ----------
lpath = os.path.join(RD, "logic_answers.json")
if os.path.exists(lpath):
    la = json.load(open(lpath))
    suite = json.load(open(os.path.join(HERE, "logic_suite.json")))
    key = {p["id"]: p["answer"] for p in suite}

    def norm(v):
        if isinstance(v, str):
            return v.strip().lower()
        if isinstance(v, dict):
            return {str(k).strip(): norm(x) for k, x in v.items()}
        if isinstance(v, list):
            return [norm(x) for x in v]
        if isinstance(v, float) and v == int(v):
            return int(v)
        return v

    got = 0
    per = {}
    for pid, correct in key.items():
        model_ans = la.get(pid, {}).get("parsed")
        ok = model_ans is not None and norm(model_ans) == norm(correct)
        per[pid] = "OK" if ok else f"wrong (got {json.dumps(model_ans)[:80]}, want {json.dumps(correct)})"
        got += 3 if ok else 0
    score["B_logic"] = got
    score["detail"]["logic"] = per

score["total"] = round(score["A1_hidden"] + score["A2_probes"] + score["A3_quality"]
                       + score["A4_efficiency"] + score["B_logic"], 1)
json.dump(score, open(os.path.join(RD, "score.json"), "w"), indent=2)
print(json.dumps(score, indent=2))
