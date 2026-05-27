# Changelog

## v0.2.5 — 2026-05-27

Post-0.2.4 feature and quality updates.

Highlights:

- Added `copyspace-guard compare` for two external schedules on one demand matrix.
- Added `copyspace-guard bench-bounds` and integrated bounds benchmarking into `bench-suite`.
- Added community/project docs: `CONTRIBUTING.md`, `GOVERNANCE.md`, `CODE_OF_CONDUCT.md`, PR/issue templates, and `CODEOWNERS`.
- Added importer hardening and expanded importer test coverage (including happy-path parsing).
- Added optional `--max-gap-vs-greedy` threshold directly to `audit`.
- Fixed deterministic tie handling in fractional odd-subset lower-bound selection.
- Optimized fractional odd-subset candidate walk to avoid repeated list rebuilds in the inner loop.
- Added `--max-gap` support in `audit` for one-step CI gating.
- Unified `audit` gate-failure behavior to explicit gate reasons with exit code `2`.
- Added explicit test coverage for gate warning visibility when `bounds_complete=false`.
- Added a `fractional_exact` STRICT1 bounds mode (exact odd-subset fractional lower bound with guarded slot limit).

## v0.2.4 — 2026-05-27

Audit-first release.

Highlights:

- Repositioned docs and client guidance around external schedule auditing.
- Added external schedule import commands: `import-msccl`, `import-taccl`, and mapped `import-csv`.
- Added first-class `copyspace-guard audit` mode for audit-only runs.
- Added explicit external-audit interpretation metadata (`audit_note`, `gap_vs_greedy`).
- Improved large `STRICT1` lower bounds with fractional and LP-core odd-subset relaxations (no external dependencies).

## v0.2.3 — 2026-05-21

Security and release hardening.

Highlights:

- Bumped the package metadata to `0.2.3` after the anonymized CSV export hardening release.
- Hardened Markdown report rendering against user-controlled text injection.
- Applied output-path guardrails to all CLI write paths.
- Added size and row limits to anonymize commands.

## v0.2.2 — 2026-05-21

PyPI publishing fix.

Highlights:

- Restricted the PyPI Trusted Publishing job to upload only wheel and sdist distributions from release artifacts.

## v0.2.1 — 2026-05-21

Release and verification hardening.

Highlights:

- Added expanded tests for CLI commands, CSV error handling, validators, schema contracts, ROI calculations, report rendering, solver branches and release artifacts.
- Raised measured source coverage to 94% and added a README coverage badge.
- Added PyPI Trusted Publishing through GitHub Actions OIDC for tag releases.
- Documented the required PyPI trusted publisher configuration.

## v0.2.0 — 2026-05-20

Production-oriented pilot hardening release.

Highlights:

- Added release pipeline with wheel/sdist build, wheel-install smoke, `twine check`, checksums, release manifest and SBOM-style inventory.
- Added GitHub tag release workflow with Docker smoke and release artifact upload.
- Added machine-readable `copyspace-guard doctor --json` output for CI and client wrappers.
- Added `copyspace-guard bench-suite` and `make production-check` for performance smoke gating.
- Added golden compatibility coverage for the reference `ring15` summary artifact.
- Added artifact contract, operations, production-readiness and security policy docs.
- Included `SECURITY.md` and golden fixtures in source distributions.

## v0.1.0-pilot — 2026-05-20

Pilot-grade release.

Highlights:

- Metadata-only demand and schedule analysis.
- STRICT1 and READ1_WRITE1 resource models.
- Deterministic baseline and greedy candidate strategies.
- Streaming `--summary-only` analysis path.
- Degree, capacity and subset-density lower bounds for STRICT1.
- ROI report and CI gate.
- Schedule and demand anonymization.
- JSON schemas for v0 instance, schedule and summary artifacts.
- Unit and CLI tests plus GitHub Actions CI.

Hardening updates:

- Runtime artifact contract validation command.
- Local `doctor` command and version output for pilot support.
- `make pilot-check` for repeatable pilot smoke validation.
- Validation error caps with `total_errors` and truncation metadata.
- Analyze guardrails for slots, demands and output ticks.
- Reusable anonymization mapping input.
- Small-instance exact solver regression oracle.
- Wheel-install and Docker smoke checks in CI.
- Report artifact schema and package typing marker.
- Partner-facing material moved under `doc/partners/`.
- `copyspace-guard doctor --root .` and `make pilot-check` define the repeatable pilot-readiness smoke path.
- `make release-check` now builds and verifies wheel/sdist, runs wheel-install smoke, checks package metadata, and generates checksums plus a CycloneDX-style SBOM.
- Tag pushes now run a GitHub release workflow that uploads wheel, sdist, checksums, release manifest and SBOM.
- Added golden artifact compatibility coverage, `doctor --json`, `bench-suite`, `make production-check`, and production-readiness operations docs.
