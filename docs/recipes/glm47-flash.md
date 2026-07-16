# GLM-4.7-Flash-NVFP4 — DGX Spark (GB10) serve recipe

Serving recipe for `unsloth/GLM-4.7-Flash-NVFP4` (revision `98b0362133bda9ee3b1b875636636c07861f5947`)
on a single DGX Spark (GB10, 128GB unified, sm_121a) with the
`ghcr.io/aeon-7/aeon-vllm-ultimate:2026-07-14-v0.25.0` image.

## Command

```
VLLM_ATTENTION_BACKEND=TRITON_MLA vllm serve unsloth/GLM-4.7-Flash-NVFP4 \
  --max-model-len 131072 \
  --max-num-seqs 2 \
  --gpu-memory-utilization 0.6 \
  --max-num-batched-tokens 4096 \
  --trust-remote-code \
  --tool-call-parser glm47 \
  --reasoning-parser glm45 \
  --enable-auto-tool-choice
```

## Flag provenance and rationale

- `VLLM_ATTENTION_BACKEND=TRITON_MLA` — required per the unsloth model card
  ([README at pinned revision](https://huggingface.co/unsloth/GLM-4.7-Flash-NVFP4/raw/98b0362133bda9ee3b1b875636636c07861f5947/README.md)):
  `VLLM_ATTENTION_BACKEND=TRITON_MLA vllm serve unsloth/GLM-4.7-Flash-NVFP4`.
  The card also warns: do not use the Marlin backend (~2x slower).
- `--tool-call-parser glm47 --reasoning-parser glm45 --enable-auto-tool-choice` — from the
  official zai-org GLM-4.7-Flash vLLM deployment section (same parsers in the SGLang recipe).
- `--gpu-memory-utilization 0.6` — **memory-safety fix, learned from a real crash.**
  TRITON_MLA does not support FP8 KV cache on Blackwell (vllm-project/vllm#35577), so this
  configuration runs BF16 KV. Combined with GLM's large vocab/head-dim memory footprint
  (vllm-project/vllm#33920), a 2026-07-16 bench run of this exact model at
  `--gpu-memory-utilization 0.7` OOMed and hard-hung the host ~90 minutes into a sustained
  benchmark (NV_ERR_NO_MEMORY, physical power cycle required). 0.6 leaves ~12GB extra
  headroom on the 119GB-usable unified-memory budget.
- `--max-model-len 131072` — half of native 202752; MLA KV is compact, context length was
  not the crash driver, and SparkBench's CONTEXT phase needs ~68k-token prompts.
- `--max-num-seqs 2 --max-num-batched-tokens 4096` — standard single-box bench settings
  used by every recipe in [RESULTS.md](../../RESULTS.md).
- `--trust-remote-code` — Glm4MoeLite architecture requires it on this vLLM build.

## Container invocation

Managed by [SparkOps](https://github.com/jilycn/sparkbench#running-benches) recipe
`glm47-flash-nvfp4`: `--gpus all --network host --ipc=host`, HF cache mount, offline env,
`--entrypoint bash IMAGE -c "exec vllm serve ..."` (aeon image entrypoint quirk).

## Status

Registered for SparkBench v2.1 evaluation 2026-07-16. Not yet scored — the 0.7-util attempt
crashed before completing; this corrected recipe is its retry.
