# Performance notes

## Summary mode

Use `--summary-only` for large workloads. Generated baseline and candidate schedules are streamed directly into the validator and full schedule JSON/CSV artifacts are not written.

Customer schedule CSVs in summary mode are also streamed and must be sorted by non-decreasing `tick`.

## Full artifact mode

Without `--summary-only`, Copy-Space Guard materializes and writes schedule JSON/CSV files. This is useful for small demos and debugging, but can produce large artifacts for high-volume workloads.

## Bounds

STRICT1 subset-density bounds are exhaustively enumerated up to the configured slot limit. For larger slot counts, `bounds_complete` is false and reports include a warning.

Use `--bounds-subset-limit N` to tune the exhaustive subset-density limit.

## Guardrails

For production or CI use, set explicit guardrails:

```bash
copyspace-guard analyze \
  --csv demands.csv \
  --bw 1048576 \
  --summary-only \
  --max-demands 100000 \
  --max-slots 10000 \
  --max-output-ticks 1000000 \
  --max-errors 100 \
  --outdir artifacts/run
```

## Benchmark

Run a synthetic ring benchmark:

```bash
copyspace-guard bench \
  --slots 64 \
  --bits-per-edge 1048576 \
  --bw 1048576 \
  --outdir artifacts/bench
```
