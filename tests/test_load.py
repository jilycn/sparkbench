from conc_eval import load_score, percentile


def test_percentiles_and_slo_score():
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile([1, 2, 3, 4], 95) == 3.85
    assert load_score(correct_rate=1.0, p95_s=15, failure_rate=0) == 100.0
    assert load_score(correct_rate=1.0, p95_s=60, failure_rate=0) == 0.0
    assert load_score(correct_rate=1.0, p95_s=20, failure_rate=0.02) == 50.0
    assert load_score(correct_rate=1.0, p95_s=20, failure_rate=0.06) == 0.0


def test_load_prompts_are_trivial_addition_service_sanity_checks():
    from conc_eval import task_stream
    prompt, answer = next(task_stream())
    assert prompt.startswith("Compute ") and "+" in prompt and "*" not in prompt
    assert 20 <= answer <= 198
