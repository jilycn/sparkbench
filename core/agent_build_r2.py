#!/usr/bin/env python3
"""Run three independent, small agent coding tasks through the common client."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from sandbox import run_pytest
from sblib import BUDGETS, Config, chat, write_json_atomic, write_text_atomic


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write the requested implementation file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run this task's hidden tests in the isolated sandbox.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

COMMON_CONTRACT = """
Use write_file only for the requested implementation file and run_tests only to test it.
Do not use eval(), exec(), compile(), filesystem access, system access, or networking.
On the first turn write a complete solution, then test and repair it. One action per turn.
Reply DONE only after the hidden tests pass.
""".strip()


def _write_candidate(work: Path, expected_name: str, arguments: dict) -> str:
    relative = arguments.get("path", "")
    if relative != expected_name:
        return f"REJECTED: write only {expected_name}"
    content = arguments.get("content")
    if not isinstance(content, str):
        return "REJECTED: content must be a string"
    target = work / expected_name
    write_text_atomic(target, content)
    return f"wrote {expected_name}"


def _run_hidden(work: Path, task: dict, harness: Path):
    candidate = work / task["filename"]
    if not candidate.is_file():
        return f"NO {task['filename']}", 0, None, "candidate missing"
    result, error, mode = run_pytest(
        candidate, harness / task["tests_file"], timeout=180
    )
    if error:
        return error, 0, mode, error
    output = result.stdout + result.stderr
    match = re.search(r"(\d+) passed", output)
    passed = int(match.group(1)) if match else 0
    return output[-1800:], passed, mode, None


def _new_metrics(task: dict) -> dict:
    return {
        "id": task["id"],
        "family": task["family"],
        "variant": task["variant"],
        "turns": 0,
        "tool_calls": 0,
        "invalid_tool_calls": 0,
        "http_errors": 0,
        "timeouts": 0,
        "truncated_turns": 0,
        "turn_seconds": [],
        "finish_reasons": [],
        "completion_tokens": [],
        "reasoning_chars": [],
        "passed": 0,
        "total": task["hidden_count"],
        "converged": False,
        "sandbox": None,
        "notes": [],
    }


def run_task(cfg: Config, harness: Path, work: Path, task: dict):
    work.mkdir(parents=True, exist_ok=True)
    metrics = _new_metrics(task)
    contract = f"{task['contract']}\n\n{COMMON_CONTRACT}"
    messages = [
        {"role": "system", "content": contract},
        {
            "role": "user",
            "content": "Start now: write a complete implementation, then run the tests.",
        },
    ]
    transcript = list(messages)
    for turn in range(1, task["max_turns"] + 1):
        metrics["turns"] = turn
        result = chat(
            cfg,
            messages,
            max_tokens=BUDGETS["agent"][0],
            wall_budget_s=BUDGETS["agent"][1],
            tag=f"agent-{task['id']}-turn-{turn}",
            extra={"tools": TOOLS, "tool_choice": "auto"},
        )
        metrics["turn_seconds"].append(round(result.latency_s, 1))
        metrics["finish_reasons"].append(result.finish_reason)
        metrics["completion_tokens"].append(result.completion_tokens or 0)
        metrics["reasoning_chars"].append(len(result.reasoning_text))
        if result.status == "http_error":
            metrics["http_errors"] += 1
            metrics["notes"].append(
                f"t{turn}: http_error {result.http_status}: "
                f"{result.error}; body={result.http_body_snippet!r}"
            )
            continue
        if result.status == "timeout":
            metrics["timeouts"] += 1
            metrics["notes"].append(f"t{turn}: timeout: {result.error}")
            continue
        if result.status == "truncated":
            metrics["truncated_turns"] += 1
        assistant = {"role": "assistant", "content": result.text}
        if result.tool_calls:
            assistant["tool_calls"] = result.tool_calls
        messages.append(assistant)
        transcript.append({"request_id": result.request_id, **assistant})
        if not result.tool_calls:
            metrics["notes"].append(f"t{turn}: no tool calls")
            break
        for call in result.tool_calls:
            metrics["tool_calls"] += 1
            function = call.get("function") or {}
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
                metrics["invalid_tool_calls"] += 1
            if function.get("name") == "write_file":
                reply = _write_candidate(work, task["filename"], arguments)
                if reply.startswith("REJECTED"):
                    metrics["invalid_tool_calls"] += 1
            elif function.get("name") == "run_tests":
                reply, passed, mode, error = _run_hidden(work, task, harness)
                metrics["sandbox"] = mode
                metrics["passed"] = passed
                metrics["converged"] = not error and passed >= metrics["total"]
            else:
                reply = "unknown tool"
                metrics["invalid_tool_calls"] += 1
            tool_message = {
                "role": "tool",
                "tool_call_id": call.get("id"),
                "content": str(reply),
            }
            messages.append(tool_message)
            transcript.append(tool_message)
        if metrics["converged"]:
            break
    _output, passed, mode, error = _run_hidden(work, task, harness)
    metrics["sandbox"] = mode
    metrics["passed"] = passed
    metrics["converged"] = not error and passed >= metrics["total"]
    if error:
        metrics["notes"].append(f"final sandbox: {error}")
    return metrics, transcript


def main() -> None:
    label, work_arg, tasks_arg, out_arg = sys.argv[1:5]
    work_root, tasks_path, out = Path(work_arg), Path(tasks_arg), Path(out_arg)
    work_root.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    candidates = out / "candidates"
    candidates.mkdir(exist_ok=True)
    tasks = json.loads(tasks_path.read_text())
    cfg = Config.from_env()
    metrics = {
        "label": label,
        "part": "A_multi_task",
        "tasks": [],
        "sampling": {
            "temperature": 0.6,
            "top_p": 0.95,
            "max_tokens": BUDGETS["agent"][0],
            "wall_budget_s": BUDGETS["agent"][1],
        },
    }
    transcripts = {}
    for task in tasks:
        task_work = work_root / task["id"]
        task_metrics, transcript = run_task(
            cfg, tasks_path.parent, task_work, task
        )
        metrics["tasks"].append(task_metrics)
        transcripts[task["id"]] = transcript
        candidate = task_work / task["filename"]
        if candidate.is_file():
            write_text_atomic(
                candidates / task["filename"], candidate.read_text()
            )
    metrics["sandbox_backends"] = sorted(
        {
            task["sandbox"]
            for task in metrics["tasks"]
            if task.get("sandbox")
        }
    )
    metrics["hidden_passed"] = sum(task["passed"] for task in metrics["tasks"])
    metrics["hidden_total"] = sum(task["total"] for task in metrics["tasks"])
    metrics["converged_tasks"] = sum(task["converged"] for task in metrics["tasks"])
    write_json_atomic(out / "metrics.json", metrics)
    write_json_atomic(out / "transcript.json", transcripts)
    write_json_atomic(out / "reasoning_audit.json", [])


if __name__ == "__main__":
    main()
