# Performance notes

## Summary mode

Use `--summary-only` for large workloads. Generated baseline and candidate schedules are streamed directly into the validator and full schedule JSON/CSV artifacts are not written.

Customer schedule CSVs in summary mode are also streamed and must be sorted by non-decreasing `tick`.

## Full artifact mode

Without `--summary-only`, Copy-Space Guard materializes and writes schedule JSON/CSV files. This is useful for small demos and debugging, but can produce large artifacts for high-volume workloads.

## Bounds

STRICT1 subset-density bounds are exhaustively enumerated up to the configured slot limit. For larger slot counts, `bounds_complete` is false and reports include a warning.

Use `--bounds-subset-limit N` to tune the exhaustive subset-density limit. The CLI enforces a hard cap to prevent accidental exponential runs; values above the cap fail fast.

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

Run synthetic benchmarks for both supported models before changing solver, validation or bounds code:

```bash
copyspace-guard bench \
  --slots 64 \
  --bits-per-edge 1048576 \
  --bw 1048576 \
  --outdir artifacts/bench

copyspace-guard bench \
  --slots 64 \
  --bits-per-edge 1048576 \
  --bw 1048576 \
  --model READ1_WRITE1 \
  --outdir artifacts/bench-readwrite
```

For release and CI smoke checks, run the suite:

```bash
copyspace-guard bench-suite \
  --outdir artifacts/bench-suite \
  --max-total-seconds 60
```

The suite writes `bench_suite.json` with per-case timings, validation reports and failure reasons. Thresholds should be calibrated per CI runner or customer environment; they are guardrails for regressions, not portable performance guarantees.

For scalability checks, also test sparse high-slot workloads, large demand counts, customer schedule CSVs with large tick gaps, and intentionally invalid schedules with `--max-errors`.

## Known failure modes

- Unsorted customer schedule CSVs fail streaming validation; sort by non-decreasing `tick`.
- Full artifact mode can create very large schedule JSON/CSV files; use `--summary-only` for CI and large pilots.
- STRICT1 lower-bound enumeration is partial when slot count exceeds the configured subset limit; inspect `bounds_complete`.
- Very large tick gaps in customer schedules preserve elapsed empty ticks and can inflate `ticks_total`.
- Anonymization mapping files may reveal original endpoint names and should be handled as sensitive data.
