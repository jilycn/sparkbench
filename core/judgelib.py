"""Strict, snapshot-local answer parsing shared by SparkBench judges."""
from __future__ import annotations

import json
import re
from pathlib import Path


def final_json_object(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    try:
        value = json.loads(lines[-1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def normalized_equal(actual, expected, *, casefold=False, numeric=False, tolerance=0.0):
    if numeric:
        if not isinstance(actual, (int, float)) or isinstance(actual, bool):
            return False
        return abs(float(actual) - float(expected)) <= tolerance
    if isinstance(actual, str) and isinstance(expected, str):
        actual, expected = actual.strip(), expected.strip()
        if casefold:
            actual, expected = actual.casefold(), expected.casefold()
        return actual == expected
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(normalized_equal(a, b, casefold=casefold) for a, b in zip(actual, expected))
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(normalized_equal(actual[key], expected[key], casefold=casefold) for key in actual)
    return actual == expected


def raw_answer(run_dir: Path, record: dict):
    request_id = record.get("request_id")
    if not request_id:
        return None
    path = run_dir / "raw" / f"{request_id}.txt"
    return final_json_object(path.read_text()) if path.is_file() else None
