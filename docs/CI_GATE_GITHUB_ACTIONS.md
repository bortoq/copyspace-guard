# CI gate example — GitHub Actions

This example fails a build when the optimized schedule exceeds an agreed gap threshold.

```yaml
name: copyspace-guard
on: [push, pull_request]

jobs:
  data-movement-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install Copy-Space Guard
        run: python -m pip install -e ./copyspace-guard
      - name: Analyze transfer demands
        run: |
          copyspace-guard analyze \
            --csv workloads/transfer_demands.csv \
            --bw 1048576 \
            --outdir artifacts/copyspace
      - name: Enforce regression threshold
        run: |
          python - <<'PY'
          import json, sys
          s = json.load(open('artifacts/copyspace/summary.json'))
          r = s['reports']['greedy']
          if r['status'] != 'PASS':
              raise SystemExit('schedule validation failed')
          if r['gap_to_lower_bound'] > 0.15:
              raise SystemExit(f"gap too high: {r['gap_to_lower_bound']}")
          if r['utilization'] < 0.85:
              raise SystemExit(f"utilization too low: {r['utilization']}")
          PY
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: copyspace-report
          path: artifacts/copyspace
```


## Local gate command

The MVP also includes a built-in gate command:

```bash
copyspace-guard gate artifacts/copyspace/summary.json \
  --report greedy \
  --max-gap 0.15 \
  --min-utilization 0.85
```

Use `--report current` to gate the customer/current schedule instead of the candidate.
