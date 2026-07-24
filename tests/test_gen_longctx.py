from gen_longctx import (
    generate_variant,
    resolve_authority,
    tokenize_or_approx,
    validate_variant,
)


def test_context_variant_is_seeded_adversarial_and_self_validating():
    first = generate_variant(91)
    second = generate_variant(91)
    assert first == second
    assert len(first["suite"]) == 10
    assert sum(item["kind"] == "conflict" for item in first["suite"]) == 2
    assert sum(item["kind"] == "compositional" for item in first["suite"]) == 2
    assert sum(item["cold"] for item in first["suite"]) == 1
    assert validate_variant(first)


def test_conflicts_require_source_authority_then_same_class_recency():
    variant = generate_variant(92)
    conflicts = [item for item in variant["suite"] if item["kind"] == "conflict"]
    assert len(conflicts) == 2
    for item in conflicts:
        case = variant["authority_cases"][item["authority_case"]]
        winner = resolve_authority(case)
        assert winner["value"] == item["answer"]
        assert winner["record_id"] == item["authority"]["winning_record"]
        assert len(item["authority"]["losing_records"]) >= 2
        # One older record has the same top authority, so source rank alone is
        # insufficient; one later record has lower authority, so recency alone
        # is also insufficient.
        assert any(
            record["source_class"] == winner["source_class"]
            and record["effective_day"] < winner["effective_day"]
            and record["value"] != winner["value"]
            for record in case["records"]
        )
        assert any(
            record["effective_day"] > winner["effective_day"]
            and record["source_rank"] < winner["source_rank"]
            and record["value"] != winner["value"]
            for record in case["records"]
        )


def test_conflict_distractors_do_not_label_themselves_false_or_superseded():
    variant = generate_variant(93)
    evidence_lines = [
        line
        for line in variant["doc"].splitlines()
        if "[EVIDENCE " in line
    ]
    assert evidence_lines
    assert all("false" not in line.casefold() for line in evidence_lines)
    assert all("superseded" not in line.casefold() for line in evidence_lines)


def test_tokenizer_falls_back_to_labeled_approximation():
    count, source = tokenize_or_approx("http://127.0.0.1:1/v1", "one two three")
    assert count > 0
    assert source == "approx"
