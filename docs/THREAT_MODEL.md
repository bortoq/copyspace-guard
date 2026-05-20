# Threat model

## Scope

Copy-Space Guard is a local CLI for analyzing data-movement metadata. It is not a hosted service and does not move production payload data.

## Assets

- Transfer metadata: source slot, destination slot, volume and optional tick.
- ROI assumptions: cost and run-frequency estimates.
- Anonymization mapping files.
- Generated reports.

## Main risks

1. **Metadata disclosure** — slot IDs and volumes can reveal infrastructure topology or workload behavior.
2. **Mapping disclosure** — anonymization mapping files can reveal original endpoint names.
3. **Misinterpreted ROI** — ROI reports are estimates, not billing records.
4. **Model mismatch** — STRICT1 or READ1_WRITE1 may not match the real system.

## Controls in v0

- Payload data is not required.
- The CLI runs locally and makes no network calls at runtime.
- Anonymization is available for demand and schedule CSVs.
- Model limitations are documented.

## Out of scope in v0

- Multi-tenant SaaS isolation.
- Cryptographic report signing.
- Compliance certification.
- Access-control management.
- Byzantine or malicious input producers.
