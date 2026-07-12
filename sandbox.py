"""Conservative preflight and isolated execution for generated agent code."""
from __future__ import annotations

import ast
import os
import resource
import shutil
import subprocess
import tempfile
from pathlib import Path


DENIED_IMPORTS = {"os", "sys", "subprocess", "socket", "shutil", "pathlib", "builtins", "importlib"}
DENIED_NAMES = {"eval", "exec", "compile", "open", "__import__", "getattr", "setattr", "delattr"}


def deny_reason(source: str) -> str | None:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return f"syntax error: {exc.msg}"
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name.split(".")[0] for alias in node.names] if isinstance(node, ast.Import) else [(node.module or "").split(".")[0]]
            if any(name in DENIED_IMPORTS for name in names):
                return "denied import"
        if isinstance(node, ast.Name) and node.id in DENIED_NAMES:
            return f"denied name: {node.id}"
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            return "denied dunder attribute"
    return None


def _limits():
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (50 * 1024**2, 50 * 1024**2))


def run_pytest(candidate: Path, tests: Path, timeout=180):
    """Run a preflight-approved candidate in a throwaway no-network namespace.

    If the host cannot create a network namespace, refuse execution rather than
    falling back to an unsandboxed test run.
    """
    reason = deny_reason(candidate.read_text())
    if reason:
        return None, f"preflight denied: {reason}"
    unshare = shutil.which("unshare")
    if not unshare:
        return None, "sandbox unavailable: unshare missing"
    with tempfile.TemporaryDirectory(prefix="sparkbench-agent-") as temporary:
        work = Path(temporary)
        shutil.copy2(candidate, work / "interp.py")
        shutil.copy2(tests, work / "test_interp.py")
        environment = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": "", "HOME": str(work),
                       "PYTHONDONTWRITEBYTECODE": "1"}
        command = [unshare, "-n", "--", os.environ.get("SPARKBENCH_PYTHON", os.sys.executable),
                   "-m", "pytest", "-q", "--no-header", "test_interp.py"]
        try:
            result = subprocess.run(command, cwd=work, capture_output=True, text=True, env=environment,
                                    preexec_fn=_limits, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None, "sandbox wall timeout"
        if result.returncode and "Operation not permitted" in (result.stdout + result.stderr):
            return None, "sandbox unavailable: unshare denied"
        return result, None


def run_script(candidate: Path, script: Path, timeout=180):
    reason = deny_reason(candidate.read_text())
    if reason:
        return None, f"preflight denied: {reason}"
    unshare = shutil.which("unshare")
    if not unshare:
        return None, "sandbox unavailable: unshare missing"
    with tempfile.TemporaryDirectory(prefix="sparkbench-agent-") as temporary:
        work = Path(temporary)
        shutil.copy2(candidate, work / "interp.py")
        shutil.copy2(script, work / "probes.py")
        environment = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": "", "HOME": str(work),
                       "PYTHONDONTWRITEBYTECODE": "1"}
        try:
            result = subprocess.run([unshare, "-n", "--", os.sys.executable, "probes.py"], cwd=work,
                                    capture_output=True, text=True, env=environment, preexec_fn=_limits, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None, "sandbox wall timeout"
        if result.returncode and "Operation not permitted" in (result.stdout + result.stderr):
            return None, "sandbox unavailable: unshare denied"
        return result, None
