# Pilot readiness

Copy-Space Guard is pilot-grade when the checks below pass for the target repository or client package.

## Required checks

Run before sharing a pilot bundle or using the CLI in a customer review:

```bash
make test
make pilot-check
make build
```

For an installed CLI inside a copied project directory:

```bash
copyspace-guard doctor --root .
copyspace-guard analyze \
  --csv examples/ring15.csv \
  --bw 256 \
  --roi examples/roi.yml \
  --summary-only \
  --outdir /tmp/copyspace-guard-pilot
copyspace-guard validate-artifact --kind summary /tmp/copyspace-guard-pilot/summary.json
copyspace-guard gate /tmp/copyspace-guard-pilot/summary.json --config examples/copyspace_guard.yml
```

## Pilot scope

Included:

- metadata-only demand and schedule analysis;
- STRICT1 and READ1_WRITE1 endpoint resource models;
- deterministic baseline and greedy candidate comparison;
- JSON, Markdown and HTML report output;
- CI gate checks over generated `summary.json`;
- anonymization for demand and schedule CSVs;
- guardrails for slots, demands, output ticks and stored validation errors;
- schema and runtime contract validation for v0 artifacts.

Not included:

- proof that greedy is globally optimal;
- topology-aware or path-aware networking;
- production transfer execution;
- hosted service security boundary;
- signed report bundles or SBOM-backed releases.

## Customer handoff expectations

- Use `client-package/` for a minimal pilot bundle.
- Keep anonymization mapping files private.
- Use `--summary-only` for large traces unless full schedule artifacts are explicitly needed.
- Confirm the resource model before interpreting savings.
- Treat ROI values as first-pass estimates until calibrated with customer infrastructure costs.
