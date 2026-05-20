# Data handling

Copy-Space Guard needs metadata, not payload data.

## Minimum required data

Demand CSV:

```csv
src_slot,dst_slot,bits_total
0,1,65536
```

Optional current schedule CSV:

```csv
tick,src_slot,dst_slot,len_bits
0,0,1,256
```

## Sensitive files

Treat these as sensitive unless intentionally shared:

- raw demand traces;
- raw schedule traces;
- ROI configs;
- `mapping.json` files produced by anonymization;
- generated reports for real customer workloads.

## Recommended pilot flow

1. Anonymize slot IDs.
2. Share only metadata, never payloads.
3. Keep mapping files inside the customer environment.
4. Calibrate ROI assumptions with the customer before using savings externally.
