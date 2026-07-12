#!/usr/bin/env python3
"""Batch-1 load correctness evaluator using the common 64-token/45-second budget."""
import json
import os
import random
import re
import sys
import threading
import time

from sblib import BUDGETS, Config, chat, write_json_atomic

random.seed(20260712)
TASKS = [{"q": f"Compute {a}*{b}+{c}. Reply with ONLY the final integer.", "answer": a * b + c}
         for a, b, c in [(random.randint(120, 999), random.randint(12, 99), random.randint(100, 999))
                         for _ in range(20)]]


def main():
    label, out = sys.argv[1:3]
    os.makedirs(out, exist_ok=True)
    cfg = Config.from_env()
    results = [None] * len(TASKS)

    def worker(worker_id):
        for offset in range(5):
            index = worker_id * 5 + offset
            result = chat(cfg, [{"role": "user", "content": TASKS[index]["q"]}],
                          max_tokens=BUDGETS["load"][0], wall_budget_s=BUDGETS["load"][1],
                          tag=f"load-{index}", extra={"chat_template_kwargs": {"enable_thinking": False}})
            numbers = re.findall(r"-?\d+", result.text.replace(",", ""))
            got = int(numbers[-1]) if numbers else None
            results[index] = {"idx": index, "worker": worker_id, "request_id": result.request_id,
                              "seconds": round(result.latency_s, 1), "error": result.error,
                              "status": result.status, "finish_reason": result.finish_reason,
                              "got": got, "correct": result.status == "ok" and got == TASKS[index]["answer"]}

    started = time.monotonic()
    threads = [threading.Thread(target=worker, args=(worker_id,)) for worker_id in range(4)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    latencies = [record["seconds"] for record in results]
    summary = {"label": label, "correct": sum(record["correct"] for record in results), "total": len(results),
               "http_errors": sum(record["status"] == "http_error" for record in results),
               "wall_seconds": round(time.monotonic() - started, 1), "lat_min": min(latencies),
               "lat_max": max(latencies), "lat_avg": round(sum(latencies) / len(latencies), 1), "results": results}
    write_json_atomic(os.path.join(out, "conc_results.json"), summary)


if __name__ == "__main__":
    main()
