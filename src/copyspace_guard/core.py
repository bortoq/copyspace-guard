from __future__ import annotations

import csv
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple, Any

MODEL = "STRICT1"

Demand = Dict[str, int]
Chunk = Dict[str, int]
Schedule = Dict[str, Any]
Instance = Dict[str, Any]


@dataclass(frozen=True)
class Report:
    status: str
    version: int
    model: str
    errors: List[Dict[str, Any]]
    ticks_total: int = 0
    bits_total: int = 0
    bits_per_tick: float = 0.0
    expected_bits_per_tick: int = 0
    utilization: float = 0.0
    max_degree_chunks: int = 0
    lower_bound_ticks: int = 0
    gap_ticks: int = 0
    gap_to_lower_bound: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def load_json(path: str | Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: str | Path, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")


def read_demands_csv(path: str | Path) -> List[Tuple[int, int, int]]:
    rows: List[Tuple[int, int, int]] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        has_header = "src_slot" in sample and "dst_slot" in sample and "bits_total" in sample
        if has_header:
            rdr = csv.DictReader(f)
            for i, row in enumerate(rdr, start=2):
                if not row or all((v is None or str(v).strip() == "") for v in row.values()):
                    continue
                try:
                    rows.append((int(row["src_slot"]), int(row["dst_slot"]), int(row["bits_total"])))
                except Exception as e:
                    raise ValueError(f"bad CSV row {i}: expected src_slot,dst_slot,bits_total integers") from e
        else:
            rdr = csv.reader(f)
            for i, row in enumerate(rdr, start=1):
                if not row or all(not x.strip() for x in row):
                    continue
                if len(row) < 3:
                    raise ValueError(f"bad CSV row {i}: expected 3 columns")
                rows.append((int(row[0]), int(row[1]), int(row[2])))
    if not rows:
        raise ValueError("no demands found in CSV")
    return rows


def instance_from_csv(path: str | Path, bw: int, slots: int | None = None, instance_id: str | None = None, notes: str | None = None) -> Instance:
    if bw <= 0:
        raise ValueError("copy bandwidth per tick must be > 0")
    rows = read_demands_csv(path)
    max_slot = max(max(s, t) for s, t, _ in rows)
    slots2 = slots if slots is not None else max_slot + 1
    if slots2 <= 0:
        raise ValueError("slots must be > 0")
    merged: Dict[Tuple[int, int], int] = {}
    for s, t, bits in rows:
        if s < 0 or t < 0 or s >= slots2 or t >= slots2:
            raise ValueError(f"slot out of bounds: {s}->{t} with slots={slots2}")
        if s == t:
            raise ValueError(f"src_slot equals dst_slot: {s}")
        if bits <= 0:
            raise ValueError(f"bits_total must be > 0 for {s}->{t}")
        merged[(s, t)] = merged.get((s, t), 0) + bits
    inst: Instance = {
        "version": 0,
        "model": MODEL,
        "slots": slots2,
        "copy_bw_bits_per_tick": bw,
        "demands": [
            {"src_slot": s, "dst_slot": t, "bits_total": bits}
            for (s, t), bits in sorted(merged.items())
        ],
    }
    if instance_id:
        inst["id"] = instance_id
    if notes:
        inst["notes"] = notes
    return inst


def demand_map(inst: Instance) -> Dict[Tuple[int, int], int]:
    slots = int(inst["slots"])
    out: Dict[Tuple[int, int], int] = {}
    for i, d in enumerate(inst.get("demands", [])):
        s, t, b = int(d["src_slot"]), int(d["dst_slot"]), int(d["bits_total"])
        if s < 0 or t < 0 or s >= slots or t >= slots or s == t or b <= 0:
            raise ValueError(f"bad demand[{i}]")
        out[(s, t)] = out.get((s, t), 0) + b
    return out


def validate_instance(inst: Instance) -> Tuple[int, int, List[Demand]]:
    if not isinstance(inst, dict):
        raise ValueError("instance must be an object")
    if inst.get("version") != 0:
        raise ValueError("instance.version must be 0")
    if inst.get("model") != MODEL:
        raise ValueError(f'instance.model must be "{MODEL}"')
    slots = inst.get("slots")
    bw = inst.get("copy_bw_bits_per_tick")
    if not isinstance(slots, int) or slots <= 0:
        raise ValueError("instance.slots must be int > 0")
    if not isinstance(bw, int) or bw <= 0:
        raise ValueError("instance.copy_bw_bits_per_tick must be int > 0")
    demands = inst.get("demands", [])
    if not isinstance(demands, list):
        raise ValueError("instance.demands must be a list")
    _ = demand_map(inst)
    return slots, bw, demands


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


def solve_baseline(inst: Instance) -> Schedule:
    _slots, bw, demands = validate_instance(inst)
    pending = _pending_from_demands(demands)
    ticks: List[List[Chunk]] = []
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
            used.add(s); used.add(t)
            if rem - l > 0:
                new_pending.append({"src_slot": s, "dst_slot": t, "rem_bits": rem - l})
        if not tick:
            raise RuntimeError("baseline solver made no progress")
        ticks.append(tick)
        pending = new_pending
    return {"version": 0, "model": MODEL, "ticks": ticks}


def _pending_degrees(pending: List[Dict[str, int]], bw: int) -> Dict[int, int]:
    deg: Dict[int, int] = {}
    for item in pending:
        chunks = (item["rem_bits"] + bw - 1) // bw
        deg[item["src_slot"]] = deg.get(item["src_slot"], 0) + chunks
        deg[item["dst_slot"]] = deg.get(item["dst_slot"], 0) + chunks
    return deg


def solve_greedy(inst: Instance) -> Schedule:
    _slots, bw, demands = validate_instance(inst)
    pending = _pending_from_demands(demands)
    ticks: List[List[Chunk]] = []
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
            chosen[i] = True; chosen_len[i] = l
            used.add(s); used.add(t)
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
        ticks.append(tick)
        pending = new_pending
    return {"version": 0, "model": MODEL, "ticks": ticks}


def lower_bound_ticks(inst: Instance) -> int:
    slots, bw, _demands = validate_instance(inst)
    deg = [0] * slots
    for (s, t), bits in demand_map(inst).items():
        chunks = (bits + bw - 1) // bw
        deg[s] += chunks
        deg[t] += chunks
    return max(deg) if deg else 0


def fail_report(kind: str, msg: str, **ctx: Any) -> Report:
    err = {"kind": kind, "msg": msg}
    err.update(ctx)
    return Report(status="FAIL", version=0, model=MODEL, errors=[err])


def validate_schedule(inst: Instance, sched: Schedule) -> Report:
    try:
        slots, bw, _demands = validate_instance(inst)
    except Exception as e:
        return fail_report("INSTANCE", str(e))
    if not isinstance(sched, dict):
        return fail_report("STRUCT", "schedule must be an object")
    if sched.get("version") != 0 or sched.get("model") != MODEL:
        return fail_report("STRUCT", "schedule.version/model mismatch")
    ticks = sched.get("ticks")
    if not isinstance(ticks, list):
        return fail_report("STRUCT", "schedule.ticks must be a list")

    scheduled: Dict[Tuple[int, int], int] = {}
    bits_total = 0
    for ti, tick in enumerate(ticks):
        if not isinstance(tick, list):
            return fail_report("STRUCT", "tick must be a list", tick=ti)
        used = set()
        for ci, ch in enumerate(tick):
            try:
                s, t, l = int(ch["src_slot"]), int(ch["dst_slot"]), int(ch["len_bits"])
            except Exception:
                return fail_report("STRUCT", "chunk must contain integer src_slot,dst_slot,len_bits", tick=ti, chunk=ci)
            if s < 0 or t < 0 or s >= slots or t >= slots or s == t:
                return fail_report("STRUCT", "slot bounds/self-copy violation", tick=ti, chunk=ci, src_slot=s, dst_slot=t)
            if l <= 0 or l > bw:
                return fail_report("BANDWIDTH", "len_bits out of allowed range", tick=ti, chunk=ci, len_bits=l, bw=bw)
            if s in used or t in used:
                return fail_report("STRICT1", "slot participates more than once in one tick", tick=ti, chunk=ci, src_slot=s, dst_slot=t)
            used.add(s); used.add(t)
            scheduled[(s, t)] = scheduled.get((s, t), 0) + l
            bits_total += l

    dm = demand_map(inst)
    for pair, sbits in scheduled.items():
        if pair not in dm:
            return fail_report("EXTRAS", "scheduled pair not present in demands", src_slot=pair[0], dst_slot=pair[1], scheduled_bits=sbits)
    for pair, dbits in dm.items():
        sbits = scheduled.get(pair, 0)
        if sbits != dbits:
            return fail_report("COVERAGE", "demand coverage mismatch", src_slot=pair[0], dst_slot=pair[1], demand_bits=dbits, scheduled_bits=sbits)

    ticks_total = len(ticks)
    bits_per_tick = bits_total / ticks_total if ticks_total > 0 else 0.0
    expected_bits_per_tick = (slots // 2) * bw
    utilization = bits_per_tick / expected_bits_per_tick if expected_bits_per_tick else 0.0
    lb = lower_bound_ticks(inst)
    gap = ticks_total - lb
    gap_ratio = gap / lb if lb > 0 else 0.0
    return Report(
        status="PASS", version=0, model=MODEL, errors=[], ticks_total=ticks_total, bits_total=bits_total,
        bits_per_tick=bits_per_tick, expected_bits_per_tick=expected_bits_per_tick, utilization=utilization,
        max_degree_chunks=lb, lower_bound_ticks=lb, gap_ticks=gap, gap_to_lower_bound=gap_ratio,
    )


def compare_reports(current: Report, candidate: Report, cost_per_tick: float = 0.0) -> Dict[str, Any]:
    saved_ticks = current.ticks_total - candidate.ticks_total
    saved_pct = (saved_ticks / current.ticks_total) if current.ticks_total > 0 else 0.0
    gap_reduction = current.gap_ticks - candidate.gap_ticks
    return {
        "saved_ticks": saved_ticks,
        "saved_ticks_pct": saved_pct,
        "gap_reduction_ticks": gap_reduction,
        "utilization_delta": candidate.utilization - current.utilization,
        "estimated_savings": saved_ticks * cost_per_tick,
        "cost_per_tick": cost_per_tick,
    }


def schedule_from_csv(path: str | Path, *, fill_empty_ticks: bool = True) -> Schedule:
    """Read customer schedule CSV: tick,src_slot,dst_slot,len_bits.

    tick is a zero-based non-negative integer. Rows are grouped by tick and kept in
    stable CSV order inside each tick. If fill_empty_ticks is True, missing tick
    indices become empty ticks so ticks_total preserves elapsed windows.
    """
    rows: List[Tuple[int, Chunk]] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        has_header = "tick" in sample and "src_slot" in sample and "dst_slot" in sample and "len_bits" in sample
        if has_header:
            rdr = csv.DictReader(f)
            for i, row in enumerate(rdr, start=2):
                if not row or all((v is None or str(v).strip() == "") for v in row.values()):
                    continue
                try:
                    ti = int(row["tick"])
                    s = int(row["src_slot"])
                    t = int(row["dst_slot"])
                    l = int(row["len_bits"])
                except Exception as e:
                    raise ValueError(f"bad schedule CSV row {i}: expected tick,src_slot,dst_slot,len_bits integers") from e
                if ti < 0:
                    raise ValueError(f"bad schedule CSV row {i}: tick must be >= 0")
                rows.append((ti, {"src_slot": s, "dst_slot": t, "len_bits": l}))
        else:
            rdr = csv.reader(f)
            for i, row in enumerate(rdr, start=1):
                if not row or all(not x.strip() for x in row):
                    continue
                if len(row) < 4:
                    raise ValueError(f"bad schedule CSV row {i}: expected 4 columns")
                ti, s, t, l = int(row[0]), int(row[1]), int(row[2]), int(row[3])
                if ti < 0:
                    raise ValueError(f"bad schedule CSV row {i}: tick must be >= 0")
                rows.append((ti, {"src_slot": s, "dst_slot": t, "len_bits": l}))
    if not rows:
        raise ValueError("no schedule rows found in CSV")

    max_tick = max(ti for ti, _ in rows)
    if fill_empty_ticks:
        ticks: List[List[Chunk]] = [[] for _ in range(max_tick + 1)]
    else:
        ticks = []
    if fill_empty_ticks:
        for ti, ch in rows:
            ticks[ti].append(ch)
    else:
        grouped: Dict[int, List[Chunk]] = {}
        for ti, ch in rows:
            grouped.setdefault(ti, []).append(ch)
        ticks = [grouped[ti] for ti in sorted(grouped)]
    return {"version": 0, "model": MODEL, "ticks": ticks}


def write_schedule_csv(path: str | Path, sched: Schedule) -> None:
    ticks = sched.get("ticks", [])
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tick", "src_slot", "dst_slot", "len_bits"])
        for ti, tick in enumerate(ticks):
            for ch in tick:
                w.writerow([ti, ch["src_slot"], ch["dst_slot"], ch["len_bits"]])


def gate_report(rep: Report, *, max_gap: float | None = None, min_utilization: float | None = None, max_ticks: int | None = None) -> Tuple[bool, List[str]]:
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


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "":
        return ""
    low = value.lower()
    if low in {"true", "yes", "on"}:
        return True
    if low in {"false", "no", "off"}:
        return False
    if low in {"null", "none", "~"}:
        return None
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    try:
        if any(c in value for c in [".", "e", "E"]):
            return float(value)
        return int(value, 0)
    except ValueError:
        return value


def load_config(path: str | Path) -> Dict[str, Any]:
    """Load a small JSON/YAML config without external dependencies.

    Supported YAML subset is intentionally simple and enough for pilot configs:

        roi:
          tick_seconds: 1
          gpu_count_blocked: 64
        gates:
          report: greedy
          max_gap_to_lower_bound: 0.15

    JSON files are loaded with json.load.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("config JSON must be an object")
        return data

    root: Dict[str, Any] = {}
    stack: List[Tuple[int, Dict[str, Any]]] = [(-1, root)]
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if ":" not in stripped:
            raise ValueError(f"config line {lineno}: expected key: value")
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"config line {lineno}: empty key")
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value == "":
            node: Dict[str, Any] = {}
            parent[key] = node
            stack.append((indent, node))
        else:
            parent[key] = _parse_scalar(value)
    return root


def roi_cost_per_tick(roi: Dict[str, Any] | None) -> float:
    if not roi:
        return 0.0
    if "cost_per_tick" in roi and roi["cost_per_tick"] is not None:
        return float(roi["cost_per_tick"])
    tick_seconds = float(roi.get("tick_seconds", 1.0))
    gpu_count = float(roi.get("gpu_count_blocked", 0.0))
    gpu_hour = float(roi.get("gpu_hour_cost_usd", 0.0))
    node_count = float(roi.get("node_count_blocked", 0.0))
    node_hour = float(roi.get("node_hour_cost_usd", 0.0))
    return (tick_seconds / 3600.0) * ((gpu_count * gpu_hour) + (node_count * node_hour))


def compute_roi(comparison: Dict[str, Any], roi: Dict[str, Any] | None) -> Dict[str, Any]:
    roi = dict(roi or {})
    saved_ticks = float(comparison.get("saved_ticks", 0.0))
    tick_seconds = float(roi.get("tick_seconds", 1.0))
    runs_per_day = float(roi.get("runs_per_day", 1.0))
    days_per_month = float(roi.get("days_per_month", 30.0))
    months_per_year = float(roi.get("months_per_year", 12.0))
    cost_tick = roi_cost_per_tick(roi)
    saved_seconds_per_run = saved_ticks * tick_seconds
    saved_hours_per_run = saved_seconds_per_run / 3600.0
    savings_per_run = saved_ticks * cost_tick
    monthly_runs = runs_per_day * days_per_month
    yearly_runs = monthly_runs * months_per_year
    return {
        "inputs": roi,
        "cost_per_tick": cost_tick,
        "saved_ticks_per_run": saved_ticks,
        "saved_seconds_per_run": saved_seconds_per_run,
        "saved_hours_per_run": saved_hours_per_run,
        "savings_per_run_usd": savings_per_run,
        "runs_per_day": runs_per_day,
        "monthly_runs": monthly_runs,
        "yearly_runs": yearly_runs,
        "savings_per_month_usd": savings_per_run * monthly_runs,
        "savings_per_year_usd": savings_per_run * yearly_runs,
    }


def anonymize_demands_csv(src: str | Path, dst: str | Path, mapping_out: str | Path | None = None) -> Dict[str, int]:
    """Anonymize src_slot/dst_slot values in a demands CSV.

    Works for numeric or string endpoint IDs. Output always uses integer slot IDs.
    """
    mapping: Dict[str, int] = {}

    def get_id(x: str) -> int:
        x = str(x)
        if x not in mapping:
            mapping[x] = len(mapping)
        return mapping[x]

    with open(src, "r", encoding="utf-8", newline="") as f, open(dst, "w", encoding="utf-8", newline="") as g:
        rdr = csv.DictReader(f)
        if not rdr.fieldnames or "src_slot" not in rdr.fieldnames or "dst_slot" not in rdr.fieldnames or "bits_total" not in rdr.fieldnames:
            raise ValueError("anonymize currently expects headered CSV with src_slot,dst_slot,bits_total")
        w = csv.DictWriter(g, fieldnames=rdr.fieldnames)
        w.writeheader()
        for row in rdr:
            row["src_slot"] = get_id(row["src_slot"])
            row["dst_slot"] = get_id(row["dst_slot"])
            w.writerow(row)
    if mapping_out:
        dump_json(mapping_out, mapping)
    return mapping
