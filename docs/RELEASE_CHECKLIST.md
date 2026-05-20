# Release checklist

Before tagging a release:

1. Run `make test`.
2. Run `make pilot-check`.
3. Run `make build`.
4. Build Docker image.
5. Run Docker smoke test.
6. Regenerate demo report.
7. Validate generated `summary.json` with `copyspace-guard validate-artifact --kind summary`.
8. Review README metrics and the public product wording around deterministic candidates versus optimum.
9. Update `CHANGELOG.md`.
10. Generate checksums for wheel, sdist and Docker image digest.
11. Generate or refresh SBOM for released artifacts.
12. Sign release artifacts when publishing outside internal pilots.
13. Tag release, for example `v0.1.0-alpha`.
14. Attach generated wheel/sdist if publishing artifacts.
