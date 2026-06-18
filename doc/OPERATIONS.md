# Operations guide

## Local health check

Run the doctor before a pilot handoff, CI rollout, or release:

```bash
copyspace-guard doctor --root .
copyspace-guard doctor --root . --json
```

The JSON mode is intended for CI systems and client wrappers. It returns `status`, `root`, and a list of checks with `name`, `ok`, and `detail`.

## Production-style check

Use the aggregated Make target before tagging a release:

```bash
make production-check
```

This runs static checks, unit and CLI tests, coverage, pilot readiness, build and wheel smoke, release artifact generation, and a small performance suite.

## Performance smoke

Run:

```bash
copyspace-guard bench-suite --outdir artifacts/bench-suite --max-total-seconds 60
```

The suite writes `bench_suite.json` with per-case timings and validation reports. Treat the default threshold as a smoke guard, not a hardware-independent SLA.

## Incident triage

- Re-run with `COPYSPACE_GUARD_DEBUG=1` when a CLI command reports an unexpected failure.
- Use `--summary-only` for large workloads to avoid large schedule artifacts.
- Use `--max-errors`, `--max-demands`, `--max-slots`, and `--max-output-ticks` to keep client-side runs bounded.
- Preserve `summary.json`, reports, input CSVs, command line, package version, and `doctor --json` output when investigating a failure.
