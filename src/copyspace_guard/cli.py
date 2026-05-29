from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404
import sys
from pathlib import Path
import time
from typing import Any, cast

from . import __version__
from .core import (
    anonymize_demands_csv,
    anonymize_schedule_csv,
    compare_reports,
    compute_roi,
    dump_json,
    gate_report,
    instance_from_csv,
    load_config,
    load_json,
    lower_bound_components,
    validate_artifact_contract,
    validate_summary_contract,
    schedule_from_csv,
    iter_baseline,
    iter_greedy,
    solve_baseline,
    solve_greedy,
    roi_cost_per_tick,
    validate_schedule,
    validate_schedule_csv,
    validate_ticks_iter,
    write_schedule_csv,
)
from .report import write_reports
from .types import Schedule
from .types import Report
from .types import Instance
from .importers import (
    import_csv_with_map,
    import_msccl_xml,
    import_nccl_log_demands,
    import_pytorch_trace_demands,
    import_taccl_json,
    write_imported_demands_csv,
)


def _resolve_bounds_mode(args: argparse.Namespace) -> None:
    """Normalize deprecated --bounds-mode values. Mutates args.bounds_mode in place."""
    if args.bounds_mode == "fractional_exact":
        print("WARNING: --bounds-mode fractional_exact is deprecated, use fractional_odd_subset", file=sys.stderr)
        args.bounds_mode = "fractional_odd_subset"


def _check_bounds_mode_slots(inst: Instance, bounds_mode: str) -> None:
    if bounds_mode == "fractional_odd_subset" and str(inst.get("model", "STRICT1")) == "STRICT1":
        slots = int(inst.get("slots", 0))
        if slots > 24:
            raise ValueError(f"fractional_odd_subset is limited to <= 24 slots; got {slots}")


def _validate_common_args(args: argparse.Namespace) -> None:
    if args.max_errors is not None and args.max_errors < 0:
        raise ValueError("--max-errors must be >= 0")
    if args.bounds_subset_limit < 0:
        raise ValueError("--bounds-subset-limit must be >= 0")


def _load_roi_config_and_compute(
    args: argparse.Namespace,
    rep_current: Report,
    rep_greedy: Report,
    kind: str = "customer_vs_greedy",
) -> tuple[dict[str, Any], dict[str, Any]]:
    roi_config: dict[str, Any] = {}
    if args.roi:
        loaded_roi = load_config(args.roi)
        roi_config = loaded_roi.get("roi", loaded_roi)
    cost_per_tick = args.cost_per_tick if args.cost_per_tick > 0 else roi_cost_per_tick(roi_config)
    comp = compare_reports(rep_current, rep_greedy, cost_per_tick)
    roi_summary = compute_roi(
        comp, roi_config,
        theoretical_saved_ticks=max(rep_current.gap_ticks, 0),
        kind=kind,
    )
    return comp, roi_summary


def cmd_analyze(args: argparse.Namespace) -> int:
    outdir = prepare_output_dir(Path(args.outdir))
    _validate_common_args(args)
    inst = instance_from_csv(args.csv, bw=args.bw, slots=args.slots, instance_id=args.id, notes=args.notes, model=args.model)
    _check_bounds_mode_slots(inst, args.bounds_mode)
    _resolve_bounds_mode(args)
    if args.max_slots is not None and int(inst["slots"]) > args.max_slots:
        raise ValueError(f"slot count {inst['slots']} exceeds --max-slots {args.max_slots}")
    if args.max_demands is not None and len(inst.get("demands", [])) > args.max_demands:
        raise ValueError(f"demand count {len(inst.get('demands', []))} exceeds --max-demands {args.max_demands}")

    current = None
    greedy = None
    if args.summary_only:
        if args.current_schedule_json:
            current = load_json(args.current_schedule_json)
            current_label = "customer_current"
            rep_current = validate_schedule(
                inst,
                current,
                max_errors=args.max_errors,
                bounds_subset_limit=args.bounds_subset_limit,
                strict1_bounds_mode=args.bounds_mode,
            )
        elif args.current_schedule_csv:
            current_label = "customer_current"
            rep_current = validate_schedule_csv(
                inst,
                args.current_schedule_csv,
                max_errors=args.max_errors,
                bounds_subset_limit=args.bounds_subset_limit,
                strict1_bounds_mode=args.bounds_mode,
            )
        else:
            current_label = "baseline"
            rep_current = validate_ticks_iter(
                inst,
                iter_baseline(inst),
                max_errors=args.max_errors,
                bounds_subset_limit=args.bounds_subset_limit,
                strict1_bounds_mode=args.bounds_mode,
            )
        rep_greedy = validate_ticks_iter(
            inst,
            iter_greedy(inst),
            max_errors=args.max_errors,
            bounds_subset_limit=args.bounds_subset_limit,
            strict1_bounds_mode=args.bounds_mode,
        )
    else:
        if args.current_schedule_json:
            current = load_json(args.current_schedule_json)
            current_label = "customer_current"
        elif args.current_schedule_csv:
            current = schedule_from_csv(args.current_schedule_csv, model=str(inst.get("model", "STRICT1")))
            current_label = "customer_current"
        else:
            current = solve_baseline(inst)
            current_label = "baseline"
        greedy = solve_greedy(inst)
        rep_current = validate_schedule(
            inst,
            current,
            max_errors=args.max_errors,
            bounds_subset_limit=args.bounds_subset_limit,
            strict1_bounds_mode=args.bounds_mode,
        )
        rep_greedy = validate_schedule(
            inst,
            greedy,
            max_errors=args.max_errors,
            bounds_subset_limit=args.bounds_subset_limit,
            strict1_bounds_mode=args.bounds_mode,
        )
    if args.max_output_ticks is not None:
        for label, rep in [(current_label, rep_current), ("greedy", rep_greedy)]:
            if rep.ticks_total > args.max_output_ticks:
                raise ValueError(f"{label} ticks_total {rep.ticks_total} exceeds --max-output-ticks {args.max_output_ticks}")
    roi_kind = "baseline_vs_greedy" if current_label == "baseline" else "customer_vs_greedy"
    comp, roi_summary = _load_roi_config_and_compute(args, rep_current, rep_greedy, kind=roi_kind)

    rep_current_dict = rep_current.to_dict()
    rep_greedy_dict = rep_greedy.to_dict()

    dump_json(outdir / "instance.json", inst)
    if not args.summary_only:
        if current is None or greedy is None:
            raise RuntimeError("internal error: schedules were not materialized")
        dump_json(outdir / f"schedule_{current_label}.json", current)
        write_schedule_csv(outdir / f"schedule_{current_label}.csv", current)
        dump_json(outdir / "schedule_greedy.json", greedy)
        write_schedule_csv(outdir / "schedule_greedy.csv", greedy)
    if current_label == "customer_current":
        customer_ticks = rep_current.ticks_total
        gap_vs_greedy = 0.0 if customer_ticks <= 0 else (customer_ticks - rep_greedy.ticks_total) / customer_ticks
        rep_current_dict["gap_practical"] = gap_vs_greedy
    dump_json(outdir / f"report_{current_label}.json", rep_current_dict)
    dump_json(outdir / "report_greedy.json", rep_greedy_dict)
    reports = {"greedy": rep_greedy_dict, "current": rep_current_dict, current_label: rep_current_dict}
    if current_label == "baseline":
        reports["baseline"] = rep_current.to_dict()
    summary = {
        "instance": inst,
        "current_label": current_label,
        "candidate_label": "greedy",
        "reports": reports,
        "comparison": comp,
        "roi": roi_summary,
        "analysis_options": {
            "bounds_subset_limit": args.bounds_subset_limit,
            "max_errors": args.max_errors,
            "summary_only": args.summary_only,
        },
        "artifacts": {
            "instance": "instance.json",
            "schedule_current": None if args.summary_only else f"schedule_{current_label}.json",
            "schedule_current_csv": None if args.summary_only else f"schedule_{current_label}.csv",
            "schedule_greedy": None if args.summary_only else "schedule_greedy.json",
            "schedule_greedy_csv": None if args.summary_only else "schedule_greedy.csv",
            "report_current": f"report_{current_label}.json",
            "report_greedy": "report_greedy.json",
            "report_markdown": "report.md",
            "report_html": "report.html",
        },
    }
    if current_label == "customer_current":
        summary["audit"] = {
            "audit_note": (
                "gap_to_lower_bound reflects an abstract model without topology. "
                "If your solver accounts for topology constraints, gap > 0 may be expected."
            ),
            "gap_vs_greedy": gap_vs_greedy,
        }
    validate_summary_contract(summary)
    dump_json(outdir / "summary.json", summary)
    write_reports(outdir, summary)

    print(f"Copy-Space Guard analysis written to: {outdir}")
    gap_rel = rep_current.gap_reliability or "unknown"
    baseline_tag = " (baseline comparison)" if current_label == "baseline" else ""
    print(f"{current_label}: status={rep_current.status} ticks={rep_current.ticks_total} lb={rep_current.lower_bound_ticks} gap={rep_current.gap_to_lower_bound:.6f} util={rep_current.utilization:.4f} gap_rel={gap_rel}")
    print(f"greedy:   status={rep_greedy.status} ticks={rep_greedy.ticks_total} lb={rep_greedy.lower_bound_ticks} gap={rep_greedy.gap_to_lower_bound:.6f} util={rep_greedy.utilization:.4f} gap_rel={rep_greedy.gap_reliability or 'unknown'}")
    print(f"saved_ticks={comp['saved_ticks']} estimated_savings={comp['estimated_savings']:.2f}{baseline_tag}")
    return 0 if rep_current.status == "PASS" and rep_greedy.status == "PASS" else 2


def cmd_audit(args: argparse.Namespace) -> int:
    outdir = prepare_output_dir(Path(args.outdir))
    _validate_common_args(args)
    inst = instance_from_csv(args.demands, bw=args.bw, slots=args.slots, instance_id=args.id, notes=args.notes, model=args.model)
    _check_bounds_mode_slots(inst, args.bounds_mode)
    _resolve_bounds_mode(args)
    if args.schedule_json and args.schedule_csv:
        raise SystemExit("use only one of --schedule-json or --schedule-csv")
    if args.solver_plugin and (args.schedule_json or args.schedule_csv):
        raise SystemExit("use either --solver-plugin or a schedule input, not both")
    if not args.solver_plugin and not args.schedule_json and not args.schedule_csv:
        raise SystemExit("provide one of --schedule-json, --schedule-csv, or --solver-plugin")
    if args.solver_plugin:
        plugin = Path(args.solver_plugin)
        if not plugin.exists():
            raise FileNotFoundError(f"solver plugin not found: {plugin}")
        payload = json.dumps(inst)
        proc = subprocess.run(  # nosec B603
            [sys.executable, str(plugin)],
            input=payload,
            text=True,
            capture_output=True,
            timeout=float(args.solver_plugin_timeout),
            check=False,
        )
        if proc.returncode != 0:
            raise ValueError(f"solver plugin failed with exit code {proc.returncode}: {proc.stderr.strip()}")
        if args.solver_plugin_max_output_bytes is not None and len(proc.stdout.encode("utf-8")) > int(args.solver_plugin_max_output_bytes):
            raise ValueError("solver plugin output exceeds --solver-plugin-max-output-bytes")
        try:
            schedule = json.loads(proc.stdout)
        except Exception as e:
            raise ValueError("solver plugin did not return valid schedule JSON") from e
        rep = validate_schedule(
            inst,
            schedule,
            max_errors=args.max_errors,
            bounds_subset_limit=args.bounds_subset_limit,
            strict1_bounds_mode=args.bounds_mode,
        )
    elif args.schedule_json:
        schedule = load_json(args.schedule_json)
        rep = validate_schedule(
            inst,
            schedule,
            max_errors=args.max_errors,
            bounds_subset_limit=args.bounds_subset_limit,
            strict1_bounds_mode=args.bounds_mode,
        )
    else:
        schedule = schedule_from_csv(args.schedule_csv, model=str(inst.get("model", "STRICT1")))
        rep = validate_schedule(
            inst,
            schedule,
            max_errors=args.max_errors,
            bounds_subset_limit=args.bounds_subset_limit,
            strict1_bounds_mode=args.bounds_mode,
        )
    if args.max_output_ticks is not None and rep.ticks_total > args.max_output_ticks:
        raise ValueError(f"customer_current ticks_total {rep.ticks_total} exceeds --max-output-ticks {args.max_output_ticks}")
    rep_greedy = validate_ticks_iter(
        inst,
        iter_greedy(inst),
        max_errors=args.max_errors,
        bounds_subset_limit=args.bounds_subset_limit,
        strict1_bounds_mode=args.bounds_mode,
    )
    if rep.ticks_total > 0:
        gap_vs_greedy = (rep.ticks_total - rep_greedy.ticks_total) / rep.ticks_total
    else:
        gap_vs_greedy = 0.0
    rep_dict = rep.to_dict()
    rep_dict["gap_practical"] = gap_vs_greedy

    gate_fail_reasons: list[str] = []
    if args.max_gap is not None:
        if not rep.bounds_complete:
            gate_fail_reasons.append("bounds_complete=false: gap is a lower estimate only; use --max-gap-vs-greedy or relax threshold")
        elif rep.gap_to_lower_bound > args.max_gap:
            gate_fail_reasons.append(f"gap_to_lower_bound {rep.gap_to_lower_bound:.6f} exceeds --max-gap {args.max_gap:.6f}")
    if args.max_gap_vs_greedy is not None:
        if gap_vs_greedy > args.max_gap_vs_greedy:
            gate_fail_reasons.append(f"gap_vs_greedy {gap_vs_greedy:.6f} exceeds --max-gap-vs-greedy {args.max_gap_vs_greedy:.6f}")
    dump_json(outdir / "instance.json", inst)
    dump_json(outdir / "schedule_customer_current.json", schedule)
    write_schedule_csv(outdir / "schedule_customer_current.csv", schedule)
    dump_json(outdir / "report_customer_current.json", rep_dict)
    summary = {
        "instance": inst,
        "current_label": "customer_current",
        "candidate_label": "customer_current",
        "reports": {"current": rep_dict, "customer_current": rep_dict},
        "comparison": {
            "comparable": True,
            "comparison_note": "Audit-only mode: no baseline/candidate comparison requested.",
            "saved_ticks": 0,
            "saved_ticks_pct": 0.0,
            "gap_reduction_ticks": 0,
            "utilization_delta": 0.0,
            "estimated_savings": 0.0,
            "cost_per_tick": 0.0,
        },
        "roi": compute_roi({"comparable": True, "saved_ticks": 0}, {}, theoretical_saved_ticks=max(rep.gap_ticks, 0)),
        "audit": {
            "audit_only": True,
            "audit_note": (
                "gap_to_lower_bound reflects an abstract model without topology. "
                "If your solver accounts for topology constraints, gap > 0 may be expected."
            ),
            "gap_vs_greedy": gap_vs_greedy,
        },
        "artifacts": {
            "instance": "instance.json",
            "schedule_current": "schedule_customer_current.json",
            "schedule_current_csv": "schedule_customer_current.csv",
            "schedule_greedy": None,
            "schedule_greedy_csv": None,
            "report_current": "report_customer_current.json",
            "report_greedy": "report_customer_current.json",
            "report_markdown": "report.md",
            "report_html": "report.html",
        },
    }
    dump_json(outdir / "summary.json", summary)
    write_reports(outdir, summary)
    print(f"Copy-Space Guard audit written to: {outdir}")
    print(f"customer_current: status={rep.status} ticks={rep.ticks_total} lb={rep.lower_bound_ticks} util={rep.utilization:.4f}")
    print(f"practical_gap={gap_vs_greedy:.6f} (vs greedy, always reliable)")
    print(
        f"theoretical_gap={rep.gap_to_lower_bound:.6f} "
        f"(vs lower bound, {'exact' if rep.gap_reliability == 'exact' else 'lower estimate'})"
    )
    if gate_fail_reasons:
        print("AUDIT GATE FAIL", file=sys.stderr)
        for reason in gate_fail_reasons:
            print(f"- {reason}", file=sys.stderr)
        return 2
    return 0 if rep.status == "PASS" else 2


def _load_schedule_auto(path: str, *, model: str) -> Schedule:
    p = Path(path)
    if p.suffix.lower() == ".csv":
        return schedule_from_csv(path, model=model)
    return cast(Schedule, load_json(path))


def cmd_compare(args: argparse.Namespace) -> int:
    outdir = prepare_output_dir(Path(args.outdir))
    _validate_common_args(args)
    inst = instance_from_csv(args.demands, bw=args.bw, slots=args.slots, instance_id=args.id, notes=args.notes, model=args.model)
    _check_bounds_mode_slots(inst, args.bounds_mode)
    _resolve_bounds_mode(args)
    sched_a = _load_schedule_auto(args.schedule_a, model=str(inst.get("model", "STRICT1")))
    sched_b = _load_schedule_auto(args.schedule_b, model=str(inst.get("model", "STRICT1")))
    rep_a = validate_schedule(
        inst,
        sched_a,
        max_errors=args.max_errors,
        bounds_subset_limit=args.bounds_subset_limit,
        strict1_bounds_mode=args.bounds_mode,
    )
    rep_b = validate_schedule(
        inst,
        sched_b,
        max_errors=args.max_errors,
        bounds_subset_limit=args.bounds_subset_limit,
        strict1_bounds_mode=args.bounds_mode,
    )
    if args.max_output_ticks is not None:
        if rep_a.ticks_total > args.max_output_ticks:
            raise ValueError(f"schedule_a ticks_total {rep_a.ticks_total} exceeds --max-output-ticks {args.max_output_ticks}")
        if rep_b.ticks_total > args.max_output_ticks:
            raise ValueError(f"schedule_b ticks_total {rep_b.ticks_total} exceeds --max-output-ticks {args.max_output_ticks}")

    comp, roi_summary = _load_roi_config_and_compute(args, rep_a, rep_b)

    dump_json(outdir / "instance.json", inst)
    dump_json(outdir / "schedule_schedule_a.json", sched_a)
    dump_json(outdir / "schedule_schedule_b.json", sched_b)
    write_schedule_csv(outdir / "schedule_schedule_a.csv", sched_a)
    write_schedule_csv(outdir / "schedule_schedule_b.csv", sched_b)
    dump_json(outdir / "report_schedule_a.json", rep_a.to_dict())
    dump_json(outdir / "report_schedule_b.json", rep_b.to_dict())
    summary = {
        "instance": inst,
        "current_label": "schedule_a",
        "candidate_label": "schedule_b",
        "reports": {
            "current": rep_a.to_dict(),
            "schedule_a": rep_a.to_dict(),
            "schedule_b": rep_b.to_dict(),
        },
        "comparison": comp,
        "roi": roi_summary,
        "analysis_options": {
            "bounds_subset_limit": args.bounds_subset_limit,
            "max_errors": args.max_errors,
            "mode": "compare",
        },
        "artifacts": {
            "instance": "instance.json",
            "schedule_current": "schedule_schedule_a.json",
            "schedule_current_csv": "schedule_schedule_a.csv",
            "schedule_greedy": "schedule_schedule_b.json",
            "schedule_greedy_csv": "schedule_schedule_b.csv",
            "report_current": "report_schedule_a.json",
            "report_greedy": "report_schedule_b.json",
            "report_markdown": "report.md",
            "report_html": "report.html",
        },
        "compare": {
            "note": "compare mode evaluates two provided external schedules on one demand matrix.",
            "schedule_a_path": args.schedule_a,
            "schedule_b_path": args.schedule_b,
        },
    }
    validate_summary_contract(summary)
    dump_json(outdir / "summary.json", summary)
    write_reports(outdir, summary)
    print(f"Copy-Space Guard compare written to: {outdir}")
    print(f"schedule_a: status={rep_a.status} ticks={rep_a.ticks_total} lb={rep_a.lower_bound_ticks} gap={rep_a.gap_to_lower_bound:.6f} util={rep_a.utilization:.4f} gap_rel={rep_a.gap_reliability or 'unknown'}")
    print(f"schedule_b: status={rep_b.status} ticks={rep_b.ticks_total} lb={rep_b.lower_bound_ticks} gap={rep_b.gap_to_lower_bound:.6f} util={rep_b.utilization:.4f} gap_rel={rep_b.gap_reliability or 'unknown'}")
    print(f"saved_ticks={comp['saved_ticks']} estimated_savings={comp['estimated_savings']:.2f}")
    return 0 if rep_a.status == "PASS" and rep_b.status == "PASS" else 2


def cmd_validate(args: argparse.Namespace) -> int:
    _validate_common_args(args)
    inst = load_json(args.instance)
    _check_bounds_mode_slots(inst, args.bounds_mode)
    _resolve_bounds_mode(args)
    sched = load_json(args.schedule)
    rep = validate_schedule(
        inst,
        sched,
        max_errors=args.max_errors,
        bounds_subset_limit=args.bounds_subset_limit,
        strict1_bounds_mode=args.bounds_mode,
    )
    if args.report:
        report_path = prepare_output_file(Path(args.report))
        dump_json(report_path, rep.to_dict())
    print(rep.status)
    if rep.status != "PASS":
        print(rep.errors[0], file=sys.stderr)
        if rep.errors_truncated:
            print(f"... {rep.total_errors - len(rep.errors)} additional errors omitted", file=sys.stderr)
        return 2
    print(f"ticks={rep.ticks_total} lb={rep.lower_bound_ticks} gap={rep.gap_to_lower_bound:.6f} util={rep.utilization:.4f}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    summary = load_json(args.summary)
    outdir = prepare_output_dir(Path(args.outdir))
    write_reports(outdir, summary)
    print(f"reports written to: {outdir}")
    return 0


def cmd_schedule_csv_to_json(args: argparse.Namespace) -> int:
    sched = schedule_from_csv(args.csv, fill_empty_ticks=not args.compact_ticks, model=args.model)
    out_path = prepare_output_file(Path(args.out))
    dump_json(out_path, sched)
    print(f"schedule JSON written to: {out_path}")
    return 0


def cmd_import_msccl(args: argparse.Namespace) -> int:
    sched = import_msccl_xml(args.xml, model=args.model, max_rows=args.max_rows, max_file_size=args.max_file_size)
    out_path = prepare_output_file(Path(args.out))
    dump_json(out_path, sched)
    print(f"schedule JSON written to: {out_path}")
    return 0


def cmd_import_taccl(args: argparse.Namespace) -> int:
    sched = import_taccl_json(args.json, model=args.model, max_rows=args.max_rows, max_file_size=args.max_file_size)
    out_path = prepare_output_file(Path(args.out))
    dump_json(out_path, sched)
    print(f"schedule JSON written to: {out_path}")
    return 0


def cmd_import_csv(args: argparse.Namespace) -> int:
    mapping: dict[str, str] = {}
    for token in args.map:
        if "=" not in token:
            raise ValueError(f"invalid --map value {token!r}; expected key=column")
        key, value = token.split("=", 1)
        mapping[key.strip()] = value.strip()
    for needed in ("tick", "src", "dst", "len"):
        if needed not in mapping:
            raise ValueError(f"missing mapping for {needed}; expected --map {needed}=<column>")
    sched = import_csv_with_map(
        args.csv,
        tick=mapping["tick"],
        src=mapping["src"],
        dst=mapping["dst"],
        length=mapping["len"],
        model=args.model,
        max_rows=args.max_rows,
        max_file_size=args.max_file_size,
    )
    out_path = prepare_output_file(Path(args.out))
    dump_json(out_path, sched)
    print(f"schedule JSON written to: {out_path}")
    return 0


def cmd_import_nccl_log(args: argparse.Namespace) -> int:
    rows, _meta = import_nccl_log_demands(args.log, max_rows=args.max_rows, max_file_size=args.max_file_size)
    out_path = prepare_output_file(Path(args.out))
    write_imported_demands_csv(rows, out_path)
    print(f"demands CSV written to: {out_path} rows={len(rows)}")
    return 0


def cmd_import_pytorch_trace(args: argparse.Namespace) -> int:
    rows, _meta = import_pytorch_trace_demands(args.trace, max_rows=args.max_rows, max_file_size=args.max_file_size)
    out_path = prepare_output_file(Path(args.out))
    write_imported_demands_csv(rows, out_path)
    print(f"demands CSV written to: {out_path} rows={len(rows)}")
    return 0


def cmd_infer(args: argparse.Namespace) -> int:
    path = Path(args.log)
    kind = args.kind
    if kind is None:
        ext = path.suffix.lower()
        if ext == ".json":
            kind = "pytorch"
        else:
            kind = "nccl"
    if kind == "nccl":
        rows, meta = import_nccl_log_demands(path, max_rows=args.max_rows, max_file_size=args.max_file_size)
    else:
        rows, meta = import_pytorch_trace_demands(path, max_rows=args.max_rows, max_file_size=args.max_file_size)
    slots = meta["slots"]
    bw = meta.get("max_bytes_per_transfer", 0) * 8
    print(f"inferred: slots={slots} bw={bw} bits (= max transfer size; use actual NIC bandwidth if known)")
    throughput = meta.get("throughput_estimate_gbps")
    if throughput is not None:
        print(f"throughput estimate: {throughput} GB/s")
    demands_path = None
    if args.out:
        out_path = prepare_output_file(Path(args.out))
        write_imported_demands_csv(rows, out_path)
        demands_path = str(out_path)
        print(f"demands CSV written to: {out_path}")
    if demands_path:
        print(f"run: copyspace-guard audit --demands {demands_path} --bw {bw} --slots {slots} --schedule schedule.csv")
    else:
        print(f"run: copyspace-guard import-nccl-log {path} --out demands.csv --bw {bw} --slots {slots}")
    return 0


def cmd_validate_artifact(args: argparse.Namespace) -> int:
    obj = load_json(args.path)
    validate_artifact_contract(args.kind, obj)
    print(f"{args.kind} artifact is valid")
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    summary = load_json(args.summary)
    cfg = {}
    if args.config:
        loaded = load_config(args.config)
        cfg = loaded.get("gates", loaded)
    report_name = args.report or cfg.get("report", "greedy")
    reports = summary.get("reports", {})
    if report_name == "current":
        report_name = summary.get("current_label", "baseline")
    if report_name not in reports:
        raise SystemExit(f"report not found in summary: {report_name}")
    from .core import Report
    rep = Report(**reports[report_name])
    max_gap = args.max_gap if args.max_gap is not None else cfg.get("max_gap_to_lower_bound", cfg.get("max_gap"))
    max_gap_vs_greedy = args.max_gap_vs_greedy if args.max_gap_vs_greedy is not None else cfg.get("max_gap_vs_greedy")
    min_util = args.min_utilization if args.min_utilization is not None else cfg.get("min_utilization")
    max_ticks = args.max_ticks if args.max_ticks is not None else cfg.get("max_ticks")
    ok, reasons = gate_report(
        rep,
        max_gap=float(max_gap) if max_gap is not None else None,
        min_utilization=float(min_util) if min_util is not None else None,
        max_ticks=int(max_ticks) if max_ticks is not None else None,
    )
    gap_vs_greedy_value = None
    if max_gap_vs_greedy is not None:
        audit = summary.get("audit", {})
        if isinstance(audit, dict) and isinstance(audit.get("gap_vs_greedy"), (int, float)):
            gap_vs_greedy_value = float(audit["gap_vs_greedy"])
        else:
            current_label = summary.get("current_label", "baseline")
            reports_obj = summary.get("reports", {})
            cur = reports_obj.get(current_label)
            greedy = reports_obj.get("greedy")
            if isinstance(cur, dict) and isinstance(greedy, dict):
                cur_ticks = int(cur.get("ticks_total", 0))
                greedy_ticks = int(greedy.get("ticks_total", 0))
                if cur_ticks > 0:
                    gap_vs_greedy_value = (cur_ticks - greedy_ticks) / cur_ticks
        if gap_vs_greedy_value is None:
            reasons.append("gap_vs_greedy unavailable in summary for this report")
        elif gap_vs_greedy_value > float(max_gap_vs_greedy):
            reasons.append(f"gap_vs_greedy {gap_vs_greedy_value:.6f} > max_gap_vs_greedy {float(max_gap_vs_greedy):.6f}")
    ok = len(reasons) == 0
    if ok:
        extra = f" gap_vs_greedy={gap_vs_greedy_value:.6f}" if gap_vs_greedy_value is not None else ""
        print(f"GATE PASS report={report_name} ticks={rep.ticks_total} gap={rep.gap_to_lower_bound:.6f} util={rep.utilization:.4f}{extra}")
        return 0
    print(f"GATE FAIL report={report_name}", file=sys.stderr)
    for r in reasons:
        print(f"- {r}", file=sys.stderr)
    return 2


def cmd_anonymize(args: argparse.Namespace) -> int:
    if args.max_rows is not None and args.max_rows < 0:
        raise ValueError("--max-rows must be >= 0")
    if args.max_file_size is not None and args.max_file_size < 0:
        raise ValueError("--max-file-size must be >= 0")
    if args.max_unique_slots is not None and args.max_unique_slots < 0:
        raise ValueError("--max-unique-slots must be >= 0")
    out_path = prepare_output_file(Path(args.out))
    mapping_path = prepare_output_file(Path(args.mapping)) if args.mapping else None
    if args.kind == "schedule":
        mapping = anonymize_schedule_csv(
            args.csv,
            out_path,
            mapping_path,
            args.mapping_in,
            max_rows=args.max_rows,
            max_file_size=args.max_file_size,
            max_unique_slots=args.max_unique_slots,
        )
    else:
        mapping = anonymize_demands_csv(
            args.csv,
            out_path,
            mapping_path,
            args.mapping_in,
            max_rows=args.max_rows,
            max_file_size=args.max_file_size,
            max_unique_slots=args.max_unique_slots,
        )
    print(f"anonymized CSV written to: {out_path}")
    if mapping_path:
        print(f"mapping written to: {mapping_path}")
    print(f"unique_slots={len(mapping)}")
    return 0


def cmd_bench(args: argparse.Namespace) -> int:
    result = run_synthetic_bench(
        slots=args.slots,
        bits_per_edge=args.bits_per_edge,
        bw=args.bw,
        model=args.model,
        outdir=Path(args.outdir),
        write_demands=True,
    )
    print(
        "bench "
        f"elapsed={float(result['elapsed_seconds']):.6f}s "
        f"slots={result['slots']} model={result['model']} "
        f"baseline_ticks={cast(dict[str, Any], result['baseline'])['ticks_total']} "
        f"greedy_ticks={cast(dict[str, Any], result['greedy'])['ticks_total']}"
    )
    baseline = cast(dict[str, Any], result["baseline"])
    greedy = cast(dict[str, Any], result["greedy"])
    return 0 if baseline["status"] == "PASS" and greedy["status"] == "PASS" else 2


def run_synthetic_bench(
    *,
    slots: int,
    bits_per_edge: int,
    bw: int,
    model: str,
    outdir: Path,
    write_demands: bool,
) -> dict[str, Any]:
    rows = ["src_slot,dst_slot,bits_total"]
    for i in range(slots):
        rows.append(f"{i},{(i + 1) % slots},{bits_per_edge}")
    outdir = prepare_output_dir(outdir)
    demands = outdir / "bench_demands.csv"
    if write_demands:
        demands.write_text("\n".join(rows) + "\n", encoding="utf-8")
    else:
        demands = outdir / f"bench_{model.lower()}_{slots}.csv"
        demands.write_text("\n".join(rows) + "\n", encoding="utf-8")
    t0 = time.perf_counter()
    inst = instance_from_csv(demands, bw=bw, model=model)
    rep_baseline = validate_ticks_iter(inst, iter_baseline(inst))
    rep_greedy = validate_ticks_iter(inst, iter_greedy(inst))
    elapsed = time.perf_counter() - t0
    result: dict[str, Any] = {
        "slots": slots,
        "bits_per_edge": bits_per_edge,
        "bw": bw,
        "model": model,
        "elapsed_seconds": elapsed,
        "baseline": rep_baseline.to_dict(),
        "greedy": rep_greedy.to_dict(),
    }
    dump_json(outdir / "bench.json", result)
    return result


def cmd_bench_suite(args: argparse.Namespace) -> int:
    outdir = prepare_output_dir(Path(args.outdir))
    cases: list[dict[str, Any]] = [
        {"name": "strict1-ring32", "slots": 32, "bits_per_edge": 1048576, "bw": 1048576, "model": "STRICT1"},
        {"name": "strict1-ring128", "slots": 128, "bits_per_edge": 1048576, "bw": 1048576, "model": "STRICT1"},
        {"name": "read1-write1-ring128", "slots": 128, "bits_per_edge": 1048576, "bw": 1048576, "model": "READ1_WRITE1"},
    ]
    results: list[dict[str, Any]] = []
    suite_start = time.perf_counter()
    for case in cases:
        case_dir = outdir / str(case["name"])
        result = run_synthetic_bench(
            slots=int(case["slots"]),
            bits_per_edge=int(case["bits_per_edge"]),
            bw=int(case["bw"]),
            model=str(case["model"]),
            outdir=case_dir,
            write_demands=False,
        )
        result["name"] = case["name"]
        results.append(result)
    total_elapsed = time.perf_counter() - suite_start
    failures: list[str] = []
    for result in results:
        name = str(result["name"])
        elapsed = float(result["elapsed_seconds"])
        baseline = cast(dict[str, Any], result["baseline"])
        greedy = cast(dict[str, Any], result["greedy"])
        if baseline["status"] != "PASS" or greedy["status"] != "PASS":
            failures.append(f"{name}: validation failed")
        if args.max_case_seconds is not None and elapsed > args.max_case_seconds:
            failures.append(f"{name}: elapsed {elapsed:.6f}s exceeds --max-case-seconds {args.max_case_seconds}")
    if args.max_total_seconds is not None and total_elapsed > args.max_total_seconds:
        failures.append(f"total elapsed {total_elapsed:.6f}s exceeds --max-total-seconds {args.max_total_seconds}")
    bounds_start = time.perf_counter()
    bounds_args = argparse.Namespace(
        outdir=str(outdir / "bounds"),
        min_slots=32,
        max_slots=256,
        step_slots=32,
        bw=1048576,
        patterns="ring,pair-plus-clique",
        bounds_subset_limit=20,
        max_case_seconds=args.max_case_seconds,
        max_total_seconds=None,
    )
    bounds_rc = cmd_bench_bounds(bounds_args)
    bounds_elapsed = time.perf_counter() - bounds_start
    if bounds_rc != 0:
        failures.append("bounds benchmark failed")
    suite = {
        "version": 0,
        "elapsed_seconds": total_elapsed + bounds_elapsed,
        "case_count": len(results),
        "failures": failures,
        "cases": results,
        "bounds_bench": {
            "outdir": "bounds",
            "elapsed_seconds": bounds_elapsed,
            "status": "PASS" if bounds_rc == 0 else "FAIL",
        },
    }
    outdir.mkdir(parents=True, exist_ok=True)
    dump_json(outdir / "bench_suite.json", suite)
    print(f"bench-suite elapsed={total_elapsed + bounds_elapsed:.6f}s cases={len(results)} failures={len(failures)}")
    for result in results:
        greedy = cast(dict[str, Any], result["greedy"])
        print(f"- {result['name']} elapsed={float(result['elapsed_seconds']):.6f}s greedy_ticks={greedy['ticks_total']}")
    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 2
    return 0


def _make_bounds_bench_instance(*, slots: int, pattern: str, bw: int) -> Instance:
    demands: list[dict[str, int]] = []
    if pattern == "ring":
        for i in range(slots):
            demands.append({"src_slot": i, "dst_slot": (i + 1) % slots, "bits_total": bw})
    elif pattern == "pair-plus-clique":
        pair_count = slots // 3
        offset = slots - pair_count
        for i in range(pair_count):
            demands.append({"src_slot": i, "dst_slot": offset + i, "bits_total": 13 * bw})
        clique = list(range(max(0, pair_count - 5), pair_count))
        for i in range(len(clique)):
            for j in range(i + 1, len(clique)):
                demands.append({"src_slot": clique[i], "dst_slot": clique[j], "bits_total": 3 * bw})
    else:
        for i in range(slots):
            demands.append({"src_slot": i, "dst_slot": (i + 1) % slots, "bits_total": bw})
            demands.append({"src_slot": i, "dst_slot": (i + 2) % slots, "bits_total": bw})
    return cast(Instance, {
        "version": 0,
        "model": "STRICT1",
        "slots": slots,
        "copy_bw_bits_per_tick": bw,
        "demands": demands,
    })


def cmd_bench_bounds(args: argparse.Namespace) -> int:
    outdir = prepare_output_dir(Path(args.outdir))
    if args.min_slots < 2 or args.max_slots < args.min_slots or args.step_slots <= 0:
        raise ValueError("invalid slot range for bench-bounds")
    if args.bw <= 0:
        raise ValueError("--bw must be > 0")
    patterns = [p.strip() for p in args.patterns.split(",") if p.strip()]
    if not patterns:
        raise ValueError("no benchmark patterns selected")

    t0 = time.perf_counter()
    cases: list[dict[str, Any]] = []
    failures: list[str] = []
    for pattern in patterns:
        for slots in range(args.min_slots, args.max_slots + 1, args.step_slots):
            inst = _make_bounds_bench_instance(slots=slots, pattern=pattern, bw=args.bw)
            t_case = time.perf_counter()
            lbs = lower_bound_components(inst, exhaustive_subset_limit=args.bounds_subset_limit)
            elapsed = time.perf_counter() - t_case
            case = {
                "pattern": pattern,
                "slots": slots,
                "elapsed_seconds": elapsed,
                "lower_bound_ticks": int(lbs["lower_bound_ticks"]),
                "density_lower_bound": int(lbs["density_lower_bound"]),
                "witness_kind": str(cast(dict[str, Any], lbs["lower_bound_witness"]).get("kind", "")),
                "bounds_complete": bool(lbs["bounds_complete"]),
            }
            if args.max_case_seconds is not None and elapsed > args.max_case_seconds:
                failures.append(f"{pattern}/{slots}: elapsed {elapsed:.6f}s exceeds --max-case-seconds {args.max_case_seconds}")
            cases.append(case)
    total_elapsed = time.perf_counter() - t0
    if args.max_total_seconds is not None and total_elapsed > args.max_total_seconds:
        failures.append(f"total elapsed {total_elapsed:.6f}s exceeds --max-total-seconds {args.max_total_seconds}")
    summary = {
        "version": 0,
        "elapsed_seconds": total_elapsed,
        "case_count": len(cases),
        "failures": failures,
        "cases": cases,
    }
    dump_json(outdir / "bench_bounds.json", summary)
    print(f"bench-bounds elapsed={total_elapsed:.6f}s cases={len(cases)} failures={len(failures)}")
    max_auto = max((c["slots"] for c in cases if c["bounds_complete"]), default=0)
    min_partial = min((c["slots"] for c in cases if not c["bounds_complete"]), default=9999)
    print("bench-bounds recommendation by slot count:", file=sys.stderr)
    if max_auto >= args.min_slots:
        print(f"  slots <= {max_auto}: --bounds-mode auto (exhaustive, exact)", file=sys.stderr)
    print(f"  slots {min_partial}-{args.max_slots}: --bounds-mode fractional_heuristic (faster, estimated)", file=sys.stderr)
    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 2
    return 0


def doctor_checks(root: Path) -> list[dict[str, object]]:
    root = root.resolve()
    checks: list[dict[str, object]] = []
    required_paths = [
        "README.md",
        "pyproject.toml",
        "schemas/instance_v0.schema.json",
        "schemas/report_v0.schema.json",
        "schemas/schedule_v0.schema.json",
        "schemas/summary_v0.schema.json",
        "examples/ring15.csv",
        "examples/roi.yml",
        "client-package/README_CLIENT.md",
    ]
    for rel in required_paths:
        ok = (root / rel).exists()
        checks.append({"name": f"path:{rel}", "ok": ok, "detail": "found" if ok else "missing"})

    try:
        inst = instance_from_csv(root / "examples" / "ring15.csv", bw=256)
        rep = validate_ticks_iter(inst, iter_greedy(inst))
        checks.append({"name": "demo:greedy-validation", "ok": rep.status == "PASS", "detail": f"status={rep.status} ticks={rep.ticks_total}"})
    except Exception as e:
        checks.append({"name": "demo:greedy-validation", "ok": False, "detail": str(e)})

    for kind, rel in [
        ("instance", "schemas/instance_v0.schema.json"),
        ("report", "schemas/report_v0.schema.json"),
        ("schedule", "schemas/schedule_v0.schema.json"),
        ("summary", "schemas/summary_v0.schema.json"),
    ]:
        try:
            load_json(root / rel)
            checks.append({"name": f"schema-json:{kind}", "ok": True, "detail": "valid JSON"})
        except Exception as e:
            checks.append({"name": f"schema-json:{kind}", "ok": False, "detail": str(e)})
    return checks


def prepare_output_dir(path: Path) -> Path:
    if any(part == ".." for part in path.parts):
        raise ValueError("--outdir must not contain parent directory traversal")
    if path.exists() and not path.is_dir():
        raise ValueError(f"--outdir must be a directory: {path}")
    if path.exists() and path.is_symlink():
        raise ValueError(f"--outdir must not be a symlink: {path}")
    for ancestor in path.parents:
        if ancestor.exists() and ancestor.is_symlink():
            raise ValueError(f"--outdir must not traverse through a symlink: {path}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def prepare_output_file(path: Path) -> Path:
    if any(part == ".." for part in path.parts):
        raise ValueError(f"output path must not contain parent directory traversal: {path}")
    if path.exists():
        if path.is_dir():
            raise ValueError(f"output path must not be a directory: {path}")
        if path.is_symlink():
            raise ValueError(f"output path must not be a symlink: {path}")
    for ancestor in path.parents:
        if ancestor.exists() and ancestor.is_symlink():
            raise ValueError(f"output path must not traverse through a symlink: {path}")
    parent = path.parent
    if parent.exists() and not parent.is_dir():
        raise ValueError(f"output path parent must be a directory: {parent}")
    parent.mkdir(parents=True, exist_ok=True)
    return path


def cmd_doctor(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    checks = doctor_checks(root)
    failed = [check for check in checks if not check["ok"]]
    recommendations: list[str] = []
    if args.demands:
        inst = instance_from_csv(args.demands, bw=args.bw, slots=args.slots, model=args.model)
        slots = int(inst["slots"])
        if slots > 20:
            recommendations.append(
                f"slots={slots}: gap_to_lower_bound is a lower estimate for large STRICT1 instances; use --max-gap-vs-greedy"
            )
            recommendations.append("recommended bounds mode: --bounds-mode fractional_heuristic")
            recommendations.append("recommended CI metric: --max-gap-vs-greedy <threshold>")
        else:
            recommendations.append(f"slots={slots}: gap_to_lower_bound can be exact on exhaustive path")
            recommendations.append("recommended bounds mode: --bounds-mode auto")
            recommendations.append("recommended CI metric: --max-gap <threshold> (optionally also --max-gap-vs-greedy)")
    if args.json:
        print(
            json.dumps(
                {
                    "status": "FAIL" if failed else "PASS",
                    "root": str(root),
                    "checks": checks,
                    "recommendations": recommendations,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1 if failed else 0
    for check in checks:
        status = "OK" if check["ok"] else "FAIL"
        print(f"{status} {check['name']} {check['detail']}")
    for rec in recommendations:
        print(f"INFO {rec}")
    if failed:
        print(f"doctor failed: {len(failed)} check(s) failed", file=sys.stderr)
        return 1
    print(f"doctor passed: {len(checks)} checks")
    return 0


def _add_instance_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--model", choices=["STRICT1", "READ1_WRITE1"], default="STRICT1", help="resource model")
    p.add_argument("--slots", type=int, default=None, help="slot count; inferred if omitted")
    p.add_argument("--id", default=None)
    p.add_argument("--notes", default=None)


def _add_bounds_args(p: argparse.ArgumentParser, *, include_exact: bool = True) -> None:
    choices = ["auto", "fractional_heuristic", "fractional_odd_subset"]
    if include_exact:
        choices.append("fractional_exact")
    p.add_argument("--bounds-subset-limit", type=int, default=20, help="STRICT1 exhaustive subset-density bound slot limit")
    p.add_argument("--bounds-mode", choices=choices, default="auto", help="STRICT1 lower-bound mode")
    p.add_argument("--max-errors", type=int, default=None, help="maximum validation errors stored in reports")
    p.add_argument("--max-output-ticks", type=int, default=None, help="fail if report exceeds this tick count")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="copyspace-guard", description="Deterministic data-movement audit and CI gate")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="run current/baseline vs deterministic candidate analysis from demands CSV")
    a.add_argument("--csv", required=True, help="CSV with src_slot,dst_slot,bits_total")
    a.add_argument("--bw", type=int, required=True, help="copy bandwidth per tick in bits")
    _add_instance_args(a)
    a.add_argument("--cost-per-tick", type=float, default=0.0, help="optional business estimate in dollars per saved tick")
    a.add_argument("--roi", default=None, help="optional ROI config JSON/YAML")
    a.add_argument("--current-schedule-json", default=None, help="optional customer/current schedule JSON")
    a.add_argument("--current-schedule-csv", default=None, help="optional customer/current schedule CSV: tick,src_slot,dst_slot,len_bits")
    a.add_argument("--summary-only", action="store_true", help="do not write full schedule JSON/CSV artifacts")
    _add_bounds_args(a)
    a.add_argument("--max-demands", type=int, default=None, help="fail if normalized demand count exceeds this limit")
    a.add_argument("--max-slots", type=int, default=None, help="fail if slot count exceeds this limit")
    a.add_argument("--outdir", default="artifacts/analysis")
    a.set_defaults(func=cmd_analyze)

    au = sub.add_parser("audit", help="audit one provided schedule against demands without baseline/greedy solving")
    au.add_argument("--demands", required=True, help="CSV with src_slot,dst_slot,bits_total")
    au.add_argument("--bw", type=int, required=True, help="copy bandwidth per tick in bits")
    _add_instance_args(au)
    au.add_argument("--schedule-json", default=None, help="customer schedule JSON")
    au.add_argument("--schedule-csv", "--schedule", dest="schedule_csv", default=None, help="customer schedule CSV: tick,src_slot,dst_slot,len_bits")
    au.add_argument("--solver-plugin", default=None, help="external solver plugin path (reads instance JSON from stdin, writes schedule JSON to stdout)")
    au.add_argument("--solver-plugin-timeout", type=float, default=300.0, help="timeout in seconds for --solver-plugin")
    au.add_argument("--solver-plugin-max-output-bytes", type=int, default=8_000_000, help="max stdout bytes accepted from --solver-plugin")
    _add_bounds_args(au)
    au.add_argument("--max-gap", type=float, default=None, help="optional CI threshold for gap_to_lower_bound")
    au.add_argument("--max-gap-vs-greedy", type=float, default=None, help="optional CI threshold for (current_ticks-greedy_ticks)/current_ticks")
    au.add_argument("--outdir", default="artifacts/audit")
    au.set_defaults(func=cmd_audit)

    c = sub.add_parser("compare", help="compare two provided schedules against one demands matrix")
    c.add_argument("--demands", required=True, help="CSV with src_slot,dst_slot,bits_total")
    c.add_argument("--bw", type=int, required=True, help="copy bandwidth per tick in bits")
    c.add_argument("--schedule-a", required=True, help="schedule A path (.json or .csv)")
    c.add_argument("--schedule-b", required=True, help="schedule B path (.json or .csv)")
    _add_instance_args(c)
    c.add_argument("--cost-per-tick", type=float, default=0.0, help="optional business estimate in dollars per saved tick")
    c.add_argument("--roi", default=None, help="optional ROI config JSON/YAML")
    _add_bounds_args(c)
    c.add_argument("--outdir", default="artifacts/compare")
    c.set_defaults(func=cmd_compare)

    v = sub.add_parser("validate", help="validate an existing schedule against an instance")
    v.add_argument("instance")
    v.add_argument("schedule")
    v.add_argument("--report")
    _add_bounds_args(v, include_exact=False)
    v.set_defaults(func=cmd_validate)

    r = sub.add_parser("report", help="regenerate markdown/html reports from summary.json")
    r.add_argument("summary")
    r.add_argument("--outdir", default="artifacts/report")
    r.set_defaults(func=cmd_report)

    sc = sub.add_parser("schedule-csv-to-json", help="convert schedule CSV tick,src_slot,dst_slot,len_bits to JSON")
    sc.add_argument("--csv", required=True)
    sc.add_argument("--out", required=True)
    sc.add_argument("--model", choices=["STRICT1", "READ1_WRITE1"], default="STRICT1")
    sc.add_argument("--compact-ticks", action="store_true", help="drop missing empty tick windows")
    sc.set_defaults(func=cmd_schedule_csv_to_json)

    im = sub.add_parser("import-msccl", help="import an MSCCL XML schedule into schedule JSON")
    im.add_argument("xml")
    im.add_argument("--out", required=True)
    im.add_argument("--model", choices=["STRICT1", "READ1_WRITE1"], default="STRICT1")
    im.add_argument("--max-rows", type=int, default=None)
    im.add_argument("--max-file-size", type=int, default=None)
    im.set_defaults(func=cmd_import_msccl)

    it = sub.add_parser("import-taccl", help="import a TACCL JSON schedule into schedule JSON")
    it.add_argument("json")
    it.add_argument("--out", required=True)
    it.add_argument("--model", choices=["STRICT1", "READ1_WRITE1"], default="STRICT1")
    it.add_argument("--max-rows", type=int, default=None)
    it.add_argument("--max-file-size", type=int, default=None)
    it.set_defaults(func=cmd_import_taccl)

    ic = sub.add_parser("import-csv", help="import custom schedule CSV into schedule JSON with explicit column mapping")
    ic.add_argument("--csv", required=True)
    ic.add_argument("--map", action="append", default=[], help="mapping tokens: tick=col src=col dst=col len=col")
    ic.add_argument("--out", required=True)
    ic.add_argument("--model", choices=["STRICT1", "READ1_WRITE1"], default="STRICT1")
    ic.add_argument("--max-rows", type=int, default=None)
    ic.add_argument("--max-file-size", type=int, default=None)
    ic.set_defaults(func=cmd_import_csv)

    inl = sub.add_parser("import-nccl-log", help="import NCCL debug log into demands CSV")
    inl.add_argument("log")
    inl.add_argument("--out", required=True, help="output demands CSV path")
    inl.add_argument("--max-rows", type=int, default=None)
    inl.add_argument("--max-file-size", type=int, default=None)
    inl.set_defaults(func=cmd_import_nccl_log)

    ipt = sub.add_parser("import-pytorch-trace", help="import PyTorch profiler trace JSON into demands CSV")
    ipt.add_argument("trace")
    ipt.add_argument("--out", required=True, help="output demands CSV path")
    ipt.add_argument("--max-rows", type=int, default=None)
    ipt.add_argument("--max-file-size", type=int, default=None)
    ipt.set_defaults(func=cmd_import_pytorch_trace)

    i = sub.add_parser("infer", help="infer bandwidth and slot count from a communication log")
    i.add_argument("log", help="NCCL debug log or PyTorch trace JSON path")
    i.add_argument("--kind", choices=["nccl", "pytorch"], default=None, help="log kind (auto-detect by extension)")
    i.add_argument("--out", default=None, help="output demands CSV path (optional)")
    i.add_argument("--max-rows", type=int, default=None)
    i.add_argument("--max-file-size", type=int, default=None)
    i.set_defaults(func=cmd_infer)

    va = sub.add_parser("validate-artifact", help="validate a generated v0 JSON artifact contract")
    va.add_argument("--kind", choices=["instance", "schedule", "report", "summary"], required=True)
    va.add_argument("path")
    va.set_defaults(func=cmd_validate_artifact)

    g = sub.add_parser("gate", help="apply CI thresholds to summary.json")
    g.add_argument("summary")
    g.add_argument("--config", default=None, help="optional gate config JSON/YAML")
    g.add_argument("--report", choices=["greedy", "baseline", "current", "customer_current"], default=None)
    g.add_argument("--max-gap", type=float, default=None)
    g.add_argument("--max-gap-vs-greedy", type=float, default=None)
    g.add_argument("--min-utilization", type=float, default=None)
    g.add_argument("--max-ticks", type=int, default=None)
    g.set_defaults(func=cmd_gate)

    an = sub.add_parser("anonymize", help="anonymize src_slot/dst_slot in a demands CSV")
    an.add_argument("--csv", required=True)
    an.add_argument("--out", required=True)
    an.add_argument("--mapping", default=None)
    an.add_argument("--mapping-in", default=None, help="optional existing mapping JSON to reuse")
    an.add_argument("--kind", choices=["demands", "schedule"], default="demands")
    an.add_argument("--max-rows", type=int, default=None, help="maximum data rows to process")
    an.add_argument("--max-file-size", type=int, default=None, help="maximum input CSV size in bytes")
    an.add_argument("--max-unique-slots", type=int, default=None, help="maximum number of unique slot IDs to map")
    an.set_defaults(func=cmd_anonymize)

    b = sub.add_parser("bench", help="run a synthetic ring benchmark without writing full schedules")
    b.add_argument("--slots", type=int, default=64)
    b.add_argument("--bits-per-edge", type=int, default=1048576)
    b.add_argument("--bw", type=int, default=1048576)
    b.add_argument("--model", choices=["STRICT1", "READ1_WRITE1"], default="STRICT1")
    b.add_argument("--outdir", default="artifacts/bench")
    b.set_defaults(func=cmd_bench)

    bb = sub.add_parser("bench-bounds", help="benchmark lower-bound algorithms on synthetic STRICT1 instances")
    bb.add_argument("--outdir", default="artifacts/bench-bounds")
    bb.add_argument("--min-slots", type=int, default=32)
    bb.add_argument("--max-slots", type=int, default=256)
    bb.add_argument("--step-slots", type=int, default=32)
    bb.add_argument("--bw", type=int, default=1048576)
    bb.add_argument("--patterns", default="ring,pair-plus-clique", help="comma-separated patterns: ring,pair-plus-clique,ring2")
    bb.add_argument("--bounds-subset-limit", type=int, default=20)
    bb.add_argument("--max-case-seconds", type=float, default=None)
    bb.add_argument("--max-total-seconds", type=float, default=None)
    bb.set_defaults(func=cmd_bench_bounds)

    bs = sub.add_parser("bench-suite", help="run production-oriented synthetic performance smoke suite")
    bs.add_argument("--outdir", default="artifacts/bench-suite")
    bs.add_argument("--max-case-seconds", type=float, default=None)
    bs.add_argument("--max-total-seconds", type=float, default=None)
    bs.set_defaults(func=cmd_bench_suite)

    d = sub.add_parser("doctor", help="check local pilot installation and bundled demo assets")
    d.add_argument("--root", default=".", help="project/client package root to check")
    d.add_argument("--json", action="store_true", help="emit machine-readable check results")
    d.add_argument("--demands", default=None, help="optional demands CSV for applicability diagnostics")
    d.add_argument("--bw", type=int, default=256, help="bandwidth in bits per tick for --demands diagnostics")
    d.add_argument("--slots", type=int, default=None, help="optional slot count override for --demands diagnostics")
    d.add_argument("--model", choices=["STRICT1", "READ1_WRITE1"], default="STRICT1", help="resource model for --demands diagnostics")
    d.set_defaults(func=cmd_doctor)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        return args.func(args)
    except KeyboardInterrupt:
        print("ERROR: interrupted", file=sys.stderr)
        return 130
    except (FileNotFoundError, ValueError, OSError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # pragma: no cover - defensive CLI boundary
        import os
        if os.environ.get("COPYSPACE_GUARD_DEBUG"):
            raise
        print(f"ERROR: unexpected failure: {e}", file=sys.stderr)
        print("Set COPYSPACE_GUARD_DEBUG=1 to show a traceback.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
