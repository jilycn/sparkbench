#!/usr/bin/env python3
"""Generate and reference-validate seeded hidden interpreter task variants."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


VARIANTS = {
    0: ("precedence", "Variant requirement: verify arithmetic precedence and parenthesized expressions."),
    1: ("shortcircuit", "Variant requirement: verify && and || short-circuit undefined variables."),
    2: ("closures", "Variant requirement: verify independent closure state and captured reassignment."),
}


def _extra_test(name):
    cases = {
        "precedence": "def test_variant_precedence():\n    assert run('print(2 + 3 * 4); print((2 + 3) * 4);') == [14, 20]\n",
        "shortcircuit": "def test_variant_shortcircuit():\n    assert run('print(false && nope); print(true || nope);') == [False, True]\n",
        "closures": "def test_variant_closures():\n    assert run('func m() { let n = 0; func i() { n = n + 1; return n; } return i; } let a = m(); let b = m(); print(a()); print(a()); print(b());') == [1, 2, 1]\n",
        "smoke": "def test_smoke_variant():\n    assert run('print(6 * 7);') == [42]\n",
    }
    return cases[name]


def generate_agent_task(seed: int, source_root: Path, staging: Path, variant: str | None = None):
    name, requirement = ("smoke", "Development smoke variant only.") if variant == "smoke" else VARIANTS[seed % len(VARIANTS)]
    staging.mkdir(parents=True, exist_ok=True)
    hidden = (source_root / "test_interp.py").read_text() + "\n" + _extra_test(name)
    (staging / "agent_hidden_tests.py").write_text(hidden)
    shutil.copy2(source_root / "edge_probes.py", staging / "agent_edge_probes.py")
    spec = {"variant": name, "seed": seed, "requirement": requirement}
    (staging / "agent_task.json").write_text(json.dumps(spec, indent=2) + "\n")
    reference = source_root / "reference_interp.py"
    # Test source imports ``interp``; validate inside a disposable directory where the
    # committed reference implementation is deliberately exposed under that name.
    temporary = staging / "reference_check"
    temporary.mkdir()
    shutil.copy2(reference, temporary / "interp.py")
    shutil.copy2(staging / "agent_hidden_tests.py", temporary / "test_interp.py")
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "--no-header", "test_interp.py"],
                            cwd=temporary, capture_output=True, text=True, timeout=120)
    shutil.rmtree(temporary)
    if result.returncode:
        raise ValueError(f"reference validation failed: {result.stdout[-500:]} {result.stderr[-500:]}")
    return {"variant": name, "reference_validated": True,
            "files": [Path("agent_hidden_tests.py"), Path("agent_edge_probes.py"), Path("agent_task.json")]}
