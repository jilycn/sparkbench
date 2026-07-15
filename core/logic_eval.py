#!/usr/bin/env python3
"""Logic evaluator using the common SparkBench budgeted HTTP client."""
import json
import os
import re
import sys

from sblib import BUDGETS, Config, chat, write_json_atomic

SYS = ("You are solving a logic puzzle. Reason carefully, then output your final answer as a single JSON "
       "object EXACTLY in the format requested by the puzzle, on the last line of your reply. "
       "Output nothing after the JSON object.")


def extract_json(text):
    best = None
    best_key = (-1, 10**9)
    for match in re.finditer(r"\{", text):
        depth = 0
        for index in range(match.start(), len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        candidate = json.loads(text[match.start():index + 1])
                        key = (index, -match.start())
                        if key > best_key:
                            best_key, best = key, candidate
                    except json.JSONDecodeError:
                        pass
                    break
    return best


def main():
    label, suite_path, out = sys.argv[1:4]
    del label
    out = os.fspath(out)
    os.makedirs(out, exist_ok=True)
    cfg = Config.from_env()
    answers = {}
    for puzzle in json.load(open(suite_path)):
        result = chat(cfg, [{"role": "system", "content": SYS}, {"role": "user", "content": puzzle["q"]}],
                      max_tokens=BUDGETS["logic"][0], wall_budget_s=BUDGETS["logic"][1],
                      tag=f"logic-{puzzle['id']}")
        answers[puzzle["id"]] = {
            "request_id": result.request_id, "seconds": round(result.latency_s, 1),
            "error": result.error, "status": result.status, "parsed": extract_json(result.text),
            "finish_reason": result.finish_reason, "completion_tokens": result.completion_tokens,
            "reasoning_chars": len(result.reasoning_text),
        }
    write_json_atomic(os.path.join(out, "logic_answers.json"), answers)


if __name__ == "__main__":
    main()
