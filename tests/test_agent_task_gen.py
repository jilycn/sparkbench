from pathlib import Path

from gen_agent_task import generate_agent_task
from sandbox import deny_reason


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
    assert deny_reason("def run(x): return []\n") is None
