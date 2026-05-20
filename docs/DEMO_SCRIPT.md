# Five-minute demo script

## 0:00 — Setup

"Copy-Space Guard is a metadata-only audit tool. We do not move your data. We inspect the movement plan."

## 0:45 — Input

Show `examples/ring15.csv`:

```csv
src_slot,dst_slot,bits_total
0,1,65536
```

Explain: slots can be GPUs, hosts, storage nodes, workers, partitions or endpoints.

## 1:30 — Run

```bash
copyspace-guard analyze \
  --csv examples/ring15.csv \
  --bw 256 \
  --roi examples/roi.yml \
  --outdir artifacts/demo
```

## 2:15 — Output

Open `artifacts/demo/report.html`.

Point to:

- current ticks;
- candidate ticks;
- saved ticks;
- utilization gain;
- annualized savings.

## 3:30 — CI gate

```bash
copyspace-guard gate artifacts/demo/summary.json \
  --config examples/copyspace_guard.yml
```

Explain: this becomes a regression gate for scheduler/storage/query changes.

## 4:15 — Customer ask

"For a real audit we need one sanitized trace and your capacity assumption. If you have the actual current schedule, we compare against it directly."

## 5:00 — Close

Offer Diagnostic Audit: 10 business days, fixed scope, $12,500.
