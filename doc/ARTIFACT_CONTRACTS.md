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

`schemas/*.schema.json` are the published structural compatibility contract.
`copyspace-guard validate-artifact --kind summary` adds semantic validation, including checks that `reports[current_label]` and `reports[candidate_label]` are both present.

## Compatibility policy

For `version: 0`:

- required fields remain present unless a new artifact version is introduced;
- labels such as `baseline`, `customer_current`, `current`, and `greedy` keep their current meaning;
- numeric metrics keep the same units;
- new optional fields may be added with backward-compatible semantics.

In `audit` mode, `summary.json` is still `version: 0`, and may include additional optional `audit` metadata. In that mode, `candidate_label` can equal `customer_current` to indicate audit-only evaluation with no greedy/baseline comparison.

In `compare` mode, `summary.json` may use labels such as `current`, `schedule_a`, and `schedule_b`. JSON Schema intentionally permits this structurally, while semantic validation still requires the selected `current_label` and `candidate_label` keys to exist in `reports`.

Breaking changes require a new artifact version and migration notes in the changelog.

## Golden coverage

The test suite includes a golden compatibility check for the bundled `examples/ring15.csv` summary-only run. It verifies stable labels, key metrics, and artifact names so release checks catch accidental contract drift.
