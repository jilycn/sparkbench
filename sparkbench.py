#!/usr/bin/env python3
"""SparkBench v2 snapshot-executing driver."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import importlib.util
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

sys.path.insert(0, str(Path(__file__).resolve().parent / "core"))
from sblib import append_jsonl, write_json_atomic, write_text_atomic


PHASES = ("tools", "agent", "logic", "math", "context", "load")
# This list is deliberately explicit. Add new runtime inputs here before they are
# eligible for a frozen run; do not replace it with a glob.
HARNESS_FILES = (
    "core/sblib.py", "core/sandbox.py", "core/stability.py", "core/power_sample.py", "core/inject_eval.py", "core/gen_inject.py", "core/agent_build_r2.py", "core/logic_eval.py", "core/qa_eval.py", "core/conc_eval.py", "core/think_probe.py", "core/judge.py", "core/logic_judge.py", "core/judge3.py", "core/judgelib.py", "sparkbench_report.py", "docs/SCORING_AGENT.md", "docs/SCORING_QA.md", "core/gen_agent_task.py", "core/gen_logic.py", "core/gen_math.py", "core/gen_longctx.py",
)

TOOL_EVAL_PARAMETERS = {
    "--temperature": "0.6",
    "--top-p": "0.95",
    "--top-k": "20",
    "--trials": "1",
    "--parallel": "1",
    "--timeout": "240",
    "--max-turns": "8",
    "--reference-date": "2026-03-20",
    "--error-rate": "0.0",
}


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
    logic_sample_ids: list[str]
    agent_variant: str
    context_variant: str


def materialize_dynamic_inputs(source_root: Path, staging: Path, seed: int, base_url: str | None = None,
                               agent_variant: str | None = None) -> Materialization:
    """Generate all run-specific inputs before the read-only snapshot is frozen."""
    staging.mkdir(parents=True, exist_ok=True)
    if not (source_root / "core" / "gen_math.py").exists():
        # Minimal fake roots used by snapshot tests have no generator sources.
        return Materialization([], [], [], "static-pending", "static-pending")
    from gen_agent_task import generate_agent_task
    from gen_logic import generate_pool as generate_logic_pool
    from gen_logic import sample_pool as sample_logic_pool
    from gen_math import generate_pool as generate_math_pool
    from gen_math import sample_pool as sample_math_pool
    from gen_longctx import generate_variant, tokenize_or_approx, validate_variant
    math_sample = sample_math_pool(generate_math_pool(seed), seed)
    logic_sample = sample_logic_pool(generate_logic_pool(seed), seed)
    write_json_atomic(staging / "math_suite.json", math_sample)
    write_json_atomic(staging / "logic_suite.json", logic_sample)
    variant = generate_variant(seed)
    if not validate_variant(variant):
        raise ValueError("generated context variant failed validation")
    write_text_atomic(staging / "longctx_doc.txt", variant["doc"])
    write_json_atomic(staging / "longctx_suite.json", variant["suite"])
    token_count, token_source = tokenize_or_approx(base_url, variant["doc"]) if base_url else (len(variant["doc"].split()) * 1.4, "approx")
    write_json_atomic(
        staging / "longctx_meta.json",
        {
            "seed": seed,
            "token_count": token_count,
            "token_source": token_source,
            "authority_cases": sorted(variant["authority_cases"]),
        },
    )
    agent = generate_agent_task(seed, source_root, staging, variant=agent_variant)
    return Materialization(
        [
            Path("math_suite.json"),
            Path("logic_suite.json"),
            Path("longctx_doc.txt"),
            Path("longctx_suite.json"),
            Path("longctx_meta.json"),
            *agent["files"],
        ],
        [item["id"] for item in math_sample],
        [item["id"] for item in logic_sample],
        agent["variant"],
        f"seed-{seed}",
    )


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
        destination = harness / relative_path.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        hashes[relative_path.name] = sha256(destination)
    _make_read_only(harness)
    return {"seed": seed, "files": hashes}


def verify_snapshot(harness: Path, expected_hashes: dict[str, str]) -> bool:
    return all((harness / relative).is_file() and sha256(harness / relative) == expected
               for relative, expected in expected_hashes.items())


def load_harness_module(harness: Path, name: str):
    spec = importlib.util.spec_from_file_location(f"sparkbench_snapshot_{name}", harness / f"{name}.py")
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load snapshot module {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def _tool_eval_metadata(tool: Path) -> dict[str, Any] | None:
    """Read distribution metadata with the tool's own interpreter."""
    try:
        first_line = tool.read_text(errors="replace").splitlines()[0]
    except (OSError, IndexError):
        return None
    if not first_line.startswith("#!"):
        return None
    interpreter = first_line[2:].strip()
    script = r'''
import importlib.metadata as metadata
import json
from pathlib import Path
import tool_eval_bench

root = Path(tool_eval_bench.__file__).resolve().parent
files = set()
for pattern in (
    "evals/*.py",
    "domain/scenarios.py",
    "domain/tools*.py",
    "runner/orchestrator.py",
    "runner/service.py",
    "adapters/openai_compat.py",
):
    files.update(path for path in root.glob(pattern) if path.is_file())
try:
    from tool_eval_bench.evals.scenarios import ALL_SCENARIOS
    scenario_count = len(ALL_SCENARIOS)
except Exception:
    scenario_count = None
print(json.dumps({
    "version": metadata.version("tool-eval-bench"),
    "package_root": str(root),
    "suite_files": [str(path.relative_to(root)) for path in sorted(files)],
    "scenario_count": scenario_count,
}))
'''
    value = _run_json([interpreter, "-c", script])
    return value if isinstance(value, dict) else None


def _external_suite_hash(package_root: Path, relative_files: list[str]) -> str | None:
    root = package_root.resolve()
    digest = hashlib.sha256()
    count = 0
    for relative in sorted(set(relative_files)):
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            return None
        if not path.is_file():
            return None
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
        count += 1
    return digest.hexdigest() if count else None


def tool_eval_provenance(tool: Path, seed: int | None = None) -> dict[str, Any]:
    metadata = _tool_eval_metadata(tool) or {}
    package_root = metadata.get("package_root")
    files = metadata.get("suite_files") if isinstance(metadata.get("suite_files"), list) else []
    suite_hash = (
        _external_suite_hash(Path(package_root), files)
        if isinstance(package_root, str)
        else None
    )
    try:
        resolved = str(tool.resolve(strict=True))
    except OSError:
        resolved = None
    return {
        "available": bool(metadata),
        "version": metadata.get("version"),
        "cmd": str(tool),
        "resolved_cmd": resolved,
        "suite_hash": suite_hash,
        "suite_files": files,
        "scenario_count": metadata.get("scenario_count"),
        "parameters": {
            **TOOL_EVAL_PARAMETERS,
            "--seed": str(seed) if seed is not None else "run seed",
        },
        "parser_contract": r"tools.log: Score:\s*<earned>\s*/\s*<possible>",
    }


def verify_tool_eval_provenance(recorded: dict[str, Any]) -> bool:
    seed_value = recorded.get("parameters", {}).get("--seed")
    try:
        seed = int(seed_value)
    except (TypeError, ValueError):
        seed = None
    current = tool_eval_provenance(Path(recorded.get("cmd", "")), seed=seed)
    return bool(recorded.get("version") and recorded.get("suite_hash")) and all(
        current.get(key) == recorded.get(key) for key in ("version", "suite_hash")
    )


def capture_provenance(base_url: str, container: str | None, seed: int = 20260712) -> dict[str, Any]:
    tool = shutil.which("tool-eval-bench") or str(Path.home() / ".local/bin/tool-eval-bench")
    tooleval = tool_eval_provenance(Path(tool), seed=seed)
    inspect = _run_json(["docker", "inspect", container]) if container else None
    image_digest = None
    serve_cmd = None
    if isinstance(inspect, list) and inspect:
        item = inspect[0]
        image_digest = item.get("Image")
        serve_cmd = item.get("Path")
    gpu = _run_json(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"])
    return {
        "tooleval": tooleval,
        "server_env": {"models_response": _get_models(base_url), "image_digest": image_digest,
                       "serve_cmd": serve_cmd, "gpu_name": gpu, "driver_version": gpu},
    }


def readiness(base_url: str, retries: int = 6, delay_s: float = 2.0) -> bool:
    for _ in range(retries):
        if _get_models(base_url) is not None:
            return True
        time.sleep(delay_s)
    return False


def phase_command(phase: str, harness: Path, trial_dir: Path, label: str, base_url: str, model: str,
                  seed: int = 20260712) -> list[list[str]]:
    py = sys.executable
    if phase == "tools":
        tool = shutil.which("tool-eval-bench") or str(Path.home() / ".local/bin/tool-eval-bench")
        parameters = [
            value
            for flag, setting in TOOL_EVAL_PARAMETERS.items()
            for value in (flag, setting)
        ]
        return [[tool, "--base-url", base_url, "--model", model, *parameters,
                 "--seed", str(seed), "--perf"]]
    if phase == "agent":
        return [[py, str(harness / "agent_build_r2.py"), label, str(trial_dir / "work_agent"),
                 str(harness / "agent_tasks.json"), str(trial_dir / "round2")],
                [py, str(harness / "judge.py"), str(trial_dir / "round2")]]
    if phase == "logic":
        return [[py, str(harness / "logic_eval.py"), label, str(harness / "logic_suite.json"), str(trial_dir / "round2")],
                [py, str(harness / "logic_judge.py"), str(trial_dir / "round2")]]
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


def required_phase_artifact(phase: str, trial_dir: Path) -> Path | None:
    return {
        "agent": trial_dir / "round2" / "score.json",
        "logic": trial_dir / "round2" / "logic_score.json",
        "math": trial_dir / "round3" / "score3.json",
        "context": trial_dir / "round3" / "score3.json",
        "load": trial_dir / "round3" / "load.json",
    }.get(phase)


def final_run_status(any_failed: bool, phases: list[str], agent_variant: str | None) -> str:
    if any_failed or set(phases) != set(PHASES) or agent_variant == "smoke":
        return "PARTIAL"
    return "COMPLETE"


def run_phase(phase: str, harness: Path, trial_dir: Path, label: str, base_url: str, model: str,
              seed: int = 20260712) -> bool:
    environment = os.environ.copy()
    environment.update({"SPARKBENCH_BASE_URL": base_url, "SPARKBENCH_MODEL": model,
                        "SPARKBENCH_RUN_DIR": str(trial_dir), "PYTHONDONTWRITEBYTECODE": "1"})
    for command in phase_command(phase, harness, trial_dir, label, base_url, model, seed):
        output = trial_dir / f"{phase}.log"
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("a", encoding="utf-8") as log:
            result = subprocess.run(command, cwd=harness, env=environment, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            return False
    required = required_phase_artifact(phase, trial_dir)
    if required is not None and not required.is_file():
        append_jsonl(trial_dir / "events.jsonl", {"request_id": f"phase-{phase}-artifact", "ts": time.time(),
                                                    "phase": phase, "status": "phase_error",
                                                    "error": f"required score artifact missing: {required.name}"})
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
        sandbox_mode = None
        if "agent" in phases:
            from sandbox import sandbox_available
            sandbox_mode = sandbox_available()
            if not sandbox_mode:
                write_status(run_dir, {"run_status": "INVALID", "phases": {phase: "pending" for phase in phases},
                                       "reason": "agent sandbox unavailable: unshare and docker failed"})
                return 2
        staging = run_dir / "staging"
        generated = materialize_dynamic_inputs(source_root, staging, args.seed, args.base_url, args.agent_variant)
        files = list(dict.fromkeys(list(HARNESS_FILES) + [str(p) for p in generated.files]))
        snapshot = snapshot_harness(source_root, run_dir, files,
                                    seed=args.seed, staged_root=staging)
        provenance = capture_provenance(args.base_url, args.container, args.seed)
        manifest = {"label": args.label, "harness_git_commit": _run_json(["git", "-C", str(source_root), "rev-parse", "HEAD"]),
                    "git_dirty": bool(_run_json(["git", "-C", str(source_root), "status", "--porcelain"])),
                    **snapshot, "scoring_version": 2, "suite_version": "2.2",
                    "math_sample_ids": generated.math_sample_ids, "agent_variant": generated.agent_variant,
                    "logic_sample_ids": generated.logic_sample_ids,
                    "tool_suite_hash": provenance["tooleval"].get("suite_hash"),
                    "context_variant": generated.context_variant, "cmdline": sys.argv,
                    "base_url": args.base_url, "model": args.model, "container": args.container,
                    "phases": phases, "trials": args.trials, "correlation_id": correlation_id,
                    "development_only": args.agent_variant == "smoke",
                    "started_ts": time.time(), "agent_sandbox": sandbox_mode, **provenance}
        write_json_atomic(run_dir / "manifest.json", manifest)
        status: dict[str, Any] = {"run_status": "RUNNING", "phases": {phase: "pending" for phase in phases},
                                  "trials": {f"trial_{number}": {phase: "pending" for phase in phases}
                                             for number in range(1, args.trials + 1)}}
        write_status(run_dir, status)
        if "tools" in phases and not verify_tool_eval_provenance(provenance["tooleval"]):
            status["run_status"] = "INVALID"
            status["reason"] = "tool-eval provenance unavailable or changed before run"
            write_status(run_dir, status)
            return 2
        stability = load_harness_module(run_dir / "harness", "stability")
        stability_before = stability.system_snapshot(args.container)
        if not readiness(args.base_url):
            status["run_status"] = "INVALID"
            status["reason"] = "readiness failed"
            write_status(run_dir, status)
            return 2
        sampler = None
        power_state = {"enabled": bool(args.power), "available": False, "note": "not requested"}
        if args.power:
            from power_sample import PowerSampler
            sampler = PowerSampler(run_dir / "power.jsonl")
            power_state = {"enabled": True, "available": sampler.start(),
                           "note": None if sampler.available else "nvidia-smi power sampling unavailable"}
        any_failed = False
        for trial in range(1, args.trials + 1):
            if status.get("aborted"):
                break
            trial_dir = run_dir / f"trial_{trial}"
            trial_dir.mkdir()
            phase_times = {}
            for phase in phases:
                status["phases"][phase] = "running"
                status["trials"][f"trial_{trial}"][phase] = "running"
                write_status(run_dir, status)
                started_phase = time.time()
                ok = run_phase(phase, run_dir / "harness", trial_dir, args.label, args.base_url, args.model,
                               args.seed)
                phase_times[phase] = {"started_ts": started_phase, "ended_ts": time.time()}
                if not ok:
                    any_failed = True
                    status["phases"][phase] = "failed"
                    status["trials"][f"trial_{trial}"][phase] = "failed"
                elif status["phases"][phase] != "failed":
                    status["phases"][phase] = "ok"
                    status["trials"][f"trial_{trial}"][phase] = "ok"
                write_status(run_dir, status)
                if (trial_dir / "ENDPOINT_DOWN").exists():
                    # Fail-fast: the endpoint is dead; benching the corpse records
                    # instant-timeout zeros as if measured (bit us 4+ times).
                    any_failed = True
                    status["aborted"] = "endpoint_down"
                    for trial_phases in status["trials"].values():
                        for pending in phases:
                            if trial_phases.get(pending) == "pending":
                                trial_phases[pending] = "skipped_endpoint_down"
                    for pending in phases:
                        if status["phases"].get(pending) == "pending":
                            status["phases"][pending] = "skipped_endpoint_down"
                    write_status(run_dir, status)
                    break
            if args.inject and not status.get("aborted"):
                started_phase = time.time()
                inject_result = subprocess.run([sys.executable, str(run_dir / "harness" / "inject_eval.py"), args.label, str(trial_dir)],
                                               cwd=run_dir / "harness", env={**os.environ, "SPARKBENCH_BASE_URL": args.base_url,
                                                                              "SPARKBENCH_MODEL": args.model, "SPARKBENCH_RUN_DIR": str(trial_dir)},
                                               capture_output=True, text=True)
                phase_times["inject"] = {"started_ts": started_phase, "ended_ts": time.time()}
                if inject_result.returncode:
                    any_failed = True
                    status["trials"][f"trial_{trial}"]["inject"] = "failed"
            write_json_atomic(trial_dir / "phase_times.json", phase_times)
        if sampler:
            sampler.stop()
        write_json_atomic(run_dir / "power.json", power_state)
        if "tools" in phases and not verify_tool_eval_provenance(provenance["tooleval"]):
            status["run_status"] = "INVALID"
            status["reason"] = "tool-eval suite changed during run"
            write_status(run_dir, status)
            return 2
        if not verify_snapshot(run_dir / "harness", snapshot["files"]):
            status["run_status"] = "INVALID"
            status["reason"] = "harness integrity mismatch"
            write_status(run_dir, status)
            return 2
        stability_payload = stability.write_stability(run_dir, stability_before, args.container)
        if stability_payload.get("observation_failed"):
            status["run_status"] = "INVALID"
            status["reason"] = "stability observation failed (container requested but not inspectable)"
            write_status(run_dir, status)
            return 2
        status["run_status"] = final_run_status(any_failed, phases, args.agent_variant)
        if args.agent_variant == "smoke":
            status["reason"] = "development-only agent smoke variant"
        status["ended_ts"] = time.time()
        write_status(run_dir, status)
        report_log = run_dir / "report.log"
        with report_log.open("w", encoding="utf-8") as log:
            report_result = subprocess.run([sys.executable, str(run_dir / "harness" / "sparkbench_report.py"), str(run_dir)],
                                           cwd=run_dir / "harness", stdout=log, stderr=subprocess.STDOUT)
        if report_result.returncode:
            status["run_status"] = "PARTIAL"
            status["reason"] = "report generation failed"
            write_status(run_dir, status)
            return 1
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
    command.add_argument("--agent-variant", choices=("smoke",))
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
