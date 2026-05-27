# KV-Cache Disaggregated Inference — 4 Prefill + 4 Decode GPUs

## What this models

Disaggregated inference (Splitwise / vLLM PD-disaggregation pattern):
- Prefill GPUs (slots 0-3): process the prompt, generate KV-cache
- Decode GPUs (slots 4-7): receive KV-cache, run autoregressive generation
- Each prefill GPU sends its KV-cache shard to ALL decode GPUs (all-to-all K_{4,4})

## How numbers were derived

Model: LLaMA-3 70B
- num_layers = 80
- num_kv_heads = 8 (Grouped Query Attention, GQA)
- head_dim = 128
- dtype = BF16 (2 bytes)
- seq_len = 8192 tokens

KV-cache total size:
  seq_len × num_layers × 2 (K+V) × num_kv_heads × head_dim × bytes
  = 8192 × 80 × 2 × 8 × 128 × 2
  = 2,684,354,560 bytes ≈ 2.68 GB

With 4 prefill GPUs (TP=4), each holds 1/4 of KV-cache = 671 MB
Each prefill GPU sends its shard to ALL 4 decode GPUs: 671 MB / 4 = 167 MB per link

bits_total = 167,772,160 bytes × 8 = 1,342,177,280 bits ≈ 1.34 Gbits

## Sources

- LLaMA-3 architecture (public): 70B model, GQA with 8 KV heads, head_dim=128
  https://ai.meta.com/research/publications/the-llama-3-herd-of-models/
- Splitwise (ISCA 2024): disaggregated prefill-decode inference
  https://arxiv.org/abs/2311.18677
- vLLM PD-disaggregation blog:
  https://blog.vllm.ai/2024/09/05/perf-update.html
- Mooncake (prefill-centric disaggregated architecture):
  https://arxiv.org/abs/2407.00079

## Recommended copyspace-guard command

```bash
copyspace-guard analyze \
  --csv examples/kv_cache_disagg/demands.csv \
  --bw 50000000000 \
  --slots 8 \
  --model READ1_WRITE1 \
  --roi examples/kv_cache_disagg/roi.yml \
  --id kv-cache-disagg-llama3-70b \
  --outdir artifacts/kv-cache-disagg
```

## Parameters explained

- `--bw 50000000000`: 50 GB/s — NVLink within node or InfiniBand HDR
- `--model READ1_WRITE1`: each GPU can send to one and receive from one simultaneously
- `--slots 8`: 4 prefill (0-3) + 4 decode (4-7)
- 8 slots → bounds_complete=True, gap exact
- Pattern: complete bipartite graph K_{4,4}

## Expected output

- Bipartite K_{4,4}: each decode GPU receives from 4 prefill GPUs
- degree_lb = 4 (each decode GPU: 4 incoming; each prefill GPU: 4 outgoing)
- Under READ1_WRITE1: lower_bound = 4 ticks (one receive per tick per decode GPU)
- Greedy should achieve gap ≈ 0.0
- Insight: STRICT1 would require 8 ticks (no simultaneous send+receive)
  → quantifies the value of full-duplex transfer for disaggregated inference

## Caveats

Real KV-cache transfer may be chunked (streamed while generation starts).
seq_len=8192 represents a long-context scenario; shorter contexts (2048) would
yield ~4x smaller transfers. Adjust seq_len in the formula above to match your workload.
