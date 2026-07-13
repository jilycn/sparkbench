from pathlib import Path

from gen_agent_task import generate_agent_task
from sandbox import SANDBOX_DOCKER, _cleanup_workspace, _docker_command, deny_reason, sandbox_available


def test_agent_variants_are_seeded_and_reference_validated(tmp_path):
    root = Path(__file__).parents[1]
    first = generate_agent_task(12, root, tmp_path / "one")
    second = generate_agent_task(12, root, tmp_path / "two")
    assert first["variant"] == second["variant"]
    assert (tmp_path / "one" / "agent_hidden_tests.py").read_text() == (tmp_path / "two" / "agent_hidden_tests.py").read_text()
    assert first["reference_validated"] is True


def test_smoke_variant_is_explicit_and_not_seed_selected(tmp_path):
    root = Path(__file__).parents[1]
    task = generate_agent_task(99, root, tmp_path, variant="smoke")
    assert task["variant"] == "smoke"


def test_preflight_denies_dynamic_or_system_access_before_execution():
    assert deny_reason("import os\n")
    assert deny_reason("x.__class__\n")
    assert deny_reason("eval('1')\n")
    assert deny_reason("x.__globals__\n")
    assert deny_reason("class Token:\n    __slots__ = ('value',)\n    def __init__(self): pass\n") is None
    assert deny_reason("dict.__getitem__({}, 'x')\n") is None
    assert deny_reason("def run(x): return []\n") is None


def test_sandbox_selection_falls_back_to_docker_when_unshare_is_unavailable(monkeypatch):
    monkeypatch.setattr("sandbox._probe_unshare", lambda: False)
    monkeypatch.setattr("sandbox._probe_docker", lambda: True)
    assert sandbox_available() == SANDBOX_DOCKER


def test_docker_sandbox_runs_as_the_host_user(tmp_path, monkeypatch):
    monkeypatch.setattr("sandbox.os.getuid", lambda: 1234)
    monkeypatch.setattr("sandbox.os.getgid", lambda: 5678)
    command = _docker_command(tmp_path, ["python", "runner.py"])
    assert command[command.index("--user") + 1] == "1234:5678"


def test_workspace_cleanup_failure_is_logged_and_never_raises(monkeypatch):
    class BrokenTemporaryDirectory:
        def cleanup(self):
            raise PermissionError("root-owned __pycache__")

    warnings = []
    monkeypatch.setattr("sandbox._record_cleanup_warning", warnings.append)
    _cleanup_workspace(BrokenTemporaryDirectory())
    assert len(warnings) == 1
    assert "root-owned" in warnings[0]
