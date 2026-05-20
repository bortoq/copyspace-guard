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

## On-prem option

The MVP runs locally with no external dependencies and no network calls. For sensitive environments, run it inside the customer's own workstation, CI runner or cluster login node.

## Not yet production security

This MVP is not a production security product. It does not include:

- compliance certification;
- access-control system;
- cryptographic receipt verification in the CLI;
- production multi-tenant SaaS hardening.

Enterprise roadmap can add VCopySpace-style receipts, ledger settlement and replayable trace audit.
