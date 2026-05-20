from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

from .types import Chunk, Demand, Instance, MODEL, Schedule


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


def instance_from_csv(
    path: str | Path,
    bw: int,
    slots: int | None = None,
    instance_id: str | None = None,
    notes: str | None = None,
) -> Instance:
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


def iter_schedule_csv_ticks(path: str | Path, *, fill_empty_ticks: bool = True) -> Iterator[List[Chunk]]:
    """Stream a sorted schedule CSV as ticks.

    The CSV must be sorted by non-decreasing tick. Missing ticks are emitted as
    empty lists when fill_empty_ticks is True. This preserves elapsed windows
    without materializing the entire schedule in memory.
    """
    current_tick: int | None = None
    current_chunks: List[Chunk] = []
    last_tick = -1
    with open(path, "r", encoding="utf-8", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        has_header = "tick" in sample and "src_slot" in sample and "dst_slot" in sample and "len_bits" in sample
        if has_header:
            iterator = csv.DictReader(f)
            def parse(row: Dict[str, str], i: int) -> Tuple[int, Chunk]:
                try:
                    ti = int(row["tick"])
                    ch = {"src_slot": int(row["src_slot"]), "dst_slot": int(row["dst_slot"]), "len_bits": int(row["len_bits"])}
                except Exception as e:
                    raise ValueError(f"bad schedule CSV row {i}: expected tick,src_slot,dst_slot,len_bits integers") from e
                return ti, ch
            rows = ((i, row) for i, row in enumerate(iterator, start=2))
        else:
            iterator2 = csv.reader(f)
            def parse(row: List[str], i: int) -> Tuple[int, Chunk]:  # type: ignore[no-redef]
                if len(row) < 4:
                    raise ValueError(f"bad schedule CSV row {i}: expected 4 columns")
                return int(row[0]), {"src_slot": int(row[1]), "dst_slot": int(row[2]), "len_bits": int(row[3])}
            rows = ((i, row) for i, row in enumerate(iterator2, start=1))

        any_rows = False
        for i, row in rows:
            if not row:
                continue
            ti, ch = parse(row, i)  # type: ignore[arg-type]
            if ti < 0:
                raise ValueError(f"bad schedule CSV row {i}: tick must be >= 0")
            if ti < last_tick:
                raise ValueError("schedule CSV must be sorted by non-decreasing tick for streaming validation")
            any_rows = True
            if current_tick is None:
                if fill_empty_ticks:
                    for _ in range(ti):
                        yield []
                current_tick = ti
            if ti != current_tick:
                yield current_chunks
                if fill_empty_ticks:
                    for _ in range(current_tick + 1, ti):
                        yield []
                current_tick = ti
                current_chunks = []
            current_chunks.append(ch)
            last_tick = ti

        if not any_rows:
            raise ValueError("no schedule rows found in CSV")
        yield current_chunks


def schedule_from_csv(path: str | Path, *, fill_empty_ticks: bool = True) -> Schedule:
    return {"version": 0, "model": MODEL, "ticks": list(iter_schedule_csv_ticks(path, fill_empty_ticks=fill_empty_ticks))}


def write_schedule_csv(path: str | Path, sched: Schedule) -> None:
    ticks = sched.get("ticks", [])
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tick", "src_slot", "dst_slot", "len_bits"])
        for ti, tick in enumerate(ticks):
            for ch in tick:
                w.writerow([ti, ch["src_slot"], ch["dst_slot"], ch["len_bits"]])


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
    """Load JSON or a deliberately small YAML subset without runtime deps."""
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
