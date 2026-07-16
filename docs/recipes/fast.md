# Recipe: Qwen3.6-35B-A3B NVFP4-Fast (speed alternative, MTP-2)

Serving recipe for `unsloth/Qwen3.6-35B-A3B-NVFP4-Fast` on a single DGX Spark (GB10, SM12.1).
Mixed FP8-attention/NVFP4-experts quant with MTP-2 speculative decoding. Trades some AGENT/LOGIC
quality for throughput — see result below.

Source model card has no serve command. Every flag below is our own engineering, validated by the
SparkBench run cited at the bottom.

## Verbatim command

```bash
docker run -d --name "$CONTAINER" \
    --restart=unless-stopped \
    --gpus all --network host --ipc=host \
    -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
    -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 -e VLLM_ALLOW_LONG_MAX_MODEL_LEN=1 \
    -e CUTE_DSL_ARCH=sm_121a \
    --entrypoint bash "ghcr.io/aeon-7/aeon-vllm-ultimate:2026-07-14-v0.25.0" -c "exec vllm serve \
      unsloth/Qwen3.6-35B-A3B-NVFP4-Fast \
      --host 0.0.0.0 --port 8000 --served-model-name local-ai \
      --max-model-len 262144 --max-num-seqs 2 --gpu-memory-utilization 0.7 \
      --max-num-batched-tokens 4096 \
      --trust-remote-code --quantization compressed-tensors --moe-backend flashinfer_cutlass \
      --kv-cache-dtype fp8 --enable-prefix-caching \
      --reasoning-parser qwen3 --enable-auto-tool-choice --tool-call-parser qwen3_coder \
      --speculative-config '{\"method\":\"mtp\",\"num_speculative_tokens\":2}'"
```

`--max-num-batched-tokens 4096` is required for the same reason as the MLP-Only recipe in this
directory (hybrid Mamba/GDN Mamba-cache-align block-size assertion at engine-core init) — this
model shares the same base architecture.

The `--speculative-config` value above is backslash-escaped for its position inside the outer
`docker ... -c "..."` double-quoted string. Unwrapped, the flag is:

```
--speculative-config '{"method":"mtp","num_speculative_tokens":2}'
```

## Result

SparkBench v2.1, single trial, 2026-07-16: **72.5/100 (B)**. AGENT 45.7/100, median speed **94.5
t/s** (2.5x the MLP-Only recipe's 37.2 t/s) via MTP-2 speculative decoding. Full axis breakdown
and recipe provenance: `../../RESULTS.md` in this repo, entry `q36_nvfp4_fast`.
