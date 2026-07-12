"""Shared, dependency-free SparkBench v2 runtime helpers."""

from __future__ import annotations

import dataclasses
import json
import os
import socket
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


@dataclasses.dataclass
class Config:
    base_url: str
    model: str
    run_dir: Path
    api_key: str | None = None
    _counter: int = dataclasses.field(default=0, init=False, repr=False)
    _counter_lock: threading.Lock = dataclasses.field(default_factory=threading.Lock, init=False, repr=False)

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            base_url=os.environ.get("SPARKBENCH_BASE_URL", "http://localhost:8000/v1"),
            model=os.environ.get("SPARKBENCH_MODEL", "local-ai"),
            run_dir=Path(os.environ.get("SPARKBENCH_RUN_DIR", ".")),
            api_key=os.environ.get("SPARKBENCH_API_KEY"),
        )

    def next_request_id(self, tag: str) -> str:
        safe_tag = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in tag).strip("-") or "request"
        with self._counter_lock:
            self._counter += 1
            return f"{safe_tag}-{self._counter:04d}"


@dataclasses.dataclass
class ChatResult:
    text: str
    finish_reason: str | None
    status: str
    latency_s: float
    ttft_s: float | None
    prompt_tokens: int | None
    completion_tokens: int | None
    request_id: str
    error: str | None = None


def write_json_atomic(path: str | Path, obj: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(obj, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def append_jsonl(path: str | Path, obj: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(obj, separators=(",", ":")) + "\n").encode("utf-8")
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def _content_from_event(event: dict[str, Any]) -> str:
    choice = (event.get("choices") or [{}])[0]
    delta = choice.get("delta") or choice.get("message") or {}
    content = delta.get("content") or ""
    if isinstance(content, list):
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return str(content)


def _event_finish_reason(event: dict[str, Any]) -> str | None:
    choices = event.get("choices") or []
    return choices[0].get("finish_reason") if choices else None


def _event_usage(event: dict[str, Any]) -> tuple[int | None, int | None]:
    usage = event.get("usage") or {}
    return usage.get("prompt_tokens"), usage.get("completion_tokens")


def _write_raw(cfg: Config, request_id: str, text: str) -> None:
    raw_dir = cfg.run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / f"{request_id}.txt"
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=raw_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def chat(
    cfg: Config,
    messages: list[dict[str, Any]],
    *,
    max_tokens: int,
    wall_budget_s: float,
    tag: str,
    temperature: float = 0.6,
    top_p: float = 0.95,
    extra: dict[str, Any] | None = None,
) -> ChatResult:
    """Make one budgeted OpenAI-compatible streaming chat request and record its artifact."""
    request_id = cfg.next_request_id(tag)
    started = time.monotonic()
    payload: dict[str, Any] = {
        "model": cfg.model,
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if extra:
        payload.update(extra)
    headers = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"
    request = urllib.request.Request(
        cfg.base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
    )

    text_parts: list[str] = []
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    ttft_s: float | None = None
    status = "ok"
    error: str | None = None
    response = None
    try:
        response = urllib.request.urlopen(request, timeout=max(0.01, wall_budget_s))
        while True:
            elapsed = time.monotonic() - started
            if elapsed >= wall_budget_s:
                raise TimeoutError("wall budget exceeded")
            remaining = max(0.01, wall_budget_s - elapsed)
            raw_socket = getattr(getattr(response, "fp", None), "raw", None)
            sock = getattr(raw_socket, "_sock", None)
            if sock is not None:
                sock.settimeout(remaining)
            line = response.readline()
            if not line:
                break
            if not line.startswith(b"data:"):
                continue
            value = line[5:].strip()
            if value == b"[DONE]":
                break
            try:
                event = json.loads(value)
            except json.JSONDecodeError:
                continue
            piece = _content_from_event(event)
            if piece and ttft_s is None:
                ttft_s = time.monotonic() - started
            text_parts.append(piece)
            finish_reason = _event_finish_reason(event) or finish_reason
            pt, ct = _event_usage(event)
            prompt_tokens = pt if pt is not None else prompt_tokens
            completion_tokens = ct if ct is not None else completion_tokens
    except urllib.error.HTTPError as exc:
        status = "http_error"
        error = f"HTTP {exc.code}"
    except (TimeoutError, socket.timeout, urllib.error.URLError) as exc:
        status = "timeout"
        error = str(exc)[:200]
    except Exception as exc:  # transport failures are reported rather than crashing a phase
        status = "http_error"
        error = f"{type(exc).__name__}: {exc}"[:200]
    finally:
        if response is not None:
            response.close()

    if status == "ok" and finish_reason == "length":
        status = "truncated"
    latency_s = time.monotonic() - started
    text = "".join(text_parts)
    _write_raw(cfg, request_id, text)
    append_jsonl(cfg.run_dir / "events.jsonl", {
        "request_id": request_id,
        "ts": time.time(),
        "phase": tag,
        "status": status,
        "finish_reason": finish_reason,
        "latency_s": round(latency_s, 6),
        "ttft_s": round(ttft_s, 6) if ttft_s is not None else None,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "wall_budget_s": wall_budget_s,
        "max_tokens": max_tokens,
        "error": error,
    })
    return ChatResult(text, finish_reason, status, latency_s, ttft_s, prompt_tokens,
                      completion_tokens, request_id, error)
