# Customer schedule format

For real pilots, Copy-Space Guard should compare the customer's actual/current schedule against a deterministic candidate schedule.

## CSV format

```csv
tick,src_slot,dst_slot,len_bits
0,0,1,256
0,2,3,256
1,1,2,256
```

Fields:

- `tick` — zero-based discrete time window;
- `src_slot` — source endpoint;
- `dst_slot` — destination endpoint;
- `len_bits` — amount moved during that tick.

Rows with the same tick are executed in the same tick and must satisfy the active resource model.

## Run analysis with customer schedule

```bash
copyspace-guard analyze \
  --csv demands.csv \
  --bw 256 \
  --current-schedule-csv current_schedule.csv \
  --outdir artifacts/customer-run
```

The report will treat `customer_current` as the current schedule and compare it to `greedy`.

## Convert to JSON

```bash
copyspace-guard schedule-csv-to-json \
  --csv current_schedule.csv \
  --out current_schedule.json
```

Then:

```bash
copyspace-guard validate instance.json current_schedule.json
```

## Important notes

- Missing tick numbers are treated as empty elapsed ticks by default.
- This preserves runtime windows if a customer had idle periods.
- Use `--compact-ticks` only when missing tick numbers should be ignored.

## Streaming mode sort requirement

When `copyspace-guard analyze --summary-only` is used with `--current-schedule-csv`, the schedule CSV is streamed and must be sorted by non-decreasing `tick`. This keeps memory usage bounded for large traces. If the file is not sorted, the CLI exits with a readable error.
