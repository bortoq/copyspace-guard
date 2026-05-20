from __future__ import annotations

import argparse
import sys
from pathlib import Path
import time

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


def cmd_analyze(args: argparse.Namespace) -> int:
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    if args.max_errors is not None and args.max_errors < 0:
        raise ValueError("--max-errors must be >= 0")
    if args.bounds_subset_limit < 0:
        raise ValueError("--bounds-subset-limit must be >= 0")
    inst = instance_from_csv(args.csv, bw=args.bw, slots=args.slots, instance_id=args.id, notes=args.notes, model=args.model)
    if args.current_schedule_json and args.current_schedule_csv:
        raise SystemExit("use only one of --current-schedule-json or --current-schedule-csv")
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
            rep_current = validate_schedule(inst, current, max_errors=args.max_errors, bounds_subset_limit=args.bounds_subset_limit)
        elif args.current_schedule_csv:
            current_label = "customer_current"
            rep_current = validate_schedule_csv(inst, args.current_schedule_csv, max_errors=args.max_errors, bounds_subset_limit=args.bounds_subset_limit)
        else:
            current_label = "baseline"
            rep_current = validate_ticks_iter(inst, iter_baseline(inst), max_errors=args.max_errors, bounds_subset_limit=args.bounds_subset_limit)
        rep_greedy = validate_ticks_iter(inst, iter_greedy(inst), max_errors=args.max_errors, bounds_subset_limit=args.bounds_subset_limit)
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
        rep_current = validate_schedule(inst, current, max_errors=args.max_errors, bounds_subset_limit=args.bounds_subset_limit)
        rep_greedy = validate_schedule(inst, greedy, max_errors=args.max_errors, bounds_subset_limit=args.bounds_subset_limit)
    if args.max_output_ticks is not None:
        for label, rep in [(current_label, rep_current), ("greedy", rep_greedy)]:
            if rep.ticks_total > args.max_output_ticks:
                raise ValueError(f"{label} ticks_total {rep.ticks_total} exceeds --max-output-ticks {args.max_output_ticks}")
    roi_config = {}
    if args.roi:
        loaded_roi = load_config(args.roi)
        roi_config = loaded_roi.get("roi", loaded_roi)
    cost_per_tick = args.cost_per_tick if args.cost_per_tick > 0 else roi_cost_per_tick(roi_config)
    comp = compare_reports(rep_current, rep_greedy, cost_per_tick)
    roi_summary = compute_roi(comp, roi_config)

    dump_json(outdir / "instance.json", inst)
    if not args.summary_only:
        assert current is not None
        assert greedy is not None
        dump_json(outdir / f"schedule_{current_label}.json", current)
        write_schedule_csv(outdir / f"schedule_{current_label}.csv", current)
        dump_json(outdir / "schedule_greedy.json", greedy)
        write_schedule_csv(outdir / "schedule_greedy.csv", greedy)
    dump_json(outdir / f"report_{current_label}.json", rep_current.to_dict())
    dump_json(outdir / "report_greedy.json", rep_greedy.to_dict())
    reports = {"greedy": rep_greedy.to_dict(), "current": rep_current.to_dict(), current_label: rep_current.to_dict()}
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
    validate_summary_contract(summary)
    dump_json(outdir / "summary.json", summary)
    write_reports(outdir, summary)

    print(f"Copy-Space Guard analysis written to: {outdir}")
    print(f"{current_label}: status={rep_current.status} ticks={rep_current.ticks_total} lb={rep_current.lower_bound_ticks} gap={rep_current.gap_to_lower_bound:.6f} util={rep_current.utilization:.4f}")
    print(f"greedy:   status={rep_greedy.status} ticks={rep_greedy.ticks_total} lb={rep_greedy.lower_bound_ticks} gap={rep_greedy.gap_to_lower_bound:.6f} util={rep_greedy.utilization:.4f}")
    print(f"saved_ticks={comp['saved_ticks']} estimated_savings={comp['estimated_savings']:.2f}")
    return 0 if rep_current.status == "PASS" and rep_greedy.status == "PASS" else 2


def cmd_validate(args: argparse.Namespace) -> int:
    if args.max_errors is not None and args.max_errors < 0:
        raise ValueError("--max-errors must be >= 0")
    if args.bounds_subset_limit < 0:
        raise ValueError("--bounds-subset-limit must be >= 0")
    inst = load_json(args.instance)
    sched = load_json(args.schedule)
    rep = validate_schedule(inst, sched, max_errors=args.max_errors, bounds_subset_limit=args.bounds_subset_limit)
    if args.report:
        dump_json(args.report, rep.to_dict())
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
    write_reports(args.outdir, summary)
    print(f"reports written to: {args.outdir}")
    return 0


def cmd_schedule_csv_to_json(args: argparse.Namespace) -> int:
    sched = schedule_from_csv(args.csv, fill_empty_ticks=not args.compact_ticks, model=args.model)
    dump_json(args.out, sched)
    print(f"schedule JSON written to: {args.out}")
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
    if args.kind == "schedule":
        mapping = anonymize_schedule_csv(args.csv, args.out, args.mapping, args.mapping_in)
    else:
        mapping = anonymize_demands_csv(args.csv, args.out, args.mapping, args.mapping_in)
    print(f"anonymized CSV written to: {args.out}")
    if args.mapping:
        print(f"mapping written to: {args.mapping}")
    print(f"unique_slots={len(mapping)}")
    return 0


def cmd_bench(args: argparse.Namespace) -> int:
    rows = ["src_slot,dst_slot,bits_total"]
    for i in range(args.slots):
        rows.append(f"{i},{(i + 1) % args.slots},{args.bits_per_edge}")
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    demands = outdir / "bench_demands.csv"
    demands.write_text("\n".join(rows) + "\n", encoding="utf-8")
    t0 = time.perf_counter()
    inst = instance_from_csv(demands, bw=args.bw, model=args.model)
    rep_baseline = validate_ticks_iter(inst, iter_baseline(inst))
    rep_greedy = validate_ticks_iter(inst, iter_greedy(inst))
    elapsed = time.perf_counter() - t0
    result = {
        "slots": args.slots,
        "bits_per_edge": args.bits_per_edge,
        "bw": args.bw,
        "model": args.model,
        "elapsed_seconds": elapsed,
        "baseline": rep_baseline.to_dict(),
        "greedy": rep_greedy.to_dict(),
    }
    dump_json(outdir / "bench.json", result)
    print(f"bench elapsed={elapsed:.6f}s slots={args.slots} model={args.model} baseline_ticks={rep_baseline.ticks_total} greedy_ticks={rep_greedy.ticks_total}")
    return 0 if rep_baseline.status == "PASS" and rep_greedy.status == "PASS" else 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="copyspace-guard", description="Deterministic data-movement audit and CI gate")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="run current/baseline vs deterministic candidate analysis from demands CSV")
    a.add_argument("--csv", required=True, help="CSV with src_slot,dst_slot,bits_total")
    a.add_argument("--bw", type=int, required=True, help="copy bandwidth per tick in bits")
    a.add_argument("--model", choices=["STRICT1", "READ1_WRITE1"], default="STRICT1", help="resource model")
    a.add_argument("--slots", type=int, default=None, help="slot count; inferred if omitted")
    a.add_argument("--id", default="demo-workload")
    a.add_argument("--notes", default=None)
    a.add_argument("--cost-per-tick", type=float, default=0.0, help="optional business estimate in dollars per saved tick")
    a.add_argument("--roi", default=None, help="optional ROI config JSON/YAML")
    a.add_argument("--current-schedule-json", default=None, help="optional customer/current schedule JSON")
    a.add_argument("--current-schedule-csv", default=None, help="optional customer/current schedule CSV: tick,src_slot,dst_slot,len_bits")
    a.add_argument("--summary-only", action="store_true", help="do not write full schedule JSON/CSV artifacts")
    a.add_argument("--bounds-subset-limit", type=int, default=20, help="STRICT1 exhaustive subset-density bound slot limit")
    a.add_argument("--max-errors", type=int, default=None, help="maximum validation errors stored in reports")
    a.add_argument("--max-demands", type=int, default=None, help="fail if normalized demand count exceeds this limit")
    a.add_argument("--max-slots", type=int, default=None, help="fail if slot count exceeds this limit")
    a.add_argument("--max-output-ticks", type=int, default=None, help="fail if any compared report exceeds this tick count")
    a.add_argument("--outdir", default="artifacts/analysis")
    a.set_defaults(func=cmd_analyze)

    v = sub.add_parser("validate", help="validate an existing schedule against an instance")
    v.add_argument("instance")
    v.add_argument("schedule")
    v.add_argument("--report")
    v.add_argument("--bounds-subset-limit", type=int, default=20)
    v.add_argument("--max-errors", type=int, default=None)
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

    va = sub.add_parser("validate-artifact", help="validate a generated v0 JSON artifact contract")
    va.add_argument("--kind", choices=["instance", "schedule", "report", "summary"], required=True)
    va.add_argument("path")
    va.set_defaults(func=cmd_validate_artifact)

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
    an.add_argument("--mapping-in", default=None, help="optional existing mapping JSON to reuse")
    an.add_argument("--kind", choices=["demands", "schedule"], default="demands")
    an.set_defaults(func=cmd_anonymize)

    b = sub.add_parser("bench", help="run a synthetic ring benchmark without writing full schedules")
    b.add_argument("--slots", type=int, default=64)
    b.add_argument("--bits-per-edge", type=int, default=1048576)
    b.add_argument("--bw", type=int, default=1048576)
    b.add_argument("--model", choices=["STRICT1", "READ1_WRITE1"], default="STRICT1")
    b.add_argument("--outdir", default="artifacts/bench")
    b.set_defaults(func=cmd_bench)
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
