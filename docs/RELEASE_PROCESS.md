# Release process

Copy-Space Guard release artifacts are produced from a clean tree and verified before publishing.

## Local release check

```bash
make release-check
```

This runs:

- static checks, type checks, unit tests and CLI smoke tests;
- pilot readiness smoke checks;
- wheel and sdist build;
- wheel install smoke in a clean virtual environment;
- `twine check` over built distributions;
- `SHA256SUMS`, `release_manifest.csv` and `sbom.cdx.json` generation.

## Tag release

```bash
git tag -a vX.Y.Z[-label] -m "Copy-Space Guard vX.Y.Z release"
git push origin main
git push origin vX.Y.Z[-label]
```

The GitHub release workflow runs `make release-check`, performs Docker smoke testing, uploads build artifacts, and attaches them to the GitHub release for tag builds.

## Generated release files

- `copyspace_guard-*.whl`
- `copyspace_guard-*.tar.gz`
- `SHA256SUMS`
- `release_manifest.csv`
- `sbom.cdx.json`

## Current boundary

The SBOM is a local CycloneDX-style dependency and artifact inventory generated without external services. Production distribution can add stronger signing and external SBOM tooling later.
