import json

from stability import assess_stability, collect_events


def test_events_are_union_counted_once_across_trials(tmp_path):
    for trial, statuses in ((1, ["ok", "timeout"]), (2, ["truncated", "http_error"])):
        directory = tmp_path / f"trial_{trial}"
        directory.mkdir()
        (directory / "events.jsonl").write_text("".join(json.dumps({"status": status}) + "\n" for status in statuses))
    counts = collect_events(tmp_path)
    assert counts == {"timeout": 1, "truncated": 1, "http_error": 1}


def test_stability_caps_are_explicit():
    runaway = assess_stability({"timeout": 0, "truncated": 1, "http_error": 0}, {"restarts": 0, "oom": 0})
    fatal = assess_stability({"timeout": 0, "truncated": 0, "http_error": 0}, {"restarts": 1, "oom": 0})
    assert runaway["grade_cap"] == "A-"
    assert fatal["grade_cap"] == "C"
