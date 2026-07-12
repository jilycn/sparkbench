# SparkBench

One-command benchmark for local LLM serving recipes (model + quant + image + parser +
flags) on OpenAI-compatible endpoints. Built for the DGX Spark, works anywhere.
It measures six ability axes (incl. STABILITY) plus speed, then prints a per-category scorecard with a
weighted overall score and a letter grade that stability failures can cap.

```
| Category | Raw      | Score /100 | Weight | Weighted |
|----------|----------|------------|--------|----------|
| TOOLS    | 90/100   | 90.0       | 27%    | 24.3     |
| AGENT    | 61/70    | 87.1       | 22%    | 19.2     |
| REASON   | 51/60    | 85.0       | 18%    | 15.3     |
| CONTEXT  | 25/30    | 83.3       | 13%    | 10.8     |
| LOAD     | 20/20    | 100.0      | 10%    | 10.0     |
| STABILITY| 100/100  | 100.0      | 10%    | 10.0     |
| OVERALL  |          |            |        | 89.6/100 — grade A- |
```

## What it tests

| Axis | What | How |
|---|---|---|
| TOOLS (27%) | tool selection among 52 tools, schema discipline, multi-turn state, injection resistance | [tool-eval-bench] full 63-scenario suite |
| AGENT (22%) | sustained agentic coding: build a working language interpreter against a hidden pytest suite, up to 20 tool-use turns | `agent_build_r2.py` + `judge.py` (hidden tests 40 + unseen edge probes 10 + static code quality 10 + efficiency 10) |
| REASON (18%) | 10 logic puzzles + 10 multi-step math problems | `logic_eval.py`, `qa_eval.py`; every answer brute-force/programmatically verified |
| CONTEXT (13%) | 6 questions over a 45k-token synthetic ops log requiring cross-document joins | `qa_eval.py` with `longctx_doc.txt` |
| LOAD (10%) | answer correctness under 4-way concurrent load (not just throughput) | `conc_eval.py` |
| SPEED (sidebar) | pp/tg t/s, TTFT at depth/concurrency | parsed from tool-eval-bench `--perf` |
| Forensics (report) | does the stack emit reasoning_content? 5 configs probed | `think_probe.py` |

STABILITY (10%) is scored per run: start at 100, deduct per event — runaway −40,
request timeout −20, HTTP error −15, invalid tool call −10, container restart −60,
NVRM/OOM kernel warning −10, server dead after run −60. System evidence (restart
counts, kernel events, liveness) is captured automatically into stability_sys.json.
On top of the score, hard failures also cap the grade: any runaway (a response truncated at the token
cap) caps the grade at B; any crash/OOM caps at C. A fast model that melts under
pressure cannot grade A.

## Requirements

- An OpenAI-compatible endpoint serving ONE model (default `http://localhost:8000/v1`,
  served-model-name `local-ai`)
- `tool-eval-bench` on PATH or in `~/.local/bin` (install: `uv tool install tool-eval-bench`)
- Python 3.10+ and a venv with pytest (see Install)

## Install

```bash
cd ~/sparkbench
python3 -m venv venv
venv/bin/pip install pytest
chmod +x sparkbench.sh
```

## Run

```bash
# benchmark whatever is serving on :8000
./sparkbench.sh my-recipe-name

# custom endpoint
./sparkbench.sh my-recipe-name http://otherhost:8000/v1
```

Takes ~60–90 minutes. Results land in `~/bench/sparkbench/<label>_<timestamp>/`:

```
scorecard.md / scorecard.json   <- the result
sparkbench.log                  <- full run log
tool-eval.rich.txt              <- raw 63-scenario output + perf tables
round2/  metrics.json transcript.json interp.py score.json reasoning_audit.json
round3/  math_answers.json longctx_answers.json conc_results.json think_report.json score3.json
```

Compare recipes by diffing their `scorecard.md`. All raw per-turn data (finish_reasons,
token counts, reasoning sizes) is kept, so any score can be audited down to the request.

## Fixed test conditions (do not change between recipes)

- Sampling: temperature 0.6, top_p 0.95, top_k 20 (Qwen-style thinking-safe; temp 0
  causes repetition runaways in thinking models and invalidates results)
- max_tokens 120k for agent/reasoning tasks, 8k concurrency, 16k forensics
- Every question runs in an isolated request; agent task capped at 20 turns

## Regenerating suites (optional)

Suites ship pre-generated and verified. To regenerate (e.g., to prevent contamination
after a model has seen them):

```bash
venv/bin/python gen_logic.py     # brute-force-verifies unique answers, else asserts
venv/bin/python gen_math.py      # recomputes programmatic ground truth
venv/bin/python gen_longctx.py   # rebuilds 45k-token doc + planted facts
```

Change the `random.seed(...)` in each generator to get a fresh variant. Generators
self-verify: a non-unique puzzle or contaminated document fails generation.

The AGENT hidden suite (`test_interp.py`) is fixed; validate any edit by confirming a
reference solution still passes 31/31 and `edge_probes.py` scores 10/10.

## Caveats

- One model per endpoint at a time (on 128GB Spark, two models = OOM)
- The endpoint must allow 120k-token completions (`--max-model-len` ≥ ~130k)
- Scores are comparable ONLY across runs with identical suites and sampling
- tool-eval-bench TC scenarios are its own project's; SparkBench consumes its
  normalized `Score: N / 100` line

[tool-eval-bench]: https://pypi.org/project/tool-eval-bench/
