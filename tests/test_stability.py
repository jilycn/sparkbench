import json

from stability import assess_stability, collect_events


def test_events_are_union_counted_once_across_trials(tmp_path):
    for trial, statuses in ((1, ["ok", "timeout"]), (2, ["truncated", "http_error"])):
        directory = tmp_path / f"trial_{trial}"
        directory.mkdir()
        (directory / "events.jsonl").write_text("".join(json.dumps({"status": status}) + "\n" for status in statuses))
    counts = collect_events(tmp_path)
    assert counts == {"timeout": 1, "truncated": 1, "http_error": 1, "total": 4}


def test_stability_caps_are_explicit():
    runaway = assess_stability({"timeout": 0, "truncated": 1, "http_error": 0, "total": 1}, {"restarts": 0, "oom": 0})
    fatal = assess_stability({"timeout": 0, "truncated": 0, "http_error": 0, "total": 1}, {"restarts": 1, "oom": 0})
    assert runaway["grade_cap"] == "A-"
    assert fatal["grade_cap"] == "C"


def test_low_rate_events_in_a_long_run_do_not_zero_the_score():
    # 22 truncated + 3 timeout out of 1722 completions (the actual MLP-Only run)
    # used to floor at 0 under the old flat per-event penalty; a low single-digit
    # rate should barely dent the score and must not trip runaway.
    result = assess_stability({"timeout": 3, "truncated": 22, "http_error": 0, "total": 1722},
                               {"restarts": 0, "oom": 0})
    assert result["score100"] > 90
    assert result["runaway"] is False
    assert result["grade_cap"] is None


def test_high_rate_events_still_trigger_runaway():
    result = assess_stability({"timeout": 0, "truncated": 10, "http_error": 0, "total": 50},
                               {"restarts": 0, "oom": 0})
    assert result["runaway"] is True
    assert result["grade_cap"] == "A-"
