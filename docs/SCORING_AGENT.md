# Round 2 Scoring Standard — 100 points total, fully automated (judge.py)

## Part A — Interpreter Build (70 pts)

### A1. Hidden test suite (40 pts)
- 30 hidden tests, proportional: `passed/30 × 40`
- Tests cover: arithmetic, variables, scoping, if/else, while, functions,
  closures, recursion, mutual recursion, higher-order functions, shadowing,
  error cases (undefined var, arity mismatch), deep recursion (no stack death)

### A2. Unseen edge probes (10 pts)
- 10 additional probes NOT in the hidden suite, run by judge after the fact
- 1 pt each. Measures generalization vs overfitting to observed failures.

### A3. Code quality — static, automated (10 pts)
| Check | Pts |
|---|---|
| No `eval`/`exec`/`compile` anywhere (using Python eval = cheating, contract bans it) | 3 |
| No bare `except:` (must catch specific exceptions) | 2 |
| Structured: ≥ 5 functions/methods or classes (not one giant blob) | 2 |
| Deep-recursion safe: judge runs 500-deep recursion probe without RecursionError crash | 2 |
| Size sanity: file ≤ 30 KB (no padded/dead code) | 1 |

### A4. Agentic efficiency (10 pts)
- Converged ≤6 turns: 10 · ≤9: 8 · ≤12: 6 · ≤15: 4 · not converged: 0
- Deductions: −2 per invalid tool call, −2 per truncated (finish_reason=length) turn, −2 per HTTP error (floor 0)

## Part B — Logic Puzzles (30 pts)
- 10 brute-force-verified puzzles × 3 pts, exact-match JSON answer
- Malformed/unparseable JSON answer = 0 for that puzzle
- Each puzzle solved in isolated request, thinking ON, temp 0.6, max_tokens 120k

## Stability Gates (reported, not scored — any FAIL flags the recipe)
- ZERO server crashes / OOM / container restarts during run
- ZERO thinking-runaway turns (turn >900s without producing a tool call or answer)
- ZERO tool-call parse failures (invalid JSON args)
- Server responsive after run (health probe)

## Rules
- Same fixed harness for all models: temp 0.6, top_p 0.95, top_k 20, max_tokens 120k, thinking ON
- MAX_TURNS 20 for Part A
- Judge is a script (judge.py), no human/LLM vibes in scoring
- Suite validated solvable: reference solution must score 70/70 on Part A before any model runs
