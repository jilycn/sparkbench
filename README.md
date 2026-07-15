# SparkBench

[![CI](https://github.com/jilycn/sparkbench/actions/workflows/ci.yml/badge.svg)](https://github.com/jilycn/sparkbench/actions/workflows/ci.yml)

A frozen-snapshot benchmark for **local LLM serving recipes**. Point it at any OpenAI-compatible
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
- **Zero runtime dependencies.** Pure Python 3.12+ standard library. `pytest` for the test suite,
  Docker for the agent sandbox.

## Quickstart

```bash
git clone https://github.com/jilycn/sparkbench && cd sparkbench
python3 -m venv venv && venv/bin/pip install pytest   # pytest only needed for the test suite

# serve your model on any OpenAI-compatible endpoint, then:
venv/bin/python sparkbench.py run my-recipe-label \
  --base-url http://localhost:8000/v1 \
  --model local-ai \
  --bench-root ./results
```

Useful variants:

```bash
--phases agent,load        # ~20 min gate run (our tier-1 screen: fail this → don't bother with full)
--trials 3                 # repeatability: medians + ranges across trials
--container my-container   # docker container name, enables restart/oom detection in STABILITY
--seed 42                  # reproducible generated samples
--probe --inject --power   # report-only sidebars (edge probes, prompt injection, GPU power)
```

Run the test suite: `venv/bin/python -m pytest -q`.

## The seven axes

| Axis | Weight | What it measures |
|---|---:|---|
| **TOOLS** | 27% | Single-turn function calling over a fixed eval suite: valid calls, correct arguments, correct format — and *not* calling tools when it shouldn't. |
| **AGENT** | 22% | Multi-turn agentic coding: the model must build a working language interpreter through tool use (write file / run tests) inside the sandbox. Scored on a hidden test suite (40), unseen generalization probes (10), static code quality — no `eval` cheating, structured code (10), turn efficiency with penalties per truncation/invalid call (10), plus exact-JSON logic puzzles (30). See [SCORING_AGENT.md](SCORING_AGENT.md). |
| **LOGIC** | 10% | Brute-force-verified logic puzzles; answers must be exact final-line JSON. Reasoning *with format discipline*. |
| **MATH** | 8% | 30 seeded, stratified problems under a tight budget (2048 tokens / 120 s). Punishes models that need long chain-of-thought to compute. |
| **CONTEXT** | 10% | Adversarial long-context retrieval + reasoning over a generated document. Verifies the advertised window actually works. |
| **LOAD** | 13% | Concurrent trivial requests scored on a latency SLO: full marks at p95 ≤ 15 s, sliding to zero at 60 s. Correctness is a sanity floor (>1% wrong caps at 50; >5% zeroes). "Can the pipe survive real usage." |
| **STABILITY** | 10% | Event-sourced: timeouts, truncations, HTTP errors, container restarts, OOM/dmesg. *Known limitation: current zero-out policy is too strict and non-discriminating; a rate-scaled version is planned (see CHANGELOG).* |

Grade policy (`SCORING.md`): any fatal server event caps the grade at C; any scored-phase
truncation/runaway caps at A-. The grade is a summary — read the profile.

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
The leaderboard enforces this: legacy runs are shown but never ranked against current ones.

## License

MIT — see [LICENSE](LICENSE).
