import hashlib
import subprocess
import sys
from pathlib import Path

from sparkbench import SUITE_VERSION


ROOT = Path(__file__).parents[1]
ARCHIVE_SHA256 = "ff9de572e034b5ac8baabf1b46c8749fda79c7cf94760d7d92ed00ebc7bb5abb"
ARCHIVE_BYTES = 11985
ARCHIVE_START = "<!-- BEGIN VERBATIM V2.1 ARCHIVE -->\n"
ARCHIVE_END = "<!-- END VERBATIM V2.1 ARCHIVE -->"


def test_results_preserves_the_complete_v21_board_verbatim():
    text = (ROOT / "RESULTS.md").read_text()
    archived = text.split(ARCHIVE_START, 1)[1].split(ARCHIVE_END, 1)[0]
    payload = archived.encode()
    assert len(payload) == ARCHIVE_BYTES
    assert hashlib.sha256(payload).hexdigest() == ARCHIVE_SHA256


def test_only_current_scoring_policy_remains_and_documents_the_current_suite():
    policy = (ROOT / "docs" / "SCORING.md").read_text()
    # Exact, not a prefix: "2.2" matches "2.2.1" and let a stale policy ship.
    assert f"suite_version` `{SUITE_VERSION}`" in policy
    assert "12 hidden correctness tests" in policy
    assert "48 judged units" in policy
    assert not (ROOT / "docs" / "SCORING_AGENT.md").exists()
    assert not (ROOT / "docs" / "SCORING_QA.md").exists()


def test_dead_probe_and_committed_generated_context_are_removed():
    assert not (ROOT / "core" / "think_probe.py").exists()
    for name in ("longctx_doc.txt", "longctx_meta.json", "longctx_suite.json"):
        assert not (ROOT / "suites" / name).exists()


def test_dead_probe_and_stress_flags_are_not_advertised():
    result = subprocess.run(
        [sys.executable, str(ROOT / "sparkbench.py"), "run", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "--probe" not in result.stdout
    assert "--stress" not in result.stdout


def test_release_docs_state_the_version_boundary():
    readme = (ROOT / "README.md").read_text()
    changelog = (ROOT / "CHANGELOG.md").read_text()
    results = (ROOT / "RESULTS.md").read_text()
    assert f"suite {SUITE_VERSION}" in readme.lower()
    assert f"## Suite {SUITE_VERSION}" in changelog
    assert "## Suite 2.1" in changelog
    assert "not comparable" in results.lower()


def test_every_version_declaration_agrees_with_the_driver():
    """One stale declaration is enough to rank a run at the wrong score.

    The 2.2.1 repair shipped with the leaderboard still declaring 2.2, which
    would have kept a migrated run ranked at its uncorrected total.
    """
    import scoreio

    assert scoreio.CURRENT_SUITE == SUITE_VERSION
    assert SUITE_VERSION not in scoreio.SUPERSEDED_SUITES
    results = (ROOT / "RESULTS.md").read_text()
    assert f"# SparkBench suite {SUITE_VERSION} results" in results
