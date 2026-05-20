# Outbound email templates

## Ultra-short

Subject: Quick audit for wasted data movement in <company> AI infra

Hi <name>,

I’m building Copy-Space Guard, a metadata-only tool that checks transfer schedules for conflicts, lower-bound gap and utilization regressions.

If you can share a sanitized `src,dst,bytes` trace from one AI/HPC/data workload, I can return a deterministic report showing whether the movement plan is wasting ticks and how to gate regressions in CI.

Worth a 20-minute call?

— <sender>

## Technical

Subject: Deterministic lower-bound report for data movement schedules

Hi <name>,

Many AI and analytics systems lose time not in compute, but in shuffle, staging, checkpointing, replication and storage-tier movement.

Copy-Space Guard takes a transfer demand matrix like:

```csv
src_slot,dst_slot,bits_total
0,1,65536
```

and produces:

- conflict validation under a declared resource model;
- baseline vs candidate schedule comparison;
- `lower_bound_ticks` and `gap_to_lower_bound`;
- utilization metrics;
- CI gate thresholds for regressions.

It is metadata-only; no payload data is required.

I’m offering a fixed-scope Data Movement Savings Audit for one workload. If you have a trace or demand matrix, I can show a sample report quickly.

Open to a short technical review?

— <sender>

## Storage/vendor angle

Subject: Independent movement-efficiency report for storage/AI demos

Hi <name>,

For storage and AI infrastructure demos, customers often ask whether data placement and movement policies are really efficient.

Copy-Space Guard is a deterministic audit layer that turns transfer demands into lower-bound gap, utilization and regression reports. It can be used as a benchmark harness or customer-facing proof report without moving payload data.

I’d like to test it on one representative movement pattern from your platform and return a shareable report.

Interested?

— <sender>
