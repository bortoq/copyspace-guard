# Paid pilot offer — Data Movement Savings Audit

## Objective

Identify measurable waste and regressions in one customer data-movement workload and deliver a deterministic report suitable for engineering review and CI gating.

## Duration

10 business days for the diagnostic package. 3–4 weeks for an optimization sprint with custom importer and model extension.

## Customer provides

Minimum:

- CSV or JSON transfer demands: `src_slot,dst_slot,bits_total`.
- Description of what a slot means: GPU, host, disk, storage tier, worker, partition, endpoint, etc.
- Per-tick or per-window transfer capacity.

Optional:

- Current schedule if available.
- Logs from job scheduler, storage system, data pipeline or query engine.
- Approximate cost per tick/window, GPU-hour, node-hour or failed SLA.
- Constraints not captured by STRICT1.

## Vendor delivers

1. Normalized workload contract (`instance.json`).
2. Baseline/candidate schedules.
3. Validation reports.
4. Markdown and HTML audit report.
5. CI-gate recommendation.
6. Executive summary with estimated savings and next steps.

## Success criteria

At least one of:

- find correctness conflict or hidden model violation;
- show `gap_to_lower_bound` above agreed threshold;
- produce candidate schedule with fewer ticks than baseline;
- define CI gate that catches future regressions;
- identify required model extension for a deeper paid sprint.

## Fixed-scope pricing

### Diagnostic Audit — $9,500

- one workload;
- one input format;
- STRICT1 model;
- baseline vs greedy comparison;
- report and one review call.

### Optimization Sprint — $35,000

- up to three workloads;
- custom importer;
- scheduler comparison including customer-provided schedule;
- CI gate integration draft;
- model extension recommendation.

### Enterprise Pilot — from $75,000

- on-prem packaging;
- private adapters;
- integration with internal CI;
- security review support;
- roadmap for audit/ledger/cost attribution.

## Out of scope for the diagnostic package

- moving real payload data;
- production deployment;
- topology-aware network optimizer;
- replacing customer scheduler;
- production security or compliance certification;
- storage system implementation.
