import json
from pathlib import Path

from judge3 import grade_suite
from logic_judge import grade_logic
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


def test_math_judge_reports_per_difficulty_splits(tmp_path, monkeypatch):
    suite = [
        {"id": "e", "difficulty": "easy", "answer": 2, "numeric": True},
        {"id": "m", "difficulty": "med", "answer": 3, "numeric": True},
        {"id": "h", "difficulty": "hard", "answer": 5, "numeric": True},
    ]
    (tmp_path / "math_suite.json").write_text(json.dumps(suite))
    trial = tmp_path / "trial_1"
    round3 = trial / "round3"
    raw = trial / "raw"
    round3.mkdir(parents=True)
    raw.mkdir()
    records = {}
    for item, actual in zip(suite, (2, 0, 5)):
        request_id = f"math-{item['id']}"
        (raw / f"{request_id}.txt").write_text(json.dumps({"answer": actual}) + "\n")
        records[item["id"]] = {"request_id": request_id, "status": "ok"}
    (round3 / "math_answers.json").write_text(json.dumps(records))
    monkeypatch.chdir(tmp_path)
    total, _detail, _flags, breakdown = grade_suite(
        round3, "math_suite.json", "math_answers.json", 1, "math"
    )
    assert total == 2
    assert breakdown == {
        "easy": {"correct": 1, "total": 1, "score100": 100.0},
        "med": {"correct": 0, "total": 1, "score100": 0.0},
        "hard": {"correct": 1, "total": 1, "score100": 100.0},
    }


def test_logic_judge_is_strict_and_reports_family_splits(tmp_path):
    trial = tmp_path / "trial_1"
    round2 = trial / "round2"
    raw = trial / "raw"
    round2.mkdir(parents=True)
    raw.mkdir()
    suite = [
        {"id": "a", "family": "assignment", "answer": {"A": 1}},
        {"id": "b", "family": "code", "answer": {"code": [1, 2, 3, 4]}},
    ]
    records = {}
    for item, answer in zip(suite, ({"A": 1}, {"code": [1, 2, 3, 0]})):
        request_id = f"logic-{item['id']}"
        (raw / f"{request_id}.txt").write_text(json.dumps(answer) + "\n")
        records[item["id"]] = {"request_id": request_id}
    (round2 / "logic_answers.json").write_text(json.dumps(records))
    score = grade_logic(round2, suite)
    assert score["correct"] == 1
    assert score["score100"] == 50.0
    assert score["family_breakdown"]["assignment"]["score100"] == 100.0
    assert score["family_breakdown"]["code"]["score100"] == 0.0
