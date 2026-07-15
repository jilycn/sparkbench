# SparkBench v2 results — NVIDIA DGX Spark (GB10)

**Hardware:** NVIDIA DGX Spark — GB10, 128 GB unified memory (~119 GiB usable), ~273 GB/s memory
bandwidth, sm_121a, single GPU (TP=1).
**Method:** full v2 runs, 1 trial each, reasoning/thinking disabled where the recipe allows, served
as `local-ai` on `:8000`. Scoring policy v2 (weights in README). All runs July 2026.

## Leaderboard

| # | Recipe | Speed¹ | TOOLS | AGENT | LOGIC | MATH | CONTEXT | LOAD | STAB | **Total** | Grade |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | Qwen3.6-35B-A3B **FP8 no-MTP** (vLLM) | 48 t/s | 91 | **45.3** | 40 | 16.7 | 80 | 100 | 0 | **60.9** | C |
| 2 | Qwen3.6-35B-A3B **Unsloth NVFP4** (vLLM) | **68 t/s** | 89 | 7.1 | 80 | 23.3 | 70 | 100 | 0 | **55.5** | D |
| 3 | Qwen3-Coder-Next **NVFP4 GB10** (vLLM) | 61 t/s | 84 | 11.1 | 60 | 76.7 | 30 | 100 | 0 | **53.3** | D |
| 4 | Qwen3.5-122B-A10B **DFlash** (installer) | 61 t/s² | 88 | 7.1 | 60 | 20.0 | 60 | 100 | 0 | **52.0** | D |
| 5 | DeepSeek-V4-Flash **UD-IQ3_XXS** (llama.cpp) | 13 t/s | 87 | 0 | **100** | 76.7 | 0 | 0 | 0 | **39.6** | D |
| 6 | Qwen3-Next-80B-A3B-Thinking **NVFP4** (vLLM) | 39 t/s | 68 | 0 | **100** | 26.7 | 60 | 0 | 0 | **36.5** | D |
| — | Gemma-4-26B-A4B **NVFP4** (vLLM, PARTIAL) | 31 t/s | 83 | 0 | 60 | 3.3 | 0 | 100 | n/a | — | — |

¹ Observed single-stream generation speed: median `completion_tokens / latency_s` over successful
requests ≥ 200 completion tokens, from each run's `events.jsonl`. Includes prefill time, so it
slightly understates pure decode speed.
² Speculative decoding (DFlash): p90 hit 85 t/s; speed varies with draft acceptance rate.

### What the data says

- **AGENT is the discriminator.** Everything serves tools acceptably (TOOLS 68–91); only one recipe
  can actually drive a multi-turn agentic task (45.3 vs ≤ 11.1 for all others).
- **Speed and quality are separate axes.** The fastest recipe (Unsloth NVFP4, 68 t/s) is not the
  best one; the champion runs at 48 t/s. The 273 GB/s bandwidth math holds: NVFP4 4-bit reads fewer
  bytes per token than FP8 and is proportionally faster on the same base model.
- **Smart ≠ servable.** The two LOGIC-100 models (DeepSeek, 80B-Thinking) both scored LOAD 0 —
  one too slow (96 GB weights on a 273 GB/s box), one drowned in its own reasoning
  (432 truncations in one run).
- **STABILITY scored 0 for every run** under the current zero-out policy — non-discriminating,
  rate-scaled fix planned.

## Recipes (exact serve configurations)

All vLLM recipes run in `ghcr.io/spark-arena/dgx-vllm-eugr-nightly` or
`ghcr.io/aeon-7/aeon-vllm-ultimate` images with the HF cache mounted. Common pattern:
`docker run --gpus all` + `vllm serve <model> --served-model-name local-ai --host 0.0.0.0 --port 8000`.

### #1 — Qwen3.6-35B-A3B FP8, no MTP (the incumbent/champion)

```
vllm serve <qwen3.6-35b-a3b-fp8> \
  --served-model-name local-ai --host 0.0.0.0 --port 8000 \
  --max-model-len 262144 --max-num-batched-tokens 32768 --max-num-seqs 4 \
  --trust-remote-code --chat-template <unsloth.jinja> \
  --gpu-memory-utilization 0.8 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3 \
  --kv-cache-dtype fp8 --load-format instanttensor \
  --attention-backend flashinfer --enable-prefix-caching -tp 1 -pp 1
```

### #2 — Qwen3.6-35B-A3B Unsloth NVFP4

Same flags as #1 minus `--kv-cache-dtype fp8 --load-format instanttensor`, weights =
`unsloth/Qwen3.6-35B-A3B-NVFP4`.

### #3 — Qwen3-Coder-Next NVFP4 (GB10 community build)

```
vllm serve saricles/Qwen3-Coder-Next-NVFP4-GB10 \
  --served-model-name local-ai --host 0.0.0.0 --port 8000 \
  --max-model-len 131072 --gpu-memory-utilization 0.85 \
  --enable-auto-tool-choice --tool-call-parser qwen3_xml
```
(aeon image; env: `VLLM_ALLOW_LONG_MAX_MODEL_LEN=1 TORCH_MATMUL_PRECISION=high
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True VLLM_USE_FLASHINFER_MOE_FP4=0
VLLM_TEST_FORCE_FP8_MARLIN=0 VLLM_NVFP4_GEMM_BACKEND=flashinfer-cutlass`)

### #4 — Qwen3.5-122B-A10B DFlash (one-shot installer)

Published as an installer repo: `github.com/Entrpi/qwen3.5-122B-A10B-on-spark` @
`a77cbdab26956ef6ac9cdca544e5fb9ec1f3bb2a` → `./install.sh --start`. Serves container `qwen-spark`,
image pinned `ghcr.io/aeon-7/aeon-vllm-ultimate@sha256:be9e05a1…`, model name `qwen`, 262k context.

### #5 — DeepSeek-V4-Flash UD-IQ3_XXS (llama.cpp)

llama.cpp built for sm_121a, `llama-server --jinja` on :8000, GGUF =
`unsloth/DeepSeek-V4-Flash-GGUF` UD-IQ3_XXS (96 GB, 4 shards). Verdict: highest reasoning on the
board, decode too slow to serve interactively on 273 GB/s — LOAD/CONTEXT both zero.

### #6 — Qwen3-Next-80B-A3B-Thinking NVFP4

`nvidia/Qwen3-Next-80B-A3B-Thinking-NVFP4` (aeon image, `--tool-call-parser hermes
--reasoning-parser deepseek_r1`, 262k). Thinking-only: no way to cap rumination → 432 truncations,
AGENT 0, LOAD 0. Its Instruct sibling OOM-crashed the host at 262k context and was not re-run.

### — Gemma-4-26B-A4B NVFP4 (partial)

`nvidia/Gemma-4-26B-A4B-NVFP4` (aeon image, `--tool-call-parser gemma4 --reasoning-parser gemma4`,
131k). Stability phase crashed → PARTIAL; near-zero MATH/CONTEXT.

## Legacy (scoring v1 — never comparable to v2)

| Recipe | v1 score |
|---|---|
| Qwen3.6-35B Unsloth std | 91.6 / A |
| Qwen3.6-35B FP8 + DFlash (xml parser) | 90.6 / B |
| Qwen3.6-35B FP8 no-MTP | 88.6 / A- |

v1 used a different suite and weights; the leaderboard tool refuses to rank v1 against v2.
