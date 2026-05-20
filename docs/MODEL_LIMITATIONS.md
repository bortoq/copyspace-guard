# Model limitations

Copy-Space Guard v0 uses `STRICT1`, a deliberately simple baseline model.

## STRICT1

Within one tick, each slot may participate in at most one transfer total:

- either one send;
- or one receive;
- not both;
- not multiple transfers.

This is equivalent to scheduling chunks as matchings over the slot graph.

## Good fits

STRICT1 is useful when the system behaves like endpoint-limited data movement:

- one active transfer per endpoint per time window;
- no same-tick fanout;
- no full-duplex assumption;
- no topology/path modeling required for the first audit.

## Not modeled in v0

- network topology and routes;
- asymmetric bandwidth;
- multiple NICs or queues per endpoint;
- separate read and write capacity;
- broadcast/fanout semantics;
- storage tier locality;
- address-level offsets inside endpoints;
- real transfer execution.

## Next likely model

The next useful extension is `READ1_WRITE1`: one read and one write per slot per
tick. This is often closer to full-duplex systems.
