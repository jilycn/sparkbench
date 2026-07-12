from pathlib import Path

from sblib import BUDGETS


def test_plan_budget_table_is_centralized():
    assert BUDGETS == {
        "logic": (8192, 240), "math": (2048, 120), "context": (2048, 180),
        "agent": (12288, 240), "load": (64, 45), "probe": (2048, 120), "stress": (16384, 300),
    }


def test_all_phase_evaluators_use_shared_client_not_hardcoded_endpoint():
    root = Path(__file__).parents[1]
    for name in ("agent_build_r2.py", "logic_eval.py", "qa_eval.py", "conc_eval.py", "think_probe.py"):
        text = (root / name).read_text()
        assert "from sblib import" in text
        assert "localhost:8000" not in text
