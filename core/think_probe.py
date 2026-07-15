#!/usr/bin/env python3
"""Optional thinking diagnostic using the shared budgeted client."""
import os
import sys

from sblib import BUDGETS, Config, chat, write_json_atomic

HARD = "How many positive integers n <= 200 are divisible by 3 or 5 but not both? Work it out."
CONFIGS = [
    ("default", {}),
    ("kwargs_think_true", {"chat_template_kwargs": {"enable_thinking": True}}),
    ("kwargs_think_false", {"chat_template_kwargs": {"enable_thinking": False}}),
    ("soft_switch_think", {"prefix": "/think "}),
    ("soft_switch_nothink", {"prefix": "/no_think "}),
]


def main():
    _label, out = sys.argv[1:3]
    os.makedirs(out, exist_ok=True)
    cfg = Config.from_env()
    report = {}
    for name, extra in CONFIGS:
        payload = dict(extra)
        prompt = payload.pop("prefix", "") + HARD
        result = chat(cfg, [{"role": "user", "content": prompt}], max_tokens=BUDGETS["probe"][0],
                      wall_budget_s=BUDGETS["probe"][1], tag=f"probe-{name}", extra=payload)
        report[name] = {"request_id": result.request_id, "seconds": round(result.latency_s, 1),
                        "completion_tokens": result.completion_tokens,
                        "reasoning_chars": len(result.reasoning_text), "content_chars": len(result.text),
                        "has_think_tag_in_content": "<think>" in result.text,
                        "finish_reason": result.finish_reason, "status": result.status, "error": result.error}
    write_json_atomic(os.path.join(out, "think_report.json"), report)


if __name__ == "__main__":
    main()
