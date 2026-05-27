# LLaMA-3 70B Checkpoint Broadcast — 8 GPU Star

## What this models

Failure recovery checkpoint broadcast: after a GPU failure, rank 0 reads the
checkpoint from storage and distributes shards to all other 7 GPUs.
Uses ZeRO-3 sharding: each GPU holds 1/8 of the total model.

## How numbers were derived

- Model: LLaMA-3 70B, 70,000,000,000 parameters
- Precision: BF16 = 2 bytes per parameter
- Total checkpoint size: 70B × 2 = 140 GB
- ZeRO-3 shard per GPU: 140 GB / 8 = 17.5 GB
- Pattern: star — GPU 0 (disk reader) sends full shard to each of 7 GPUs
- bits_total = 17.5 GB × 8 bits = 140,000,000,000 bits per link

Note: 140 Gbits here represents the FULL checkpoint read by GPU 0 per peer,
because in naive broadcast GPU 0 must send 17.5 GB to each of 7 receivers.
Optimized tree broadcast would halve the load on GPU 0.

## Sources

- Meta AI / LLaMA-3 architecture: 70B parameters, BF16 weights
  https://ai.meta.com/research/publications/the-llama-3-herd-of-models/
  ISCA 2025: "Scaling Llama 3 Training with Efficient Parallelism Strategies"
  https://aisystemcodesign.github.io/papers/Llama3-ISCA25.pdf
- SOSP 2023 Gemini: "checkpoint size of GPT2-100B on each GPU is 9.4 GB"
  https://www.cs.rice.edu/~eugeneng/papers/SOSP23.pdf
- ByteCheckpoint (NSDI 2025): all-to-all checkpoint transfer design
  https://www.usenix.org/system/files/nsdi25-wan-borui.pdf

## Recommended copyspace-guard command

```bash
copyspace-guard analyze \
  --csv examples/llama3_70b_checkpoint/demands.csv \
  --bw 400000000000 \
  --model STRICT1 \
  --roi examples/llama3_70b_checkpoint/roi.yml \
  --id llama3-70b-checkpoint \
  --outdir artifacts/llama3-checkpoint
```

## Parameters explained

- `--bw 400000000000`: 400 GB/s — InfiniBand NDR400 unidirectional
- `--model STRICT1`: checkpoint sender (GPU 0) can only send to one GPU at a time
  (disk I/O is the bottleneck, not NIC; GPU 0 cannot pipeline reads)
- 8 slots → bounds_complete=True, gap exact

## Expected output

- degree_lb = 7 (slot 0 participates in 7 transfers)
- lower_bound_ticks = 7 (star pattern is irreducibly sequential under STRICT1)
- Greedy = 7 ticks, gap = 0.0 — cannot do better than 7 under STRICT1
- Insight: switching to READ1_WRITE1 (tree broadcast) would halve ticks to ~4

## Caveats

Real checkpoint recovery uses tree broadcast (0→1, 0→4, then 1→2, 1→3, 4→5, 4→6, etc.)
which is READ1_WRITE1 compatible. Run with --model READ1_WRITE1 to see the
theoretical improvement from a tree broadcast schedule.
