#!/usr/bin/env python3
"""Math/context evaluator using common budgets and artifact retention."""
import json
import os
import re
import sys

from sblib import BUDGETS, Config, chat, write_json_atomic

SYS = ("Solve the problem. Reason carefully, then output your final answer as a single JSON object "
       "EXACTLY in the requested format on the last line. Output nothing after the JSON object.")


def extract_json(text):
    candidates = re.findall(r"\{(?:[^{}]|\{[^{}]*\})*\}", text, flags=re.DOTALL)
    for candidate in reversed(candidates):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def main():
    _label, suite_path, out, name, *context_path = sys.argv[1:]
    context = open(context_path[0]).read() if context_path else None
    phase = "context" if context is not None else "math"
    os.makedirs(out, exist_ok=True)
    cfg = Config.from_env()
    answers = {}
    for item in json.load(open(suite_path)):
        user = item["q"] if context is None else (
            "Below is an operations log. Read it, then answer the question at the end.\n\n"
            f"=== LOG START ===\n{context}\n=== LOG END ===\n\nQUESTION: {item['q']}")
        result = chat(cfg, [{"role": "system", "content": SYS}, {"role": "user", "content": user}],
                      max_tokens=BUDGETS[phase][0], wall_budget_s=BUDGETS[phase][1],
                      tag=f"{phase}-{item['id']}")
        answers[item["id"]] = {
            "request_id": result.request_id, "seconds": round(result.latency_s, 1),
            "error": result.error, "status": result.status, "parsed": extract_json(result.text),
            "finish_reason": result.finish_reason, "completion_tokens": result.completion_tokens,
            "reasoning_chars": len(result.reasoning_text),
        }
    write_json_atomic(os.path.join(out, name), answers)


if __name__ == "__main__":
    main()
