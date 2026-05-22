# Artifact contracts

Copy-Space Guard emits versioned JSON artifacts with `version: 0`. The v0 contract is intentionally small and stable for pilot and early production integrations.

## Contract files

- `schemas/instance_v0.schema.json` describes normalized demand input.
- `schemas/schedule_v0.schema.json` describes materialized schedules.
- `schemas/report_v0.schema.json` describes one validation report.
- `schemas/summary_v0.schema.json` describes the combined analysis result.

Validate generated artifacts with:

```bash
copyspace-guard validate-artifact --kind summary artifacts/run/summary.json
copyspace-guard validate-artifact --kind report artifacts/run/report_greedy.json
```

## Compatibility policy

For `version: 0`:

- required fields remain present unless a new artifact version is introduced;
- labels such as `baseline`, `customer_current`, `current`, and `greedy` keep their current meaning;
- numeric metrics keep the same units;
- new optional fields may be added with backward-compatible semantics.

Breaking changes require a new artifact version and migration notes in the changelog.

## Golden coverage

The test suite includes a golden compatibility check for the bundled `examples/ring15.csv` summary-only run. It verifies stable labels, key metrics, and artifact names so release checks catch accidental contract drift.
