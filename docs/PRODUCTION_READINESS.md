# Production readiness

Copy-Space Guard is closer to production grade after the release, contract, operations, and performance hardening work, but it should still be treated as an early production CLI until real customer traces exercise the edge cases.

## Done

- Deterministic artifact contracts and schema validation.
- Golden compatibility coverage for the reference summary output.
- Release workflow with build, wheel smoke, checksum, manifest, and SBOM-like artifact.
- Machine-readable `doctor --json` for wrappers and CI.
- Production-style `bench-suite` smoke with JSON output and threshold gates.
- Local-only metadata processing with no runtime dependencies.

## Still required for full production grade

- Customer-trace benchmark baselines from real workloads and hardware.
- A formal support matrix for maximum slots, demands, ticks, and artifact sizes.
- Signed release provenance, not only checksums and manifests.
- Security response policy with named contacts and vulnerability handling SLA.
- Topology-aware model when pilots require path/link capacity constraints.
- Long-running soak tests for very large customer schedule CSVs.
