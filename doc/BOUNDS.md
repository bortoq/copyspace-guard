# STRICT1 lower bounds

Copy-Space Guard v0 models a tick as a matching over slots: each slot can
participate in at most one transfer per tick.

The report currently computes these deterministic lower bounds:

1. **Degree lower bound**
   - For each slot, count all incident chunks.
   - Any schedule needs at least the maximum incident chunk count.

2. **Capacity lower bound**
   - Each tick can contain at most `floor(slots / 2)` chunks.
   - Any schedule needs at least `ceil(total_chunks / floor(slots / 2))` ticks.

3. **Subset density lower bound**
   - For each subset `S`, a tick can contain at most `floor(|S| / 2)` transfers internal to `S`.
   - Any schedule needs at least `ceil(internal_chunks(S) / floor(|S| / 2))` ticks.
   - For slot counts up to the exhaustive limit, Copy-Space Guard checks every subset.

`lower_bound_ticks` is the maximum of these values.

## Important limitation

These are lower bounds, not a universal optimality proof for every possible
multigraph edge-coloring instance. If a candidate equals the lower bound, it is
optimal with respect to the implemented bound family and the declared STRICT1
model. For difficult graphs, the true optimum may still be higher than the
reported lower bound.

## READ1_WRITE1 bounds

For `READ1_WRITE1`, each slot may send once and receive once per tick. The implemented bounds are:

- maximum outgoing chunk count per source slot;
- maximum incoming chunk count per destination slot;
- full-graph capacity bound `ceil(total_chunks / slots)`.

These bounds are marked complete for the current v0 implementation.
