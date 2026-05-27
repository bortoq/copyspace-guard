from __future__ import annotations

import math
import heapq
from typing import Any, Dict, List, Tuple

from .io import demand_map, validate_instance
from .types import Instance, READ1_WRITE1, STRICT1

DEFAULT_EXHAUSTIVE_SUBSET_LIMIT = 20
MAX_EXHAUSTIVE_SUBSET_LIMIT = 24
DEFAULT_STRICT1_BOUNDS_MODE = "auto"
STRICT1_BOUNDS_MODES = {"auto", "fractional_exact"}
MAX_FRACTIONAL_EXACT_SLOTS = 24
BOUNDS_REASON_AUTO_EXHAUSTIVE = "auto_exhaustive"
BOUNDS_REASON_AUTO_PARTIAL = "auto_partial"
BOUNDS_REASON_EXACT_FRACTIONAL_MODE = "exact_fractional_mode"
BOUNDS_REASON_READ1_WRITE1_COMPLETE = "read1_write1_complete"


def _chunk_edges(inst: Instance) -> Tuple[int, int, str, List[Tuple[int, int, int]]]:
    slots, bw, _ = validate_instance(inst)
    model = str(inst.get("model", STRICT1))
    edges: List[Tuple[int, int, int]] = []
    for (s, t), bits in demand_map(inst).items():
        chunks = (bits + bw - 1) // bw
        edges.append((s, t, chunks))
    return slots, bw, model, edges


def _build_weight_matrix(slots: int, edges: List[Tuple[int, int, int]]) -> List[List[int]]:
    w = [[0] * slots for _ in range(slots)]
    for s, t, c in edges:
        w[s][t] += c
        w[t][s] += c
    return w


def _compute_internal_edge_sums(w: List[List[int]]) -> List[int]:
    n = len(w)
    internal = [0] * (1 << n)
    for mask in range(1, 1 << n):
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
    return internal


def _compute_edge_internal(slots: int, edges: List[Tuple[int, int, int]]) -> Tuple[List[List[int]], List[int]]:
    w = _build_weight_matrix(slots, edges)
    return w, _compute_internal_edge_sums(w)


def _strict1_bounds(
    slots: int,
    edges: List[Tuple[int, int, int]],
    exhaustive_subset_limit: int,
    strict1_bounds_mode: str,
) -> Dict[str, Any]:
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
    bounds_complete_reason = BOUNDS_REASON_AUTO_EXHAUSTIVE if bounds_complete else BOUNDS_REASON_AUTO_PARTIAL

    if strict1_bounds_mode == "fractional_exact":
        if slots > MAX_FRACTIONAL_EXACT_SLOTS:
            raise ValueError(
                f"fractional_exact is limited to <= {MAX_FRACTIONAL_EXACT_SLOTS} slots; got {slots}"
            )
        if slots >= 3:
            _, internal = _compute_edge_internal(slots, edges)
            frac_lb = 0
            frac_num = 0
            frac_den = 1
            best_subset: list[int] = []
            best_internal = 0
            for mask in range(1, 1 << slots):
                k = mask.bit_count()
                if k < 3 or (k % 2 == 0):
                    continue
                frac_num = 2 * internal[mask]
                frac_den = k - 1
                mask_lb = math.ceil(frac_num / frac_den) if internal[mask] else 0
                if mask_lb > frac_lb:
                    frac_lb = mask_lb
                    best_subset = [i for i in range(slots) if mask & (1 << i)]
                    best_internal = internal[mask]
            if frac_lb > density_lb:
                density_lb = frac_lb
                witness = {
                    "kind": "fractional_exact_odd_subset",
                    "subset": best_subset,
                    "subset_size": len(best_subset),
                    "internal_chunks": best_internal,
                    "fraction_numerator": 2 * best_internal,
                    "fraction_denominator": max(1, len(best_subset) - 1),
                    "formula": "ceil(2*E(S)/(abs(S)-1))",
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
            "bounds_complete": slots <= MAX_FRACTIONAL_EXACT_SLOTS,
            "bounds_complete_reason": BOUNDS_REASON_EXACT_FRACTIONAL_MODE,
            "exhaustive_subset_limit": exhaustive_subset_limit,
            "strict1_bounds_mode": strict1_bounds_mode,
        }

    if bounds_complete and slots >= 2:
        w, internal = _compute_edge_internal(slots, edges)
        for mask in range(1, 1 << slots):
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
    elif slots >= 2:
        # Deterministic large-instance fallback: evaluate dense subsets around
        # high-degree vertices to tighten the lower bound without full 2^N scan.
        w = _build_weight_matrix(slots, edges)
        ranked = sorted(range(slots), key=lambda i: deg[i], reverse=True)
        seed_count = min(12, slots)
        for seed in ranked[:seed_count]:
            subset = {seed}
            neighbors = sorted((j for j in range(slots) if j != seed), key=lambda j: w[seed][j], reverse=True)
            for node in neighbors:
                subset.add(node)
                k = len(subset)
                cap = k // 2
                if cap <= 0:
                    continue
                internal_chunks = 0
                ss = sorted(subset)
                for i, u in enumerate(ss):
                    for v in ss[i + 1:]:
                        internal_chunks += w[u][v]
                lb_value = math.ceil(internal_chunks / cap) if internal_chunks else 0
                if lb_value > density_lb:
                    density_lb = lb_value
                    witness = {
                        "kind": "subset_density_heuristic",
                        "subset": ss,
                        "subset_size": k,
                        "internal_chunks": internal_chunks,
                        "tick_capacity_chunks": cap,
                    }
        # Fractional relaxation (odd-subset bound) heuristic for larger instances:
        # chi'_f >= max_{S odd} ceil( 2*E(S) / (|S|-1) ).
        # We search odd subsets using high-degree seeds and heavy-edge seeds.
        heavy_edges = heapq.nlargest(min(24, len(edges)), edges, key=lambda e: e[2])
        edge_seeds = {s for s, _t, _c in heavy_edges} | {t for _s, t, _c in heavy_edges}
        candidate_seeds = []
        seen = set()
        for node in ranked[: min(16, slots)] + sorted(edge_seeds):
            if node not in seen:
                seen.add(node)
                candidate_seeds.append(node)
        for seed in candidate_seeds:
            subset = {seed}
            selected = [False] * slots
            selected[seed] = True
            internal_chunks = 0
            while True:
                best_node = None
                best_gain = -1
                for node in range(slots):
                    if selected[node]:
                        continue
                    gain = 0
                    for u in subset:
                        gain += w[node][u]
                    if gain > best_gain or (gain == best_gain and (best_node is None or node < best_node)):
                        best_gain = gain
                        best_node = node
                if best_node is None:
                    break
                subset.add(best_node)
                selected[best_node] = True
                internal_chunks += max(best_gain, 0)
                k = len(subset)
                if k >= 3 and (k % 2 == 1):
                    frac_lb = math.ceil((2 * internal_chunks) / (k - 1)) if internal_chunks else 0
                    if frac_lb > density_lb:
                        ss = sorted(subset)
                        density_lb = frac_lb
                        witness = {
                            "kind": "fractional_relaxation_odd_subset",
                            "subset": ss,
                            "subset_size": k,
                            "internal_chunks": internal_chunks,
                            "formula": "ceil(2*E(S)/(abs(S)-1))",
                        }
        # LP-relaxation core pass: exact odd-subset scan on a larger high-pressure core.
        # This is equivalent to tightening the fractional matching lower bound on the core.
        core_size = min(18, slots)
        core_nodes = sorted(ranked[:core_size])
        core_index = {v: i for i, v in enumerate(core_nodes)}
        wc = [[0] * core_size for _ in range(core_size)]
        for s, t, c in edges:
            if s in core_index and t in core_index:
                i = core_index[s]
                j = core_index[t]
                wc[i][j] += c
                wc[j][i] += c
        if core_size >= 3:
            internal = _compute_internal_edge_sums(wc)
            lp_lb = 0
            for mask in range(1, 1 << core_size):
                k = mask.bit_count()
                if k < 3 or (k % 2 == 0):
                    continue
                lp_lb = math.ceil((2 * internal[mask]) / (k - 1)) if internal[mask] else 0
                if lp_lb > density_lb:
                    density_lb = lp_lb
                    witness = {
                        "kind": "lp_relaxation_core_odd_subset",
                        "subset": [core_nodes[i] for i in range(core_size) if mask & (1 << i)],
                        "subset_size": k,
                        "internal_chunks": internal[mask],
                        "formula": "ceil(2*E(S)/(abs(S)-1))",
                        "core_size": core_size,
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
        "bounds_complete_reason": bounds_complete_reason,
        "exhaustive_subset_limit": exhaustive_subset_limit,
        "strict1_bounds_mode": strict1_bounds_mode,
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
        "bounds_complete_reason": BOUNDS_REASON_READ1_WRITE1_COMPLETE,
        "exhaustive_subset_limit": None,
    }


def lower_bound_components(
    inst: Instance,
    *,
    exhaustive_subset_limit: int = DEFAULT_EXHAUSTIVE_SUBSET_LIMIT,
    strict1_bounds_mode: str = DEFAULT_STRICT1_BOUNDS_MODE,
) -> Dict[str, Any]:
    """Return deterministic lower bounds for the instance model."""
    if exhaustive_subset_limit < 0:
        raise ValueError("exhaustive_subset_limit must be >= 0")
    if exhaustive_subset_limit > MAX_EXHAUSTIVE_SUBSET_LIMIT:
        raise ValueError(f"exhaustive_subset_limit {exhaustive_subset_limit} exceeds hard cap {MAX_EXHAUSTIVE_SUBSET_LIMIT}")
    if strict1_bounds_mode not in STRICT1_BOUNDS_MODES:
        raise ValueError(f"unsupported strict1_bounds_mode: {strict1_bounds_mode}")
    slots, _bw, model, edges = _chunk_edges(inst)
    if model == READ1_WRITE1:
        out = _read1_write1_bounds(slots, edges)
    else:
        out = _strict1_bounds(slots, edges, exhaustive_subset_limit, strict1_bounds_mode)
    out["model"] = model
    return out


def lower_bound_ticks(inst: Instance) -> int:
    return int(lower_bound_components(inst)["lower_bound_ticks"])
