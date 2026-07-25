# Mistral-Small-4-119B-2603-NVFP4 — PR #222 recipe (SparkOps key: `mistral-small4-119b-nvfp4`)

**STATUS: PARKED (register-only).** Per gpt-5.6-sol decision D2 (thread
`bench-prep-4-candidates`, 2026-07-25): the evidence base (open PR + forum thread, no solo-GB10
published benchmark numbers) does not yet meet the candidate bar. Registered for readiness; do
not stage or bench until the bar is met and the user authorizes.

Every engine flag below is transcribed from eugr/spark-vllm-docker **PR #222** (open, unmerged),
fork `blauerberg/spark-vllm-docker` @ commit `876c20311a94`:

- Recipe yaml: `https://raw.githubusercontent.com/blauerberg/spark-vllm-docker/876c20311a94/recipes/mistral-small-4-119b-2603-nvfp4.yaml`
  (captured copy at `docs/recipes/prep/mistral_recipe.yaml`,
  sha256 `0708d019db869a3e01e70807687878eef85a4270aee7fdeed7388a89404c0913`)
- PR: `https://github.com/eugr/spark-vllm-docker/pull/222` — recipe follows Mistral's official
  HF model-card serving section; `solo_only: true` (GB10-unified targeted); deployment history:
  NVIDIA forum thread 363863.
- PR metadata capture: `docs/recipes/prep/pr222.json`
  (sha256 `cd7cac6403e8b748ef5fc67a41f95056212a1c200f4783145896160a931ec5b2`)

Model: `mistralai/Mistral-Small-4-119B-2603-NVFP4` @ revision
`b1a9048590131d38491bd23a7c9f6ed0962f0358` (70.8 GB, Mistral-native format, 36 layers, MLA
kv_lora_rank 256 + qk_rope 64, MoE 128 experts / 4 per token + 1 shared, native ctx 1M
llama4-scaled, recipe caps 262144).

## Resolved verbatim command (placeholders → the yaml's own `defaults` map)

```
vllm serve mistralai/Mistral-Small-4-119B-2603-NVFP4
--served-model-name local-ai
--host 0.0.0.0
--port 8000
--max-model-len 262144
--gpu-memory-utilization 0.8
--attention-backend TRITON_MLA
--tool-call-parser mistral
--enable-auto-tool-choice
--reasoning-parser mistral
--max-num-batched-tokens 16384
--max-num-seqs 4
```

## Deviations from source (recorded, human-approved)

| item | source | ours | reason |
|---|---|---|---|
| runtime mod `mods/fix-mistral-small-4-119b-2603-nvfp4` | applies vllm-project/vllm PR #41119 diff at container start | **omitted** | #41119 merged upstream 2026-05-11 and is contained in the 0.26-era pinned image; the mod script itself no-ops ("skipping") when the patch cannot apply. sol decision D2. |
| `--max-num-seqs` | absent from yaml | `4` | sol decision D5: specify a conservative concurrency cap for the 70.8 GB model on unified memory (matches sibling solo Spark recipes' seqs=4). |
| `--served-model-name` | absent | `local-ai` | SparkBench/gateway endpoint contract (standing operator alias) |
| build_args `--tf5` | eugr build alias | n/a | deprecated tag alias; resolved by pinning the nightly digest directly |

## Image

`ghcr.io/spark-arena/dgx-vllm-eugr-nightly@sha256:a7f4917477eca584b271b0587dd48abf0f68657c4a2d93f7265402097be45404`
(tag `2026072502`, CI-tested nightly) per sol decision D4.

## Fit math (GB10 unified, ~119 GiB usable) — tightest of the current candidates

Weights 70.8 GB + MLA KV = 36 layers × (256 + 64) × 2 B ≈ 23,040 B/token → 6.04 GiB per
262,144-token sequence + ~7 GiB runtime overhead ≈ 84 GiB vs budget 0.8 × 119 = 95.2 GiB.
OS retains ~24 GiB outside budget. NOTE (sol D5): SparkOps `fit`'s generic 10 KB/token constant
UNDERESTIMATES this model's KV — use this doc's 23 KB/token figure, never bare `fit` output.
