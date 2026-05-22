# ROI and gate configuration

## ROI config

Use ROI config to turn saved ticks into an executive business estimate.

Example `roi.yml`:

```yaml
roi:
  tick_seconds: 1
  gpu_count_blocked: 64
  gpu_hour_cost_usd: 2.50
  node_count_blocked: 0
  node_hour_cost_usd: 0
  runs_per_day: 12
  days_per_month: 30
  months_per_year: 12
```

Run:

```bash
copyspace-guard analyze \
  --csv examples/ring15.csv \
  --bw 256 \
  --roi examples/roi.yml \
  --outdir artifacts/demo
```

Report fields:

- saved ticks per run;
- saved seconds/hours per run;
- savings per run;
- savings per month;
- savings per year.

## Gate config

Example `copyspace_guard.yml`:

```yaml
gates:
  report: greedy
  max_gap_to_lower_bound: 0.15
  min_utilization: 0.85
```

Run:

```bash
copyspace-guard gate artifacts/demo/summary.json \
  --config examples/copyspace_guard.yml
```

Exit codes:

- `0` — pass;
- `2` — fail;
- `1` — usage or parse error.
