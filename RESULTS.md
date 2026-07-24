# SparkBench v2 results — NVIDIA DGX Spark (GB10)

**Hardware:** NVIDIA DGX Spark — GB10, 128 GB unified memory (~119 GiB usable), ~273 GB/s memory
bandwidth, sm_121a, single GPU (TP=1).
**Method:** full v2 runs, 1 trial each unless noted, reasoning/thinking disabled where the recipe
allows, served as `local-ai` on `:8000`. Scoring policy v2; STABILITY uses the v2.1 rate-scaled
formula (applied retroactively to pre-v2.1 runs via `rescore_v21.py` — same recorded events, new
formula, provenance untouched). All runs July 2026. Last updated **2026-07-23**.

**Axis weights:** TOOLS 27 · AGENT 22 · LOAD 13 · LOGIC 10 · CONTEXT 10 · STABILITY 10 · MATH 8

## Leaderboard

| # | Recipe | Speed¹ | LOAD agg² | CTX TTFT | TOOLS | AGENT | LOGIC | MATH | CONTEXT | LOAD | STAB | **Total** | Grade |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | Qwen3.6-35B-A3B **MLP-Only NVFP4** (vLLM 0.25.1, aeon) | 38 t/s | 40 | 17.7 s | 91 | **82.6** | 50³ | 20.0 | 70 | 100 | 92.7 | **78.7** | B |
| 2 | Qwen3.6-35B-A3B MLP-Only NVFP4 (vLLM 0.25.0) | 37 t/s | 50 | 20.7 s | 89 | 53.9 | 80 | 23.3 | 80 | 100 | 95.1 | **76.2** | B |
| 3 | Ornith-1.0-35B **AEON Ultimate NVFP4** (vLLM) | **107 t/s** | **77** | 15.2 s | 85 | 33.4 | 90 | 40.0 | 80 | 100 | 91.3 | **72.6** | B |
| 4 | Qwen3.6-35B-A3B NVFP4 **"fast"** (spec decode) | 95 t/s | 45 | 11.2 s | 92 | 45.7 | 60 | 26.7 | 70 | 100 | 95.4 | **72.5** | B |
| 5 | Qwen3.6-35B-A3B **FP8 no-MTP** (vLLM) | 48 t/s | 61 | 16.5 s | 91 | 45.3 | 40 | 16.7 | 80 | 100 | 95.2 | **70.4** | B |
| 6 | Qwen3.6-35B-A3B **Unsloth NVFP4** (vLLM) | 68 t/s | 92 | 12.4 s | 89 | 7.1 | 80 | 23.3 | 70 | 100 | 97.8 | **65.3** | C |
| 7 | Qwen3.6-35B-A3B NVFP4 **MTP** (spec decode) | **110 t/s** | 40 | 8.9 s | 88 | 7.1 | 70 | 10.0 | 90 | 100 | 94.7 | **64.7** | C |
| 8 | Qwen3-Coder-Next **NVFP4 GB10** (vLLM) | 61 t/s | **142** | 35.5 s | 84 | 11.1 | 60 | 76.7 | 30 | 100 | 99.6 | **63.3** | C |
| 9 | Qwen3.5-122B-A10B **DFlash** (installer) | 61 t/s | 23 | 36.0 s | 88 | 7.1 | 60 | 20.0 | 60 | 100 | 90.4 | **61.0** | C |
| 10 | DeepSeek-V4 **D-Spark GGUF 2-bit** (llama.cpp) | 24 t/s | 31 | — | 87 | 7.1 | 80 | 76.7 | 0⁴ | 100 | 0⁴ | **52.2** | D |
| 11 | DeepSeek-V4-Flash **UD-IQ3_XXS GGUF** (llama.cpp) | 13 t/s | 6 | — | 87 | 0 | **100** | 76.7 | 0 | 0 | 41.0 | **43.7** | D |
| 12 | Gemma-4-26B-A4B **NVFP4** (vLLM 0.25.1, aeon) | 30 t/s | — | — | 87 | 0 | 40 | 6.7 | 0⁴ | 0⁴ | 0⁴ | **28.0** | D |

¹ Median single-stream generation speed: `completion_tokens / latency_s` over successful requests
≥ 200 completion tokens, from each run's `events.jsonl`. Includes prefill, so it slightly
understates pure decode. Do **not** derive speed from `latency − ttft`: streaming buffering makes
`ttft_s` unreliable and produces nonsense (we measured "692–3823 t/s" that way).
² Aggregate throughput during the concurrent LOAD phase: total completion tokens / wall window.
³ Champion LOGIC: in-run 50; an approved 3-trial LOGIC-only rerun scored 80/60/80 (median 80,
range 20). Official total stays 78.7 as scored; merging the rerun median would give 81.7.
⁴ Zeros from benching a dead endpoint after a mid-run kill (harness fail-fast gap — known
limitation): the serve died (legitimate OOM-tripwire kill or crash) and later phases scored
against nothing.

## Partial / DNF (no comparable total)

| Recipe | Status | Evidence |
|---|---|---|
| poolside **Laguna-S-2.1 NVFP4 + DFlash** | DROPPED 2026-07-23 | 3 attempts. (a) card config (util 0.85/262k) → genuine kernel `NV_ERR_NO_MEMORY` on the plain `vllm/vllm-openai:v0.25.1` image — the card envelope assumes poolside's flashinfer-nightly stack; (b) operator false-kill (tooling bug, fixed); (c) Spark-Arena-proven config (0.72/131k/seqs 8, identical container, arena run `sub1784787587343`) verified flag-for-flag — TOOLS/LOGIC ran, but **every AGENT turn burned the full 240 s wall** (engine healthy, 22G free): the thinking loop exhausts the budget and DFlash can't save it. Ceiling mid-60s. 45 t/s measured. |
| Gemma-4-31B **QAT W4A16** (June QAT recipe + MTP) | family closed | TOOLS 89 / **AGENT 0.0** / LOGIC 60 / MATH 50 · 39 t/s · died ~CONTEXT. Ceiling 67. |
| Gemma-4-26B-A4B (first run, 07-14) | superseded | TOOLS 83 / AGENT 0.0 / LOGIC 60 / MATH 3.3 · 31 t/s. |
| ressl/Ornith-1.0-35B NVFP4 (base) | tombstoned | 4 serve attempts, 4 kernel NVRM bursts, box froze once. Card validated on a **discrete RTX PRO 6000**, never on Spark — hardware-class mismatch (unified memory ≠ discrete VRAM), not model fitness. AEON variant (#3) is the Spark-validated sibling. |
| Qwen3-Next-80B family | discarded | Thinking: 432 truncations, D/36.5. Instruct: OOMed the box at 262k ctx. |
| GLM-4.7-Flash (NVFP4, AWQ) | discarded | Serve-unstable on GB10 across both quants; 0-score runs only. GLM-5.2: smallest artifact 139 GB > 119 GB pool — physically out. |

## What the data says

- **AGENT is the discriminator.** Everything serves tools acceptably (TOOLS 84–92); only the
  champion actually drives a multi-turn agentic task (82.6 vs ≤ 53.9 for everything else).
- **The engine version was worth +28.7 AGENT.** Rows 1 and 2 are the *same weights* — the only
  change is vLLM 0.25.0 → 0.25.1 (aeon build). Multi-turn tool streaming got materially better.
  Re-bench your champion when the engine moves.
- **Speed and quality remain separate axes.** The two ~110 t/s recipes (AEON, MTP) give up 6–14
  total points; the champion is the *slowest* B-tier recipe at 38 t/s. Pick by workload: AEON at
  107 t/s / 72.6 is the latency-optimized alternative to the 78.7 champion.
- **Attention quantization predicts AGENT death.** Every recipe with attention compressed to
  4-bit scored AGENT ≤ 11; recipes that keep attention in high precision (MLP-only quant, FP8)
  hold 45–83. Check the quant config before you download.
- **Streaming agentic parsing is its own failure mode.** Gemma-4 (both sizes, two engines) and
  Laguna time out or emit nothing usable in multi-turn streaming tool loops while acing
  single-turn TOOLS — parser/loop behavior, not intelligence. TheAgentCompany reports the same
  0% pattern for Gemma-4.
- **GGUF pays ~2–3x speed on GB10.** No native-FP4 path: 13–24 t/s vs 38–110 for
  vLLM NVFP4/FP8 of comparable or larger models.

## Champion recipe (exact)

`ghcr.io/aeon-7/aeon-vllm-ultimate@sha256:c15e2c4b…` (vLLM 0.25.1 build), weights
`vroomfondel/Qwen3.6-35B-A3B-NVFP4-MLP-Only-ModelOpt@b2d01351`:

```
vllm serve vroomfondel/Qwen3.6-35B-A3B-NVFP4-MLP-Only-ModelOpt \
  --host 0.0.0.0 --port 8000 --served-model-name local-ai \
  --max-model-len 262144 --max-num-seqs 2 --max-num-batched-tokens 4096 \
  --gpu-memory-utilization 0.7 --trust-remote-code \
  --quantization modelopt --kv-cache-dtype fp8 --enable-prefix-caching \
  --reasoning-parser qwen3 --enable-auto-tool-choice --tool-call-parser qwen3_coder
```

All recipes (with full flag-level provenance, evidence links, and tombstones) live in the
SparkOps registry on the box; machine-generated views: `~/sparkops/RECIPES.md` and
`~/bench/sparkbench/LEADERBOARD.md`.

## Operational findings (July 2026 campaign)

- **aeon-vllm-ultimate v0.25.1 (`c15e2c4b`) speculative-drafter paths are broken:** Laguna DFlash
  crashes with `AttributeError: embed_normalizer`; Gemma MTP fails with a shape mismatch. Stock
  `vllm/vllm-openai:v0.25.1` works for those; the aeon build is fine for non-speculative serving.
- **Unified memory commits under load, not at boot.** A recipe can serve cleanly and OOM the
  kernel minutes-to-hours later (KV growth, spec-decode verify buffers uncounted by
  `gpu-memory-utilization`). Post-serving watchdog: any new kernel NVRM line or available memory
  ≤ 1 GiB → abort. Init-window NVRM probing lines are benign (verified on a healthy champion).
- **Hardware-class check:** recipes validated on discrete-VRAM Blackwell (RTX PRO 6000 / 5090) do
  NOT transfer utilization/context values to 121 GB unified memory. "Single GPU" is not enough.
- **Quant-specific flags:** never graft memory/context/batch flags across precisions of the same
  model (a BF16 recipe's 0.85 util is not a QAT-W4A16 recipe's 0.85).
- **Harness fail-fast gap (known limitation):** if the serve dies mid-run, later phases bench a
  dead endpoint and record instant-timeout zeros as if measured. Reads as ⁴ above. Fix planned.

## History

- **2026-07-23** — champion re-verified on vLLM 0.25.1 (78.7/B); Laguna dropped after 3 attempts;
  Gemma-4 family closed (streaming-agentic AGENT 0); speed lane added to reporting; STABILITY
  v2.1 rate-scale retro-applied; power-cut reboot survived with single-champion auto-restore.
- **2026-07-15** — first v2.1 board; MLP-only NVFP4 takes the throne from FP8 no-MTP.
- **2026-07-12** — scoring v1 retired (v1 scores not comparable; see git history for the v1 board).
