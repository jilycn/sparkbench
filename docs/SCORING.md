# SparkBench v2 scoring policy

SparkBench is profile-first: inspect axes, latency, stability, and repeatability before using the grade.

| Axis | Weight | Policy |
|---|---:|---|
| TOOLS | 27% | Normalized external tool-eval score. |
| AGENT | 22% | Hidden-task correctness, probes, policy, and turn efficiency. |
| LOGIC | 10% | Strict final-line JSON logic answers. |
| MATH | 8% | Seeded 30-item stratified sample. |
| CONTEXT | 10% | Seeded adversarial long-context retrieval/reasoning. |
| LOAD | 13% | Latency SLO; correctness is a service-sanity floor. |
| STABILITY | 10% | Event-sourced run stability. |

LOAD measures the latency SLO: full score through p95 15s and linear decline to zero at 60s. Trivial
addition answers are only a service-sanity floor: wrong/error/truncation rate above 1% caps at 50,
and above 5% scores zero.

Any fatal server event (container restart, OOM, driver Xid) caps the policy grade at C, regardless of
volume. STABILITY's non-fatal penalty (timeouts/truncations/HTTP errors) is rate-scaled per 100
completions (v2.1+, `suite_version` "2.1"): a couple of `max_tokens` truncations in a run of hundreds
of completions is routine agentic behavior, not instability, and no longer floors the score. A run
crosses into "runaway" (caps the grade at A-) only once any event rate exceeds 5% of completions in
that run. Runs scored under `suite_version` "2-pending" used a flat per-event deduction that floored
STABILITY at 0 for nearly any non-trivial AGENT-phase run — treat that field as uninformative on those
older runs; the other six axes are unaffected by this change.

Partial runs have no overall or grade and show stability as N/A. The optional INJECT, STRESS, PROBE,
and POWER sidebars are report-only. Power is a GPU-only estimate, not whole-system energy.

Scores compare directly only when scoring version, suite version, and sampled identities match.
