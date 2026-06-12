from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

from .types import Chunk, Demand, Instance, MODEL, MODELS, Schedule

SPREADSHEET_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


def _is_header_row(row: List[str], required: set[str]) -> bool:
    fields = {str(x).lstrip("\ufeff").strip() for x in row}
    return required.issubset(fields)


def _csv_cell_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _is_blank_row(cells: List[Any]) -> bool:
    return all(_csv_cell_text(cell) == "" for cell in cells)


def _is_comment_row(cells: List[Any]) -> bool:
    for cell in cells:
        text = _csv_cell_text(cell)
        if not text:
            continue
        return text.startswith("#")
    return False


def csv_safe_cell(value: Any) -> Any:
    """Return a spreadsheet-safe CSV cell value.

    CSV consumers such as Excel and Google Sheets may interpret cells beginning
    with formula trigger characters as formulas. Prefixing a single quote keeps
    the displayed text stable while preserving ordinary numeric values.
    """
    if not isinstance(value, str):
        return value
    if value.startswith(SPREADSHEET_FORMULA_PREFIXES):
        return "'" + value
    return value


def load_json(path: str | Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: str | Path, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")


def read_demands_csv(path: str | Path) -> List[Tuple[int, int, int]]:
    rows: List[Tuple[int, int, int]] = []
    #TODO:? utf-8-sig
    with open(path, "r", encoding="utf-8", newline="") as f:
        rdr = csv.reader(f)
        first_row: List[str] | None = None
        first_lineno = 0
        for i, row in enumerate(rdr, start=1):
            if not row or _is_comment_row(row) or _is_blank_row(row):
                continue
            first_row = row
            first_lineno = i
            break
        if first_row is None:
            raise ValueError("no demands found in CSV")

        required = {"src_slot", "dst_slot", "bits_total"}
        if _is_header_row(first_row, required):
            fieldnames = [x.lstrip("\ufeff").strip() for x in first_row]
            dict_rows = csv.DictReader(f, fieldnames=fieldnames)
            for i, dict_row in enumerate(dict_rows, start=first_lineno + 1):
                values = list(dict_row.values()) if dict_row else []
                if not dict_row or _is_comment_row(values) or _is_blank_row(values):
                    continue
                try:
                    rows.append((int(dict_row["src_slot"]), int(dict_row["dst_slot"]), int(dict_row["bits_total"])))
                except Exception as e:
                    raise ValueError(f"bad CSV row {i}: {dict_row} : expected src_slot,dst_slot,bits_total integers") from e
        else:
            pending_rows = [(first_lineno, [x.lstrip("\ufeff") for x in first_row])]
            pending_rows.extend(enumerate(rdr, start=first_lineno + 1))
            for i, list_row in pending_rows:
                if not list_row or _is_comment_row(list_row) or _is_blank_row(list_row):
                    continue
                if len(list_row) < 3:
                    raise ValueError(f"bad CSV row {i}: {list_row}: expected 3 columns")
                try:
                    rows.append((int(list_row[0]), int(list_row[1]), int(list_row[2])))
                except Exception as e:
                    raise ValueError(f"bad CSV row {i}: {list_row}: expected src_slot,dst_slot,bits_total integers") from e
    if not rows:
        raise ValueError("no demands found in CSV")
    return rows


def instance_from_csv(
    path: str | Path,
    bw: int,
    slots: int | None = None,
    instance_id: str | None = None,
    notes: str | None = None,
    model: str = MODEL,
) -> Instance:
    if model not in MODELS:
        raise ValueError(f"unsupported model: {model}")
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
        "model": model,
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
    if inst.get("model") not in MODELS:
        raise ValueError(f"instance.model must be one of {sorted(MODELS)}")
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
        rdr = csv.reader(f)
        first_row: List[str] | None = None
        first_lineno = 0
        for i, row in enumerate(rdr, start=1):
            if not row or _is_comment_row(row) or _is_blank_row(row):
                continue
            first_row = row
            first_lineno = i
            break
        if first_row is None:
            raise ValueError("no schedule rows found in CSV")

        required = {"tick", "src_slot", "dst_slot", "len_bits"}
        if _is_header_row(first_row, required):
            fieldnames = [x.lstrip("\ufeff").strip() for x in first_row]
            iterator = csv.DictReader(f, fieldnames=fieldnames)
            any_rows = False
            for i, dict_row in enumerate(iterator, start=first_lineno + 1):
                values = list(dict_row.values()) if dict_row else []
                if not dict_row or _is_comment_row(values) or _is_blank_row(values):
                    continue
                try:
                    ti = int(dict_row["tick"])
                    ch: Chunk = {"src_slot": int(dict_row["src_slot"]), "dst_slot": int(dict_row["dst_slot"]), "len_bits": int(dict_row["len_bits"])}
                except Exception as e:
                    raise ValueError(f"bad schedule CSV row {i}: expected tick,src_slot,dst_slot,len_bits integers") from e
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
        else:
            rows = [(first_lineno, [x.lstrip("\ufeff") for x in first_row])]
            rows.extend(enumerate(rdr, start=first_lineno + 1))
            any_rows = False
            for i, list_row in rows:
                if not list_row or _is_comment_row(list_row) or _is_blank_row(list_row):
                    continue
                if len(list_row) < 4:
                    raise ValueError(f"bad schedule CSV row {i}: expected 4 columns")
                try:
                    ti = int(list_row[0])
                    chunk: Chunk = {"src_slot": int(list_row[1]), "dst_slot": int(list_row[2]), "len_bits": int(list_row[3])}
                except Exception as e:
                    raise ValueError(f"bad schedule CSV row {i}: expected tick,src_slot,dst_slot,len_bits integers") from e
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
                current_chunks.append(chunk)
                last_tick = ti

        if not any_rows:
            raise ValueError("no schedule rows found in CSV")
        yield current_chunks


def schedule_from_csv(path: str | Path, *, fill_empty_ticks: bool = True, model: str = MODEL) -> Schedule:
    if model not in MODELS:
        raise ValueError(f"unsupported model: {model}")
    return {"version": 0, "model": model, "ticks": list(iter_schedule_csv_ticks(path, fill_empty_ticks=fill_empty_ticks))}


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
