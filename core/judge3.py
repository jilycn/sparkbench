#!/usr/bin/env python3
"""Strict snapshot-local round-3 judge."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from judgelib import ParsedAnswer, normalized_equal, raw_parsed_answer, summarize_envelopes
from sblib import write_json_atomic


@dataclass
class SuiteGrade:
    """One round-3 suite's outcome.

    A dataclass rather than a tuple because the judge now reports format
    compliance alongside the score, and a five-slot tuple invites the kind of
    positional-unpacking mistake this judge cannot afford.
    """

    points: int = 0
    detail: dict = field(default_factory=dict)
    flags: list = field(default_factory=list)
    difficulty_counts: dict = field(default_factory=dict)
    compliance: dict = field(default_factory=lambda: summarize_envelopes([]))


def describe(parsed: ParsedAnswer, value: object, expected: object, ok: bool) -> str:
    """Explain one item's outcome, separating a wrong answer from an unread one."""
    if ok:
        return "OK"
    if parsed.is_gradable:
        return f"wrong (got {value!r}, want {expected!r})"
    return (
        f"not graded [{parsed.envelope}]: {parsed.detail}"
        f" (parsed {parsed.value!r}, want {expected!r})"
    )


def grade_suite(run_dir: Path, suite_name: str, answers_name: str, points: int) -> SuiteGrade:
    suite = json.loads((Path.cwd() / suite_name).read_text())
    answers_path = run_dir / answers_name
    if not answers_path.exists():
        return SuiteGrade(detail={"missing": answers_name})
    answers = json.loads(answers_path.read_text())
    grade = SuiteGrade()
    parsed_answers = []
    for item in suite:
        record = answers.get(item["id"], {})
        parsed = raw_parsed_answer(run_dir.parent, record)
        parsed_answers.append(parsed)
        value = parsed.value.get("answer") if parsed.is_gradable else None
        ok = parsed.is_gradable and normalized_equal(
            value, item["answer"], numeric=item.get("numeric", False), tolerance=item.get("tol", 0)
        )
        grade.detail[item["id"]] = describe(parsed, value, item["answer"], ok)
        grade.points += points if ok else 0
        if difficulty := item.get("difficulty"):
            counts = grade.difficulty_counts.setdefault(difficulty, {"correct": 0, "total": 0})
            counts["correct"] += int(ok)
            counts["total"] += 1
        if record.get("status") in ("timeout", "truncated", "http_error"):
            grade.flags.append(f"{item['id']}: {record['status']}")
        elif parsed.envelope == "missing_transcript":
            grade.flags.append(f"{item['id']}: {parsed.detail}")
    for counts in grade.difficulty_counts.values():
        counts["score100"] = round(counts["correct"] / counts["total"] * 100, 1)
    grade.compliance = summarize_envelopes(parsed_answers)
    return grade


def main() -> None:
    run_dir = Path(sys.argv[1])
    math = grade_suite(run_dir, "math_suite.json", "math_answers.json", 1)
    longctx = grade_suite(run_dir, "longctx_suite.json", "longctx_answers.json", 3)
    score = {
        "C_math": math.points,
        "D_longctx": longctx.points,
        "E_concurrency": 0,
        "total": 0,
        "detail": {"math": math.detail, "longctx": longctx.detail},
        "flags": math.flags + longctx.flags,
        "math_breakdown": math.difficulty_counts,
        "format_compliance": {"math": math.compliance, "longctx": longctx.compliance},
    }
    conc = run_dir / "conc_results.json"
    if conc.exists():
        data = json.loads(conc.read_text())
        score["E_concurrency"] = round(data["correct"] / data["total"] * 20, 1)
    score["total"] = score["C_math"] + score["D_longctx"] + score["E_concurrency"]
    write_json_atomic(run_dir / "score3.json", score)


if __name__ == "__main__":
    main()
