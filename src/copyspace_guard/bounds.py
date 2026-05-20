from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from .io import demand_map, validate_instance
from .types import Instance, READ1_WRITE1, STRICT1

DEFAULT_EXHAUSTIVE_SUBSET_LIMIT = 20
MAX_EXHAUSTIVE_SUBSET_LIMIT = 24


def _chunk_edges(inst: Instance) -> Tuple[int, int, str, List[Tuple[int, int, int]]]:
    slots, bw, _ = validate_instance(inst)
    model = str(inst.get("model", STRICT1))
    edges: List[Tuple[int, int, int]] = []
    for (s, t), bits in demand_map(inst).items():
        chunks = (bits + bw - 1) // bw
        edges.append((s, t, chunks))
    return slots, bw, model, edges


def _strict1_bounds(slots: int, edges: List[Tuple[int, int, int]], exhaustive_subset_limit: int) -> Dict[str, Any]:
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
        w = [[0] * slots for _ in range(slots)]
        for s, t, c in edges:
            w[s][t] += c
            w[t][s] += c
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


def _read1_write1_bounds(slots: int, edges: List[Tuple[int, int, int]]) -> Dict[str, Any]:
    total_chunks = sum(c for _s, _t, c in edges)
    out_deg = [0] * slots
    in_deg = [0] * slots
    for s, t, c in edges:
        out_deg[s] += c
        in_deg[t] += c
    degree_lb = max(out_deg + in_deg) if slots else 0
    tick_capacity = slots
    capacity_lb = math.ceil(total_chunks / tick_capacity) if tick_capacity > 0 else 0
    lower = max(degree_lb, capacity_lb)
    witness = {
        "kind": "directed_read_write_capacity",
        "slots": slots,
        "total_chunks": total_chunks,
        "tick_capacity_chunks": tick_capacity,
        "max_out_degree_chunks": max(out_deg) if out_deg else 0,
        "max_in_degree_chunks": max(in_deg) if in_deg else 0,
    }
    return {
        "degree_lower_bound": degree_lb,
        "capacity_lower_bound": capacity_lb,
        "density_lower_bound": capacity_lb,
        "lower_bound_ticks": lower,
        "total_chunks": total_chunks,
        "tick_capacity_chunks": tick_capacity,
        "lower_bound_witness": witness,
        "bounds_complete": True,
        "exhaustive_subset_limit": None,
    }


def lower_bound_components(inst: Instance, *, exhaustive_subset_limit: int = DEFAULT_EXHAUSTIVE_SUBSET_LIMIT) -> Dict[str, Any]:
    """Return deterministic lower bounds for the instance model."""
    if exhaustive_subset_limit < 0:
        raise ValueError("exhaustive_subset_limit must be >= 0")
    if exhaustive_subset_limit > MAX_EXHAUSTIVE_SUBSET_LIMIT:
        raise ValueError(f"exhaustive_subset_limit {exhaustive_subset_limit} exceeds hard cap {MAX_EXHAUSTIVE_SUBSET_LIMIT}")
    slots, _bw, model, edges = _chunk_edges(inst)
    if model == READ1_WRITE1:
        out = _read1_write1_bounds(slots, edges)
    else:
        out = _strict1_bounds(slots, edges, exhaustive_subset_limit)
    out["model"] = model
    return out


def lower_bound_ticks(inst: Instance) -> int:
    return int(lower_bound_components(inst)["lower_bound_ticks"])
