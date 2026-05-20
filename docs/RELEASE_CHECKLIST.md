# Release checklist

Before tagging a release:

1. Run `make test`.
2. Run `python -m build`.
3. Build Docker image.
4. Regenerate demo report.
5. Review README metrics.
6. Update `CHANGELOG.md`.
7. Tag release, for example `v0.1.0-alpha`.
8. Attach generated wheel/sdist if publishing artifacts.
