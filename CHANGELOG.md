# Changelog

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
