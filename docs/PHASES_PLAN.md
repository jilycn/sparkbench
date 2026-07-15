# SparkBench — per-phase runs + per-axis scoring + model compare (DRAFT for Codex review)

> Implement task-by-task, TDD where practical, commit per task. **Draft — under review, don't code yet.**

**Goal:** Let each SparkBench axis run **individually** and still score, so two models can be compared
on a single axis (e.g. just math). Add a compare tool. Fully backward-compatible: a bare
`sparkbench.sh <label>` still runs all 6 axes and produces today's scorecard unchanged.

**Where:** `~/sparkbench/` (NOT a git repo — back up before touching; it is also the tool a live bench
executes, so NEVER edit files while a bench runs — stage on copies, swap in when idle).

## Axes → phase scripts (current)
- TOOLS+SPEED → `tool-eval-bench` (external) → `tool-eval.rich.txt`
- AGENT → `agent_build_r2.py` → `round2/`
- REASON-logic → `logic_eval.py` + `judge.py` → `round2/`
- REASON-math → `qa_eval.py math_suite.json` → `round3/`
- CONTEXT → `qa_eval.py longctx_suite.json` → `round3/`
- LOAD → `conc_eval.py` → `round3/`
- STABILITY → sys snapshot → `stability_sys.json`
- SCORECARD → `sparkbench_report.py` reads the above → `scorecard.md`

## Constraints
- **Backward compatibility is sacred.** `sparkbench.sh <label>` with no phase arg MUST behave exactly
  as today (all axes, same scorecard). A regression here breaks live benching.
- No edits to any file while a bench is running. Develop on `*.new` copies; deploy when `:8000` is idle.
- Per-axis normalization/weights must match today's `sparkbench_report.py` exactly (no silent rescoring).

---

### Task 1: `sparkbench_report.py` emits per-axis `scores.json` + partial-aware overall

**Files:** Modify `sparkbench_report.py` (on a copy `sparkbench_report.py.new` first); add
`test_report_scoring.py`.

**Interfaces:** Report always writes `scores.json`:
```json
{ "label": "...", "axes": { "MATH": {"raw":"51/60","score":85.0,"weight":0.18,"weighted":15.3}, ... },
  "present": ["TOOLS","MATH",...], "complete": false,
  "overall": null, "grade": null }        // overall+grade only when all axes present
```
When all axes present → compute `overall`/`grade` exactly as today + write `scorecard.md` as today.
When partial → `scorecard.md` shows the present axes + "PARTIAL — axes: MATH" and no overall.

- [ ] TDD: feed a fixture artifact dir with only math → `scores.json` has MATH axis + `complete:false`,
  `overall:null`; feed a full dir → identical overall/grade to the current implementation (golden).
- [ ] Commit `feat(sparkbench): per-axis scores.json + partial-aware scorecard`.

---

### Task 2: `sparkbench.sh --phases <csv>` selector (backward compatible)

**Files:** Modify `sparkbench.sh` (on `sparkbench.sh.new`); add `test_phase_selector.sh` (bats-style or
a shell test).

**Interfaces:** `sparkbench.sh <label> [--phases all|tools,agent,logic,math,context,load]`. Default
(arg absent) = `all` → today's exact sequence. Each phase block guarded by
`want <name>` (a helper that returns true if the phase is selected). The `[0/6] server ready` gate and
stability snapshot always run. `[6/6] SCORECARD` always runs (it now scores whatever is present).

- [ ] TDD: `--phases math` runs only qa_eval math + scorecard (assert other round2/round3 artifacts are
  absent and scores.json has only MATH); bare invocation runs all (assert all axes present). Verify
  `bash -n sparkbench.sh.new` is clean BEFORE any deploy.
- [ ] Commit `feat(sparkbench): --phases selector, all by default`.

---

### Task 3: `sparkbench_compare.py` — two (or N) runs, per-axis, one axis or all

**Files:** Create `sparkbench_compare.py`; add `test_compare.py`.

**Interfaces:** `sparkbench_compare.py <labelA> <labelB> [--axis MATH] [--bench-root ~/bench/sparkbench]`
— locate each label's newest run dir, read its `scores.json`, print a table:
```
axis     A(label_a)   B(label_b)   Δ
MATH     85.0         78.3         +6.7
```
`--axis MATH` restricts to one axis. If a run lacks the requested axis, say so (don't invent). Also
`--json` for machine output. N-way if >2 labels given.

- [ ] TDD: two fixture `scores.json` → correct per-axis diff; `--axis MATH` restricts; missing axis is
  reported not fabricated. Commit `feat(sparkbench): compare runs by axis`.

---

### Task 4: deploy safely + docs

**Files:** Swap `*.new` → real files (only when `:8000` idle / no bench running); update
`~/sparkbench/README.md` with the new usage; note in `~/bench/RECIPES.md` (via a copy, not while a
bench runs).

- [ ] Verify: run `sparkbench.sh <tmplabel> --phases math` against a live model end-to-end, confirm a
  MATH-only `scores.json` + partial scorecard; run a full bench and confirm the overall matches the
  pre-change golden. Commit `chore(sparkbench): deploy phase-selectable scoring + docs`.

---

## Open questions for Codex
1. Is splitting REASON into separate `math` and `context` (longctx) axes correct, or keep them fused
   as today's phase 4? (They share `round3/` + `qa_eval.py`.)
2. STABILITY is measured across the whole run — does a single-phase run produce a meaningful STABILITY
   score, or should STABILITY be marked N/A for partial runs?
3. Backward-compat risk: any phase that implicitly depends on an earlier phase's artifact? (e.g. does
   the scorecard or a judge step assume round2 exists when only math ran?) Enumerate cross-phase deps.
4. Golden-score safety: best way to prove the full-run overall is byte-identical to today's before we
   deploy?
