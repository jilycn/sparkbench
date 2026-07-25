import json
from pathlib import Path

from judge3 import grade_suite
from logic_judge import grade_logic
from judgelib import final_json_object, normalized_equal, raw_parsed_answer, terminal_answer


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
    grade = grade_suite(round3, "math_suite.json", "math_answers.json", 1)
    assert grade.points == 2
    assert grade.difficulty_counts == {
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


# --- suite 2.2.1 terminal-answer contract ---------------------------------


def test_pretty_printed_terminal_object_is_graded():
    # Suite 2.2 graded this shape as wrong because the last physical line is "}".
    # The model obeyed the contract: the answer object is terminal.
    text = '{\n  "Faye": 4,\n  "Galen": 2,\n  "Hana": 1,\n  "Ivo": 3\n}'
    parsed = terminal_answer(text)
    assert parsed.envelope == "multiline_terminal"
    assert parsed.is_gradable
    assert parsed.value == {"Faye": 4, "Galen": 2, "Hana": 1, "Ivo": 3}


def test_single_line_terminal_object_keeps_its_own_envelope():
    parsed = terminal_answer('reasoning\n{"answer": 7}\n')
    assert parsed.envelope == "strict_single_line"
    assert parsed.is_gradable


def test_trailing_prose_reports_the_answer_but_is_not_graded():
    parsed = terminal_answer('{"answer": 30}\nThis is my explanation.')
    assert parsed.envelope == "trailing_content"
    assert not parsed.is_gradable
    assert parsed.value == {"answer": 30}
    assert final_json_object('{"answer": 30}\nThis is my explanation.') is None


def test_closing_code_fence_is_named_and_not_graded():
    # Crediting this envelope is a scoring-policy change, not a parser repair.
    parsed = terminal_answer('```json\n{"answer": 12}\n```')
    assert parsed.envelope == "fenced_terminal"
    assert not parsed.is_gradable
    assert parsed.value == {"answer": 12}


def test_braces_inside_string_values_do_not_fake_a_terminal_object():
    parsed = terminal_answer('{"note": "a } inside text", "answer": 3}')
    assert parsed.is_gradable
    assert parsed.value == {"note": "a } inside text", "answer": 3}


def test_an_earlier_object_never_outranks_the_terminal_one():
    parsed = terminal_answer('{"answer": 1}\n{"answer": 2}')
    assert parsed.is_gradable
    assert parsed.value == {"answer": 2}


def test_non_dict_terminal_json_is_distinguished_from_no_answer():
    parsed = terminal_answer("[1, 2, 3]")
    assert parsed.envelope == "non_dict_json"
    assert not parsed.is_gradable


def test_empty_and_prose_only_transcripts_report_no_json():
    assert terminal_answer("   \n\n").envelope == "no_json"
    assert terminal_answer("I cannot solve this.").envelope == "no_json"


def test_missing_transcript_is_distinguished_from_a_bad_one(tmp_path):
    (tmp_path / "raw").mkdir()
    assert raw_parsed_answer(tmp_path, {}).envelope == "missing_transcript"
    assert raw_parsed_answer(tmp_path, {"request_id": "absent"}).envelope == "missing_transcript"


def test_booleans_and_integers_are_not_interchangeable():
    # Python evaluates True == 1, which would let a boolean-logic answer match
    # an integer-assignment expectation.
    assert not normalized_equal({"Signal": True}, {"Signal": 1})
    assert not normalized_equal({"Slot": 1}, {"Slot": True})
    assert normalized_equal({"Signal": True}, {"Signal": True})


def test_logic_judge_reports_envelope_categories_and_withholds_fenced_credit(tmp_path):
    trial = tmp_path / "trial_1"
    round2 = trial / "round2"
    raw = trial / "raw"
    round2.mkdir(parents=True)
    raw.mkdir()
    suite = [
        {"id": "a", "family": "assignment", "answer": {"A": 1}},
        {"id": "b", "family": "assignment", "answer": {"B": 2}},
        {"id": "c", "family": "code", "answer": {"code": [1]}},
    ]
    bodies = {
        "a": '{\n  "A": 1\n}',              # pretty printed, compliant
        "b": '```json\n{"B": 2}\n```',      # correct but fenced
        "c": "no idea",                      # no answer at all
    }
    records = {}
    for item in suite:
        request_id = f"logic-{item['id']}"
        (raw / f"{request_id}.txt").write_text(bodies[item["id"]])
        records[item["id"]] = {"request_id": request_id}
    (round2 / "logic_answers.json").write_text(json.dumps(records))

    score = grade_logic(round2, suite)

    assert score["correct"] == 1
    compliance = score["format_compliance"]
    assert compliance["total"] == 3
    assert compliance["graded"] == 1
    assert compliance["transport_failures"] == 0
    assert compliance["envelopes"]["multiline_terminal"] == 1
    assert compliance["envelopes"]["fenced_terminal"] == 1
    assert compliance["envelopes"]["no_json"] == 1
    # A withheld answer must not read as a reasoning failure.
    assert score["detail"]["b"].startswith("not graded [fenced_terminal]")
    assert "{'B': 2}" in score["detail"]["b"]


def test_round3_judge_flags_a_missing_transcript_as_transport(tmp_path, monkeypatch):
    suite = [{"id": "q", "difficulty": "easy", "answer": 2, "numeric": True}]
    (tmp_path / "math_suite.json").write_text(json.dumps(suite))
    trial = tmp_path / "trial_1"
    round3 = trial / "round3"
    round3.mkdir(parents=True)
    (trial / "raw").mkdir()
    (round3 / "math_answers.json").write_text(json.dumps({"q": {"request_id": "gone"}}))
    monkeypatch.chdir(tmp_path)

    grade = grade_suite(round3, "math_suite.json", "math_answers.json", 1)

    assert grade.points == 0
    assert grade.compliance["transport_failures"] == 1
    assert grade.compliance["graded"] == 0
    assert any("gone" in flag for flag in grade.flags)
