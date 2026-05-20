# Copy-Space Guard — Sales one-pager

## One-liner

**Copy-Space Guard finds wasted data movement before it burns GPU, storage and network budget.**

It validates and compares transfer schedules using deterministic lower-bound metrics, then turns the result into an engineering report and a CI regression gate.

## Target buyer

- VP / Director of AI Infrastructure
- HPC platform lead
- Data platform / analytics infrastructure lead
- Storage vendor product/solutions team
- Database or query-engine performance team

## Pain

Modern AI, HPC and analytics workloads spend large amounts of time moving data:

- checkpointing and restore;
- dataset staging;
- distributed shuffle;
- compaction, partitioning and materialization;
- replication and repair;
- storage tier movement;
- KV-cache movement and offload in inference systems.

Teams often have schedulers and scripts, but lack an independent deterministic way to answer:

1. Is this movement plan conflict-free?
2. How far is it from a lower bound?
3. Did a code change make movement worse?
4. What is the cost of the wasted ticks?

## Offer

A fixed-scope **Data Movement Savings Audit**.

Input:

- a CSV/JSON transfer trace or demand matrix;
- basic resource assumptions;
- optional cost assumptions such as $/GPU-hour, $/node-hour or $/transfer window.

Output:

- deterministic validation report;
- baseline vs candidate comparison;
- lower-bound gap and utilization metrics;
- estimated savings model;
- CI gate recipe;
- recommendation for next model extensions.

## Why now

AI infrastructure is increasingly limited by data locality, checkpointing, storage throughput and orchestration overhead. Teams buy GPUs first, then discover that feeding them efficiently is a separate infrastructure problem.

Copy-Space Guard is a low-risk way to quantify the problem from metadata before buying or rewriting infrastructure.

## Differentiation

- Metadata-only: no customer payload data required.
- Deterministic: same input produces same report.
- Independent: validates the client's existing scheduler instead of replacing it.
- Lower-bound based: reports normalized gap, not only pass/fail.
- CI-ready: converts performance assumptions into regression gates.
- Enterprise path: receipt-based metering and ledger integration via VCopySpace roadmap.

## Initial pricing suggestion

- Diagnostic Audit: **$5k–15k**
- Optimization Sprint: **$25k–75k**
- Enterprise on-prem license + support: **$30k–200k/year**
- Vendor/OEM integration: **$100k+**
