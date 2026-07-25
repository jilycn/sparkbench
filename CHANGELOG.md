# Changelog

## Suite 2.2.1 - 2026-07-25

- Repaired the answer parser. Suite 2.2 accepted a terminal JSON answer only when the whole object
  fitted on the last physical line, so a model that pretty-printed an otherwise compliant answer was
  graded wrong. Judging now decodes with `raw_decode` and requires the decode to consume the reply
  through its final character, which also makes the parser safe against braces inside string values
  and prevents an earlier object from outranking a later contradictory one.
- The contract is unchanged. Replies that append prose or a closing code fence after the answer
  object still fail it. Crediting those envelopes would be a scoring-policy change and is not made
  here.
- Judges now report why an item was not graded instead of collapsing every failure into `None`, and
  each JSON-answer suite carries an unweighted, report-only `format_compliance` block. Every
  response is classified on its own: it counts as evaluable only when it arrived intact with a
  transcript, and compliant only when it is evaluable and meets the contract, so a truncated reply
  that happens to end in a valid object is not read as compliance.
- Rescored runs are selected through `core/scoreio.py`, which prefers a `.v221` sidecar only when its
  record verifies the frozen harness, reports no missing transcripts, carries input and judge
  hashes, and agrees with the sidecar it vouches for including its hash. The leaderboard and compare
  tool both go through it, and a run whose rescore was refused stays visible at its recorded score.
- The injection probe reports `semantic_pass` separately from `format_compliant`. A correct answer
  in a code fence was previously recorded as a failed injection defence.
- Fixed a latent comparison hole: Python evaluates `True == 1`, so a boolean answer could satisfy an
  integer expectation.
- Archived 2.2 runs were re-graded from their preserved transcripts by `rescore_v221.py` into
  `.v221.json` sidecars, leaving every published artifact untouched. Across seven runs, four items
  regraded, all in `holo31-35b-nvfp4-arena-b` (73.0 to 77.4). No other run moved.
- Questions, prompts, phases and weights are unchanged from suite 2.2, so 2.2.1 values are
  backward-migratable rather than a clean break. Strict-graded 2.2 numbers as originally published
  are not point-comparable with 2.2.1 values; re-grade them first.

## Suite 2.2 — 2026-07-24

- Replaced ten public LOGIC puzzles with an eight-item deterministic sample from a 24-item,
  solver-verified generated pool. Distance clues use an explicit positional convention and a
  materialization-time alternate-reading guard.
- Expanded MATH to 15 independently verified templates while retaining a balanced 30-item sample;
  reports now include easy/medium/hard splits.
- Replaced the single brittle AGENT interpreter task with three independent semantic task families,
  each carrying 12 hidden correctness tests and 4 adversarial probes.
- Made CONTEXT conflicts genuine authority-arbitration questions and retained compositional and
  near-miss cases.
- Pinned TOOLS provenance with package version, suite content hash, and explicit sampling parameters.
- Removed dead probe/stress flags and committed generated-suite artifacts; consolidated scoring into
  one canonical policy.
- Established a hard suite-version boundary: suite 2.1 remains archived and is never ranked or
  point-compared with suite 2.2.

## Suite 2.1 — archived

- Introduced seeded, budgeted math, rate-scaled stability, frozen snapshots, multi-trial reporting,
  fail-fast endpoint handling, optional injection/power sidebars, and version-aware comparison.
- Suite 2.1 results remain stored as originally scored. They are not rescored into suite 2.2.
