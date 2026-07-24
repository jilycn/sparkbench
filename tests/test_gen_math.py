from collections import Counter

from gen_math import TEMPLATES, generate_pool, independent_answer, sample_pool


def _kinds():
    return [kind for kinds in TEMPLATES.values() for kind in kinds]


def test_pool_is_deterministic_stratified_and_independently_verifiable():
    pool = generate_pool(99)
    assert pool == generate_pool(99)
    assert len(pool) == 300
    assert {difficulty: sum(item["difficulty"] == difficulty for item in pool)
            for difficulty in ("easy", "med", "hard")} == {"easy": 100, "med": 100, "hard": 100}
    assert Counter(item["kind"] for item in pool) == Counter({kind: 20 for kind in _kinds()})
    assert {difficulty: len(kinds) for difficulty, kinds in TEMPLATES.items()} == {
        "easy": 5, "med": 5, "hard": 5
    }
    for item in pool:
        assert independent_answer(item) == item["answer"]


def test_sample_is_seeded_balanced_and_has_stable_ids():
    pool = generate_pool(77)
    sample = sample_pool(pool, 123)
    assert sample == sample_pool(pool, 123)
    assert len(sample) == 30
    assert {difficulty: sum(item["difficulty"] == difficulty for item in sample)
            for difficulty in ("easy", "med", "hard")} == {"easy": 10, "med": 10, "hard": 10}
    assert Counter(item["kind"] for item in sample) == Counter({kind: 2 for kind in _kinds()})
    assert len({item["id"] for item in sample}) == 30


def test_math_questions_and_parameter_sets_are_not_duplicated():
    pool = generate_pool(41)
    assert len({item["q"] for item in pool}) == len(pool)
    assert len({(item["kind"], tuple(item["params"])) for item in pool}) == len(pool)
