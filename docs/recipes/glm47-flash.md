# GLM-4.7-Flash-NVFP4 — DGX Spark (GB10) serve recipe

Serving recipe for `unsloth/GLM-4.7-Flash-NVFP4` (revision `98b0362133bda9ee3b1b875636636c07861f5947`)
on a single DGX Spark (GB10, 128GB unified, sm_121a) with the
`ghcr.io/aeon-7/aeon-vllm-ultimate` image (digest-pinned in the SparkOps recipe).

## Command — verbatim official, zero local engine flags

```
VLLM_ATTENTION_BACKEND=TRITON_MLA vllm serve unsloth/GLM-4.7-Flash-NVFP4 \
  --speculative-config.method mtp \
  --speculative-config.num_speculative_tokens 1 \
  --tool-call-parser glm47 \
  --reasoning-parser glm45 \
  --enable-auto-tool-choice
```

Every engine flag traces verbatim to an official model card:

- `VLLM_ATTENTION_BACKEND=TRITON_MLA` + bare `vllm serve unsloth/GLM-4.7-Flash-NVFP4` — the
  complete official recipe from the
  [unsloth model card](https://huggingface.co/unsloth/GLM-4.7-Flash-NVFP4/raw/98b0362133bda9ee3b1b875636636c07861f5947/README.md)
  (pinned revision). The card also warns: do not use the Marlin backend (~2x slower).
- `--speculative-config.method mtp`, `--speculative-config.num_speculative_tokens 1`,
  `--tool-call-parser glm47`, `--reasoning-parser glm45`, `--enable-auto-tool-choice` — from the
  [zai-org GLM-4.7-Flash card](https://huggingface.co/zai-org/GLM-4.7-Flash/raw/7dd20894a642a0aa287e9827cb1a1f7f91386b67/README.md)
  vLLM deploy section (pinned revision). The checkpoint carries the MTP head
  (`num_nextn_predict_layers = 1` in its config.json).
- Only adaptation: `--tensor-parallel-size 4` dropped — multi-GPU flag, the Spark is TP=1.
- `--host/--port/--served-model-name` — operator-local deployment choices.

All other engine behavior (memory utilization, context length, batching) is **vLLM defaults,
exactly as the official recipe implies**. No locally-invented tuning flags.

## History

A 2026-07-16 bench attempt of this model used a hand-rolled command with four locally-invented,
unsourced flags carried over from a different model family's recipe; it OOMed and hard-hung the
host (physical power cycle). The run was retired and replaced by this verbatim-official recipe.
An earlier revision of this document proposed locally-tuned memory flags; that revision was
rejected in review for the same reason — engineering flags without official sourcing or explicit
operator approval don't ship.

## Status

Registered as SparkOps recipe `glm47-flash-nvfp4` (all evidence pinned to immutable revisions,
passes live re-verification). Awaiting SparkBench v2.1 run.
