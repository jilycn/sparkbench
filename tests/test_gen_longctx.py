from gen_longctx import generate_variant, tokenize_or_approx, validate_variant


def test_context_variant_is_seeded_adversarial_and_self_validating():
    first = generate_variant(91)
    second = generate_variant(91)
    assert first == second
    assert len(first["suite"]) == 10
    assert sum(item["kind"] == "conflict" for item in first["suite"]) == 2
    assert sum(item["kind"] == "compositional" for item in first["suite"]) == 2
    assert sum(item["cold"] for item in first["suite"]) == 1
    assert validate_variant(first)


def test_tokenizer_falls_back_to_labeled_approximation():
    count, source = tokenize_or_approx("http://127.0.0.1:1/v1", "one two three")
    assert count > 0
    assert source == "approx"
