#!/usr/bin/env python3
"""SparkBench v2 snapshot-executing driver.

The dynamic-suite materialization hook is intentionally static in Batch 1. Tasks 5, 6,
and 9 replace it with generated math/context/agent inputs before the snapshot is frozen.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from sblib import write_json_atomic


PHASES = ("tools", "agent", "logic", "math", "context", "load")
# This list is deliberately explicit. Add new runtime inputs here before they are
# eligible for a frozen run; do not replace it with a glob.
HARNESS_FILES = (
    "sblib.py", "agent_build_r2.py", "logic_eval.py", "qa_eval.py", "conc_eval.py",
    "think_probe.py", "judge.py", "judge3.py", "edge_probes.py", "test_interp.py",
    "logic_suite.json", "math_suite.json", "math_pool.json", "math_stress.json", "longctx_suite.json", "longctx_doc.txt", "longctx_meta.json",
    "SCORING_AGENT.md", "SCORING_QA.md",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class Materialization:
    files: list[Path]
    math_sample_ids: list[str]
    agent_variant: str
    context_variant: str


def materialize_dynamic_inputs(source_root: Path, staging: Path, seed: int, base_url: str | None = None) -> Materialization:
    """Batch-1 seam for Tasks 5/6/9.

    Future generators must write staged files here, validate them, and return their
    relative paths before ``snapshot_harness`` copies and hashes the complete harness.
    """
    staging.mkdir(parents=True, exist_ok=True)
    pool_path = source_root / "math_pool.json"
    if not pool_path.exists():
        # Batch-1 tests use minimal fake roots. Production v2 always commits the pool.
        return Materialization([], [], "static-pending", "static-pending")
    from gen_math import sample_pool
    from gen_longctx import generate_variant, tokenize_or_approx, validate_variant
    pool = json.loads(pool_path.read_text())
    sample = sample_pool(pool, seed)
    target = staging / "math_suite.json"
    target.write_text(json.dumps(sample, indent=2) + "\n")
    variant = generate_variant(seed)
    if not validate_variant(variant):
        raise ValueError("generated context variant failed validation")
    (staging / "longctx_doc.txt").write_text(variant["doc"])
    (staging / "longctx_suite.json").write_text(json.dumps(variant["suite"], indent=2) + "\n")
    token_count, token_source = tokenize_or_approx(base_url, variant["doc"]) if base_url else (len(variant["doc"].split()) * 1.4, "approx")
    (staging / "longctx_meta.json").write_text(json.dumps({"seed": seed, "token_count": token_count,
                                                              "token_source": token_source}, indent=2) + "\n")
    # Task 9 adds generated agent paths to this same pre-freeze result.
    return Materialization([Path("math_suite.json"), Path("longctx_doc.txt"), Path("longctx_suite.json"),
                            Path("longctx_meta.json")], [item["id"] for item in sample],
                           "static-pending", f"seed-{seed}")


def _make_read_only(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_file():
            path.chmod(0o444)
        elif path.is_dir():
            path.chmod(0o555)
    root.chmod(0o555)


def snapshot_harness(source_root: Path, run_dir: Path, files: list[str] | tuple[str, ...], *, seed: int,
                     staged_root: Path | None = None) -> dict[str, Any]:
    harness = run_dir / "harness"
    harness.mkdir(parents=True, exist_ok=False)
    hashes: dict[str, str] = {}
    for relative in files:
        relative_path = Path(relative)
        source = (staged_root / relative_path if staged_root and (staged_root / relative_path).is_file()
                  else source_root / relative_path)
        if not source.is_file():
            raise FileNotFoundError(f"required harness file missing: {relative}")
        destination = harness / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        hashes[relative_path.as_posix()] = sha256(destination)
    _make_read_only(harness)
    return {"seed": seed, "files": hashes}


def verify_snapshot(harness: Path, expected_hashes: dict[str, str]) -> bool:
    return all((harness / relative).is_file() and sha256(harness / relative) == expected
               for relative, expected in expected_hashes.items())


def parse_phases(value: str) -> list[str]:
    if value == "all":
        return list(PHASES)
    phases = [part.strip() for part in value.split(",") if part.strip()]
    unknown = sorted(set(phases) - set(PHASES))
    if not phases or unknown:
        raise ValueError(f"unknown or empty phase selection: {', '.join(unknown) or value}")
    return phases


def write_status(run_dir: Path, status: dict[str, Any]) -> None:
    write_json_atomic(run_dir / "status.json", status)


@contextlib.contextmanager
def bench_lock(bench_root: Path) -> Iterator[None]:
    bench_root.mkdir(parents=True, exist_ok=True)
    lock_path = bench_root / ".lock"
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"SparkBench lock is held: {lock_path}") from exc
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _run_json(command: list[str], timeout: float = 10) -> Any | None:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return result.stdout.strip() or None


def _get_models(base_url: str) -> Any | None:
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/models", timeout=10) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None


def capture_provenance(base_url: str, container: str | None) -> dict[str, Any]:
    tool = shutil.which("tool-eval-bench") or str(Path.home() / ".local/bin/tool-eval-bench")
    version = _run_json([tool, "--version"]) if Path(tool).exists() or shutil.which(tool) else None
    inspect = _run_json(["docker", "inspect", container]) if container else None
    image_digest = None
    serve_cmd = None
    if isinstance(inspect, list) and inspect:
        item = inspect[0]
        image_digest = item.get("Image")
        serve_cmd = item.get("Path")
    gpu = _run_json(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"])
    return {
        "tooleval": {"version": version, "cmd": tool, "suite_hash": None,
                     "parser_contract": "Task 11 adapter pending"},
        "server_env": {"models_response": _get_models(base_url), "image_digest": image_digest,
                       "serve_cmd": serve_cmd, "gpu_name": gpu, "driver_version": gpu},
    }


def readiness(base_url: str, retries: int = 6, delay_s: float = 2.0) -> bool:
    for _ in range(retries):
        if _get_models(base_url) is not None:
            return True
        time.sleep(delay_s)
    return False


def phase_command(phase: str, harness: Path, trial_dir: Path, label: str, base_url: str, model: str) -> list[list[str]]:
    py = sys.executable
    if phase == "tools":
        tool = shutil.which("tool-eval-bench") or str(Path.home() / ".local/bin/tool-eval-bench")
        return [[tool, "--base-url", base_url, "--model", model, "--perf"]]
    if phase == "agent":
        return [[py, str(harness / "agent_build_r2.py"), label, str(trial_dir / "work_agent"),
                 str(harness / "test_interp.py"), str(trial_dir / "round2")]]
    if phase == "logic":
        return [[py, str(harness / "logic_eval.py"), label, str(harness / "logic_suite.json"), str(trial_dir / "round2")],
                [py, str(harness / "judge.py"), str(trial_dir / "round2")]]
    if phase == "math":
        return [[py, str(harness / "qa_eval.py"), label, str(harness / "math_suite.json"),
                 str(trial_dir / "round3"), "math_answers.json"],
                [py, str(harness / "judge3.py"), str(trial_dir / "round3")]]
    if phase == "context":
        return [[py, str(harness / "qa_eval.py"), label, str(harness / "longctx_suite.json"),
                 str(trial_dir / "round3"), "longctx_answers.json", str(harness / "longctx_doc.txt")],
                [py, str(harness / "judge3.py"), str(trial_dir / "round3")]]
    if phase == "load":
        return [[py, str(harness / "conc_eval.py"), label, str(trial_dir / "round3")],
                [py, str(harness / "judge3.py"), str(trial_dir / "round3")]]
    raise ValueError(phase)


def run_phase(phase: str, harness: Path, trial_dir: Path, label: str, base_url: str, model: str) -> bool:
    environment = os.environ.copy()
    environment.update({"SPARKBENCH_BASE_URL": base_url, "SPARKBENCH_MODEL": model,
                        "SPARKBENCH_RUN_DIR": str(trial_dir), "PYTHONDONTWRITEBYTECODE": "1"})
    for command in phase_command(phase, harness, trial_dir, label, base_url, model):
        output = trial_dir / f"{phase}.log"
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("a", encoding="utf-8") as log:
            result = subprocess.run(command, cwd=harness, env=environment, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            return False
    return True


def run(args: argparse.Namespace) -> int:
    source_root = Path(__file__).resolve().parent
    bench_root = Path(args.bench_root).expanduser()
    phases = parse_phases(args.phases)
    correlation_id = args.correlation_id or str(uuid.uuid4())
    with bench_lock(bench_root):
        run_dir = bench_root / f"{args.label}_{time.strftime('%Y%m%d-%H%M%S')}"
        run_dir.mkdir(parents=True)
        staging = run_dir / "staging"
        generated = materialize_dynamic_inputs(source_root, staging, args.seed, args.base_url)
        files = list(dict.fromkeys(list(HARNESS_FILES) + [str(p) for p in generated.files]))
        snapshot = snapshot_harness(source_root, run_dir, files,
                                    seed=args.seed, staged_root=staging)
        provenance = capture_provenance(args.base_url, args.container)
        manifest = {"harness_git_commit": _run_json(["git", "-C", str(source_root), "rev-parse", "HEAD"]),
                    "git_dirty": bool(_run_json(["git", "-C", str(source_root), "status", "--porcelain"])),
                    **snapshot, "scoring_version": 2, "suite_version": "2-pending",
                    "math_sample_ids": generated.math_sample_ids, "agent_variant": generated.agent_variant,
                    "context_variant": generated.context_variant, "cmdline": sys.argv,
                    "base_url": args.base_url, "model": args.model, "container": args.container,
                    "phases": phases, "trials": args.trials, "correlation_id": correlation_id,
                    "started_ts": time.time(), **provenance}
        write_json_atomic(run_dir / "manifest.json", manifest)
        status: dict[str, Any] = {"run_status": "RUNNING", "phases": {phase: "pending" for phase in phases}}
        write_status(run_dir, status)
        if not readiness(args.base_url):
            status["run_status"] = "INVALID"
            status["reason"] = "readiness failed"
            write_status(run_dir, status)
            return 2
        any_failed = False
        for trial in range(1, args.trials + 1):
            trial_dir = run_dir / f"trial_{trial}"
            trial_dir.mkdir()
            for phase in phases:
                status["phases"][phase] = "running"
                write_status(run_dir, status)
                ok = run_phase(phase, run_dir / "harness", trial_dir, args.label, args.base_url, args.model)
                if not ok:
                    any_failed = True
                    status["phases"][phase] = "failed"
                elif status["phases"][phase] != "failed":
                    status["phases"][phase] = "ok"
                write_status(run_dir, status)
        if not verify_snapshot(run_dir / "harness", snapshot["files"]):
            status["run_status"] = "INVALID"
            status["reason"] = "harness integrity mismatch"
            write_status(run_dir, status)
            return 2
        status["run_status"] = "PARTIAL" if any_failed else "COMPLETE"
        status["ended_ts"] = time.time()
        write_status(run_dir, status)
        # Task 10/11 add stability and scorecard generation here.
        return 1 if any_failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("run")
    command.add_argument("label")
    command.add_argument("--phases", default="all")
    command.add_argument("--base-url", default="http://localhost:8000/v1")
    command.add_argument("--model", default=os.environ.get("SPARKBENCH_MODEL", "local-ai"))
    command.add_argument("--container")
    command.add_argument("--trials", type=int, default=1)
    command.add_argument("--probe", action="store_true")
    command.add_argument("--inject", action="store_true")
    command.add_argument("--power", action="store_true")
    command.add_argument("--stress", action="store_true")
    command.add_argument("--seed", type=int, default=20260712)
    command.add_argument("--bench-root", default="~/bench/sparkbench")
    command.add_argument("--correlation-id")
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("--trials must be at least 1")
    try:
        return run(args)
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        print(f"sparkbench: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
