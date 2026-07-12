# SparkBench v2

SparkBench is a frozen-snapshot benchmark for local OpenAI-compatible LLM serving recipes. It measures
tools, agentic coding, logic, sampled math, adversarial long context, load behavior, and stability. The
report leads with that profile; the grade is a versioned policy summary, not a substitute for it.

```bash
~/sparkbench-v2/venv/bin/python ~/sparkbench-v2/sparkbench.py run recipe-label \
  --base-url http://localhost:8000/v1 --model local-ai
```

Use `--phases math` for a partial, per-axis run; `--trials 3` for repeatability; `--inject` and
`--power` for report-only sidebars. Every run freezes the harness, generated samples, and manifest before
testing. A source edit cannot affect a live run.

Results are written under `~/bench/sparkbench/`. Compare only matched samples with
`sparkbench_compare.py`; use the leaderboard for latest comparable COMPLETE v2 results. See
`SCORING.md` for exact weights/budgets and `docs/CUTOVER.md` for the operator-only switch procedure.
