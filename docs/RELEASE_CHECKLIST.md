# Release checklist

Before tagging a release:

1. Run `make test`.
2. Run `make pilot-check`.
3. Run `make release-check`.
4. Build Docker image.
5. Run Docker smoke test.
6. Regenerate demo report.
7. Validate generated `summary.json` with `copyspace-guard validate-artifact --kind summary`.
8. Review README metrics and the public product wording around deterministic candidates versus optimum.
9. Update `CHANGELOG.md`.
10. Review `dist/SHA256SUMS`, `dist/release_manifest.csv` and `dist/sbom.cdx.json`.
11. Sign release artifacts when publishing outside internal pilots.
12. Tag release, for example `v0.1.0-pilot`.
13. Push the tag and confirm the GitHub release workflow succeeds.
