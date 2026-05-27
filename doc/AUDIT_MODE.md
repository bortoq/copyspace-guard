# Audit Mode

`copyspace-guard audit` is the preferred entry point when you already have a schedule from an external solver.

## When to use `audit` vs `analyze`

- Use `audit` when you want to validate one provided schedule and measure its gap.
- Use `analyze` when you also want deterministic baseline/greedy comparison artifacts.

## Command

```bash
copyspace-guard audit \
  --demands demands.csv \
  --bw 256 \
  --schedule current_schedule.csv \
  --outdir artifacts/audit
```

## Interpreting `audit_note`

- `audit_note` reminds you that `gap_to_lower_bound` is computed in the abstract model.
- If your external solver includes topology/path constraints, positive gap can still be expected.

## Interpreting `gap_vs_greedy`

In `analyze` with `customer_current`, the summary includes:

`gap_vs_greedy = (customer_ticks - greedy_ticks) / customer_ticks`

- Positive: current schedule is slower than greedy.
- Zero: equal to greedy.
- Negative: current schedule is faster than greedy.

For large-slot instances where lower bounds may be partial, this metric is often more stable for CI thresholding than `gap_to_lower_bound` alone.
