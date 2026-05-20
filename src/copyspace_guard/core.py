"""Backward-compatible public API re-exports for Copy-Space Guard."""
from .anonymize import anonymize_demands_csv, anonymize_schedule_csv
from .bounds import lower_bound_components, lower_bound_ticks
from .io import (
    demand_map,
    dump_json,
    instance_from_csv,
    iter_schedule_csv_ticks,
    load_config,
    load_json,
    read_demands_csv,
    schedule_from_csv,
    validate_instance,
    write_schedule_csv,
)
from .roi import compare_reports, compute_roi, roi_cost_per_tick
from .solvers import iter_baseline, iter_greedy, solve_baseline, solve_greedy
from .types import Chunk, Demand, Instance, MODEL, Report, Schedule
from .validate import fail_report, gate_report, validate_schedule, validate_schedule_csv, validate_ticks_iter

__all__ = [
    "MODEL",
    "Demand",
    "Chunk",
    "Schedule",
    "Instance",
    "Report",
    "load_json",
    "dump_json",
    "read_demands_csv",
    "instance_from_csv",
    "demand_map",
    "validate_instance",
    "iter_schedule_csv_ticks",
    "schedule_from_csv",
    "write_schedule_csv",
    "load_config",
    "lower_bound_components",
    "lower_bound_ticks",
    "iter_baseline",
    "iter_greedy",
    "solve_baseline",
    "solve_greedy",
    "fail_report",
    "validate_schedule",
    "validate_schedule_csv",
    "validate_ticks_iter",
    "gate_report",
    "compare_reports",
    "compute_roi",
    "roi_cost_per_tick",
    "anonymize_demands_csv",
    "anonymize_schedule_csv",
]
