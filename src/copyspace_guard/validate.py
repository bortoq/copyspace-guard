from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from .bounds import lower_bound_components
from .io import demand_map, iter_schedule_csv_ticks, validate_instance
from .types import Chunk, Instance, MODEL, Report, Schedule


def fail_report(kind: str, msg: str, **ctx: Any) -> Report:
    err = {"kind": kind, "msg": msg}
    err.update(ctx)
    return Report(status="FAIL", version=0, model=MODEL, errors=[err])


def _final_report(inst: Instance, ticks_total: int, bits_total: int, errors: List[Dict[str, Any]]) -> Report:
    try:
        slots, bw, _ = validate_instance(inst)
        lbs = lower_bound_components(inst)
    except Exception as e:
        return fail_report("INSTANCE", str(e))
    bits_per_tick = bits_total / ticks_total if ticks_total > 0 else 0.0
    expected_bits_per_tick = (slots // 2) * bw
    utilization = bits_per_tick / expected_bits_per_tick if expected_bits_per_tick else 0.0
    lb = int(lbs["lower_bound_ticks"])
    gap = ticks_total - lb if not errors else 0
    gap_ratio = gap / lb if lb > 0 and not errors else 0.0
    return Report(
        status="FAIL" if errors else "PASS",
        version=0,
        model=MODEL,
        errors=errors,
        ticks_total=ticks_total,
        bits_total=bits_total,
        bits_per_tick=bits_per_tick,
        expected_bits_per_tick=expected_bits_per_tick,
        utilization=utilization,
        degree_lower_bound=int(lbs["degree_lower_bound"]),
        capacity_lower_bound=int(lbs["capacity_lower_bound"]),
        density_lower_bound=int(lbs["density_lower_bound"]),
        max_degree_chunks=int(lbs["degree_lower_bound"]),
        lower_bound_ticks=lb,
        gap_ticks=gap,
        gap_to_lower_bound=gap_ratio,
        lower_bound_witness=dict(lbs.get("lower_bound_witness", {})),
        bounds_complete=bool(lbs.get("bounds_complete", True)),
    )


def validate_ticks_iter(inst: Instance, ticks: Iterable[List[Chunk]]) -> Report:
    try:
        slots, bw, _demands = validate_instance(inst)
    except Exception as e:
        return fail_report("INSTANCE", str(e))

    errors: List[Dict[str, Any]] = []
    scheduled: Dict[Tuple[int, int], int] = {}
    bits_total = 0
    ticks_total = 0

    def add_error(kind: str, msg: str, **ctx: Any) -> None:
        err = {"kind": kind, "msg": msg}
        err.update(ctx)
        errors.append(err)

    for ti, tick in enumerate(ticks):
        ticks_total += 1
        if not isinstance(tick, list):
            add_error("STRUCT", "tick must be a list", tick=ti)
            continue
        used = set()
        for ci, ch in enumerate(tick):
            if not isinstance(ch, dict):
                add_error("STRUCT", "chunk must be an object", tick=ti, chunk=ci)
                continue
            try:
                s, t, l = int(ch["src_slot"]), int(ch["dst_slot"]), int(ch["len_bits"])
            except Exception:
                add_error("STRUCT", "chunk must contain integer src_slot,dst_slot,len_bits", tick=ti, chunk=ci)
                continue

            chunk_valid = True
            if s < 0 or t < 0 or s >= slots or t >= slots:
                add_error("STRUCT", "slot out of bounds", tick=ti, chunk=ci, src_slot=s, dst_slot=t)
                chunk_valid = False
            if s == t:
                add_error("STRUCT", "src_slot == dst_slot", tick=ti, chunk=ci, slot=s)
                chunk_valid = False
            if l <= 0 or l > bw:
                add_error("BANDWIDTH", "len_bits out of allowed range", tick=ti, chunk=ci, len_bits=l, bw=bw)
                chunk_valid = False
            if s in used or t in used:
                add_error("STRICT1", "slot participates more than once in one tick", tick=ti, chunk=ci, src_slot=s, dst_slot=t)
                chunk_valid = False

            if chunk_valid:
                used.add(s)
                used.add(t)
                scheduled[(s, t)] = scheduled.get((s, t), 0) + l
                bits_total += l
            else:
                if 0 <= s < slots:
                    used.add(s)
                if 0 <= t < slots:
                    used.add(t)

    try:
        dm = demand_map(inst)
    except Exception as e:
        return fail_report("INSTANCE", str(e))

    for pair, sbits in sorted(scheduled.items()):
        if pair not in dm:
            add_error("EXTRAS", "scheduled pair not present in demands", src_slot=pair[0], dst_slot=pair[1], scheduled_bits=sbits)
    for pair, dbits in sorted(dm.items()):
        sbits = scheduled.get(pair, 0)
        if sbits != dbits:
            add_error(
                "COVERAGE",
                "demand coverage mismatch",
                subkind="COVERAGE_UNDER" if sbits < dbits else "COVERAGE_OVER",
                src_slot=pair[0],
                dst_slot=pair[1],
                demand_bits=dbits,
                scheduled_bits=sbits,
            )

    return _final_report(inst, ticks_total, bits_total, errors)


def validate_schedule(inst: Instance, sched: Schedule) -> Report:
    if not isinstance(sched, dict):
        return fail_report("STRUCT", "schedule must be an object")
    if sched.get("version") != 0:
        return fail_report("STRUCT", "schedule.version must be 0")
    if sched.get("model") != MODEL:
        return fail_report("STRUCT", f'schedule.model must be "{MODEL}"')
    ticks = sched.get("ticks")
    if not isinstance(ticks, list):
        return fail_report("STRUCT", "schedule.ticks must be a list")
    return validate_ticks_iter(inst, ticks)


def validate_schedule_csv(inst: Instance, path: str, *, fill_empty_ticks: bool = True) -> Report:
    return validate_ticks_iter(inst, iter_schedule_csv_ticks(path, fill_empty_ticks=fill_empty_ticks))


def gate_report(
    rep: Report,
    *,
    max_gap: float | None = None,
    min_utilization: float | None = None,
    max_ticks: int | None = None,
) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    if rep.status != "PASS":
        reasons.append(f"status is {rep.status}, expected PASS")
    if max_gap is not None and rep.gap_to_lower_bound > max_gap:
        reasons.append(f"gap_to_lower_bound {rep.gap_to_lower_bound:.6f} > max_gap {max_gap:.6f}")
    if min_utilization is not None and rep.utilization < min_utilization:
        reasons.append(f"utilization {rep.utilization:.6f} < min_utilization {min_utilization:.6f}")
    if max_ticks is not None and rep.ticks_total > max_ticks:
        reasons.append(f"ticks_total {rep.ticks_total} > max_ticks {max_ticks}")
    return (len(reasons) == 0), reasons
