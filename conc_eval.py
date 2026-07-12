#!/usr/bin/env python3
"""SparkBench v2 sustained short-answer LOAD evaluator."""
from __future__ import annotations

import os
import random
import re
import sys
import threading
import time

from sblib import BUDGETS, Config, chat, write_json_atomic


def percentile(values, q):
    values = sorted(values)
    if not values:
        return 0.0
    position = (len(values) - 1) * q / 100
    low, high = int(position), min(int(position) + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (position - low)


def load_score(*, correct_rate, p95_s, failure_rate):
    if failure_rate > 0.05:
        return 0.0
    latency_factor = 1.0 if p95_s <= 15 else max(0.0, (60 - p95_s) / 45)
    score = correct_rate * latency_factor * 100
    return min(50.0, score) if failure_rate > 0.01 else round(score, 1)


def task_stream():
    rng = random.Random(20260712)
    while True:
        a, b, c = rng.randint(120, 999), rng.randint(12, 99), rng.randint(100, 999)
        yield f"Compute {a}*{b}+{c}. Reply with ONLY the final integer.", a * b + c


def main():
    label, out = sys.argv[1:3]
    duration = float(os.environ.get("SPARKBENCH_LOAD_DURATION", "120"))
    concurrency = int(os.environ.get("SPARKBENCH_LOAD_CONCURRENCY", "8"))
    os.makedirs(out, exist_ok=True)
    cfg = Config.from_env()
    records, records_lock = [], threading.Lock()
    deadline = time.monotonic() + duration

    def worker(worker_id):
        stream = task_stream()
        while time.monotonic() < deadline:
            question, expected = next(stream)
            result = chat(cfg, [{"role": "user", "content": question}], max_tokens=BUDGETS["load"][0],
                          wall_budget_s=BUDGETS["load"][1], tag=f"load-{worker_id}",
                          extra={"chat_template_kwargs": {"enable_thinking": False}})
            values = re.findall(r"-?\d+", result.text.replace(",", ""))
            got = int(values[-1]) if values else None
            record = {"worker": worker_id, "request_id": result.request_id, "latency_s": result.latency_s,
                      "completion_tokens": result.completion_tokens or 0, "status": result.status,
                      "finish_reason": result.finish_reason, "correct": result.status == "ok" and got == expected,
                      "got": got}
            with records_lock:
                records.append(record)

    started = time.monotonic()
    threads = [threading.Thread(target=worker, args=(worker_id,)) for worker_id in range(concurrency)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    wall = max(time.monotonic() - started, 0.001)
    latencies = [record["latency_s"] for record in records]
    errors = sum(record["status"] in ("timeout", "http_error") for record in records)
    truncations = sum(record["status"] == "truncated" for record in records)
    correct = sum(record["correct"] for record in records)
    total = len(records)
    error_rate, truncation_rate = errors / total if total else 1.0, truncations / total if total else 1.0
    payload = {"label": label, "concurrency": concurrency, "duration_s": duration, "n": total,
               "p50_s": round(percentile(latencies, 50), 3), "p95_s": round(percentile(latencies, 95), 3),
               "p99_s": round(percentile(latencies, 99), 3), "error_rate": error_rate,
               "truncation_rate": truncation_rate, "correct_rate": correct / total if total else 0.0,
               "throughput_tok_s": round(sum(record["completion_tokens"] for record in records) / wall, 3),
               "thinking_disabled_requested": True, "records": records}
    payload["score100"] = load_score(correct_rate=payload["correct_rate"], p95_s=payload["p95_s"],
                                      failure_rate=error_rate + truncation_rate)
    write_json_atomic(os.path.join(out, "load.json"), payload)


if __name__ == "__main__":
    main()
