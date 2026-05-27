# GPT-2 DDP AllReduce — 8 GPU Ring

## What this models

Standard PyTorch DistributedDataParallel training of GPT-2 (306M parameters).
Gradient AllReduce via NCCL Ring algorithm across 8 GPUs on a single DGX node.

## How numbers were derived

- Model: GPT-2, 306,000,000 parameters (FP32 gradients)
- Gradient buffer: 306M × 4 bytes = 1.224 GB
- Ring AllReduce: reduce-scatter + all-gather
  - Each GPU sends (N-1)/N × total to the next GPU in the ring
  - Simplified to equal ring-link demand: 1.224 GB × 8 / 8 = ~268 MB per link
  - bits_total = 2,142,000,000 bits ≈ 268 MB × 8
- Pattern: ring 0→1→2→3→4→5→6→7→0

## Source

- arxiv:2110.10401 "Monitoring Collective Communication Among GPUs" (ComScribe)
  Table 3: AllReduce size measurement during PyTorch DDP training
  https://arxiv.org/abs/2110.10401
- PyTorch DDP documentation: gradient bucket size default 25 MB
  https://pytorch.org/docs/stable/notes/ddp.html

## Recommended copyspace-guard command

```bash
copyspace-guard analyze \
  --csv examples/gpt2_ddp_allreduce/demands.csv \
  --bw 25000000000 \
  --model READ1_WRITE1 \
  --roi examples/gpt2_ddp_allreduce/roi.yml \
  --id gpt2-ddp-8gpu \
  --outdir artifacts/gpt2-ddp
```

## Parameters explained

- `--bw 25000000000`: 25 GB/s — NVLink 3.0 unidirectional bandwidth per GPU pair
- `--model READ1_WRITE1`: NVLink is full-duplex; each GPU can send and receive simultaneously
- 8 slots → bounds_complete=True, gap_to_lower_bound is mathematically exact

## Expected output

- Baseline (naive round-robin): likely 8 ticks
- Greedy: 4 ticks (READ1_WRITE1 allows full parallel ring)
- lower_bound_ticks: 4
- gap = 0.0 (greedy is optimal for uniform ring)

## Caveats

Real DDP uses gradient bucketing: instead of one large AllReduce,
PyTorch splits gradients into ~25 MB buckets and overlaps with backward pass.
This model captures the total volume per step, not the bucketed pattern.
Actual latency depends on computation/communication overlap.
