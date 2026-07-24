import json
from types import SimpleNamespace
from pathlib import Path

from gen_agent_task import generate_agent_task
from sandbox import (
    SANDBOX_DOCKER,
    SANDBOX_UNSHARE,
    _cleanup_workspace,
    _docker_command,
    _limits,
    _prepare_workspace,
    _run_in_sandbox,
    _unshare_command,
    deny_reason,
    run_pytest,
    sandbox_available,
)


def test_three_agent_families_are_seeded_independent_and_reference_validated(tmp_path):
    root = Path(__file__).parents[1]
    first = generate_agent_task(12, root, tmp_path / "one")
    second = generate_agent_task(12, root, tmp_path / "two")
    assert first["variant"] == second["variant"]
    tasks = json.loads((tmp_path / "one" / "agent_tasks.json").read_text())
    assert [task["family"] for task in tasks] == ["records", "dependencies", "ledger"]
    assert len({task["id"] for task in tasks}) == 3
    assert all(task["hidden_count"] == 12 and task["probe_count"] == 4 for task in tasks)
    assert sum(task["hidden_count"] for task in tasks) == 36
    assert sum(task["probe_count"] for task in tasks) == 12
    assert sum(task["hidden_count"] + task["probe_count"] for task in tasks) == 48
    for task in tasks:
        for key in ("tests_file", "probes_file"):
            assert (tmp_path / "one" / task[key]).read_text() == (
                tmp_path / "two" / task[key]
            ).read_text()
    assert first["reference_validated"] is True


def test_each_family_has_real_seeded_semantic_variation(tmp_path):
    root = Path(__file__).parents[1]
    variants = []
    for seed in range(3):
        out = tmp_path / str(seed)
        generate_agent_task(seed, root, out)
        variants.append(
            tuple(task["variant"] for task in json.loads((out / "agent_tasks.json").read_text()))
        )
    assert len(set(variants)) == 3
    assert all(len(set(family_variants)) == 3 for family_variants in zip(*variants))


def test_smoke_variant_is_explicit_single_task_and_not_seed_selected(tmp_path):
    root = Path(__file__).parents[1]
    task = generate_agent_task(99, root, tmp_path, variant="smoke")
    assert task["variant"] == "smoke"
    tasks = json.loads((tmp_path / "agent_tasks.json").read_text())
    assert len(tasks) == 1
    assert tasks[0]["development_only"] is True


def test_preflight_denies_dynamic_or_system_access_before_execution():
    assert deny_reason("import os\n")
    assert deny_reason("x.__class__\n")
    assert deny_reason("eval('1')\n")
    assert deny_reason("x.__globals__\n")
    assert deny_reason("class Token:\n    __slots__ = ('value',)\n    def __init__(self): pass\n") is None
    assert deny_reason("dict.__getitem__({}, 'x')\n") is None
    assert deny_reason("def run(x): return []\n") is None


def test_ast_denial_happens_before_any_sandbox_execution(tmp_path, monkeypatch):
    candidate = tmp_path / "solution.py"
    candidate.write_text("import socket\n")
    tests = tmp_path / "test_solution.py"
    tests.write_text("def test_never_runs(): assert False\n")
    monkeypatch.setattr(
        "sandbox.sandbox_available",
        lambda: (_ for _ in ()).throw(AssertionError("sandbox must not be reached")),
    )
    result, error, mode = run_pytest(candidate, tests)
    assert result is None
    assert error == "preflight denied: denied import"
    assert mode is None


def test_sandbox_selection_falls_back_to_docker_when_unshare_is_unavailable(monkeypatch):
    monkeypatch.setattr("sandbox.os.geteuid", lambda: 1000)
    monkeypatch.setattr("sandbox._probe_unshare", lambda: False)
    monkeypatch.setattr("sandbox._probe_docker", lambda: True)
    assert sandbox_available() == SANDBOX_DOCKER


def test_sandbox_refuses_to_execute_as_root(monkeypatch):
    monkeypatch.setattr("sandbox.os.geteuid", lambda: 0)
    monkeypatch.setattr(
        "sandbox._probe_unshare",
        lambda: (_ for _ in ()).throw(AssertionError("must fail before probing")),
    )
    assert sandbox_available() is None


def test_every_sandbox_backend_disables_network(tmp_path):
    docker = _docker_command(tmp_path, ["python", "runner.py"])
    assert "--network=none" in docker
    assert _unshare_command(["python", "runner.py"])[:3] == ["unshare", "-n", "--"]


def test_unshare_uses_minimal_environment_and_rlimits(tmp_path, monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured.update({"command": command, **kwargs})
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setenv("HF_TOKEN", "must-not-leak")
    monkeypatch.setattr("sandbox.subprocess.run", fake_run)
    result, error = _run_in_sandbox(
        tmp_path, ["python", "runner.py"], SANDBOX_UNSHARE, 10
    )
    assert result.returncode == 0 and error is None
    assert set(captured["env"]) == {
        "PATH",
        "PYTHONPATH",
        "HOME",
        "PYTHONDONTWRITEBYTECODE",
    }
    assert captured["env"]["HOME"] == str(tmp_path)
    assert captured["preexec_fn"] is _limits


def test_docker_resource_and_filesystem_caps_remain_enforced(tmp_path):
    command = _docker_command(tmp_path, ["python", "runner.py"])
    for flag in ("--memory=2g", "--cpus=2", "--pids-limit=256", "--read-only", "--tmpfs"):
        assert flag in command
    assert "HOME=/tmp" in command


def test_docker_sandbox_runs_as_the_host_user(tmp_path, monkeypatch):
    monkeypatch.setattr("sandbox.os.getuid", lambda: 1234)
    monkeypatch.setattr("sandbox.os.getgid", lambda: 5678)
    command = _docker_command(tmp_path, ["python", "runner.py"])
    assert command[command.index("--user") + 1] == "1234:5678"
    assert "0:0" not in command


def test_generic_candidate_filename_is_preserved_in_throwaway_workspace(tmp_path):
    candidate = tmp_path / "records_solution.py"
    tests = tmp_path / "agent_records_tests.py"
    candidate.write_text("def normalize(value): return value\n")
    tests.write_text("def test_empty(): assert True\n")
    temporary, work = _prepare_workspace(
        candidate, tests, candidate.name, tests.name
    )
    try:
        assert (work / candidate.name).is_file()
        assert (work / tests.name).is_file()
        assert not (work / "interp.py").exists()
    finally:
        _cleanup_workspace(temporary)


def test_workspace_cleanup_failure_is_logged_and_never_raises(monkeypatch):
    class BrokenTemporaryDirectory:
        def cleanup(self):
            raise PermissionError("root-owned __pycache__")

    warnings = []
    monkeypatch.setattr("sandbox._record_cleanup_warning", warnings.append)
    _cleanup_workspace(BrokenTemporaryDirectory())
    assert len(warnings) == 1
    assert "root-owned" in warnings[0]
