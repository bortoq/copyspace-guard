# Pitch deck — Copy-Space Guard

## Slide 1 — Title

Copy-Space Guard: deterministic data-movement audit for AI, HPC and analytics infrastructure.

## Slide 2 — Problem

Expensive compute waits for data. Shuffle, checkpointing, replication, staging and KV-cache movement can dominate real workload time and cost.

## Slide 3 — Why existing tooling misses it

Transfer tools move bytes. Orchestrators schedule tasks. Storage platforms serve data. Teams still lack an independent lower-bound report for movement plans.

## Slide 4 — Product

Metadata-only CLI/reporting tool that validates schedules, compares current vs candidate, computes lower-bound gap and produces CI gates.

## Slide 5 — Demo result

Example:

- current: 768 ticks;
- candidate: 549 ticks;
- saved: 219 ticks;
- utilization: 71.43% → 99.92%;
- gap: 50.00% → 7.23%.

## Slide 6 — ROI

With ROI config, saved ticks become:

- saved seconds per run;
- GPU/node-hours saved;
- savings per run/month/year.

## Slide 7 — Differentiation

- deterministic;
- independent validator;
- lower-bound gap, not just pass/fail;
- metadata-only;
- CI-ready;
- enterprise path to receipt/ledger accounting.

## Slide 8 — Beachhead customers

- AI infrastructure teams;
- GPU cloud/HPC teams;
- storage vendors;
- database/query engine teams;
- data platform teams.

## Slide 9 — Paid pilot

Data Movement Savings Audit:

- 10 business days;
- one workload;
- report bundle;
- CI gate;
- a fixed-scope pilot fee fixed fee.

## Slide 10 — Ask

Provide one sanitized `src,dst,bits` trace and optional current schedule. We return a deterministic audit report and a go/no-go recommendation for deeper optimization.
