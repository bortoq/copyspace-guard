from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import (
    anonymize_demands_csv,
    compare_reports,
    compute_roi,
    dump_json,
    gate_report,
    instance_from_csv,
    load_config,
    load_json,
    schedule_from_csv,
    solve_baseline,
    solve_greedy,
    roi_cost_per_tick,
    validate_schedule,
    write_schedule_csv,
)
from .report import write_reports


def cmd_analyze(args: argparse.Namespace) -> int:
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    inst = instance_from_csv(args.csv, bw=args.bw, slots=args.slots, instance_id=args.id, notes=args.notes)
    if args.current_schedule_json and args.current_schedule_csv:
        raise SystemExit("use only one of --current-schedule-json or --current-schedule-csv")

    if args.current_schedule_json:
        current = load_json(args.current_schedule_json)
        current_label = "customer_current"
    elif args.current_schedule_csv:
        current = schedule_from_csv(args.current_schedule_csv)
        current_label = "customer_current"
    else:
        current = solve_baseline(inst)
        current_label = "baseline"

    greedy = solve_greedy(inst)
    rep_current = validate_schedule(inst, current)
    rep_greedy = validate_schedule(inst, greedy)
    roi_config = {}
    if args.roi:
        loaded_roi = load_config(args.roi)
        roi_config = loaded_roi.get("roi", loaded_roi)
    cost_per_tick = args.cost_per_tick if args.cost_per_tick > 0 else roi_cost_per_tick(roi_config)
    comp = compare_reports(rep_current, rep_greedy, cost_per_tick)
    roi_summary = compute_roi(comp, roi_config)

    dump_json(outdir / "instance.json", inst)
    dump_json(outdir / f"schedule_{current_label}.json", current)
    write_schedule_csv(outdir / f"schedule_{current_label}.csv", current)
    dump_json(outdir / "schedule_greedy.json", greedy)
    write_schedule_csv(outdir / "schedule_greedy.csv", greedy)
    dump_json(outdir / f"report_{current_label}.json", rep_current.to_dict())
    dump_json(outdir / "report_greedy.json", rep_greedy.to_dict())
    summary = {
        "instance": inst,
        "current_label": current_label,
        "candidate_label": "greedy",
        "reports": {"baseline": rep_current.to_dict(), "greedy": rep_greedy.to_dict(), current_label: rep_current.to_dict()},
        "comparison": comp,
        "roi": roi_summary,
        "artifacts": {
            "instance": "instance.json",
            "schedule_current": f"schedule_{current_label}.json",
            "schedule_current_csv": f"schedule_{current_label}.csv",
            "schedule_greedy": "schedule_greedy.json",
            "schedule_greedy_csv": "schedule_greedy.csv",
            "report_current": f"report_{current_label}.json",
            "report_greedy": "report_greedy.json",
            "report_markdown": "report.md",
            "report_html": "report.html",
        },
    }
    dump_json(outdir / "summary.json", summary)
    write_reports(outdir, summary)

    print(f"Copy-Space Guard analysis written to: {outdir}")
    print(f"{current_label}: status={rep_current.status} ticks={rep_current.ticks_total} lb={rep_current.lower_bound_ticks} gap={rep_current.gap_to_lower_bound:.6f} util={rep_current.utilization:.4f}")
    print(f"greedy:   status={rep_greedy.status} ticks={rep_greedy.ticks_total} lb={rep_greedy.lower_bound_ticks} gap={rep_greedy.gap_to_lower_bound:.6f} util={rep_greedy.utilization:.4f}")
    print(f"saved_ticks={comp['saved_ticks']} estimated_savings={comp['estimated_savings']:.2f}")
    return 0 if rep_current.status == "PASS" and rep_greedy.status == "PASS" else 2


def cmd_validate(args: argparse.Namespace) -> int:
    inst = load_json(args.instance)
    sched = load_json(args.schedule)
    rep = validate_schedule(inst, sched)
    if args.report:
        dump_json(args.report, rep.to_dict())
    print(rep.status)
    if rep.status != "PASS":
        print(rep.errors[0], file=sys.stderr)
        return 2
    print(f"ticks={rep.ticks_total} lb={rep.lower_bound_ticks} gap={rep.gap_to_lower_bound:.6f} util={rep.utilization:.4f}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    summary = load_json(args.summary)
    write_reports(args.outdir, summary)
    print(f"reports written to: {args.outdir}")
    return 0


def cmd_schedule_csv_to_json(args: argparse.Namespace) -> int:
    sched = schedule_from_csv(args.csv, fill_empty_ticks=not args.compact_ticks)
    dump_json(args.out, sched)
    print(f"schedule JSON written to: {args.out}")
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
    min_util = args.min_utilization if args.min_utilization is not None else cfg.get("min_utilization")
    max_ticks = args.max_ticks if args.max_ticks is not None else cfg.get("max_ticks")
    ok, reasons = gate_report(
        rep,
        max_gap=float(max_gap) if max_gap is not None else None,
        min_utilization=float(min_util) if min_util is not None else None,
        max_ticks=int(max_ticks) if max_ticks is not None else None,
    )
    if ok:
        print(f"GATE PASS report={report_name} ticks={rep.ticks_total} gap={rep.gap_to_lower_bound:.6f} util={rep.utilization:.4f}")
        return 0
    print(f"GATE FAIL report={report_name}", file=sys.stderr)
    for r in reasons:
        print(f"- {r}", file=sys.stderr)
    return 2


def cmd_anonymize(args: argparse.Namespace) -> int:
    mapping = anonymize_demands_csv(args.csv, args.out, args.mapping)
    print(f"anonymized CSV written to: {args.out}")
    if args.mapping:
        print(f"mapping written to: {args.mapping}")
    print(f"unique_slots={len(mapping)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="copyspace-guard", description="Deterministic data-movement audit MVP")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="run baseline vs optimized analysis from demands CSV")
    a.add_argument("--csv", required=True, help="CSV with src_slot,dst_slot,bits_total")
    a.add_argument("--bw", type=int, required=True, help="copy bandwidth per tick in bits")
    a.add_argument("--slots", type=int, default=None, help="slot count; inferred if omitted")
    a.add_argument("--id", default="demo-workload")
    a.add_argument("--notes", default=None)
    a.add_argument("--cost-per-tick", type=float, default=0.0, help="optional business estimate in dollars per saved tick")
    a.add_argument("--roi", default=None, help="optional ROI config JSON/YAML")
    a.add_argument("--current-schedule-json", default=None, help="optional customer/current schedule JSON")
    a.add_argument("--current-schedule-csv", default=None, help="optional customer/current schedule CSV: tick,src_slot,dst_slot,len_bits")
    a.add_argument("--outdir", default="artifacts/analysis")
    a.set_defaults(func=cmd_analyze)

    v = sub.add_parser("validate", help="validate an existing schedule against an instance")
    v.add_argument("instance")
    v.add_argument("schedule")
    v.add_argument("--report")
    v.set_defaults(func=cmd_validate)

    r = sub.add_parser("report", help="regenerate markdown/html reports from summary.json")
    r.add_argument("summary")
    r.add_argument("--outdir", default="artifacts/report")
    r.set_defaults(func=cmd_report)

    sc = sub.add_parser("schedule-csv-to-json", help="convert schedule CSV tick,src_slot,dst_slot,len_bits to JSON")
    sc.add_argument("--csv", required=True)
    sc.add_argument("--out", required=True)
    sc.add_argument("--compact-ticks", action="store_true", help="drop missing empty tick windows")
    sc.set_defaults(func=cmd_schedule_csv_to_json)

    g = sub.add_parser("gate", help="apply CI thresholds to summary.json")
    g.add_argument("summary")
    g.add_argument("--config", default=None, help="optional gate config JSON/YAML")
    g.add_argument("--report", choices=["greedy", "baseline", "current", "customer_current"], default=None)
    g.add_argument("--max-gap", type=float, default=None)
    g.add_argument("--min-utilization", type=float, default=None)
    g.add_argument("--max-ticks", type=int, default=None)
    g.set_defaults(func=cmd_gate)

    an = sub.add_parser("anonymize", help="anonymize src_slot/dst_slot in a demands CSV")
    an.add_argument("--csv", required=True)
    an.add_argument("--out", required=True)
    an.add_argument("--mapping", default=None)
    an.set_defaults(func=cmd_anonymize)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
