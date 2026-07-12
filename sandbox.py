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
SANDBOX_UNSHARE = "unshare"
SANDBOX_DOCKER = "docker"
# Pinned, locally present image. It provides Python 3 but not pytest, so the
# throwaway workspace receives a deliberately tiny stdlib test runner.
DOCKER_IMAGE = "ghcr.io/aeon-7/aeon-vllm-ultimate@sha256:f6d453d0b4a7ef90eefee486f4ff769cc2e1bb1e206df16d70370da09c02203c"


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


def _probe_unshare():
    return bool(shutil.which("unshare")) and subprocess.run(["unshare", "-n", "true"], capture_output=True).returncode == 0


def _probe_docker():
    if not shutil.which("docker"):
        return False
    command = ["docker", "run", "--rm", "--network=none", "--memory=2g", "--cpus=2", "--pids-limit=256",
               "--read-only", "--tmpfs", "/tmp:rw,size=64m", "--entrypoint", "/usr/local/bin/python3", DOCKER_IMAGE,
               "-c", "print('sandbox-ready')"]
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=20).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def sandbox_available():
    if _probe_unshare():
        return SANDBOX_UNSHARE
    if _probe_docker():
        return SANDBOX_DOCKER
    return None


_PYTEST_SHIM = '''class _Raises:
    def __init__(self, expected): self.expected = expected
    def __enter__(self): return self
    def __exit__(self, typ, value, traceback):
        if typ is None: raise AssertionError(f"did not raise {self.expected}")
        return issubclass(typ, self.expected)
def raises(expected): return _Raises(expected)
'''
_RUNNER = '''import importlib.util
spec = importlib.util.spec_from_file_location("test_interp", "test_interp.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
tests = [getattr(mod, n) for n in dir(mod) if n.startswith("test_")]
failed = []
for test in tests:
    try: test()
    except Exception as exc: failed.append(f"{test.__name__}: {type(exc).__name__}: {exc}")
print(f"{len(tests)-len(failed)} passed")
print("\\n".join(failed))
raise SystemExit(1 if failed else 0)
'''


def _prepare_workspace(candidate: Path, script: Path, name: str):
    temporary = tempfile.TemporaryDirectory(prefix="sparkbench-agent-")
    work = Path(temporary.name)
    shutil.copy2(candidate, work / "interp.py")
    shutil.copy2(script, work / name)
    (work / "pytest.py").write_text(_PYTEST_SHIM)
    (work / "runner.py").write_text(_RUNNER.replace("test_interp.py", name))
    return temporary, work


def _run_in_sandbox(work: Path, command: list[str], mode: str, timeout: int):
    environment = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": "", "HOME": str(work), "PYTHONDONTWRITEBYTECODE": "1"}
    if mode == SANDBOX_UNSHARE:
        full_command = ["unshare", "-n", "--", *command]
        kwargs = {"cwd": work, "env": environment, "preexec_fn": _limits}
    else:
        full_command = ["docker", "run", "--rm", "--network=none", "--memory=2g", "--cpus=2", "--pids-limit=256",
                        "--read-only", "--tmpfs", "/tmp:rw,size=64m", "-v", f"{work}:/work:rw", "-w", "/work",
                        "--entrypoint", "/usr/local/bin/python3", DOCKER_IMAGE, *command[1:]]
        kwargs = {"cwd": work}
    try:
        return subprocess.run(full_command, capture_output=True, text=True, timeout=timeout, **kwargs), None
    except subprocess.TimeoutExpired:
        return None, "sandbox wall timeout"


def _run(candidate: Path, script: Path, script_name: str, command: list[str], timeout=180):
    reason = deny_reason(candidate.read_text())
    if reason:
        return None, f"preflight denied: {reason}", None
    mode = sandbox_available()
    if not mode:
        return None, "sandbox unavailable: unshare and docker failed", None
    temporary, work = _prepare_workspace(candidate, script, script_name)
    try:
        result, error = _run_in_sandbox(work, command, mode, timeout)
        return result, error, mode
    finally:
        temporary.cleanup()


def run_pytest(candidate: Path, tests: Path, timeout=180):
    result, error, mode = _run(candidate, tests, "test_interp.py", [os.sys.executable, "runner.py"], timeout)
    return result, error, mode


def run_script(candidate: Path, script: Path, timeout=180):
    result, error, mode = _run(candidate, script, "probes.py", [os.sys.executable, "probes.py"], timeout)
    return result, error, mode
