#!/usr/bin/env python3
"""Strict snapshot-local round-2 judge (agent scoring evolves further in Task 9)."""
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

from judgelib import normalized_equal, raw_answer
from sblib import write_json_atomic


def main():
    run_dir = Path(sys.argv[1])
    score = {"A1_hidden": 0.0, "A2_probes": 0, "A3_quality": 0, "A4_efficiency": 0, "B_logic": 0,
             "total": 0.0, "detail": {}}
    interp = run_dir / "interp.py"
    if interp.exists():
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", "--no-header", str(Path.cwd() / "test_interp.py")],
                                cwd=run_dir, capture_output=True, text=True, timeout=180)
        match = re.search(r"(\d+) passed", result.stdout + result.stderr)
        score["A1_hidden"] = round((int(match.group(1)) if match else 0) / 31 * 40, 1)
        tree = ast.parse(interp.read_text())
        banned = {"eval", "exec", "compile"}
        score["A3_quality"] = 10 if not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in banned for node in ast.walk(tree)) else 0
    answers_path = run_dir / "logic_answers.json"
    if answers_path.exists():
        answers = json.loads(answers_path.read_text())
        suite = json.loads((Path.cwd() / "logic_suite.json").read_text())
        for item in suite:
            parsed = raw_answer(run_dir.parent, answers.get(item["id"], {}))
            if isinstance(parsed, dict) and normalized_equal(parsed, item["answer"], casefold=True):
                score["B_logic"] += 3
    score["total"] = sum(value for key, value in score.items() if key.startswith("A") or key == "B_logic")
    write_json_atomic(run_dir / "score.json", score)


if __name__ == "__main__":
    main()
