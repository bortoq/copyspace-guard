# LLaMA-3 70B Checkpoint Broadcast — 8 GPU Star

## What this models

Failure recovery checkpoint broadcast: rank 0 reads the checkpoint from storage
and sends shards to all other 7 GPUs. Pattern: star from GPU 0.

This example demonstrates a **structurally optimal but bandwidth-bound** workload:
the star pattern is irreducibly sequential under STRICT1 — no scheduler can do better
than 7 ticks. This is an important audit result: gap=0 means the system is optimal,
not that there is no room for improvement elsewhere.

## How numbers were derived

- LLaMA-3 70B: 70B params × BF16 (2 bytes) = 140 GB total checkpoint
- ZeRO-3 shard per GPU: 140 GB / 8 = 17.5 GB
- Naive broadcast: GPU 0 sends full shard to each of 7 peers sequentially
- bits_total = 17.5 GB × 8 bits = 140,000,000,000 bits per link

## Sources

- LLaMA-3 architecture: https://ai.meta.com/research/publications/the-llama-3-herd-of-models/
- Gemini checkpoint (SOSP 2023): https://www.cs.rice.edu/~eugeneng/papers/SOSP23.pdf
- ByteCheckpoint (NSDI 2025): https://www.usenix.org/system/files/nsdi25-wan-borui.pdf

## Run the audit

```bash
copyspace-guard analyze \
  --csv examples/llama3_70b_checkpoint/demands.csv \
  --bw 400000000000 --model STRICT1 \
  --roi examples/llama3_70b_checkpoint/roi.yml \
  --id llama3-70b-checkpoint \
  --outdir artifacts/llama3-checkpoint
```

Expected output:
```
baseline: status=PASS ticks=7 lb=7 gap=0.000000 util=8.8%
greedy:   status=PASS ticks=7 lb=7 gap=0.000000 util=8.8%
saved_ticks=0
```

**Interpretation:** `gap=0.0` and `saved_ticks=0` mean the schedule is **mathematically optimal**.
Under STRICT1, GPU 0 can only participate in one transfer per tick (either sending or receiving).
Since GPU 0 must send to 7 peers, the minimum possible time is exactly 7 ticks —
no scheduler, however clever, can improve on this.

**This is a valuable audit result:** it proves your checkpoint system is already optimal
for this pattern and model. If you observe more than 7 ticks in practice, the overhead
comes from I/O or CPU bottlenecks, not from scheduling.

## Switching to tree broadcast (READ1_WRITE1)

The star pattern (STRICT1) requires 7 ticks. A tree broadcast
allows intermediate GPUs to forward data, requiring only ceil(log2(7)) = 3 ticks:

```bash
# Tree broadcast: READ1_WRITE1 (full-duplex receivers can forward)
copyspace-guard analyze \
  --csv examples/llama3_70b_checkpoint/demands.csv \
  --bw 400000000000 --model READ1_WRITE1 \
  --outdir artifacts/llama3-checkpoint-tree
# greedy: 4 ticks — lower bound = 4, gap = 0
```

**Interpretation:** switching from naive star broadcast to tree broadcast
under READ1_WRITE1 reduces checkpoint recovery time from 7 to 4 ticks (~43% faster).
This models the difference between a simple "rank 0 sends to all" implementation
vs. a tree-based collective like MPI_Bcast or NCCL broadcast.

## About utilization

`utilization=8.8%` means each transfer uses 8.8% of InfiniBand NDR400 capacity.
The link is not saturated — checkpoint recovery is latency-bound (7 sequential ticks),
not bandwidth-bound. To improve: use tree broadcast (READ1_WRITE1 model above).

## Caveats

Real checkpoint recovery uses NCCL broadcast (tree algorithm) or object stores.
The star pattern models the naive "rank 0 reads and sends" implementation.
ByteCheckpoint uses all-to-all for ZeRO-3 resharding, which is a different pattern.
