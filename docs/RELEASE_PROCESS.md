# Release process

Copy-Space Guard release artifacts are produced from a clean tree and verified before publishing.

## Local release check

```bash
make release-check
make production-check
```

This runs:

- static checks, type checks, unit tests and CLI smoke tests;
- pilot readiness smoke checks;
- wheel and sdist build;
- wheel install smoke in a clean virtual environment;
- `twine check` over built distributions;
- `SHA256SUMS`, `release_manifest.csv` and `sbom.cdx.json` generation.

`make production-check` extends this with the synthetic `bench-suite` performance smoke.

## Tag release

```bash
git tag -a vX.Y.Z[-label] -m "Copy-Space Guard vX.Y.Z release"
git push origin main
git push origin vX.Y.Z[-label]
```

The GitHub release workflow runs `make release-check`, performs Docker smoke testing, uploads build artifacts, attaches the release artifacts to the GitHub release, and then publishes the wheel/sdist to PyPI through Trusted Publishing for tag builds.

## PyPI Trusted Publishing

The workflow publishes to PyPI without a long-lived API token. Configure PyPI with a GitHub Actions trusted publisher or pending publisher that matches these values:

- PyPI project name: `copyspace-guard`
- Owner: `bortoq`
- Repository name: `copyspace-guard`
- Workflow filename: `release.yml`
- Environment name: `pypi`

The `pypi-publish` job grants `id-token: write` and uses `pypa/gh-action-pypi-publish@release/v1` without `username` or `password`, so PyPI exchanges the GitHub OIDC identity for a short-lived publishing token. Tag pushes matching `v*` publish distributions; manual `workflow_dispatch` runs execute release checks but do not publish to PyPI unless the ref is a tag.

## Generated release files

- `copyspace_guard-*.whl`
- `copyspace_guard-*.tar.gz`
- `SHA256SUMS`
- `release_manifest.csv`
- `sbom.cdx.json`

## Current boundary

The SBOM is a local CycloneDX-style dependency and artifact inventory generated without external services. Production distribution can add stronger signing and external SBOM tooling later.
