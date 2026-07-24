from collections import Counter

from gen_logic import FAMILIES, generate_pool, sample_pool, solve_item


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
