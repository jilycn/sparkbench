import json

import pytest

from sparkbench_compare import compare_runs


def _run(root, name, label, *, version=2, suite="v2", seed=1, math=None):
    directory = root / name
    directory.mkdir()
    (directory / "scores.json").write_text(json.dumps({"label": label, "scoring_version": version, "suite_version": suite,
                                                         "axes": {"MATH": {"score100": 80}, "LOAD": {"score100": 70}}}))
    (directory / "manifest.json").write_text(json.dumps({"seed": seed, "math_sample_ids": math or ["m1"],
                                                           "agent_variant": "closures", "context_variant": "seed-1"}))


def test_comparison_returns_axis_deltas_for_identical_samples(tmp_path):
    _run(tmp_path, "a_20260712-000000", "a")
    _run(tmp_path, "b_20260712-000000", "b")
    report = compare_runs(tmp_path, ["a", "b"])
    assert report["comparable"] is True
    assert report["rows"]["MATH"]["delta"] == 0


def test_sample_mismatch_is_exploratory_not_a_point_comparison(tmp_path):
    _run(tmp_path, "a_20260712-000000", "a")
    _run(tmp_path, "b_20260712-000000", "b", seed=2)
    report = compare_runs(tmp_path, ["a", "b"])
    assert report["exploratory"] is True
    assert report["rows"]["MATH"]["delta"] is None


def test_version_mismatch_refuses_unless_forced(tmp_path):
    _run(tmp_path, "a_20260712-000000", "a")
    _run(tmp_path, "b_20260712-000000", "b", version=3)
    with pytest.raises(ValueError):
        compare_runs(tmp_path, ["a", "b"])
    assert compare_runs(tmp_path, ["a", "b"], force=True)["not_comparable"] is True
