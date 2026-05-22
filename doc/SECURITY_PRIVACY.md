# Security and privacy positioning

## Metadata-only by default

Copy-Space Guard does not need customer payload data. The minimum input is transfer metadata:

- source slot;
- destination slot;
- number of bits/bytes;
- optional schedule tick.

## Sanitization

Customers can anonymize slot IDs before sharing:

```text
host-a -> 0
gpu-17 -> 1
bucket-prod-x -> 2
```

The report remains useful as long as relationships and volumes are preserved.

When anonymizing both demand and schedule CSVs, reuse the same mapping:

```bash
copyspace-guard anonymize --kind demands --csv raw_demands.csv --out demands_anon.csv --mapping mapping.json
copyspace-guard anonymize --kind schedule --csv raw_schedule.csv --out schedule_anon.csv --mapping-in mapping.json --mapping mapping.json
```

Anonymized CSV outputs preserve extra customer columns for context. Extra text cells are escaped for spreadsheet safety when they start with formula trigger characters (`=`, `+`, `-`, `@`, tab or carriage return). Numeric contract fields remain strict integers.

For untrusted or very large CSV inputs, `copyspace-guard anonymize` accepts optional `--max-rows` and `--max-file-size` guardrails.

## On-prem option

The CLI runs locally with no runtime Python dependencies and no network calls. For sensitive environments, run it inside the customer's own workstation, CI runner or cluster login node.

## Security boundary

Copy-Space Guard is a local-only metadata analysis tool, not a hosted security boundary. It does not include:

- compliance certification;
- access-control system;
- cryptographic receipt verification in the CLI;
- production multi-tenant SaaS hardening.

Enterprise roadmap can add VCopySpace-style receipts, ledger settlement and replayable trace audit.

## Mapping file sensitivity

Anonymization mapping files can reveal the original endpoint names. Treat `mapping.json` as sensitive and do not share it unless you intentionally want to reveal the mapping.

## Security status

Copy-Space Guard is a local-only CLI and not a multi-tenant SaaS security boundary. It is suitable for metadata-only local pilots, but production governance should still review trace handling, report sharing, and retention policy.
