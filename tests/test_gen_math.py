import json

from gen_math import generate_pool, independent_answer, sample_pool, stress_suite


def test_pool_is_deterministic_stratified_and_independently_verifiable():
    pool = generate_pool(99)
    assert pool == generate_pool(99)
    assert {difficulty: sum(item["difficulty"] == difficulty for item in pool)
            for difficulty in ("easy", "med", "hard")} == {"easy": 100, "med": 100, "hard": 100}
    for item in pool:
        assert independent_answer(item) == item["answer"]


def test_sample_is_seeded_balanced_and_has_stable_ids():
    pool = generate_pool(77)
    sample = sample_pool(pool, 123)
    assert sample == sample_pool(pool, 123)
    assert len(sample) == 30
    assert {difficulty: sum(item["difficulty"] == difficulty for item in sample)
            for difficulty in ("easy", "med", "hard")} == {"easy": 10, "med": 10, "hard": 10}
    assert len({item["id"] for item in sample}) == 30


def test_stress_suite_is_small_and_programmatically_grounded():
    suite = stress_suite()
    assert len(suite) == 3
    assert all(independent_answer(item) == item["answer"] for item in suite)
