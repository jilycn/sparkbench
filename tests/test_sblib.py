import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from sblib import Config, chat, write_json_atomic


class _Handler(BaseHTTPRequestHandler):
    mode = "ok"

    def log_message(self, *_args):
        pass

    def do_POST(self):
        if self.mode == "http_error":
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"broken")
            return
        if self.mode == "timeout":
            time.sleep(0.2)
        payload = {
            "choices": [{"delta": {"content": "hello"}, "finish_reason": None}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 1},
        }
        final = {"choices": [{"delta": {}, "finish_reason": "length" if self.mode == "length" else "stop"}]}
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for event in (payload, final):
            self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


@pytest.fixture
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}/v1"
    finally:
        httpd.shutdown()
        thread.join()


def _result(tmp_path, server, mode="ok", budget=1):
    _Handler.mode = mode
    cfg = Config(base_url=server, model="stub", run_dir=tmp_path)
    return chat(cfg, [{"role": "user", "content": "hi"}], max_tokens=8,
                wall_budget_s=budget, tag="logic-case")


def _events(tmp_path):
    return [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]


def test_streaming_reply_records_ttft_raw_response_and_event(tmp_path, server):
    result = _result(tmp_path, server)
    assert result.status == "ok"
    assert result.text == "hello"
    assert result.ttft_s is not None
    event = _events(tmp_path)[0]
    assert event["status"] == "ok"
    assert event["request_id"].startswith("logic-case-")
    assert (tmp_path / "raw" / f"{event['request_id']}.txt").read_text() == "hello"


def test_length_finish_is_truncated(tmp_path, server):
    result = _result(tmp_path, server, mode="length")
    assert result.status == "truncated"
    assert _events(tmp_path)[0]["finish_reason"] == "length"


def test_http_error_is_recorded(tmp_path, server):
    result = _result(tmp_path, server, mode="http_error")
    assert result.status == "http_error"
    event = _events(tmp_path)[0]
    assert event["status"] == "http_error"
    assert event["http_status"] == 500
    assert event["http_body_snippet"] == "broken"


def test_wall_budget_aborts_slow_response(tmp_path, server):
    result = _result(tmp_path, server, mode="timeout", budget=0.05)
    assert result.status == "timeout"
    assert _events(tmp_path)[0]["status"] == "timeout"


def test_atomic_json_write(tmp_path):
    target = tmp_path / "nested" / "data.json"
    write_json_atomic(target, {"ok": True})
    assert json.loads(target.read_text()) == {"ok": True}
