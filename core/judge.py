#!/usr/bin/env python3
"""Strict snapshot-local round-2 judge (agent scoring evolves further in Task 9)."""
import ast
import json
import re
import sys
from pathlib import Path

from judgelib import normalized_equal, raw_answer
from sandbox import deny_reason, run_pytest, run_script
from sblib import write_json_atomic


def main():
    run_dir = Path(sys.argv[1])
    score = {"A1_hidden": 0.0, "A2_probes": 0, "A3_quality": 0, "A4_efficiency": 0, "B_logic": 0,
             "total": 0.0, "detail": {}}
    interp = run_dir / "interp.py"
    if interp.exists():
        tests = Path.cwd() / ("agent_hidden_tests.py" if (Path.cwd() / "agent_hidden_tests.py").exists() else "test_interp.py")
        result, error, sandbox_mode = run_pytest(interp, tests)
        match = re.search(r"(\d+) passed", result.stdout + result.stderr) if result else None
        score["A1_hidden"] = round((int(match.group(1)) if match else 0) / 32 * 45, 1)
        probes = Path.cwd() / ("agent_edge_probes.py" if (Path.cwd() / "agent_edge_probes.py").exists() else "edge_probes.py")
        probe_result, _probe_error, _probe_mode = run_script(interp, probes)
        probe_match = re.search(r"(\d+)/10", probe_result.stdout) if probe_result else None
        score["A2_probes"] = round((int(probe_match.group(1)) if probe_match else 0) / 10 * 15, 1)
        score["A3_quality"] = 5 if deny_reason(interp.read_text()) is None else 0
        score["detail"]["sandbox"] = sandbox_mode or error
    answers_path = run_dir / "logic_answers.json"
    if answers_path.exists():
        answers = json.loads(answers_path.read_text())
        suite = json.loads((Path.cwd() / "logic_suite.json").read_text())
        for item in suite:
            parsed = raw_answer(run_dir.parent, answers.get(item["id"], {}))
            if isinstance(parsed, dict) and normalized_equal(parsed, item["answer"], casefold=True):
                score["B_logic"] += 3
    metrics = run_dir / "metrics.json"
    if metrics.exists():
        turns = json.loads(metrics.read_text()).get("turns", 99)
        score["A4_efficiency"] = 5 if turns <= 6 else 4 if turns <= 9 else 3 if turns <= 12 else 2 if turns <= 15 else 0
    score["total"] = sum(value for key, value in score.items() if key.startswith("A") or key == "B_logic")
    write_json_atomic(run_dir / "score.json", score)


if __name__ == "__main__":
    main()
