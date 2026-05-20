# CI gate example — GitHub Actions

This example fails a build when the candidate schedule exceeds an agreed gap threshold.

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
        run: python -m pip install -e .
      - name: Analyze transfer demands
        run: |
          copyspace-guard analyze \
            --csv workloads/transfer_demands.csv \
            --bw 1048576 \
            --summary-only \
            --outdir artifacts/copyspace
      - name: Enforce regression threshold
        run: |
          copyspace-guard gate artifacts/copyspace/summary.json \
            --report greedy \
            --max-gap 0.15 \
            --min-utilization 0.85
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: copyspace-report
          path: artifacts/copyspace
```

For repository-local thresholds, use a config file:

```bash
copyspace-guard gate artifacts/copyspace/summary.json \
  --config examples/copyspace_guard.yml
```
