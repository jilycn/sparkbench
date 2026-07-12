#!/usr/bin/env python3
"""Round-3 judge per SCORING3.md. Usage: judge3.py <results_dir>"""
import json, os, sys

RD = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
score = {"C_math": 0, "D_longctx": 0, "E_concurrency": 0, "total": 0, "detail": {}, "flags": []}

def norm(v):
    if isinstance(v, str):
        return v.strip().lower()
    if isinstance(v, list):
        return sorted(norm(x) for x in v) if all(isinstance(x, (int, float)) for x in v) else [norm(x) for x in v]
    if isinstance(v, bool):
        return v
    if isinstance(v, float) and v == int(v):
        return int(v)
    return v

def grade_suite(suite_file, answers_file, pts_each, key_name):
    suite = json.load(open(os.path.join(HERE, suite_file)))
    apath = os.path.join(RD, answers_file)
    if not os.path.exists(apath):
        score["detail"][key_name] = "missing " + answers_file
        return 0
    ans = json.load(open(apath))
    got = 0
    per = {}
    for p in suite:
        rec = ans.get(p["id"], {})
        parsed = rec.get("parsed")
        model_v = parsed.get("answer") if isinstance(parsed, dict) else None
        ok = False
        if model_v is not None:
            tol = p.get("tol")
            if tol not in (None, 0) and isinstance(model_v, (int, float)):
                ok = abs(float(model_v) - float(p["answer"])) <= tol
            else:
                ok = norm(model_v) == norm(p["answer"])
                # lenient string match: accept answer embedded in a longer phrase
                # ("Cinder team" for "Cinder") but not negations of it
                if not ok and isinstance(model_v, str) and isinstance(p["answer"], str):
                    mv = norm(model_v)
                    ok = norm(p["answer"]) in mv.split() and "not " + norm(p["answer"]) not in mv
        per[p["id"]] = "OK" if ok else f"wrong (got {json.dumps(model_v)[:60]}, want {p['answer']})"
        got += pts_each if ok else 0
        if rec.get("finish_reason") == "length":
            score["flags"].append(f"{p['id']}: RUNAWAY truncated at cap ({rec.get('completion_tokens')} tok)")
        if rec.get("error"):
            score["flags"].append(f"{p['id']}: {rec['error']}")
    score["detail"][key_name] = per
    return got

score["C_math"] = grade_suite("math_suite.json", "math_answers.json", 3, "math")
score["D_longctx"] = grade_suite("longctx_suite.json", "longctx_answers.json", 5, "longctx")

cpath = os.path.join(RD, "conc_results.json")
if os.path.exists(cpath):
    c = json.load(open(cpath))
    pts = c["correct"] / c["total"] * 20 - 2 * c.get("http_errors", 0)
    score["E_concurrency"] = round(max(0, pts), 1)
    score["detail"]["concurrency"] = {k: c[k] for k in
                                      ("correct", "total", "http_errors", "wall_seconds",
                                       "lat_min", "lat_avg", "lat_max")}
else:
    score["detail"]["concurrency"] = "missing conc_results.json"

tpath = os.path.join(RD, "think_report.json")
if os.path.exists(tpath):
    t = json.load(open(tpath))
    score["detail"]["think_forensics"] = {k: {kk: v.get(kk) for kk in
                                              ("reasoning_chars", "content_chars", "completion_tokens",
                                               "has_think_tag_in_content", "error")}
                                          for k, v in t.items()}

score["total"] = round(score["C_math"] + score["D_longctx"] + score["E_concurrency"], 1)
json.dump(score, open(os.path.join(RD, "score3.json"), "w"), indent=2)
print(json.dumps(score, indent=2))
