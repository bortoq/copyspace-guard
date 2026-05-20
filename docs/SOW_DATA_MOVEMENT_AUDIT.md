# Statement of Work — Data Movement Savings Audit

## 1. Objective

Perform a metadata-only audit of one customer data-movement workload to quantify schedule correctness, lower-bound gap, utilization and potential savings.

## 2. Duration

Diagnostic Audit: 10 business days from receipt of usable input metadata.

## 3. Customer responsibilities

Customer provides:

- transfer demand metadata in CSV/JSON or a representative log;
- definition of slots/endpoints;
- bandwidth or tick/window assumption;
- current schedule if available;
- optional ROI assumptions such as GPU-hour, node-hour, run frequency and SLA cost;
- technical contact for one kickoff and one review call.

## 4. Vendor responsibilities

Vendor provides:

- normalized workload contract;
- validation of customer/current schedule if supplied;
- deterministic candidate schedule;
- lower-bound gap, utilization and saved-tick metrics;
- ROI estimate if assumptions are supplied;
- Markdown/HTML/JSON report bundle;
- CI gate recommendation;
- list of recommended model extensions if STRICT1 is insufficient.

## 5. Deliverables

- `instance.json`
- `summary.json`
- `report.html`
- `report.md`
- current/customer schedule validation report
- candidate schedule validation report
- CI gate configuration draft
- final review call

## 6. Out of scope

- moving production payload data;
- replacing the customer scheduler;
- production storage implementation;
- guaranteed global optimality under unmodeled constraints;
- compliance certification;
- long-term support unless separately contracted.

## 7. Acceptance criteria

The audit is accepted when the report bundle is delivered and one review call is completed.

A commercially valuable result is at least one of:

- correctness issue found;
- `gap_to_lower_bound` above agreed threshold;
- candidate schedule reduces ticks;
- CI gate is defined;
- required model extension is identified.

## 8. Price

Recommended starting package: **$12,500 fixed fee**.

Optimization Sprint extension: **$45,000**.

Enterprise Pilot: **$95,000+**.
