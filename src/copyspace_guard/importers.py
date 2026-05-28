from __future__ import annotations

import csv
import json
import re
from xml.parsers import expat
from pathlib import Path
from typing import Any

from .types import MODEL, MODELS, Chunk, Schedule


def _check_import_limits(path: str | Path, *, max_rows: int | None, max_file_size: int | None) -> None:
    if max_rows is not None and max_rows < 0:
        raise ValueError("--max-rows must be >= 0")
    if max_file_size is not None and max_file_size < 0:
        raise ValueError("--max-file-size must be >= 0")
    if max_file_size is not None:
        size = Path(path).stat().st_size
        if size > max_file_size:
            raise ValueError(f"input file size {size} exceeds --max-file-size {max_file_size}")


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean is not a valid integer value")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        return int(value.strip())
    raise ValueError(f"cannot parse integer value: {value!r}")


def _schedule_from_rows(rows: list[tuple[int, int, int, int]], *, model: str = MODEL) -> Schedule:
    if model not in MODELS:
        raise ValueError(f"unsupported model: {model}")
    if not rows:
        raise ValueError("no schedule rows found")
    rows.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
    ticks: list[list[Chunk]] = []
    cur_tick = 0
    cur_chunks: list[Chunk] = []
    for tick, src, dst, bits in rows:
        if tick < 0 or src < 0 or dst < 0 or bits <= 0:
            raise ValueError("invalid schedule row values")
        while cur_tick < tick:
            ticks.append(cur_chunks)
            cur_tick += 1
            cur_chunks = []
        cur_chunks.append({"src_slot": src, "dst_slot": dst, "len_bits": bits})
    ticks.append(cur_chunks)
    return {"version": 0, "model": model, "ticks": ticks}


def import_csv_with_map(
    path: str | Path,
    *,
    tick: str,
    src: str,
    dst: str,
    length: str,
    model: str = MODEL,
    max_rows: int | None = None,
    max_file_size: int | None = None,
) -> Schedule:
    _check_import_limits(path, max_rows=max_rows, max_file_size=max_file_size)
    rows: list[tuple[int, int, int, int]] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        rdr = csv.DictReader(f)
        if rdr.fieldnames is None:
            raise ValueError("CSV must include a header row")
        required = [tick, src, dst, length]
        missing = [name for name in required if name not in rdr.fieldnames]
        if missing:
            raise ValueError(f"missing CSV columns: {', '.join(missing)}")
        for i, row in enumerate(rdr, start=2):
            if row is None:
                continue
            try:
                rows.append((_as_int(row[tick]), _as_int(row[src]), _as_int(row[dst]), _as_int(row[length])))
            except Exception as e:
                raise ValueError(f"bad CSV row {i} for mapped schedule fields") from e
            if max_rows is not None and len(rows) > max_rows:
                raise ValueError(f"mapped schedule row count exceeds --max-rows {max_rows}")
    return _schedule_from_rows(rows, model=model)


def _find_schedule_rows(obj: Any) -> list[tuple[int, int, int, int]]:
    key_options = {
        "tick": ("tick", "step", "time", "t"),
        "src": ("src_slot", "src", "from", "source", "sender"),
        "dst": ("dst_slot", "dst", "to", "target", "receiver"),
        "len": ("len_bits", "size_bits", "bits", "len", "size", "chunk_bits"),
    }
    rows: list[tuple[int, int, int, int]] = []

    def pick(d: dict[str, Any], names: tuple[str, ...]) -> Any:
        for name in names:
            if name in d:
                return d[name]
        return None

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            tick = pick(node, key_options["tick"])
            src = pick(node, key_options["src"])
            dst = pick(node, key_options["dst"])
            size = pick(node, key_options["len"])
            if tick is not None and src is not None and dst is not None and size is not None:
                rows.append((_as_int(tick), _as_int(src), _as_int(dst), _as_int(size)))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(obj)
    return rows


def import_taccl_json(
    path: str | Path,
    *,
    model: str = MODEL,
    max_rows: int | None = None,
    max_file_size: int | None = None,
) -> Schedule:
    _check_import_limits(path, max_rows=max_rows, max_file_size=max_file_size)
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    rows = _find_schedule_rows(obj)
    if max_rows is not None and len(rows) > max_rows:
        raise ValueError(f"schedule row count exceeds --max-rows {max_rows}")
    return _schedule_from_rows(rows, model=model)


def import_msccl_xml(
    path: str | Path,
    *,
    model: str = MODEL,
    max_rows: int | None = None,
    max_file_size: int | None = None,
) -> Schedule:
    _check_import_limits(path, max_rows=max_rows, max_file_size=max_file_size)
    rows: list[tuple[int, int, int, int]] = []
    parser = expat.ParserCreate()

    def on_start(_name: str, attrs: dict[str, str]) -> None:
        tick = attrs.get("tick") or attrs.get("step") or attrs.get("time")
        src = attrs.get("src") or attrs.get("from") or attrs.get("sender")
        dst = attrs.get("dst") or attrs.get("to") or attrs.get("receiver")
        size = attrs.get("len_bits") or attrs.get("size_bits") or attrs.get("bits") or attrs.get("size") or attrs.get("cnt")
        if tick is None or src is None or dst is None or size is None:
            return
        rows.append((_as_int(tick), _as_int(src), _as_int(dst), _as_int(size)))
        if max_rows is not None and len(rows) > max_rows:
            raise ValueError(f"schedule row count exceeds --max-rows {max_rows}")

    parser.StartElementHandler = on_start
    with open(path, "rb") as f:
        parser.ParseFile(f)
    return _schedule_from_rows(rows, model=model)


def _write_demands_csv(rows: list[tuple[int, int, int]], out: str | Path) -> None:
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["src_slot", "dst_slot", "bits_total"])
        for s, t, bits in rows:
            w.writerow([s, t, bits])


def import_nccl_log_demands(
    path: str | Path,
    *,
    max_rows: int | None = None,
    max_file_size: int | None = None,
) -> list[tuple[int, int, int]]:
    _check_import_limits(path, max_rows=max_rows, max_file_size=max_file_size)
    # Example supported line:
    # ring: rank 0 -> rank 1, bytes=134217728
    p = re.compile(r"rank\s+(\d+)\s*->\s*rank\s+(\d+).*?\bbytes\s*=\s*(\d+)", re.IGNORECASE)
    agg: dict[tuple[int, int], int] = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = p.search(line)
            if not m:
                continue
            src = _as_int(m.group(1))
            dst = _as_int(m.group(2))
            bits = _as_int(m.group(3)) * 8
            if src < 0 or dst < 0 or src == dst or bits <= 0:
                continue
            agg[(src, dst)] = agg.get((src, dst), 0) + bits
            if max_rows is not None and len(agg) > max_rows:
                raise ValueError(f"demand row count exceeds --max-rows {max_rows}")
    if not agg:
        raise ValueError("no NCCL rank->rank byte lines found in log")
    return [(s, t, b) for (s, t), b in sorted(agg.items())]


def import_pytorch_trace_demands(
    path: str | Path,
    *,
    max_rows: int | None = None,
    max_file_size: int | None = None,
) -> list[tuple[int, int, int]]:
    _check_import_limits(path, max_rows=max_rows, max_file_size=max_file_size)
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    events = obj.get("traceEvents", obj) if isinstance(obj, dict) else obj
    if not isinstance(events, list):
        raise ValueError("PyTorch trace must be a JSON list or contain traceEvents list")
    agg: dict[tuple[int, int], int] = {}
    for ev in events:
        if not isinstance(ev, dict):
            continue
        name = str(ev.get("name", "")).lower()
        if "nccl" not in name and "allreduce" not in name:
            continue
        args = ev.get("args", {})
        if not isinstance(args, dict):
            continue
        ranks = args.get("ranks")
        b = args.get("bytes")
        if not isinstance(ranks, list) or len(ranks) < 2 or b is None:
            continue
        bits = _as_int(b) * 8
        rr = [_as_int(x) for x in ranks]
        rr.sort()
        for i, src in enumerate(rr):
            for dst in rr[i + 1:]:
                if src == dst:
                    continue
                agg[(src, dst)] = agg.get((src, dst), 0) + bits
                if max_rows is not None and len(agg) > max_rows:
                    raise ValueError(f"demand row count exceeds --max-rows {max_rows}")
    if not agg:
        raise ValueError("no NCCL-like communication events with args.bytes+ranks found")
    return [(s, t, b) for (s, t), b in sorted(agg.items())]


def write_imported_demands_csv(
    rows: list[tuple[int, int, int]],
    out: str | Path,
) -> None:
    if not rows:
        raise ValueError("no demand rows found")
    _write_demands_csv(rows, out)
