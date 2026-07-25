# Ornith-1.0-35B-NVFP4 (sakamakismile) — Spark Arena solo recipe (SparkOps key: `ornith-sakamaki-arena`)

Every engine flag below is transcribed from Spark Arena benchmark run `sub1784974058353`
(public leaderboard backing store):

- Firestore doc: `https://firestore.googleapis.com/v1/projects/spark-arena/databases/(default)/documents/benchmarks/sub1784974058353`
- Aggregate score **1837.04**, prefill **3612.7 t/s**, `clusterSize=1` (solo GB10), runtime vLLM,
  maintainer "stormgrid".
- Captured copy of the parsed run doc committed at
  `docs/recipes/prep/recipe_sub1784974058353.json`
  (sha256 `d56bd1cb2cf71d086a6c8554c5259a8db5b49dd57d06cfe9a25f6ae72f65ce5e`).

Model: `sakamakismile/Ornith-1.0-35B-NVFP4` @ revision
`b6c70b1b77fbd1822dbe01011d8ae5a6f5dd6101` (21.9 GB, Qwen3.6-35B-A3B hybrid base: 40 layers =
30 linear-attention + 10 full-attention, 2 KV heads, head_dim 256, 465k downloads).

**Image-support verification (sol D5 park-condition, cleared 2026-07-25):** the pinned nightly
image was inspected directly (`vllm serve --help=all` inside
`ghcr.io/spark-arena/dgx-vllm-eugr-nightly@sha256:a7f4917477ec...`):
`--performance-mode {balanced,interactivity,throughput}`, `--enable-flashinfer-autotune`,
`--distributed-executor-backend [... 'ray' ...]` all present; `fastsafetensors 0.3.3` installed.

## Resolved verbatim command (template placeholders → the run doc's own `defaults` map)

```
vllm serve sakamakismile/Ornith-1.0-35B-NVFP4
--served-model-name local-ai
--host 0.0.0.0
--port 8000
--trust-remote-code
--gpu-memory-utilization 0.6
--kv-cache-dtype fp8
--load-format fastsafetensors
--max-num-batched-tokens 65536
--max-num-seqs 4
--performance-mode throughput
--enable-flashinfer-autotune
--enable-auto-tool-choice
--tool-call-parser qwen3_coder
--enable-prefix-caching
--enable-chunked-prefill
--tensor-parallel-size 1
--distributed-executor-backend ray
--max-model-len 262144
```

Environment (from the run doc's `env` map, verbatim):

```
VLLM_ALLOW_LONG_MAX_MODEL_LEN=1
NCCL_NVLS_ENABLE=0
VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS=1
PROMETHEUS_METRICS_ENABLED=0
VLLM_MARLIN_USE_ATOMIC_ADD=1
NCCL_IB_MERGE_NICS=1
```

## Deviations from source (recorded, human-approved)

| flag | source | ours | reason |
|---|---|---|---|
| `--max-model-len` | absent (engine falls back to config.json `max_position_embeddings` 262144) | `262144` explicit | sol D5 directive: "make the implicit 262,144 context explicit" — same effective value, no tuning |
| `--served-model-name` | `sakamakismile/Ornith-1.0-35B-NVFP4` | `local-ai` | SparkBench/gateway endpoint contract (standing operator alias) |

`--port 8000` and `--host 0.0.0.0` match the run doc's own defaults. `--tensor-parallel-size 1`
and `--distributed-executor-backend ray` are the run doc's solo defaults, not adaptations.

## Image

`ghcr.io/spark-arena/dgx-vllm-eugr-nightly@sha256:a7f4917477eca584b271b0587dd48abf0f68657c4a2d93f7265402097be45404`
(tag `2026072502`, CI-tested nightly) per sol decision D4. Arena score is historical evidence of
its own image era, not a measurement of this digest.

## Fit math (GB10 unified, ~119 GiB usable)

Weights 21.9 GB + KV fp8 10,240 B/token → 2.68 GiB per 262,144-token sequence. Budget
0.6 × 119 = 71.4 GiB → ~45 GiB KV pool after weights + overhead. Fits with large headroom.

Attention-quant status: v8 classifier verdict pending (author added to watch 2026-07-25,
commit 074abac); attention-quant predictor is weak-advisory only — bench decides.
