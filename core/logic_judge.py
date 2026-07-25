#!/usr/bin/env python3
"""Strict, snapshot-local judge for the generated logic suite."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from judgelib import ParsedAnswer, normalized_equal, raw_parsed_answer, summarize_envelopes
from sblib import write_json_atomic


def describe(parsed: ParsedAnswer, expected: object, ok: bool) -> str:
    """Explain one item's outcome, separating a wrong answer from an unread one.

    Suite 2.2 rendered both as "wrong (got None, ...)", which made a parser
    defect look identical to a reasoning failure.
    """
    if ok:
        return "OK"
    if parsed.is_gradable:
        return f"wrong (got {parsed.value!r}, want {expected!r})"
    return (
        f"not graded [{parsed.envelope}]: {parsed.detail}"
        f" (parsed {parsed.value!r}, want {expected!r})"
    )


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
            "format_compliance": summarize_envelopes([]),
        }
    records = json.loads(answers_path.read_text())
    detail = {}
    families = {}
    parsed_answers = []
    correct = 0
    for item in suite:
        parsed = raw_parsed_answer(run_dir.parent, records.get(item["id"], {}))
        parsed_answers.append(parsed)
        ok = parsed.is_gradable and normalized_equal(parsed.value, item["answer"], casefold=True)
        correct += int(ok)
        detail[item["id"]] = describe(parsed, item["answer"], ok)
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
        "format_compliance": summarize_envelopes(parsed_answers),
    }


def main() -> None:
    run_dir = Path(sys.argv[1])
    suite = json.loads((Path.cwd() / "logic_suite.json").read_text())
    write_json_atomic(run_dir / "logic_score.json", grade_logic(run_dir, suite))


if __name__ == "__main__":
    main()
