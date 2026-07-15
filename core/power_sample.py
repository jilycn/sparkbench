"""Optional GPU-power sampler; values are GPU-only, not whole-system energy."""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

from sblib import append_jsonl


def phase_energy_wh(samples, start, end):
    relevant = [sample for sample in samples if start <= sample["ts"] <= end]
    if len(relevant) < 2:
        return 0.0
    joules = sum((left["watts"] + right["watts"]) / 2 * (right["ts"] - left["ts"])
                 for left, right in zip(relevant, relevant[1:]))
    return round(joules / 3600, 6)


class PowerSampler:
    def __init__(self, path: Path):
        self.path, self.stop_event, self.thread, self.available = path, threading.Event(), None, bool(shutil.which("nvidia-smi"))

    def _sample(self):
        while not self.stop_event.is_set():
            try:
                result = subprocess.run(["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
                                        capture_output=True, text=True, timeout=5)
                watts = float(result.stdout.splitlines()[0].strip())
                append_jsonl(self.path, {"ts": time.time(), "watts": watts})
            except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
                self.available = False
                return
            self.stop_event.wait(1)

    def start(self):
        if not self.available:
            return False
        self.thread = threading.Thread(target=self._sample, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=6)


def samples_from(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
