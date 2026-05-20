# JSON schemas

Copy-Space Guard keeps human-readable contracts in docs and machine-readable JSON schemas in `schemas/`.

Schemas currently included:

- `schemas/instance_v0.schema.json`
- `schemas/report_v0.schema.json`
- `schemas/schedule_v0.schema.json`
- `schemas/summary_v0.schema.json`

The schemas are intentionally permissive around future extension fields (`additionalProperties: true` at the top level) while validating the core v0 structure. The summary schema validates the core report, comparison, ROI and artifact fields that downstream CI jobs are expected to consume.

The CLI also includes a lightweight runtime contract validator:

```bash
copyspace-guard validate-artifact --kind summary artifacts/run/summary.json
```

Runtime schedule validation is intentionally semantic: it checks whether a schedule covers demands and respects the declared model. Artifact contract validation is stricter about generated JSON shape. Keep both paths in tests because they protect different failure modes.
