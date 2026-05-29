# JSON schemas

Copy-Space Guard keeps human-readable contracts in `doc/` and machine-readable JSON schemas in `schemas/`.

Schemas currently included:

- `schemas/instance_v0.schema.json`
- `schemas/report_v0.schema.json`
- `schemas/schedule_v0.schema.json`
- `schemas/summary_v0.schema.json`

The schemas are intentionally permissive around future extension fields (`additionalProperties: true` at the top level) while validating the core v0 structure. The summary schema validates the core report, comparison, ROI and artifact fields that downstream CI jobs are expected to consume.

## Report fields (v0)

| Field | Type | Description |
|---|---|---|
| `status` | `"PASS"` / `"FAIL"` | Schedule validity |
| `model` | `"STRICT1"` / `"READ1_WRITE1"` | Resource model |
| `ticks_total` | integer | Total ticks in schedule |
| `gap_to_lower_bound` | number | Relative distance to lower bound |
| `gap_reliability` | `"exact"` / `"lower_estimate"` / `null` | Whether gap is exact or an estimate |
| `gap_practical` | number / `null` | `(customer_ticks - greedy_ticks) / customer_ticks` |
| `bounds_complete` | boolean | Whether bound computation is exhaustive |
| `bounds_mode` | `"auto"` / `"fractional_heuristic"` / `"fractional_odd_subset"` / `null` | Bounds mode used |
| `bounds_complete_reason` | `"auto_exhaustive"` / `"auto_partial"` / `"fractional_odd_subset"` / `"fractional_heuristic_partial"` / `"read1_write1_complete"` / `null` | Reason for bound completeness |
| `bounds_exhaustive_subset_limit` | integer / `null` | Subset limit used |

## Summary fields (v0)

| Field | Type | Description |
|---|---|---|
| `analysis_options.bounds_subset_limit` | integer | Exhaustive subset limit |
| `comparison.saved_ticks` | integer | Ticks saved by candidate vs current |
| `comparison.saved_ticks_pct` | number | Relative savings percentage |
| `roi.savings_kind` | string | `"baseline_comparison"` or `"customer_vs_greedy"` |

The CLI also includes a lightweight runtime contract validator:

```bash
copyspace-guard validate-artifact --kind summary artifacts/run/summary.json
```

Runtime schedule validation is intentionally semantic: it checks whether a schedule covers demands and respects the declared model. Artifact contract validation is stricter about generated JSON shape. Keep both paths in tests because they protect different failure modes.
