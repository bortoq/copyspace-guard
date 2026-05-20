from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from .io import demand_map, validate_instance
from .types import Instance

DEFAULT_EXHAUSTIVE_SUBSET_LIMIT = 20


def _chunk_edges(inst: Instance) -> Tuple[int, int, List[Tuple[int, int, int]]]:
    slots, bw, _ = validate_instance(inst)
    edges: List[Tuple[int, int, int]] = []
    for (s, t), bits in demand_map(inst).items():
        chunks = (bits + bw - 1) // bw
        edges.append((s, t, chunks))
    return slots, bw, edges


def lower_bound_components(inst: Instance, *, exhaustive_subset_limit: int = DEFAULT_EXHAUSTIVE_SUBSET_LIMIT) -> Dict[str, Any]:
    """Return all implemented STRICT1 matching-capacity lower bounds.

    For slots <= exhaustive_subset_limit, the density bound is computed over
    every subset S with |S| >= 2:

        ceil(internal_chunks(S) / floor(|S| / 2))

    This is the complete family of simple matching-capacity lower bounds. It is
    still a lower bound, not a proof of exact chromatic index for all graphs.
    For larger slot counts, the function returns degree and full-graph capacity
    bounds and marks bounds_complete=False.
    """
    slots, _bw, edges = _chunk_edges(inst)
    total_chunks = sum(c for _s, _t, c in edges)
    deg = [0] * slots
    for s, t, c in edges:
        deg[s] += c
        deg[t] += c
    degree_lb = max(deg) if deg else 0
    tick_capacity = slots // 2
    capacity_lb = math.ceil(total_chunks / tick_capacity) if tick_capacity > 0 else 0

    density_lb = capacity_lb
    witness: Dict[str, Any] = {
        "kind": "full_graph_capacity",
        "slots": slots,
        "internal_chunks": total_chunks,
        "tick_capacity_chunks": tick_capacity,
    }
    bounds_complete = slots <= exhaustive_subset_limit

    if bounds_complete and slots >= 2:
        # Weighted adjacency for undirected internal-edge counting.
        w = [[0] * slots for _ in range(slots)]
        for s, t, c in edges:
            a, b = (s, t) if s < t else (t, s)
            w[a][b] += c
            w[b][a] += c

        internal = [0] * (1 << slots)
        for mask in range(1, 1 << slots):
            lowbit = mask & -mask
            v = lowbit.bit_length() - 1
            prev = mask ^ lowbit
            add = 0
            m = prev
            while m:
                lb = m & -m
                u = lb.bit_length() - 1
                add += w[v][u]
                m ^= lb
            internal[mask] = internal[prev] + add
            k = mask.bit_count()
            cap = k // 2
            if cap <= 0:
                continue
            lb_value = math.ceil(internal[mask] / cap) if internal[mask] else 0
            if lb_value > density_lb:
                density_lb = lb_value
                witness = {
                    "kind": "subset_density",
                    "subset": [i for i in range(slots) if mask & (1 << i)],
                    "subset_size": k,
                    "internal_chunks": internal[mask],
                    "tick_capacity_chunks": cap,
                }

    lower = max(degree_lb, capacity_lb, density_lb)
    return {
        "degree_lower_bound": degree_lb,
        "capacity_lower_bound": capacity_lb,
        "density_lower_bound": density_lb,
        "lower_bound_ticks": lower,
        "total_chunks": total_chunks,
        "tick_capacity_chunks": tick_capacity,
        "lower_bound_witness": witness,
        "bounds_complete": bounds_complete,
        "exhaustive_subset_limit": exhaustive_subset_limit,
    }


def lower_bound_ticks(inst: Instance) -> int:
    return int(lower_bound_components(inst)["lower_bound_ticks"])
