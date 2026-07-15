# Round 3 Scoring Standard — 80 points + forensics report, fully automated (judge3.py)

## Part C — Math Reasoning (30 pts)
- 10 multi-step problems × 3 pts, exact-match JSON answer
- All problems GENERATED with seeded random numbers; ground truth computed
  programmatically (no memorized answers possible)
- Types: discount chain+tax, work rate, mixture, compound interest, meeting trains,
  LCM scheduling, combinatorics, modular exponentiation, average-after-removal, linear system
- Floats graded with ±0.01 tolerance; integers exact
- Malformed/missing JSON = 0 for that problem

## Part D — Long-Context Reasoning (30 pts)
- Synthetic 45k-token ops log with planted facts among ~2,600 distractor entries
- 6 questions × 5 pts, exact-match, each requiring genuine retrieval or linking:
  - lc1: SUM of two budget figures planted ~40k tokens apart (retrieve + arithmetic)
  - lc2: team of the key-rotation person (two facts 30k tokens apart, join required)
  - lc3: COUNT incidents for one server (aggregate across whole doc)
  - lc4: version deployed the day a person transferred (temporal join)
  - lc5: recall unique codename (single deep needle)
  - lc6: the two incident dates (multi-needle, ordered list)
- Contamination-guarded: filler entries use fixed person→team mapping and never
  mention planted entities, so no contradictory ground truth

## Part E — Concurrency Correctness (20 pts)
- 4 parallel workers × 5 sequential arithmetic tasks (20 unique, exact integer answers)
- Score = correct/20 × 20, minus 2 per HTTP error (floor 0)
- Also reports wall time, per-request latency min/avg/max under load
- Tests batched-decode correctness — not just throughput

## Part F — Thinking Forensics (report only, not scored)
- 5 configs probed: default, enable_thinking true/false via chat_template_kwargs,
  /think and /no_think soft switches
- Records per config: reasoning_content length, content length, completion tokens,
  raw <think> tag leakage, finish_reason
- Resolves whether the serve stack can emit separated reasoning at all

## Stability Gates (reported, not scored)
- ZERO HTTP errors / crashes / OOM during run; server healthy after
- Any runaway (finish_reason=length on a QA task) flagged with token count

## Rules
- Same sampling for all models: temp 0.6, top_p 0.95, top_k 20, max_tokens 120k
  (concurrency tasks capped 8k; forensics 16k)
- Every question isolated (no shared conversation state)
- Judge is a script (judge3.py); suite validated by smoke test before any model runs
- Order m2 → m1 → m3, chained automatically after round 2 completes
