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

## STRICT1 bounds modes

Copy-Space Guard supports three STRICT1 modes:

- `auto` (default):
  - exact subset-density up to `--bounds-subset-limit` (capped),
  - when subset enumeration is exhaustive, also computes the exact odd-subset
    fractional lower bound `ceil(max_S(2*E(S)/(abs(S)-1)))` over odd subsets
    as part of the same pass (no extra iteration),
  - deterministic heuristic/fractional/core relaxations for larger slot counts.
- `fractional_odd_subset`:
  - stand-alone mode that computes the exact odd-subset fractional lower bound,
  - guarded to `slots <= 24` to avoid exponential blowups,
  - useful when auto subset-density is capped but you want the odd-subset bound.
- `fractional_heuristic`:
  - computes deterministic odd-subset fractional heuristic bounds for any slot count,
  - designed for large instances where exhaustive scans are impractical.

`bounds_complete` semantics:

- In `auto`, `bounds_complete` indicates whether exhaustive subset enumeration was used under the configured limit. When exhaustive, the odd-subset fractional bound is included.
- In `fractional_odd_subset`, `bounds_complete=true` for accepted inputs (the mode rejects larger slot counts before report generation).

Report metadata now includes:

- `bounds_mode`: selected STRICT1 mode (`auto`, `fractional_odd_subset`, or `fractional_heuristic`),
- `bounds_complete_reason`: explicit reason tag (`auto_exhaustive`, `auto_partial`, `fractional_odd_subset`, `fractional_heuristic_partial`, ...).

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
