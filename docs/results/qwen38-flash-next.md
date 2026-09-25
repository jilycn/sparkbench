# Qwen3.8-Flash-Next — SparkBench 2.2.1 scorecard

**Overall: 81.4 / B+** on a single DGX Spark (GB10, 128 GB unified memory).

Qwen3.8-Flash-Next is a 180B-parameter mixture-of-experts model (NVFP4 experts, BF16 attention),
served on **one** Spark via [SparkOps](https://github.com/jilycn/sparkbench) with live provenance
verification. Run `qwen38flashnext-180b-nvfp4-nvidia-tonyd_20260914-214919`, suite 2.2.1, single
trial, status COMPLETE.

## Result

| Axis | Score | Weight | Weighted | What it measures |
|---|---:|---:|---:|---|
| TOOLS | 87.0 | 27% | 23.5 | tool-call construction and selection |
| AGENT | 87.7 | 22% | 19.3 | multi-turn agentic task families |
| MATH | 83.3 | 8% | 6.7 | math word problems (easy/med/hard) |
| LOAD | 100.0 | 13% | 13.0 | throughput and correctness under 8× concurrency |
| STABILITY | 99.3 | 10% | 9.9 | no crashes, leaks or restarts under load |
| LOGIC | 50.0 → **100** | 10% | 5.0 → 10.0 | see note below |
| CONTEXT | 40.0 → **80** | 10% | 4.0 → 8.0 | see note below |
| **Overall** | **81.4 → ~90.4** | 100% | | grade **B+** |

## Reading the score: a formatting artifact, not a weakness

LOGIC 50.0 and CONTEXT 40.0 **understate** the model. SparkBench 2.2.1 marks an answer "not graded"
when the model wraps its terminal JSON answer in a closing ` ``` ` code fence — even when the JSON
inside is correct. Flash-Next runs with thinking disabled and fences its answers, so:

- **LOGIC** — 4/8 graded, but every one of the 4 "misses" was `not graded [fenced_terminal]` with
  the parsed answer **identical to the expected answer**. Content-correct: **8/8 (100)**.
- **CONTEXT** — content-correct on **8/10** items (80); the raw 40 is the same fencing artifact.

Content-corrected, the overall is **~90.4**. This is a property of the scoring contract, not the
model: any model that fences its JSON loses points on this axis pair. Check
`format_compliance.envelopes` in the run before reading LOGIC/CONTEXT as capability.

## Where it stands

On the suite 2.2.1 single-Spark board, the raw 81.4 ranks **#4** among the 35B-class NVFP4 models.
Flash-Next is the only **180B** model on the board; content-corrected (~90.4) it leads it.

| Model | Params | Score | Grade |
|---|---|---:|---|
| ornith-aeon-ultimate-nvfp4 | 35B | 83.7 | B+ |
| ornith-aeon-v0260 | 35B | 83.3 | B+ |
| q36-fast-speed | 35B | 81.6 | B+ |
| **Qwen3.8-Flash-Next** | **180B** | **81.4** (≈90.4 corrected) | **B+** |
| q36-mlponly-champion | 35B | 79.2 | B |

## Memory and context window

The DGX Spark GB10 uses **unified memory** — CPU and GPU share one 128 GB pool (~119 GiB usable),
so there is no separate VRAM figure. The numbers below are the whole serving footprint, measured
from the run.

| | |
|---|---|
| **Context window** | **262,144 tokens** (256K) |
| **Serving footprint** | **~94 GB** active (GPU-memory-utilization 0.80) |
| &nbsp;&nbsp;— weights resident | 76.5 GiB |
| &nbsp;&nbsp;— KV cache pool | 17.1 GiB (FP8 `e4m3` KV) — holds **1,072,407 tokens** = 4.1× the 262K window |
| **Free at peak** | ~15–17 GiB headroom on one Spark |
| **On disk** | 124 GB checkpoint, but only ~76 GB is resident — the parameter-loaded-embedding (PLE) table is memory-mapped from NVMe, which is how a 180B model fits under 128 GB |

Fits on a **single** 128 GB DGX Spark. A 180B model would need roughly 360 GB in BF16, or ~90 GB
dense 4-bit; Flash-Next lands at ~94 GB by combining NVFP4 experts, BF16 attention, an FP8 KV cache
(half the size of BF16 KV), and the NVMe-mmapped PLE table.

## Run facts

- **Hardware** — 1× NVIDIA DGX Spark (GB10), 128 GB unified memory (~119 GiB usable), aarch64, sm_121a
- **Model** — `nvidia/Qwen3.8-Flash-Next-NVFP4`, 180B MoE, NVFP4 experts + BF16 attention, 262 144-token context window
- **Speed** — ~41 tokens/s single-stream on structured output; content-dependent (MTP speculative decoding accepts more drafts on predictable text such as JSON and code)
- **Engine** — vLLM, tonyd2wild single-Spark recipe (PLE-table mmap from NVMe + MTP draft head + FP8 KV-cache overlays)
- **Suite** — SparkBench 2.2.1, scoring policy v2. Weights: TOOLS 27 / AGENT 22 / LOAD 13 / LOGIC 10 / CONTEXT 10 / STABILITY 10 / MATH 8. Single trial per standing policy. Speed is reported, never scored.

---

*Reproduce: `sparkops benchmark qwen38flashnext-180b-nvfp4-nvidia-tonyd` on the DGX. Raw scores and
per-item transcripts are preserved under
`~/bench/sparkbench/qwen38flashnext-180b-nvfp4-nvidia-tonyd_20260914-214919/`.*
