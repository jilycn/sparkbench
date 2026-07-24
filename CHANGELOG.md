# Changelog

## Suite 2.2 — 2026-07-24

- Replaced ten public LOGIC puzzles with an eight-item deterministic sample from a 24-item,
  solver-verified generated pool.
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
