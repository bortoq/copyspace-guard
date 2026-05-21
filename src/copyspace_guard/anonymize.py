from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict

from .io import csv_safe_cell, dump_json, load_json


DEMAND_CONTRACT_FIELDS = {"src_slot", "dst_slot", "bits_total"}
SCHEDULE_CONTRACT_FIELDS = {"tick", "src_slot", "dst_slot", "len_bits"}


def _load_mapping(mapping_in: str | Path | None) -> Dict[str, int]:
    if not mapping_in:
        return {}
    data = load_json(mapping_in)
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, int) and v >= 0 for k, v in data.items()):
        raise ValueError("mapping input must be a JSON object of string keys to non-negative integer IDs")
    return dict(data)


def anonymize_demands_csv(
    src: str | Path,
    dst: str | Path,
    mapping_out: str | Path | None = None,
    mapping_in: str | Path | None = None,
    *,
    max_rows: int | None = None,
    max_file_size: int | None = None,
) -> Dict[str, int]:
    mapping: Dict[str, int] = _load_mapping(mapping_in)
    src_path = Path(src)
    if max_file_size is not None and src_path.stat().st_size > max_file_size:
        raise ValueError(f"anonymize input exceeds --max-file-size {max_file_size} bytes: {src_path}")

    def get_id(x: str) -> int:
        x = str(x)
        if x not in mapping:
            mapping[x] = len(mapping)
        return mapping[x]

    rows_written = 0
    with open(src_path, "r", encoding="utf-8", newline="") as f, open(dst, "w", encoding="utf-8", newline="") as g:
        rdr = csv.DictReader(f)
        if not rdr.fieldnames or not DEMAND_CONTRACT_FIELDS.issubset(set(rdr.fieldnames)):
            raise ValueError("anonymize currently expects headered CSV with src_slot,dst_slot,bits_total")
        w = csv.DictWriter(g, fieldnames=rdr.fieldnames)
        w.writeheader()
        for row in rdr:
            rows_written += 1
            if max_rows is not None and rows_written > max_rows:
                raise ValueError(f"anonymize input exceeds --max-rows {max_rows}: {src_path}")
            row["src_slot"] = get_id(row["src_slot"])
            row["dst_slot"] = get_id(row["dst_slot"])
            row = {k: (v if k in DEMAND_CONTRACT_FIELDS else csv_safe_cell(v)) for k, v in row.items()}
            w.writerow(row)
    if mapping_out:
        dump_json(mapping_out, mapping)
    return mapping


def anonymize_schedule_csv(
    src: str | Path,
    dst: str | Path,
    mapping_out: str | Path | None = None,
    mapping_in: str | Path | None = None,
    *,
    max_rows: int | None = None,
    max_file_size: int | None = None,
) -> Dict[str, int]:
    mapping: Dict[str, int] = _load_mapping(mapping_in)
    src_path = Path(src)
    if max_file_size is not None and src_path.stat().st_size > max_file_size:
        raise ValueError(f"anonymize input exceeds --max-file-size {max_file_size} bytes: {src_path}")

    def get_id(x: str) -> int:
        x = str(x)
        if x not in mapping:
            mapping[x] = len(mapping)
        return mapping[x]

    rows_written = 0
    with open(src_path, "r", encoding="utf-8", newline="") as f, open(dst, "w", encoding="utf-8", newline="") as g:
        rdr = csv.DictReader(f)
        if not rdr.fieldnames or not SCHEDULE_CONTRACT_FIELDS.issubset(set(rdr.fieldnames)):
            raise ValueError("schedule anonymize expects headered CSV with tick,src_slot,dst_slot,len_bits")
        w = csv.DictWriter(g, fieldnames=rdr.fieldnames)
        w.writeheader()
        for row in rdr:
            rows_written += 1
            if max_rows is not None and rows_written > max_rows:
                raise ValueError(f"anonymize input exceeds --max-rows {max_rows}: {src_path}")
            row["src_slot"] = get_id(row["src_slot"])
            row["dst_slot"] = get_id(row["dst_slot"])
            row = {k: (v if k in SCHEDULE_CONTRACT_FIELDS else csv_safe_cell(v)) for k, v in row.items()}
            w.writerow(row)
    if mapping_out:
        dump_json(mapping_out, mapping)
    return mapping
