from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple, cast

from .bounds import DEFAULT_EXHAUSTIVE_SUBSET_LIMIT
from .bounds import lower_bound_components
from .bounds_reason import BoundsReason
from .io import demand_map, iter_schedule_csv_ticks, validate_instance
from .types import Chunk, Instance, MODEL, READ1_WRITE1, Report, Schedule


def _is_partial_bound(reason: str | None) -> bool:
    partial = {BoundsReason.AUTO_PARTIAL, BoundsReason.FRACTIONAL_HEURISTIC_PARTIAL}
    return reason in {r.value for r in partial}


def _gap_reliability(bounds_complete: bool) -> str:
    return "lower_bound_complete" if bounds_complete else "lower_bound_partial"


def _lower_bound_enumeration(bounds_complete: bool) -> str:
    return "complete" if bounds_complete else "partial"


def fail_report(kind: str, msg: str, **ctx: Any) -> Report:
    err = {"kind": kind, "msg": msg}
    err.update(ctx)
    return Report(status="FAIL", version=0, model=MODEL, errors=[err], total_errors=1)


def _final_report(
    inst: Instance,
    ticks_total: int,
    bits_total: int,
    errors: List[Dict[str, Any]],
    *,
    total_errors: int,
    bounds_subset_limit: int,
    strict1_bounds_mode: str,
) -> Report:
    try:
        slots, bw, _ = validate_instance(inst)
        lbs = lower_bound_components(
            inst,
            exhaustive_subset_limit=bounds_subset_limit,
            strict1_bounds_mode=strict1_bounds_mode,
        )
    except Exception as e:
        return fail_report("INSTANCE", str(e))
    bits_per_tick = bits_total / ticks_total if ticks_total > 0 else 0.0
    model = str(inst.get("model", MODEL))
    expected_chunks_per_tick = slots if model == READ1_WRITE1 else (slots // 2)
    expected_bits_per_tick = expected_chunks_per_tick * bw
    utilization = bits_per_tick / expected_bits_per_tick if expected_bits_per_tick else 0.0
    lb = int(lbs["lower_bound_ticks"])
    gap = ticks_total - lb if total_errors == 0 else 0
    gap_ratio = gap / lb if lb > 0 and total_errors == 0 else 0.0
    bounds_complete = bool(lbs.get("bounds_complete", True))
    return Report(
        status="FAIL" if total_errors else "PASS",
        version=0,
        model=model,
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
        gap_reliability=_gap_reliability(bounds_complete),
        lower_bound_enumeration=_lower_bound_enumeration(bounds_complete),
        optimality_certificate="none",
        gap_practical=None,
        lower_bound_witness=dict(lbs.get("lower_bound_witness", {})),
        bounds_complete=bounds_complete,
        bounds_mode=cast(str, lbs.get("strict1_bounds_mode")) if "strict1_bounds_mode" in lbs else None,
        bounds_complete_reason=cast(str, lbs.get("bounds_complete_reason")) if "bounds_complete_reason" in lbs else None,
        bounds_exhaustive_subset_limit=lbs.get("exhaustive_subset_limit"),
        total_errors=total_errors,
        errors_truncated=total_errors > len(errors),
    )


def validate_ticks_iter(
    inst: Instance,
    ticks: Iterable[List[Chunk]],
    *,
    max_errors: int | None = None,
    bounds_subset_limit: int = DEFAULT_EXHAUSTIVE_SUBSET_LIMIT,
    strict1_bounds_mode: str = "auto",
) -> Report:
    try:
        slots, bw, _demands = validate_instance(inst)
    except Exception as e:
        return fail_report("INSTANCE", str(e))
    model = str(inst.get("model", MODEL))

    errors: List[Dict[str, Any]] = []
    total_errors = 0
    scheduled: Dict[Tuple[int, int], int] = {}
    bits_total = 0
    ticks_total = 0

    def add_error(kind: str, msg: str, **ctx: Any) -> None:
        nonlocal total_errors
        total_errors += 1
        if max_errors is not None and len(errors) >= max_errors:
            return
        err = {"kind": kind, "msg": msg}
        err.update(ctx)
        errors.append(err)

    for ti, tick in enumerate(ticks):
        ticks_total += 1
        if not isinstance(tick, list):
            add_error("STRUCT", "tick must be a list", tick=ti)
            continue
        used = set()
        used_src = set()
        used_dst = set()
        for ci, ch in enumerate(tick):
            if not isinstance(ch, dict):
                add_error("STRUCT", "chunk must be an object", tick=ti, chunk=ci)
                continue
            try:
                s, t, length = int(ch["src_slot"]), int(ch["dst_slot"]), int(ch["len_bits"])
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
            if length <= 0 or length > bw:
                add_error("BANDWIDTH", "len_bits out of allowed range", tick=ti, chunk=ci, len_bits=length, bw=bw)
                chunk_valid = False
            if model == READ1_WRITE1:
                if s in used_src:
                    add_error("READ1_WRITE1", "source slot sends more than once in one tick", tick=ti, chunk=ci, src_slot=s, dst_slot=t)
                    chunk_valid = False
                if t in used_dst:
                    add_error("READ1_WRITE1", "destination slot receives more than once in one tick", tick=ti, chunk=ci, src_slot=s, dst_slot=t)
                    chunk_valid = False
            else:
                if s in used or t in used:
                    add_error("STRICT1", "slot participates more than once in one tick", tick=ti, chunk=ci, src_slot=s, dst_slot=t)
                    chunk_valid = False

            if chunk_valid:
                if model == READ1_WRITE1:
                    used_src.add(s)
                    used_dst.add(t)
                else:
                    used.add(s)
                    used.add(t)
                scheduled[(s, t)] = scheduled.get((s, t), 0) + length
                bits_total += length

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

    return _final_report(
        inst,
        ticks_total,
        bits_total,
        errors,
        total_errors=total_errors,
        bounds_subset_limit=bounds_subset_limit,
        strict1_bounds_mode=strict1_bounds_mode,
    )


def validate_schedule(
    inst: Instance,
    sched: Schedule,
    *,
    max_errors: int | None = None,
    bounds_subset_limit: int = DEFAULT_EXHAUSTIVE_SUBSET_LIMIT,
    strict1_bounds_mode: str = "auto",
) -> Report:
    if not isinstance(sched, dict):
        return fail_report("STRUCT", "schedule must be an object")
    if sched.get("version") != 0:
        return fail_report("STRUCT", "schedule.version must be 0")
    expected_model = str(inst.get("model", MODEL))
    if sched.get("model") != expected_model:
        return fail_report("STRUCT", f'schedule.model must match instance.model "{expected_model}"')
    ticks = sched.get("ticks")
    if not isinstance(ticks, list):
        return fail_report("STRUCT", "schedule.ticks must be a list")
    return validate_ticks_iter(
        inst,
        ticks,
        max_errors=max_errors,
        bounds_subset_limit=bounds_subset_limit,
        strict1_bounds_mode=strict1_bounds_mode,
    )


def validate_schedule_csv(
    inst: Instance,
    path: str,
    *,
    fill_empty_ticks: bool = True,
    max_errors: int | None = None,
    bounds_subset_limit: int = DEFAULT_EXHAUSTIVE_SUBSET_LIMIT,
    strict1_bounds_mode: str = "auto",
) -> Report:
    return validate_ticks_iter(
        inst,
        iter_schedule_csv_ticks(path, fill_empty_ticks=fill_empty_ticks),
        max_errors=max_errors,
        bounds_subset_limit=bounds_subset_limit,
        strict1_bounds_mode=strict1_bounds_mode,
    )


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
    if max_gap is not None and not rep.bounds_complete:
        tag = f" ({rep.bounds_complete_reason})" if rep.bounds_complete_reason else ""
        reasons.append(
            "bounds_complete=false"
            f"{tag}: gap is only against a partial lower bound. Use --max-gap-vs-greedy for reliable CI gating."
        )
    if max_gap is not None and rep.gap_to_lower_bound > max_gap:
        reasons.append(f"gap_to_lower_bound {rep.gap_to_lower_bound:.6f} > max_gap {max_gap:.6f}")
    if min_utilization is not None and rep.utilization < min_utilization:
        reasons.append(f"utilization {rep.utilization:.6f} < min_utilization {min_utilization:.6f}")
    if max_ticks is not None and rep.ticks_total > max_ticks:
        reasons.append(f"ticks_total {rep.ticks_total} > max_ticks {max_ticks}")
    return (len(reasons) == 0), reasons
