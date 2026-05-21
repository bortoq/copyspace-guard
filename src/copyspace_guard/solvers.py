from __future__ import annotations

from typing import Dict, Iterable, Iterator, List, Tuple

from .io import validate_instance
from .types import Chunk, Demand, Instance, READ1_WRITE1, Schedule

DEFAULT_EXACT_CHUNK_LIMIT = 18


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


def _can_use(model: str, used: set[int], used_src: set[int], used_dst: set[int], s: int, t: int) -> bool:
    if model == READ1_WRITE1:
        return s not in used_src and t not in used_dst
    return s not in used and t not in used


def _mark_use(model: str, used: set[int], used_src: set[int], used_dst: set[int], s: int, t: int) -> None:
    if model == READ1_WRITE1:
        used_src.add(s)
        used_dst.add(t)
    else:
        used.add(s)
        used.add(t)


def iter_baseline(inst: Instance) -> Iterator[List[Chunk]]:
    _slots, bw, demands = validate_instance(inst)
    model = str(inst.get("model", "STRICT1"))
    pending = _pending_from_demands(demands)
    while pending:
        used: set[int] = set()
        used_src: set[int] = set()
        used_dst: set[int] = set()
        tick: List[Chunk] = []
        new_pending: List[Dict[str, int]] = []
        for item in pending:
            s, t, rem = item["src_slot"], item["dst_slot"], item["rem_bits"]
            if not _can_use(model, used, used_src, used_dst, s, t):
                new_pending.append(item)
                continue
            length = min(bw, rem)
            tick.append({"src_slot": s, "dst_slot": t, "len_bits": length})
            _mark_use(model, used, used_src, used_dst, s, t)
            if rem - length > 0:
                new_pending.append({"src_slot": s, "dst_slot": t, "rem_bits": rem - length})
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
    model = str(inst.get("model", "STRICT1"))
    pending = _pending_from_demands(demands)
    while pending:
        deg = _pending_degrees(pending, bw)
        order = list(range(len(pending)))

        def key(i: int, *, pending: List[Dict[str, int]] = pending, deg: Dict[int, int] = deg, bw: int = bw) -> Tuple[int, int, int, int, int]:
            it = pending[i]
            s, t, rem = it["src_slot"], it["dst_slot"], it["rem_bits"]
            score = deg.get(s, 0) + deg.get(t, 0)
            return (-score, s, t, -min(bw, rem), i)

        order.sort(key=key)
        used: set[int] = set()
        used_src: set[int] = set()
        used_dst: set[int] = set()
        tick: List[Chunk] = []
        chosen = [False] * len(pending)
        chosen_len = [0] * len(pending)
        for i in order:
            s, t, rem = pending[i]["src_slot"], pending[i]["dst_slot"], pending[i]["rem_bits"]
            if not _can_use(model, used, used_src, used_dst, s, t):
                continue
            length = min(bw, rem)
            tick.append({"src_slot": s, "dst_slot": t, "len_bits": length})
            chosen[i] = True
            chosen_len[i] = length
            _mark_use(model, used, used_src, used_dst, s, t)
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


def materialize(ticks: Iterable[List[Chunk]], model: str = "STRICT1") -> Schedule:
    return {"version": 0, "model": model, "ticks": list(ticks)}


def solve_baseline(inst: Instance) -> Schedule:
    return materialize(iter_baseline(inst), str(inst.get("model", "STRICT1")))


def solve_greedy(inst: Instance) -> Schedule:
    return materialize(iter_greedy(inst), str(inst.get("model", "STRICT1")))


def exact_optimal_ticks(inst: Instance, *, max_chunks: int = DEFAULT_EXACT_CHUNK_LIMIT) -> int:
    """Return exact optimum for small expanded chunk instances.

    This is intended as a regression oracle, not as the production scheduler.
    Each demand is expanded into bandwidth-sized unit chunks, then a depth-first
    search packs compatible chunks into the fewest ticks.
    """
    _slots, bw, demands = validate_instance(inst)
    model = str(inst.get("model", "STRICT1"))
    chunks: list[tuple[int, int]] = []
    for d in _aggregate_demands(demands):
        count = (int(d["bits_total"]) + bw - 1) // bw
        chunks.extend([(int(d["src_slot"]), int(d["dst_slot"]))] * count)
    if len(chunks) > max_chunks:
        raise ValueError(f"exact solver supports at most {max_chunks} chunks, got {len(chunks)}")
    if not chunks:
        return 0

    chunk_count = len(chunks)
    all_mask = (1 << chunk_count) - 1
    compatible_masks: list[int] = []
    for mask in range(1, 1 << chunk_count):
        used: set[int] = set()
        used_src: set[int] = set()
        used_dst: set[int] = set()
        ok = True
        for i, (s, t) in enumerate(chunks):
            if not mask & (1 << i):
                continue
            if not _can_use(model, used, used_src, used_dst, s, t):
                ok = False
                break
            _mark_use(model, used, used_src, used_dst, s, t)
        if ok:
            compatible_masks.append(mask)

    memo: dict[int, int] = {0: 0}

    def search(remaining: int) -> int:
        if remaining in memo:
            return memo[remaining]
        first = remaining & -remaining
        best = chunk_count
        for mask in compatible_masks:
            if not mask & first:
                continue
            if mask & remaining != mask:
                continue
            best = min(best, 1 + search(remaining ^ mask))
        memo[remaining] = best
        return best

    return search(all_mask)
