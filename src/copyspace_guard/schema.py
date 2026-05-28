from __future__ import annotations

from typing import Any, cast

from .io import validate_instance
from .types import Instance, MODELS


def _require_object(obj: Any, name: str) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise ValueError(f"{name} must be an object")
    return obj


def _require_keys(obj: dict[str, Any], keys: list[str], name: str) -> None:
    missing = [k for k in keys if k not in obj]
    if missing:
        raise ValueError(f"{name} missing required keys: {', '.join(missing)}")


def validate_instance_contract(obj: Any) -> None:
    validate_instance(cast("Instance", _require_object(obj, "instance")))


def validate_schedule_contract(obj: Any) -> None:
    sched = _require_object(obj, "schedule")
    _require_keys(sched, ["version", "model", "ticks"], "schedule")
    if sched["version"] != 0:
        raise ValueError("schedule.version must be 0")
    if sched["model"] not in MODELS:
        raise ValueError(f"schedule.model must be one of {sorted(MODELS)}")
    ticks = sched["ticks"]
    if not isinstance(ticks, list):
        raise ValueError("schedule.ticks must be a list")
    for ti, tick in enumerate(ticks):
        if not isinstance(tick, list):
            raise ValueError(f"schedule.ticks[{ti}] must be a list")
        for ci, chunk in enumerate(tick):
            ch = _require_object(chunk, f"schedule.ticks[{ti}][{ci}]")
            _require_keys(ch, ["src_slot", "dst_slot", "len_bits"], f"schedule.ticks[{ti}][{ci}]")
            for key in ["src_slot", "dst_slot"]:
                if not isinstance(ch[key], int) or ch[key] < 0:
                    raise ValueError(f"schedule.ticks[{ti}][{ci}].{key} must be int >= 0")
            if not isinstance(ch["len_bits"], int) or ch["len_bits"] <= 0:
                raise ValueError(f"schedule.ticks[{ti}][{ci}].len_bits must be int > 0")


def validate_report_contract(obj: Any, name: str = "report") -> None:
    rep = _require_object(obj, name)
    _require_keys(
        rep,
        [
            "status",
            "version",
            "model",
            "errors",
            "ticks_total",
            "bits_total",
            "lower_bound_ticks",
            "gap_to_lower_bound",
            "bounds_complete",
            "total_errors",
            "errors_truncated",
        ],
        name,
    )
    if rep["status"] not in {"PASS", "FAIL"}:
        raise ValueError(f"{name}.status must be PASS or FAIL")
    if rep["version"] != 0:
        raise ValueError(f"{name}.version must be 0")
    if rep["model"] not in MODELS:
        raise ValueError(f"{name}.model must be one of {sorted(MODELS)}")
    if not isinstance(rep["errors"], list):
        raise ValueError(f"{name}.errors must be a list")
    if not isinstance(rep["total_errors"], int) or rep["total_errors"] < 0:
        raise ValueError(f"{name}.total_errors must be int >= 0")
    if not isinstance(rep["errors_truncated"], bool):
        raise ValueError(f"{name}.errors_truncated must be boolean")


def validate_summary_contract(obj: Any) -> None:
    summary = _require_object(obj, "summary")
    _require_keys(summary, ["instance", "current_label", "candidate_label", "reports", "comparison", "roi", "artifacts"], "summary")
    validate_instance_contract(summary["instance"])
    reports = _require_object(summary["reports"], "summary.reports")
    if summary["candidate_label"] not in reports:
        raise ValueError("summary.reports must contain candidate_label")
    if summary["current_label"] not in reports:
        raise ValueError("summary.reports must contain current_label")
    for name, rep in reports.items():
        validate_report_contract(rep, f"summary.reports.{name}")
    comparison = _require_object(summary["comparison"], "summary.comparison")
    _require_keys(
        comparison,
        ["comparable", "comparison_note", "saved_ticks", "saved_ticks_pct", "gap_reduction_ticks", "utilization_delta", "estimated_savings", "cost_per_tick"],
        "summary.comparison",
    )
    artifacts = _require_object(summary["artifacts"], "summary.artifacts")
    _require_keys(
        artifacts,
        ["instance", "schedule_current", "schedule_current_csv", "schedule_greedy", "schedule_greedy_csv", "report_current", "report_greedy", "report_markdown", "report_html"],
        "summary.artifacts",
    )


def validate_artifact_contract(kind: str, obj: Any) -> None:
    if kind == "instance":
        validate_instance_contract(obj)
    elif kind == "schedule":
        validate_schedule_contract(obj)
    elif kind == "report":
        validate_report_contract(obj)
    elif kind == "summary":
        validate_summary_contract(obj)
    else:
        raise ValueError(f"unsupported artifact kind: {kind}")
