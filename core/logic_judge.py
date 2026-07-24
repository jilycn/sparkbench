#!/usr/bin/env python3
"""Strict, snapshot-local judge for the generated logic suite."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from judgelib import normalized_equal, raw_answer
from sblib import write_json_atomic


def grade_logic(run_dir: Path, suite: list[dict]) -> dict:
    answers_path = run_dir / "logic_answers.json"
    if not answers_path.exists():
        return {
            "missing": "logic_answers.json",
            "correct": 0,
            "total": len(suite),
            "score100": 0.0,
            "family_breakdown": {},
            "detail": {},
        }
    records = json.loads(answers_path.read_text())
    detail = {}
    families = {}
    correct = 0
    for item in suite:
        parsed = raw_answer(run_dir.parent, records.get(item["id"], {}))
        ok = isinstance(parsed, dict) and normalized_equal(
            parsed, item["answer"], casefold=True
        )
        correct += int(ok)
        detail[item["id"]] = "OK" if ok else f"wrong (got {parsed!r}, want {item['answer']!r})"
        family = families.setdefault(item["family"], {"correct": 0, "total": 0})
        family["correct"] += int(ok)
        family["total"] += 1
    for family in families.values():
        family["score100"] = round(family["correct"] / family["total"] * 100, 1)
    return {
        "correct": correct,
        "total": len(suite),
        "score100": round(correct / len(suite) * 100, 1) if suite else 0.0,
        "family_breakdown": families,
        "detail": detail,
    }


def main() -> None:
    run_dir = Path(sys.argv[1])
    suite = json.loads((Path.cwd() / "logic_suite.json").read_text())
    write_json_atomic(run_dir / "logic_score.json", grade_logic(run_dir, suite))


if __name__ == "__main__":
    main()
