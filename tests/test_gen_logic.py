from collections import Counter

import pytest

from gen_logic import (
    FAMILIES,
    _assignment_clue_text,
    _schedule_clue_text,
    generate_pool,
    sample_pool,
    solve_item,
    validate_distance_ambiguity,
)


def test_logic_pool_is_seeded_balanced_unique_and_solver_verified():
    pool = generate_pool(99)
    assert pool == generate_pool(99)
    assert len(pool) == 24
    assert Counter(item["family"] for item in pool) == Counter(
        {family: 6 for family in FAMILIES}
    )
    assert len({item["id"] for item in pool}) == len(pool)
    assert len({item["q"] for item in pool}) == len(pool)
    for item in pool:
        assert solve_item(item) == [item["answer"]]


def test_every_logic_clue_is_essential_to_the_unique_solution():
    for item in generate_pool(101):
        assert len(item["clues"]) >= 2
        for index in range(len(item["clues"])):
            weakened = {**item, "clues": item["clues"][:index] + item["clues"][index + 1 :]}
            assert len(solve_item(weakened, limit=2)) > 1


def test_logic_sample_is_two_per_family_and_seeded():
    pool = generate_pool(77)
    sample = sample_pool(pool, 123)
    assert sample == sample_pool(pool, 123)
    assert len(sample) == 8
    assert Counter(item["family"] for item in sample) == Counter(
        {family: 2 for family in FAMILIES}
    )
    assert len({item["id"] for item in sample}) == 8


def test_distance_ambiguity_guard_rejects_changed_uniqueness():
    ambiguous = {
        "id": "artificially-ambiguous-distance",
        "family": "schedule",
        "domain": {"names": ["Task-A", "Task-B", "Task-C"]},
        "answer": {
            "Task-A": "Monday",
            "Task-B": "Tuesday",
            "Task-C": "Wednesday",
        },
        "clues": [
            {"type": "before", "a": "Task-A", "b": "Task-B"},
            {"type": "distance", "a": "Task-A", "b": "Task-C", "n": 2},
        ],
    }
    assert solve_item(ambiguous) == [ambiguous["answer"]]
    with pytest.raises(ValueError, match="ambiguous distance"):
        validate_distance_ambiguity(ambiguous)


def test_all_distance_wording_uses_one_explicit_positional_convention():
    assignment = _assignment_clue_text(
        {"type": "distance", "a": "A", "b": "B", "n": 2}
    )
    schedule = _schedule_clue_text(
        {"type": "distance", "a": "Task-A", "b": "Task-B", "n": 2}
    )
    for rendered in (assignment, schedule):
        assert "absolute difference" in rendered
        assert "exactly 2" in rendered
        assert "days between" not in rendered
        assert "stations apart" not in rendered
    for item in generate_pool(20260712):
        assert " days between " not in item["q"]
        assert " stations apart" not in item["q"]
        assert all(clue.get("type") != "days_between" for clue in item["clues"])


def test_seed_20260712_sample_remains_balanced_and_ambiguity_guarded():
    sample = sample_pool(generate_pool(20260712), 20260712)
    assert Counter(item["family"] for item in sample) == Counter(
        {family: 2 for family in FAMILIES}
    )
    schedule_answers = {
        item["id"]: item["answer"] for item in sample if item["family"] == "schedule"
    }
    assert schedule_answers == {
        "logic-schedule-02": {
            "Task-Faye": "Wednesday",
            "Task-Galen": "Monday",
            "Task-Hana": "Thursday",
            "Task-Ivo": "Friday",
            "Task-Jori": "Tuesday",
        },
        "logic-schedule-04": {
            "Task-Paz": "Wednesday",
            "Task-Quin": "Tuesday",
            "Task-Rhea": "Monday",
            "Task-Sami": "Friday",
            "Task-Tova": "Thursday",
        },
    }
    for item in sample:
        validate_distance_ambiguity(item)
