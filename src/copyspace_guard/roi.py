from __future__ import annotations

from typing import Any, Dict

from .types import Report


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


def compare_reports(current: Report, candidate: Report, cost_per_tick: float = 0.0) -> Dict[str, Any]:
    comparable = current.status == "PASS" and candidate.status == "PASS"
    if not comparable:
        return {
            "comparable": False,
            "comparison_note": "Savings are not computed because current or candidate schedule validation failed.",
            "saved_ticks": 0,
            "saved_ticks_pct": 0.0,
            "gap_reduction_ticks": 0,
            "utilization_delta": 0.0,
            "estimated_savings": 0.0,
            "cost_per_tick": cost_per_tick,
        }
    saved_ticks = current.ticks_total - candidate.ticks_total
    saved_pct = (saved_ticks / current.ticks_total) if current.ticks_total > 0 else 0.0
    gap_reduction = current.gap_ticks - candidate.gap_ticks
    return {
        "comparable": True,
        "comparison_note": "OK",
        "saved_ticks": saved_ticks,
        "saved_ticks_pct": saved_pct,
        "gap_reduction_ticks": gap_reduction,
        "utilization_delta": candidate.utilization - current.utilization,
        "estimated_savings": saved_ticks * cost_per_tick,
        "cost_per_tick": cost_per_tick,
    }


def _roi_block(saved_ticks: float, roi: Dict[str, Any]) -> Dict[str, Any]:
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
        "saved_ticks": saved_ticks,
        "saved_seconds_per_run": saved_seconds_per_run,
        "saved_hours_per_run": saved_hours_per_run,
        "savings_per_run_usd": savings_per_run,
        "savings_per_month_usd": savings_per_run * monthly_runs,
        "savings_per_year_usd": savings_per_run * yearly_runs,
    }


def compute_roi(
    comparison: Dict[str, Any],
    roi: Dict[str, Any] | None,
    *,
    theoretical_saved_ticks: float | None = None,
) -> Dict[str, Any]:
    roi = dict(roi or {})
    saved_ticks = float(comparison.get("saved_ticks", 0.0)) if comparison.get("comparable", True) else 0.0
    theo_ticks = float(theoretical_saved_ticks if theoretical_saved_ticks is not None else 0.0)
    tick_seconds = float(roi.get("tick_seconds", 1.0))
    runs_per_day = float(roi.get("runs_per_day", 1.0))
    days_per_month = float(roi.get("days_per_month", 30.0))
    months_per_year = float(roi.get("months_per_year", 12.0))
    cost_tick = roi_cost_per_tick(roi)
    monthly_runs = runs_per_day * days_per_month
    yearly_runs = monthly_runs * months_per_year
    practical = _roi_block(saved_ticks, roi)
    theoretical_max = _roi_block(theo_ticks, roi)
    return {
        "inputs": roi,
        "cost_per_tick": cost_tick,
        "saved_ticks_per_run": saved_ticks,  # backward-compatible flat fields
        "saved_seconds_per_run": practical["saved_seconds_per_run"],
        "saved_hours_per_run": practical["saved_hours_per_run"],
        "savings_per_run_usd": practical["savings_per_run_usd"],
        "runs_per_day": runs_per_day,
        "monthly_runs": monthly_runs,
        "yearly_runs": yearly_runs,
        "savings_per_month_usd": practical["savings_per_month_usd"],
        "savings_per_year_usd": practical["savings_per_year_usd"],
        "practical": {
            "description": "vs greedy (practical switch target)",
            **practical,
        },
        "theoretical_max": {
            "description": "vs lower bound (upper estimate, may be unreachable)",
            **theoretical_max,
            "note": "actual savings cannot exceed this but may be less",
        },
    }
