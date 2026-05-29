# Product roadmap

## v0.1 — Public pilot CLI

- CSV demand import.
- STRICT1 and READ1_WRITE1 resource models.
- Streaming `--summary-only` analysis path.
- STRICT1 degree/capacity/subset-density lower bounds.
- Validation with accumulated diagnostics.
- ROI report and CI gate.
- Markdown/HTML/JSON report bundle.
- Demand and schedule anonymization.
- JSON schemas for v0 artifacts.
- Runtime artifact contract validation.
- Basic guardrails for large CI runs.
- Local `doctor` command and `make pilot-check`.
- Pilot readiness checklist.

## ✅ v0.2 — Pilot hardening (released)

- NCCL/PyTorch log importers (`import-nccl-log`, `import-pytorch-trace`, `infer`).
- External solver plugin (`--solver-plugin`).
- Practical/theoretical ROI split with `savings_kind`.
- `bounds_complete_reason` with public `BoundsReason` enum.
- `fractional_heuristic` bounds mode for scalable large-instance estimation.
- Real-workload examples (GPT-2, LLaMA-3, KV-cache, Megatron).
- `compare` command for side-by-side external schedule comparison.
- Inline report visualizations (ticks bars + top loaded slots) without external dependencies.

## v0.3 — Model extensions

- Topology-aware links.
- Asymmetric bandwidth.
- Broadcast/fanout support.
- Storage tier constraints.
- Optional exact solver integration for small instances.

## v1.0 — Enterprise-ready CLI

- Versioned artifact schemas.
- Signed report bundles.
- SBOM and release checksums.
- Performance benchmarks and scalability policy.
- Stable public API.
