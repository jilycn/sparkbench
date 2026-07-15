#!/usr/bin/env python3
"""Strict snapshot-local round-3 judge."""
import json
import sys
from pathlib import Path

from judgelib import normalized_equal, raw_answer
from sblib import write_json_atomic


def grade_suite(run_dir, suite_name, answers_name, points, detail_name):
    suite = json.loads((Path.cwd() / suite_name).read_text())
    answers_path = run_dir / answers_name
    if not answers_path.exists():
        return 0, {"missing": answers_name}, []
    answers = json.loads(answers_path.read_text())
    total, detail, flags = 0, {}, []
    for item in suite:
        record = answers.get(item["id"], {})
        parsed = raw_answer(run_dir.parent, record)
        value = parsed.get("answer") if isinstance(parsed, dict) else None
        ok = normalized_equal(value, item["answer"], numeric=item.get("numeric", False), tolerance=item.get("tol", 0))
        detail[item["id"]] = "OK" if ok else f"wrong (got {value!r}, want {item['answer']!r})"
        total += points if ok else 0
        if record.get("status") in ("timeout", "truncated", "http_error"):
            flags.append(f"{item['id']}: {record['status']}")
    return total, detail, flags


def main():
    run_dir = Path(sys.argv[1])
    score = {"C_math": 0, "D_longctx": 0, "E_concurrency": 0, "total": 0, "detail": {}, "flags": []}
    score["C_math"], score["detail"]["math"], flags = grade_suite(run_dir, "math_suite.json", "math_answers.json", 1, "math")
    score["flags"].extend(flags)
    score["D_longctx"], score["detail"]["longctx"], flags = grade_suite(run_dir, "longctx_suite.json", "longctx_answers.json", 3, "longctx")
    score["flags"].extend(flags)
    conc = run_dir / "conc_results.json"
    if conc.exists():
        data = json.loads(conc.read_text())
        score["E_concurrency"] = round(data["correct"] / data["total"] * 20, 1)
    score["total"] = score["C_math"] + score["D_longctx"] + score["E_concurrency"]
    write_json_atomic(run_dir / "score3.json", score)


if __name__ == "__main__":
    main()
