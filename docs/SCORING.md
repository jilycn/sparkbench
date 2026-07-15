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

Any fatal server event caps the policy grade at C. Any scored-phase truncation/runaway caps it at A-.
Partial runs have no overall or grade and show stability as N/A. The optional INJECT, STRESS, PROBE,
and POWER sidebars are report-only. Power is a GPU-only estimate, not whole-system energy.

Scores compare directly only when scoring version, suite version, and sampled identities match.
