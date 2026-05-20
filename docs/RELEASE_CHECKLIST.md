# Release checklist

Before tagging a release:

1. Run `make test`.
2. Run `python -m build --no-isolation`.
3. Build Docker image.
4. Run Docker smoke test.
5. Regenerate demo report.
6. Validate generated `summary.json` with `copyspace-guard validate-artifact --kind summary`.
7. Review README metrics.
8. Update `CHANGELOG.md`.
9. Generate checksums/SBOM for released artifacts.
10. Tag release, for example `v0.1.0-alpha`.
11. Attach generated wheel/sdist if publishing artifacts.
