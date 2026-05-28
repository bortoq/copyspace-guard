# Megatron-LM Tensor Parallel AllReduce — GPT-3 175B, TP=8

## What this models

Tensor Parallel AllReduce within a single DGX A100 node (8 GPUs, NVLink).
Accumulated communication over all 96 layers of GPT-3 175B for one training step.
Pattern: ring 0→1→2→3→4→5→6→7→0

Included files:
- `demands.csv` — ring transfer structure with GPT-3-scale volumes
- `naive_schedule.csv` — sequential schedule (one ring link at a time)
- `roi.yml` — cost model (GPU-hour cost at scale)

## How numbers were derived

GPT-3 175B (Megatron-LM, arxiv:2104.04473):
- hidden_size=12288, num_layers=96, seq_len=2048, BF16, TP=8
- Per AllReduce: 12288 × 2048 × 2 bytes = 50.3 MB; 2 per layer
- Ring per link per layer: 2 × 2 × (7/8) × 50.3 MB = 176 MB
- Total over 96 layers: 176 MB × 96 = 16.9 GB
- bits_total = 135,291,469,824 bits

## Source

- Megatron-LM (arxiv:2104.04473): https://arxiv.org/abs/2104.04473
- NVIDIA Megatron blog: https://developer.nvidia.com/blog/scaling-language-model-training-to-a-trillion-parameters-using-megatron/

## Scheduler comparison — run this to see saved_ticks

```bash
# Naive sequential: one ring link at a time, 8 ticks total
copyspace-guard analyze \
  --csv examples/megatron_tp_allreduce/demands.csv \
  --bw 600000000000 --model READ1_WRITE1 \
  --current-schedule-csv examples/megatron_tp_allreduce/naive_schedule.csv \
  --roi examples/megatron_tp_allreduce/roi.yml \
  --id megatron-gpt3-175b-tp8 \
  --outdir artifacts/megatron-tp
```

Expected output:
```
customer_current: status=PASS ticks=8 lb=1 gap=7.000000 util=2.8%
greedy:           status=PASS ticks=1 lb=1 gap=0.000000 util=22.6%
saved_ticks=7
```

**Interpretation:** a naive sequential ring (one link at a time) takes 8 ticks.
All 8 ring links can happen simultaneously under READ1_WRITE1 (NVLink full-duplex),
completing the entire AllReduce in 1 tick — **8x speedup**.

At scale (GPT-3 175B trains for weeks), this difference compounds:
even a 2x improvement in AllReduce scheduling translates to days of GPU time saved.

## Model comparison — STRICT1 vs READ1_WRITE1

```bash
# STRICT1 (half-duplex):
copyspace-guard analyze ... --model STRICT1  → greedy: 2 ticks
# READ1_WRITE1 (NVLink full-duplex):
copyspace-guard analyze ... --model READ1_WRITE1 → greedy: 1 tick
```

NVLink 4.0 bidirectional bandwidth enables simultaneous send+receive,
halving the AllReduce time compared to a half-duplex model.

## About utilization

`utilization=22.6%` (greedy) is the highest among all examples —
GPT-3's large tensors (16.9 GB per ring link) come closer to saturating NVLink 4.0 (600 GB/s).
The naive schedule (util=2.8%) wastes 7 of 8 ring links each tick.

## Caveats

Real Megatron-LM overlaps AllReduce with computation using async communication.
This model captures total TP communication volume per step, not serialized latency.
With sequence parallelism, pattern changes to AllGather + ReduceScatter.
