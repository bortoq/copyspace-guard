# Megatron-LM Tensor Parallel AllReduce — GPT-3 175B, TP=8

## What this models

Tensor Parallel AllReduce communication within a single DGX A100 node (8 GPUs).
Each transformer layer requires 2 AllReduce operations (attention + FFN output).
Accumulated over all 96 layers of GPT-3 175B for one complete training step.

## How numbers were derived

Model: GPT-3 175B (Megatron-LM configuration)
- hidden_size = 12,288
- num_layers = 96
- seq_len = 2,048 tokens
- micro_batch_size = 1
- dtype = BF16 (2 bytes)
- tensor_parallel_size (TP) = 8

Per AllReduce payload (one attention or FFN block):
  hidden_size × seq_len × micro_batch × bytes
  = 12,288 × 2,048 × 1 × 2 = 50,331,648 bytes ≈ 50.3 MB

Per layer: 2 AllReduce operations (column-parallel + row-parallel linear)

Ring AllReduce per link per layer:
  2 × (N-1)/N × size × 2 (reduce-scatter + all-gather)
  = 2 × 7/8 × 50,331,648 × 2 = 176,160,768 bytes ≈ 176 MB

Total over 96 layers per training step:
  176,160,768 × 96 = 16,911,433,728 bytes ≈ 16.9 GB per ring link

bits_total = 16,911,433,728 × 8 = 135,291,469,824 bits

## Sources

- Megatron-LM paper (NVIDIA, SC 2021): arxiv:2104.04473
  "Efficient Large-Scale Language Model Training on GPU Clusters Using Megatron-LM"
  Table 1: GPT-3 175B config: 96 layers, 96 attention heads, hidden=12288
  https://arxiv.org/abs/2104.04473
- NVIDIA Megatron-LM scaling blog:
  https://developer.nvidia.com/blog/scaling-language-model-training-to-a-trillion-parameters-using-megatron/
- Megatron-Bridge performance guide (TP communication details):
  https://docs.nvidia.com/nemo/megatron-bridge/latest/performance-guide.html

## Recommended copyspace-guard command

```bash
copyspace-guard analyze \
  --csv examples/megatron_tp_allreduce/demands.csv \
  --bw 600000000000 \
  --model READ1_WRITE1 \
  --roi examples/megatron_tp_allreduce/roi.yml \
  --id megatron-gpt3-175b-tp8 \
  --outdir artifacts/megatron-tp
```

## Parameters explained

- `--bw 600000000000`: 600 GB/s — NVLink 4.0 bidirectional aggregate bandwidth
  (NVLink 4.0: 900 GB/s total, ~600 GB/s effective per direction at scale)
- `--model READ1_WRITE1`: NVLink is full-duplex; ring AllReduce uses both directions
- 8 slots → bounds_complete=True, gap exact
- Ring pattern identical to examples/ring15.csv but with GPT-3-scale volumes

## Expected output

- Ring pattern: degree_lb = 2 × 96 × 2 chunks per GPU (send+receive per layer)
- lower_bound_ticks determined by capacity: ceil(8 links × 16.9 GB / (4 × bw))
- Greedy should achieve near-optimal for uniform ring
- Insight: compare STRICT1 vs READ1_WRITE1 to quantify NVLink full-duplex value

## Caveats

Real Megatron-LM overlaps TP communication with computation using async AllReduce.
This model captures TOTAL communication volume per step, not the serialized latency.
With sequence parallelism enabled, TP communication pattern changes to
AllGather + ReduceScatter instead of AllReduce.
The numbers assume no gradient bucketing or communication compression.
