# Copy-Space Guard — client package

This folder shows the minimum files needed for a metadata-only data-movement audit.

## 1. Provide demands

Create a CSV like `sample_demands.csv`:

```csv
src_slot,dst_slot,bits_total
0,1,65536
```

## 2. Optional: provide current schedule

If you have the actual current schedule, provide:

```csv
tick,src_slot,dst_slot,len_bits
0,0,1,256
```

## 3. Optional: provide ROI assumptions

Edit `roi.yml` with your infrastructure assumptions.

## 4. Run locally

From project root:

```bash
bash client-package/run_local.sh
```

Outputs go to `artifacts/client-demo/`.

## Privacy

Only metadata is required. You may anonymize slot IDs before sharing.
