# GPT-2 DDP AllReduce — 8 GPU Ring

## What this models

Standard PyTorch DistributedDataParallel (DDP) training of GPT-2 (306M parameters).
Gradient AllReduce via NCCL Ring algorithm across 8 GPUs on a single DGX node.

Included files:
- `demands.csv` — transfer structure (who sends what to whom)
- `naive_schedule.csv` — sequential schedule (one transfer per tick, no parallelism)
- `roi.yml` — cost model for ROI estimation

## How numbers were derived

- Model: GPT-2, 306,000,000 parameters (FP32 gradients)
- Gradient buffer: 306M × 4 bytes = 1.224 GB
- Ring AllReduce: each GPU sends its chunk to the next GPU in the ring
- bits_total per link ≈ 2,142,000,000 bits (268 MB × 8 bits)
- Pattern: ring 0→1→2→3→4→5→6→7→0

## Source

- arxiv:2110.10401 "Monitoring Collective Communication Among GPUs" (ComScribe)
  Table 3: AllReduce size measurement during PyTorch DDP training
  https://arxiv.org/abs/2110.10401

## Scheduler comparison — run this to see saved_ticks

```bash
# Naive sequential scheduler (one transfer at a time, no parallelism):
# → 8 ticks, one per GPU pair
copyspace-guard analyze \
  --csv examples/gpt2_ddp_allreduce/demands.csv \
  --bw 25000000000 --model READ1_WRITE1 \
  --current-schedule-csv examples/gpt2_ddp_allreduce/naive_schedule.csv \
  --roi examples/gpt2_ddp_allreduce/roi.yml \
  --id gpt2-ddp-8gpu \
  --outdir artifacts/gpt2-ddp
```

Expected output:
```
customer_current: status=PASS ticks=8 lb=1 gap=7.000000 util=1.1%
greedy:           status=PASS ticks=1 lb=1 gap=0.000000 util=8.6%
saved_ticks=7
```

**Interpretation:** switching from a naive sequential scheduler to a parallel
one (all 8 ring transfers happen simultaneously) delivers **8x fewer ticks**.
Under READ1_WRITE1 (NVLink full-duplex), each GPU can send and receive
simultaneously — the entire ring completes in one tick.

## Model comparison — STRICT1 vs READ1_WRITE1

```bash
# STRICT1 (half-duplex — each GPU either sends OR receives per tick):
copyspace-guard analyze \
  --csv examples/gpt2_ddp_allreduce/demands.csv \
  --bw 25000000000 --model STRICT1 \
  --outdir artifacts/gpt2-ddp-strict1
# greedy: 2 ticks

# READ1_WRITE1 (full-duplex — NVLink allows simultaneous send+receive):
copyspace-guard analyze \
  --csv examples/gpt2_ddp_allreduce/demands.csv \
  --bw 25000000000 --model READ1_WRITE1 \
  --outdir artifacts/gpt2-ddp-rw1
# greedy: 1 tick
```

**Interpretation:** NVLink full-duplex (READ1_WRITE1) halves the AllReduce time
compared to a half-duplex model. This quantifies the value of NVLink over
standard Ethernet (STRICT1) for gradient synchronization.

## About utilization

`utilization=8.6%` (greedy, READ1_WRITE1) means each GPU uses 8.6% of
its NVLink bandwidth capacity per tick. This is correct — NVLink at 25 GB/s
has much more capacity than a single AllReduce requires. Lower utilization
means bandwidth is not the bottleneck; scheduling parallelism is.

The naive schedule (util=1.1%) wastes 7 of 8 available slots by serializing.

## Caveats

Real DDP uses gradient bucketing: instead of one large AllReduce,
PyTorch splits gradients into ~25 MB buckets and overlaps communication
with backward pass computation. This model captures total volume per step.
