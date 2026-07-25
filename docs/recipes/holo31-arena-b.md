# Holo-3.1-35B-A3B-NVFP4 — Spark Arena solo recipe B (SparkOps key: `holo31-arena-b`)

Every engine flag below is transcribed from Spark Arena benchmark run `sub1784969688643`
(public leaderboard backing store):

- Firestore doc: `https://firestore.googleapis.com/v1/projects/spark-arena/databases/(default)/documents/benchmarks/sub1784969688643`
- Aggregate score **2125.53**, prefill **4181.8 t/s**, `clusterSize=1` (solo GB10), runtime vLLM,
  recipe_version 2, maintainer "stormgrid", submitted 2026-07 era.
- Captured copy of the parsed run doc committed at
  `docs/recipes/prep/recipe_sub1784969688643.json`
  (sha256 `25e44303f8223434b21fdb05c8407d32a5fe82eba01d58f64df0bfefbfcfc02a`).

**Selection rationale (recorded per review):** the same repo has an older, higher-scoring solo
run A `sub1780467628934` (score 2355.0, 2026-06-03, gpu-mem-util 0.28). Recipe B was selected by
gpt-5.6-sol decision D1 (thread `bench-prep-4-candidates`, 2026-07-25): B is the maintained
recipe_version-2 sparkrun recipe from the current stack era with materially safer KV headroom
(0.4×119 GiB = 47.6 GiB budget vs A's 33.3 GiB). Run A's score is historical context only.

Model: `Hcompany/Holo-3.1-35B-A3B-NVFP4` @ revision `76ebefd59b500fe55e1afa45995aa8553198ee6e`
(23.7 GB weights, computer-use VLM, Qwen3.6-35B-A3B hybrid base: 40 layers = 30 linear-attention
+ 10 full-attention, 2 KV heads, head_dim 256).

## Resolved verbatim command (template placeholders → the run doc's own `defaults` map, 1:1)

```
vllm serve Hcompany/Holo-3.1-35B-A3B-NVFP4
--served-model-name local-ai
--host 0.0.0.0
--port 8000
--gpu-memory-utilization 0.4
--max-model-len 262144
--max-num-seqs 10
--max-num-batched-tokens 16384
--kv-cache-dtype fp8
--mamba-ssm-cache-dtype float32
--enable-prefix-caching
--trust-remote-code
--enable-auto-tool-choice
--tool-call-parser qwen3_coder
--reasoning-parser qwen3
--tensor-parallel-size 1
--distributed-executor-backend ray
```

Environment (from the run doc's `env` map, verbatim):

```
NCCL_IB_MERGE_NICS=1
VLLM_MARLIN_USE_ATOMIC_ADD=1
NCCL_NVLS_ENABLE=0
```

## Operator-local deviations (human-approved, not engine tuning)

| flag | source value | ours | reason |
|---|---|---|---|
| `--served-model-name` | `Hcompany/Holo-3.1-35B-A3B-NVFP4` | `local-ai` | SparkBench/gateway endpoint contract (standing operator alias) |
| `--port` | `8008` | `8000` | operator serving port (standing) |

No other token deviates from the run doc. `--tensor-parallel-size 1` and
`--distributed-executor-backend ray` are the run doc's own solo defaults
(`tensor_parallel: 1`), not adaptations.

## Image

The arena run executed on sparkrun container `sparkrun-eugr-vllm-tf5` (eugr `vllm-node` image
family; `-tf5` is a deprecated alias per eugr/spark-vllm-docker README). We pin the current
CI-tested nightly `ghcr.io/spark-arena/dgx-vllm-eugr-nightly@sha256:a7f4917477eca584b271b0587dd48abf0f68657c4a2d93f7265402097be45404`
(tag `2026072502`) per sol decision D4. The arena score is historical evidence tied to its
original image era — it is NOT a measurement of this digest.

## Fit math (GB10 unified, ~119 GiB usable)

Weights 23.7 GB + KV fp8 = 10 full-attn layers × 2 kv-heads × 256 head-dim × 2 (K+V) × 1 B
= 10,240 B/token → 2.68 GiB per 262,144-token sequence. Budget 0.4 × 119 = 47.6 GiB →
~20 GiB KV pool after weights + runtime overhead. Fits with headroom.
