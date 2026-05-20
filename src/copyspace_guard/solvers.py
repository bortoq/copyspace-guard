from __future__ import annotations

from typing import Dict, Iterable, Iterator, List, Tuple

from .io import validate_instance
from .types import Chunk, Demand, Instance, Schedule


def _aggregate_demands(demands: Iterable[Demand]) -> List[Demand]:
    merged: Dict[Tuple[int, int], int] = {}
    for d in demands:
        key = (int(d["src_slot"]), int(d["dst_slot"]))
        merged[key] = merged.get(key, 0) + int(d["bits_total"])
    return [
        {"src_slot": s, "dst_slot": t, "bits_total": bits}
        for (s, t), bits in sorted(merged.items())
    ]


def _pending_from_demands(demands: Iterable[Demand]) -> List[Dict[str, int]]:
    return [
        {"src_slot": int(d["src_slot"]), "dst_slot": int(d["dst_slot"]), "rem_bits": int(d["bits_total"])}
        for d in _aggregate_demands(demands)
    ]


def iter_baseline(inst: Instance) -> Iterator[List[Chunk]]:
    _slots, bw, demands = validate_instance(inst)
    pending = _pending_from_demands(demands)
    while pending:
        used = set()
        tick: List[Chunk] = []
        new_pending: List[Dict[str, int]] = []
        for item in pending:
            s, t, rem = item["src_slot"], item["dst_slot"], item["rem_bits"]
            if s in used or t in used:
                new_pending.append(item)
                continue
            l = min(bw, rem)
            tick.append({"src_slot": s, "dst_slot": t, "len_bits": l})
            used.add(s)
            used.add(t)
            if rem - l > 0:
                new_pending.append({"src_slot": s, "dst_slot": t, "rem_bits": rem - l})
        if not tick:
            raise RuntimeError("baseline solver made no progress")
        yield tick
        pending = new_pending


def _pending_degrees(pending: List[Dict[str, int]], bw: int) -> Dict[int, int]:
    deg: Dict[int, int] = {}
    for item in pending:
        chunks = (item["rem_bits"] + bw - 1) // bw
        deg[item["src_slot"]] = deg.get(item["src_slot"], 0) + chunks
        deg[item["dst_slot"]] = deg.get(item["dst_slot"], 0) + chunks
    return deg


def iter_greedy(inst: Instance) -> Iterator[List[Chunk]]:
    _slots, bw, demands = validate_instance(inst)
    pending = _pending_from_demands(demands)
    while pending:
        deg = _pending_degrees(pending, bw)
        order = list(range(len(pending)))

        def key(i: int) -> Tuple[int, int, int, int, int]:
            it = pending[i]
            s, t, rem = it["src_slot"], it["dst_slot"], it["rem_bits"]
            score = deg.get(s, 0) + deg.get(t, 0)
            return (-score, s, t, -min(bw, rem), i)

        order.sort(key=key)
        used = set()
        tick: List[Chunk] = []
        chosen = [False] * len(pending)
        chosen_len = [0] * len(pending)
        for i in order:
            s, t, rem = pending[i]["src_slot"], pending[i]["dst_slot"], pending[i]["rem_bits"]
            if s in used or t in used:
                continue
            l = min(bw, rem)
            tick.append({"src_slot": s, "dst_slot": t, "len_bits": l})
            chosen[i] = True
            chosen_len[i] = l
            used.add(s)
            used.add(t)
        if not tick:
            raise RuntimeError("greedy solver made no progress")
        new_pending: List[Dict[str, int]] = []
        for i, item in enumerate(pending):
            if chosen[i]:
                rem2 = item["rem_bits"] - chosen_len[i]
                if rem2 > 0:
                    new_pending.append({"src_slot": item["src_slot"], "dst_slot": item["dst_slot"], "rem_bits": rem2})
            else:
                new_pending.append(item)
        yield tick
        pending = new_pending


def materialize(ticks: Iterable[List[Chunk]]) -> Schedule:
    return {"version": 0, "model": "STRICT1", "ticks": list(ticks)}


def solve_baseline(inst: Instance) -> Schedule:
    return materialize(iter_baseline(inst))


def solve_greedy(inst: Instance) -> Schedule:
    return materialize(iter_greedy(inst))
