import re
from pathlib import Path

from sparkbench_report import WEIGHTS


def test_scoring_document_weights_match_report_constants():
    text = (Path(__file__).parents[1] / "docs" / "SCORING.md").read_text()
    found = {name: int(weight) for name, weight in re.findall(r"^\| (TOOLS|AGENT|LOGIC|MATH|CONTEXT|LOAD|STABILITY) \| (\d+)% \|", text, re.MULTILINE)}
    assert found == WEIGHTS
