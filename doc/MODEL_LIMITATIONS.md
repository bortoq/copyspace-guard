# Model limitations

Copy-Space Guard v0 supports two deliberately simple endpoint-capacity models: `STRICT1` and `READ1_WRITE1`.

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
- broadcast/fanout semantics;
- storage tier locality;
- address-level offsets inside endpoints;
- real transfer execution.

## READ1_WRITE1

`READ1_WRITE1` allows one outgoing and one incoming transfer per slot per tick. It is useful for systems that approximate full-duplex endpoint behavior.

Still not modeled:

- multiple independent NICs per host;
- shared-switch oversubscription;
- storage media contention;
- object-store request limits;
- path-level routing.
