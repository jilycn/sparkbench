# NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4 - Spark Arena solo recipe

SparkOps key: `nemotron3super-120b-a12b-nvfp4-nvidia`

Every engine flag below is transcribed from Spark Arena benchmark run `sub1781065516643`
(public leaderboard backing store):

- Firestore doc: `https://firestore.googleapis.com/v1/projects/spark-arena/databases/(default)/documents/benchmarks/sub1781065516643`
- Aggregate score **746.46**, `clusterSize=1` (solo GB10), runtime vLLM, quantization NVFP4.
- Captured copy of the parsed run doc committed at `docs/recipes/prep/recipe_sub1781065516643.json`
  (sha256 `ebef6a727f96aa8e9aa6de203be4255cf4536417fdc32006b7ecd58b685698e4`).

Model: `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4` @ revision
`4f0cf9daaeb7a4d5e23f80a00e7ed15f0e03caf6` (80.3 GB across 17 safetensors shards, 2.83M downloads).

## Source selection

Five solo-GB10 runs exist for this model. Run `sub1781065516643` (2026-06-10, score 746.46) was
chosen over `sub1780820214697` (2026-06-07, score 752.68) because it serves the model's native
262,144-token context rather than capping at 105,000, and states an explicit `--max-num-seqs`.
The scores differ by 0.8 percent. The other three solo runs (507.2, 585.9, 533.5) are older and
lower and are recorded here as historical only.

## Resolved verbatim command (template placeholders resolved from the run doc's own `defaults`)

```
vllm serve nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4
--served-model-name local-ai
--host 0.0.0.0
--port 8000
--max-model-len 262144
--max-num-batched-tokens 16384
--max-num-seqs 16
--trust-remote-code
--gpu-memory-utilization 0.85
--kv-cache-dtype fp8
--enforce-eager
--load-format safetensors
--enable-prefix-caching
-tp 1
-pp 1
```

Environment (from the run doc's `env` map, verbatim):

```
VLLM_OTEL_TRACING_ENABLED=1
RAY_memory_usage_threshold=0.99
```

## Flag verification against the pinned image

`vllm serve --help=all` was run inside the pinned digest. Every flag above is present:
`--enforce-eager`, `--load-format` (with `safetensors` an explicit accepted value),
`--max-num-seqs`, `--kv-cache-dtype`, `--enable-prefix-caching`, `--max-num-batched-tokens`,
`--trust-remote-code`, `--gpu-memory-utilization`, `--max-model-len`, and `-tp` / `-pp` as real
aliases of `--tensor-parallel-size` / `--pipeline-parallel-size`.

`NemotronHForCausalLM` is registered in the image's model registry (vLLM
`0.23.1rc1.dev1479+gf8d174fc2.d20260725`).

## Deviations from source (recorded, human-approved)

| flag | source | ours | reason |
|---|---|---|---|
| `--served-model-name` | absent | `local-ai` | SparkBench/gateway endpoint contract (standing operator alias) |
| `hardware.memory_limit` | `100G` container cap | not applied | SparkOps does not impose a container memory limit; this is a harness hardware hint, not an engine flag. Recorded so the difference is visible. |

`--port 8000` and `--host 0.0.0.0` match the run doc's own defaults. `-tp 1` and `-pp 1` are the run
doc's solo defaults, not adaptations.

Spec decoding is not enabled. Neither this run nor any other solo run for this model passes an MTP
or speculative-decoding flag, though the checkpoint declares `num_nextn_predict_layers: 1` and the
image ships `NemotronHMTPModel`. An MTP variant would be a separate recipe requiring its own
provenance.

## Image

`ghcr.io/spark-arena/dgx-vllm-eugr-nightly@sha256:a7f4917477eca584b271b0587dd48abf0f68657c4a2d93f7265402097be45404`
(tag `2026072502`, CI-tested nightly). The arena run named `sparkrun-eugr-vllm-tf5`, an alias in the
same eugr/spark-vllm family; the digest is pinned here because a floating tag is not evidence. The
arena score is historical evidence of its own image era, not a measurement of this digest.

## Architecture and fit math (GB10 unified, ~119 GiB usable)

This is a hybrid, and the layer mix is what makes an 80 GB model fit comfortably. From
`config.json`, `hybrid_override_pattern` resolves 88 layers into 40 Mamba, 40 MoE-MLP and
**8 attention** layers.

- KV cache: 8 attention layers x 2 KV heads x 128 head_dim x 2 (K and V) x 1 byte (fp8)
  = **4,096 B/token**, so **1.00 GiB per 262,144-token sequence**.
- Mamba state is per sequence rather than per token: 40 layers x 128 heads x 64 dim x 128 state x 4
  bytes (float32 SSM cache) = **0.16 GiB per sequence**, plus 2.3 MiB of conv state.

At `--max-num-seqs 16` with every sequence at full context:

```
weights                 74.8 GiB
KV (16 x 1.00)          16.0 GiB
mamba state (16 x 0.16)  2.6 GiB
                        --------
                        93.4 GiB   vs budget 0.85 x 119 = 101 GiB
```

`--enforce-eager` removes CUDA-graph memory on top of that.

NOTE: SparkOps `fit` **overestimates** this model. Its generic 10 KB/token constant is 2.5x the real
4 KB/token, because it assumes every layer carries attention. Use this document's figure.

## Quantization shape

`quantization_config` (`quant_method: modelopt`) splits into two groups, and the split is not what
the "NVFP4" name implies:

- `group_1`, 4-bit float weights and activations: **40,961 targets, every one a MoE expert
  `up_proj` or `down_proj`** (512 routed experts x 40 MoE layers x 2 projections).
- `group_0`, 8-bit float: 139 targets - Mamba `in_proj`/`out_proj`, dense MLP projections, latent
  projections, and exactly two attention `o_proj`.
- `ignore` is empty, and `q_proj`, `k_proj` and `v_proj` appear in no group, so attention weights
  are not quantized.

Structurally this is an MLP-only NVFP4 checkpoint. Attention is effectively untouched, which is the
attention-safe side of the (advisory only) attention-quantization heuristic. Bench decides.
