"""Fail-fast breaker + fail-closed stability (2026-07-24, from Codex-review backlog)."""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "core"))
import sblib
from stability import assess_stability, system_delta


class _Cfg:
    def __init__(self, run_dir):
        self.run_dir = run_dir


def _reset():
    sblib._instant_failures = 0


def test_breaker_trips_on_consecutive_instant_failures(tmp_path):
    _reset()
    cfg = _Cfg(tmp_path)
    for _ in range(sblib.ENDPOINT_DOWN_THRESHOLD - 1):
        sblib._endpoint_breaker(cfg, "timeout", 0.05)
    with pytest.raises(sblib.EndpointDown):
        sblib._endpoint_breaker(cfg, "http_error", 0.05)
    assert (tmp_path / "ENDPOINT_DOWN").exists()


def test_breaker_ignores_slow_model_timeouts(tmp_path):
    _reset()
    cfg = _Cfg(tmp_path)
    for _ in range(sblib.ENDPOINT_DOWN_THRESHOLD * 2):
        sblib._endpoint_breaker(cfg, "timeout", 240.0)  # real model timeout, full budget
    assert not (tmp_path / "ENDPOINT_DOWN").exists()


def test_breaker_resets_on_success(tmp_path):
    _reset()
    cfg = _Cfg(tmp_path)
    for _ in range(sblib.ENDPOINT_DOWN_THRESHOLD - 1):
        sblib._endpoint_breaker(cfg, "timeout", 0.05)
    sblib._endpoint_breaker(cfg, "ok", 1.2)
    for _ in range(sblib.ENDPOINT_DOWN_THRESHOLD - 1):
        sblib._endpoint_breaker(cfg, "timeout", 0.05)
    assert not (tmp_path / "ENDPOINT_DOWN").exists()


def _snap(requested=True, observed=True, cid="aaa", restarts=0):
    return {"restarts": restarts, "oom": False, "dmesg_count": 0,
            "container_requested": requested, "container_observed": observed,
            "container_id": cid}


def test_recreated_container_is_fatal():
    delta = system_delta(_snap(cid="aaa"), _snap(cid="bbb"))
    assert delta["recreated"] is True
    assert assess_stability({"total": 100}, delta)["fatal"] is True


def test_lost_observability_is_fatal():
    delta = system_delta(_snap(observed=True), _snap(observed=False))
    assert delta["observability_lost"] is True
    assert assess_stability({"total": 100}, delta)["fatal"] is True


def test_unrequested_container_not_fatal():
    delta = system_delta(_snap(requested=False, observed=False, cid=None),
                         _snap(requested=False, observed=False, cid=None))
    assert delta["observability_lost"] is False
    result = assess_stability({"total": 100}, delta)
    assert result["fatal"] is False


def test_same_container_healthy_not_fatal():
    delta = system_delta(_snap(), _snap())
    assert assess_stability({"total": 100}, delta)["fatal"] is False
