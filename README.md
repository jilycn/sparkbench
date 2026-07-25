# SparkBench

[![CI](https://github.com/jilycn/sparkbench/actions/workflows/ci.yml/badge.svg)](https://github.com/jilycn/sparkbench/actions/workflows/ci.yml)

A frozen-snapshot benchmark for **local LLM serving recipes**. Current question set: **suite 2.2.1**.
Point it at any OpenAI-compatible
endpoint and it measures the whole serving experience — tool calling, multi-turn agentic coding,
logic, math under budget, adversarial long context, latency under concurrent load, and run
stability — then reports a per-axis profile with a versioned policy grade.

Built for and battle-tested on a single **NVIDIA DGX Spark (GB10, 128 GB unified memory)**, but the
harness has no hardware assumptions: it talks to `http://host:port/v1` like any client. See
[RESULTS.md](RESULTS.md) for our GB10 leaderboard and the exact serve recipes behind every score.

## Why another benchmark

Leaderboard scores measure a model. SparkBench measures a **recipe** — model + quant + engine +
flags + the box it runs on — because that's what you actually deploy. Our own results show why this
matters: models that top public reasoning leaderboards scored LOGIC 100 here and were still unusable,
because they timed out under load or drowned their answers in reasoning tokens. The single best
predictor of real-world agentic usefulness in our data is the AGENT axis, not LOGIC.

## Design principles

- **Frozen snapshot.** Every run copies the harness + generated task samples into a read-only per-run
  snapshot and re-hashes it at the end. Editing the source mid-run cannot affect a live run.
- **Budgets everywhere.** Every request carries a token budget and a wall-clock budget. Models that
  ruminate get truncated and scored accordingly — serving discipline is part of the measurement.
- **Fail closed.** A missing artifact is reported as `skipped`, never silently scored as zero. Grades
  are only issued for COMPLETE runs; partial runs show per-axis scores with no overall.
- **Sandboxed agent phase.** The agentic coding task executes model-written code inside a
  network-disabled, non-root Docker container (AST-level deny list as a second layer).
- **Event-sourced stability.** Timeouts, truncations, HTTP errors, container restarts, and kernel
  log events are recorded as first-class results, not noise.
- **Minimal dependencies.** The harness itself is pure Python 3.12+ standard library. External
  requirements: [tool-eval-bench](https://github.com/SeraphimSerapis/tool-eval-bench) for the TOOLS
  axis, Docker for the agent sandbox, `pytest` for the test suite.

## Quickstart

```bash
git clone https://github.com/jilycn/sparkbench && cd sparkbench
python3 -m venv venv && venv/bin/pip install pytest   # pytest only needed for the test suite
uv tool install tool-eval-bench                       # powers the TOOLS axis (or pipx install)

# serve your model on any OpenAI-compatible endpoint, then:
venv/bin/python sparkbench.py run my-recipe-label \
  --base-url http://localhost:8000/v1 \
  --model local-ai \
  --bench-root ./results
```

Useful variants:

```bash
--phases agent,load        # ~20 min gate run (our tier-1 screen: fail this → don't bother with full)
--container my-container   # docker container name, enables restart/oom detection in STABILITY
--trials 3                 # repeat the full phase suite N times: per-axis median + range.
                           # "verified" repeatability needs 3+ trials, no fatal event, all six
                           # non-STABILITY axes present, and every axis range <= 5.
                           # STABILITY is assessed once across the whole run, not per trial.
--seed 42                  # reproducible generated samples
--inject --power           # report-only sidebars (prompt injection, GPU power)
```

Run the test suite: `venv/bin/python -m pytest -q`.

## The seven axes

| Axis | Weight | What it measures |
|---|---:|---|
| **TOOLS** | 27% | Single-turn function calling over a fixed eval suite: valid calls, correct arguments, correct format — and *not* calling tools when it shouldn't. |
| **AGENT** | 22% | Three independent multi-turn coding families (records, dependency scheduling, ledger), one semantic variant each. Every task has 12 hidden correctness tests + 4 adversarial probes; family scores are macro-averaged to reduce task-flake variance. |
| **LOGIC** | 10% | Eight seeded puzzles sampled across four generated families. Every answer is uniquely solver-verified and every clue set is irreducible; the answer must be a terminal JSON object. |
| **MATH** | 8% | 30 seeded problems balanced 10/10/10 easy/medium/hard across 15 independently verified templates under 2048-token / 120-second per-item budgets. |
| **CONTEXT** | 10% | Ten questions over a seeded generated document: deep retrieval, compositional joins, near misses, and genuine source-authority arbitration under conflicting evidence. |
| **LOAD** | 13% | Concurrent trivial requests scored on a latency SLO: full marks at p95 ≤ 15 s, sliding to zero at 60 s. Correctness is a sanity floor (>1% wrong caps at 50; >5% zeroes). "Can the pipe survive real usage." |
| **STABILITY** | 10% | Event-sourced: timeout/truncation/HTTP-error rates plus positive restart, recreation, OOM, and filtered kernel evidence. Fatal evidence caps the grade at C; a >5% event rate caps at A-. Lost container observability makes the run INVALID rather than blaming the server. |

Grade policy ([docs/SCORING.md](docs/SCORING.md)): any fatal server event caps the grade at C; any
scored-phase truncation/runaway caps at A-. The grade is a summary — read the profile.

## Repository layout

```
sparkbench.py             # the driver — `run` entry point
sparkbench_report.py      # render a scorecard from a run dir
sparkbench_compare.py     # diff two comparable runs
sparkbench_leaderboard.py # regenerate the leaderboard from a bench root
core/                     # harness modules: evaluators, judges, generators, sandbox
suites/                   # reserved for intentionally committed static task data
docs/                     # canonical scoring policy + recipe notes
examples/                 # a real scorecard from the GB10 champion run
tests/                    # pytest suite (pure stdlib, no GPU needed)
```

Every run still freezes a *flat* snapshot of these files (`manifest.json` records the hashes), so a
source edit can never affect a live run regardless of layout.

## Output layout

Each run writes `<bench-root>/<label>_<timestamp>/`:

```
scores.json        # per-axis scores, weights, status, trials
scorecard.md       # human-readable report
status.json        # per-phase ok/failed/skipped
stability.json     # event counts + system observations
manifest.json      # snapshot hashes — the integrity record
trial_1/           # per-phase logs, timings, and raw/ full request transcripts
```

A real scorecard from the GB10 champion run: [examples/scorecard-qwen36-35b-fp8-nomtp.md](examples/scorecard-qwen36-35b-fp8-nomtp.md).

Tooling: `sparkbench_report.py` (render a scorecard), `sparkbench_compare.py` (diff two runs —
refuses cross-version or cross-sample comparisons), `sparkbench_leaderboard.py <bench-root>`
(regenerate the leaderboard from all runs).

## Comparability rules

Scores compare only when the scoring version, suite version, and sampled task identities match.
Suite 2.2.1 is a hard boundary: v2.1 scores remain archived exactly as recorded and are not comparable.
The leaderboard ranks only the latest COMPLETE runs in one identical-sample 2.2 cohort; other
samples are shown as non-comparable rather than mixed into the ranking.

## Credits

SparkBench stands on other people's work:

- **[tool-eval-bench](https://github.com/SeraphimSerapis/tool-eval-bench)** by SeraphimSerapis (MIT) —
  the entire TOOLS axis is a normalized run of this suite.
- **[vLLM](https://github.com/vllm-project/vllm)** and
  **[llama.cpp](https://github.com/ggml-org/llama.cpp)** — the serving engines under test.
- **Docker** — the agent-phase sandbox (network-disabled, non-root containers).
- The recipes in [RESULTS.md](RESULTS.md) build on community work: **aeon-7**'s GB10 vLLM images and
  DFlash patches, **spark-arena**'s nightly vLLM builds, **Entrpi**'s 122B installer, and quantized
  weights from **Unsloth**, **NVIDIA**, **saricles**, and the **Qwen**, **DeepSeek**, and **Gemma**
  model teams.

## License

MIT — see [LICENSE](LICENSE). Third-party tools and models retain their own licenses.
