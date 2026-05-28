# KV-Cache Disaggregated Inference — 4 Prefill + 4 Decode GPUs

## What this models

Disaggregated inference (Splitwise / vLLM PD-disaggregation):
- Prefill GPUs (slots 0-3): process the prompt, generate KV-cache
- Decode GPUs (slots 4-7): receive KV-cache, run autoregressive generation
- Pattern: complete bipartite graph K_{4,4} — every prefill GPU sends to every decode GPU

Included files:
- `demands.csv` — transfer structure (K_{4,4} bipartite)
- `naive_schedule.csv` — sequential schedule: prefill GPU 0 sends to all, then GPU 1, etc.
- `roi.yml` — cost model for inference throughput estimation

## How numbers were derived

Model: LLaMA-3 70B
- num_layers = 80, num_kv_heads = 8 (GQA), head_dim = 128, seq_len = 8192, dtype = BF16
- KV-cache total = 8192 × 80 × 2 × 8 × 128 × 2 bytes = 2.68 GB
- Per prefill→decode pair: 2.68 GB / (4 × 4) = 167 MB = 1,342,177,280 bits

## Sources

- LLaMA-3 architecture: https://ai.meta.com/research/publications/the-llama-3-herd-of-models/
- Splitwise (ISCA 2024): https://arxiv.org/abs/2311.18677
- vLLM PD-disaggregation: https://blog.vllm.ai/2024/09/05/perf-update.html

## Scheduler comparison — run this to see saved_ticks

```bash
# Naive sequential: prefill GPU 0 sends to all decode, then GPU 1, etc.
# → 16 ticks (one transfer at a time)
copyspace-guard analyze \
  --csv examples/kv_cache_disagg/demands.csv \
  --bw 50000000000 --model READ1_WRITE1 \
  --current-schedule-csv examples/kv_cache_disagg/naive_schedule.csv \
  --roi examples/kv_cache_disagg/roi.yml \
  --id kv-cache-disagg-llama3-70b \
  --outdir artifacts/kv-cache-disagg
```

Expected output:
```
customer_current: status=PASS ticks=16 lb=4 gap=3.000000 util=0.3%
greedy:           status=PASS ticks=4  lb=4 gap=0.000000 util=1.3%
saved_ticks=12
```

**Interpretation:** a naive sequential scheduler (one GPU sends at a time)
takes 16 ticks. An optimal parallel scheduler uses all 4 prefill GPUs
simultaneously, completing in 4 ticks — a **4x speedup**.

Under READ1_WRITE1, each prefill GPU can send to one decode GPU per tick
while simultaneously receiving (if applicable). The lower bound is 4 ticks
because each decode GPU must receive from 4 different prefill GPUs.

## Why utilization is low (1.3%)

Each of the 16 transfers carries only 167 MB over a 50 GB/s link —
the link is not saturated per tick. This is realistic for disaggregated
inference where latency (not throughput) is the bottleneck. The scheduler
still matters because parallelism reduces total time 4x regardless of
per-link utilization.

## Caveats

Real KV-cache transfer is often chunked and pipelined with generation.
seq_len=8192 is a long-context scenario; shorter contexts reduce transfer size proportionally.
