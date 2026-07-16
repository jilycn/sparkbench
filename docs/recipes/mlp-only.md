# Recipe: Qwen3.6-35B-A3B NVFP4-MLP-Only-ModelOpt (SparkBench v2.1 champion)

Serving recipe for `vroomfondel/Qwen3.6-35B-A3B-NVFP4-MLP-Only-ModelOpt` on a single DGX Spark
(GB10, SM12.1). Attention left unquantized (MLP-only NVFP4 quant) — this is the config choice
that produced the AGENT-axis result below; every all-attention-quantized NVFP4 variant of this
base model scored AGENT ~7 in the same suite.

Source model card has no serve command (it's a bare ModelOpt quantization card). Every flag below
is our own engineering, validated by the SparkBench run cited at the bottom — not copied from a
third-party doc.

## Verbatim command

```bash
docker run -d --name "$CONTAINER" \
    --restart=unless-stopped \
    --gpus all --network host --ipc=host \
    -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
    -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 -e VLLM_ALLOW_LONG_MAX_MODEL_LEN=1 \
    -e CUTE_DSL_ARCH=sm_121a \
    --entrypoint bash "ghcr.io/aeon-7/aeon-vllm-ultimate:2026-07-14-v0.25.0" -c "exec vllm serve \
      vroomfondel/Qwen3.6-35B-A3B-NVFP4-MLP-Only-ModelOpt \
      --host 0.0.0.0 --port 8000 --served-model-name local-ai \
      --max-model-len 262144 --max-num-seqs 2 --gpu-memory-utilization 0.7 \
      --max-num-batched-tokens 4096 \
      --trust-remote-code --quantization modelopt \
      --kv-cache-dtype fp8 --enable-prefix-caching \
      --reasoning-parser qwen3 --enable-auto-tool-choice --tool-call-parser qwen3_coder"
```

`--max-num-batched-tokens 4096` is required, not cosmetic: this architecture (hybrid Mamba/GDN
attention) computes an attention block size from context length that must not exceed
`max-num-batched-tokens` when `--enable-prefix-caching` forces Mamba cache "align" mode, or vLLM
raises `AssertionError: In Mamba cache align mode, block_size (2096) must be <=
max_num_batched_tokens (2048)` at engine-core init. The default (2048) is too low for this model;
4096 was root-caused and verified via a full 358-line diagnostic serve capturing the exact
assertion.

## Result

SparkBench v2.1, single trial, 2026-07-15/16: **76.2/100 (B)**. AGENT 53.9/100 (beats the prior
FP8 incumbent's 45.3). Full axis breakdown, speed (37.2 t/s median), and recipe provenance:
`../../RESULTS.md` in this repo, entry `q36_nvfp4_mlponly`.
