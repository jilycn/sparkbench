import json
from pathlib import Path

from judgelib import final_json_object, normalized_equal


def test_harvested_m1_cinder_team_is_not_leniently_accepted():
    text = (Path(__file__).parent / "fixtures" / "judge" / "m1_lc2_tail.txt").read_text()
    assert final_json_object(text) == {"answer": "Cinder team"}
    assert not normalized_equal("Cinder team", "Cinder")


def test_mid_output_json_with_following_prose_fails_final_line_contract():
    assert final_json_object('{"answer": 30}\nThis is my explanation.') is None


def test_final_line_json_and_declared_normalization_pass():
    assert final_json_object('work\n{"answer":" CINDER "}\n') == {"answer": " CINDER "}
    assert normalized_equal(" CINDER ", "cinder", casefold=True)


def test_numeric_tolerance_is_only_used_when_declared():
    assert normalized_equal(3.005, 3.0, numeric=True, tolerance=0.01)
    assert not normalized_equal(3.005, 3.0, numeric=False, tolerance=0.01)
