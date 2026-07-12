#!/usr/bin/env python3
"""Interpreter-build agent evaluator using sblib's common request budget."""
import json
import os
import re
import shutil
import sys
from pathlib import Path

from sblib import BUDGETS, Config, chat, write_json_atomic
from sandbox import run_pytest

LABEL, WORK, GOLDEN, OUT = sys.argv[1:5]
MAX_TURNS = int(os.environ.get("MAX_TURNS", "20"))
os.makedirs(WORK, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

CONTRACT = """Build a single Python file `interp.py`: a tree-walking interpreter for a small language, passing a hidden pytest suite.

REQUIRED API: def run(source: str) -> list; InterpreterError; UndefinedVariableError; ArityError.
Statements end in semicolons; support variables, blocks, if/else, while, functions, returns, print,
numbers/strings/bools/nil, precedence, short-circuit &&/||, lexical scoping, closures, recursion,
arity errors, and undefined-variable errors. Do not use Python eval(), exec(), or compile().

Use write_file only for implementation files and run_tests only to test. One action per turn. On the
first turn write a complete interp.py, then iterate with tests. Reply DONE only when all pass.
"""
TOOLS = [
    {"type": "function", "function": {"name": "write_file", "description": "Write a work-dir file.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                    "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "run_tests", "description": "Run hidden pytest.",
     "parameters": {"type": "object", "properties": {}, "required": []}}},
]


def write_file(args):
    relative = args.get("path", "")
    if ".." in relative or relative.startswith("/") or os.path.basename(relative) == "test_interp.py":
        return "REJECTED: illegal path"
    target = os.path.join(WORK, relative)
    os.makedirs(os.path.dirname(target) or WORK, exist_ok=True)
    open(target, "w").write(args.get("content", ""))
    return f"wrote {relative}"


def run_tests():
    candidate = Path(WORK) / "interp.py"
    if not candidate.exists():
        return "NO interp.py", 0, None
    result, sandbox_error, sandbox_mode = run_pytest(candidate, Path(GOLDEN), timeout=180)
    if sandbox_error:
        return sandbox_error, 0, sandbox_mode
    output = result.stdout + result.stderr
    match = re.search(r"(\d+) passed", output)
    return output[-1800:], int(match.group(1)) if match else 0, sandbox_mode


def main():
    cfg = Config.from_env()
    task_spec = os.environ.get("SPARKBENCH_AGENT_SPEC")
    metrics = {"label": LABEL, "part": "A_interp", "turns": 0, "tool_calls": 0,
               "invalid_tool_calls": 0, "http_errors": 0, "turn_seconds": [], "finish_reasons": [],
               "completion_tokens": [], "reasoning_chars": [], "passed": 0, "total": 31,
               "converged": False, "notes": [],
               "sampling": {"temperature": 0.6, "top_p": 0.95, "max_tokens": BUDGETS["agent"][0],
                            "wall_budget_s": BUDGETS["agent"][1]}}
    contract = CONTRACT + ("\n" + Path(task_spec).read_text() if task_spec else "")
    messages = [{"role": "system", "content": contract},
                {"role": "user", "content": "Start now: write a complete implementation, then test it."}]
    transcript = list(messages)
    for turn in range(1, MAX_TURNS + 1):
        metrics["turns"] = turn
        result = chat(cfg, messages, max_tokens=BUDGETS["agent"][0], wall_budget_s=BUDGETS["agent"][1],
                      tag=f"agent-turn-{turn}", extra={"tools": TOOLS, "tool_choice": "auto"})
        metrics["turn_seconds"].append(round(result.latency_s, 1))
        metrics["finish_reasons"].append(result.finish_reason)
        metrics["completion_tokens"].append(result.completion_tokens or 0)
        metrics["reasoning_chars"].append(len(result.reasoning_text))
        if result.status in ("timeout", "http_error"):
            metrics["http_errors"] += 1
            metrics["notes"].append(f"t{turn}: {result.status}: {result.error}")
            continue
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
                reply = write_file(arguments)
            elif function.get("name") == "run_tests":
                reply, passed, sandbox_mode = run_tests()
                metrics["sandbox"] = sandbox_mode
                metrics["passed"] = passed
                metrics["converged"] = passed >= metrics["total"]
            else:
                reply = "unknown tool"
                metrics["invalid_tool_calls"] += 1
            tool_message = {"role": "tool", "tool_call_id": call.get("id"), "content": str(reply)}
            messages.append(tool_message)
            transcript.append(tool_message)
        if metrics["converged"]:
            break
    _output, passed, sandbox_mode = run_tests()
    metrics["sandbox"] = sandbox_mode
    metrics["passed"] = passed
    metrics["converged"] = passed >= metrics["total"]
    if os.path.exists(os.path.join(WORK, "interp.py")):
        shutil.copy(os.path.join(WORK, "interp.py"), os.path.join(OUT, "interp.py"))
    write_json_atomic(os.path.join(OUT, "metrics.json"), metrics)
    write_json_atomic(os.path.join(OUT, "transcript.json"), transcript)
    write_json_atomic(os.path.join(OUT, "reasoning_audit.json"), [])


if __name__ == "__main__":
    main()
