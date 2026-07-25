# SparkBench suite 2.2.1 scoring policy

SparkBench is profile-first: inspect the seven axes, latency, stability, and repeatability before
using the policy grade. Suite 2.2.1 uses `scoring_version` `2` and `suite_version` `2.2.1`. It is not
point-comparable with suite 2.1 because the judged question sets changed.

| Axis | Weight | Policy |
|---|---:|---|
| TOOLS | 27% | External tool-eval score with explicit sampling parameters; package version and suite content hash are recorded and rechecked. |
| AGENT | 22% | Three independent generated coding tasks: hidden correctness, adversarial probes, policy safety, and turn efficiency. |
| LOGIC | 10% | Eight generated, uniquely solver-verified puzzles answered with a terminal JSON object. |
| MATH | 8% | Thirty generated items: 10 easy, 10 medium, and 10 hard, sampled across 15 templates. |
| CONTEXT | 10% | Ten questions over a generated long document, including genuine authority conflicts and compositional joins. |
| LOAD | 13% | Concurrent latency SLO; correctness is only a service-sanity floor. |
| STABILITY | 10% | Event-sourced, rate-scaled run stability plus positive system-failure evidence. |

## AGENT

Each run deterministically selects one semantic variant from each of three task families:
record normalization/deduplication, dependency scheduling, and transactional ledger processing.
Each family is a separate tool-use conversation and separately retained candidate, so one brittle
task cannot zero the whole axis.

Every family has 12 hidden correctness tests and 4 adversarial probes: 48 judged units across the
three tasks. The generator reference-validates every selected suite before freezing the snapshot.
AGENT has 70 raw points:

- A1 hidden correctness: 45 points, macro-averaged equally across the three families.
- A2 adversarial probes: 15 points, macro-averaged equally across the three families.
- A3 execution-policy safety: 5 points. AST denial fails this component and candidate code is never
  executed. All execution remains network-disabled, non-root, resource-capped, and fail-closed.
- A4 turn efficiency: 5 points, macro-averaged; a family must converge within its six-turn budget.

The axis score is `raw / 70 × 100`. Hidden/probe files are snapshot inputs but are never shown to
the model.

## LOGIC and MATH

LOGIC generates a 24-item pool (six per assignment, schedule, Boolean-constraint, and code-breaking
family), verifies unique solutions and irreducible clue sets, then deterministically samples two per
family. Numeric distance uses one suite-wide positional convention: the absolute difference between
the two numbered positions equals N. At materialization, every such clue is also solved under the
plausible “N intervening positions” reading; a changed answer or uniqueness rejects that clue set
and deterministically replaces it. Each item is independently requested and strict
normalization-only judging accepts only a contracted terminal JSON answer.

MATH generates a 300-item pool: 20 parameterizations of each of 15 templates, split evenly among
easy, medium, and hard. It independently recomputes every answer, then samples two per template for
30 total questions under a 2,048-token / 120-second per-item budget. The report includes
per-difficulty correct/total and score splits.

## Answer envelope and format compliance

Phase prompts ask for the answer as a single JSON object with nothing after it. Judging enforces
that contract as written: the answer object must be the last thing in the reply, decoded so that it
consumes the reply through its final character. An object may span several lines. Requiring the
decode to reach the end is what keeps the parser safe against braces inside string values and stops
an earlier object from being credited when a later, contradictory one follows.

Suite 2.2 implemented this as "the object must fit on the last physical line", which scored
compliant pretty-printed answers as wrong. Suite 2.2.1 repairs the parser. The contract itself is
unchanged: a reply that appends prose or a closing code fence after the object still does not meet
it.

Each JSON-answer suite (LOGIC, MATH, CONTEXT) reports a `format_compliance` block next to its
score. It carries counts per envelope (`strict_single_line`, `multiline_terminal`,
`fenced_terminal`, `trailing_content`, `non_dict_json`, `no_json`), a `delivery` breakdown of
runner statuses (`ok`, `timeout`, `truncated`, `http_error`), and `missing_transcripts`.

Each response is classified on its own rather than by reconciling separate totals. A response is
`format_evaluable` only when it arrived intact and its transcript exists, and `contract_compliant`
only when it is evaluable and meets the contract. `compliance_rate` is measured against the
evaluable base, so a phase full of truncations reports a small denominator instead of a flattering
rate. A truncated reply that happens to end in a valid object is not evidence that the model
complied.

Compliance is report-only and unweighted. TOOLS already measures structured output; LOGIC, MATH and
CONTEXT measure semantic correctness.

## CONTEXT

CONTEXT generates and shuffles a document and ten-question suite for the run seed. Six questions
test deep retrieval, two require composition, and two contain conflicting evidence whose answer
depends on an explicit source-authority rule rather than recency alone. Near-miss distractors avoid
lexical lookup shortcuts. The manifest records the variant and token count from `/tokenize`, with a
clearly marked approximation fallback. Cold/warm request flags are retained in the artifacts.

## LOAD and STABILITY

LOAD runs concurrency 8 for 120 seconds with at most 64 output tokens per request and thinking
disabled where the endpoint supports it. Full latency credit extends through p95 15 seconds and
declines linearly to zero at 60 seconds. Trivial addition answers are only a service-sanity floor:
wrong/error/truncation rate above 1% caps LOAD at 50; above 5% scores zero. The report retains p50,
p95, p99, aggregate request rate, and errors.

STABILITY penalties for timeout, truncation, and HTTP-error events scale by their percentage of all
recorded completions. A rate above 5% is runaway and caps the grade at A-. Positive evidence of a
container restart/recreation, OOM, or new matching kernel event is fatal and caps the grade at C.
If requested container observation cannot be established after bounded retries, the run is INVALID,
not falsely C-capped.

## Completion, trials, and sidebars

An overall score and grade exist only for a COMPLETE run with all seven axes present. Missing
artifacts are absent and listed as skipped, never invented as zero. INVALID runs refuse scoring.
For multiple trials, all trials must complete on the same frozen samples. Axis medians and ranges
are reported; repeatability is verified only for N≥3, no fatal event, and every axis spread ≤5.

INJECT and POWER are opt-in report-only sidebars. INJECT covers long-context indirect injection and
an asserted two-turn tool-result injection protocol. POWER samples `nvidia-smi` at 1 Hz and reports
GPU-only energy, not whole-system energy.

The compare tool refuses scoring-version or suite-version mismatches. Equal versions with different
seed, sampled item IDs, generated task variants, or external tool-suite hash are exploratory only,
without point deltas. `--force` overrides version refusal only and marks output NOT COMPARABLE.
