from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import (
    compare_reports,
    dump_json,
    instance_from_csv,
    load_json,
    solve_baseline,
    solve_greedy,
    validate_schedule,
)
from .report import write_reports


def cmd_analyze(args: argparse.Namespace) -> int:
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    inst = instance_from_csv(args.csv, bw=args.bw, slots=args.slots, instance_id=args.id, notes=args.notes)
    baseline = solve_baseline(inst)
    greedy = solve_greedy(inst)
    rep_base = validate_schedule(inst, baseline)
    rep_greedy = validate_schedule(inst, greedy)
    comp = compare_reports(rep_base, rep_greedy, args.cost_per_tick)

    dump_json(outdir / "instance.json", inst)
    dump_json(outdir / "schedule_baseline.json", baseline)
    dump_json(outdir / "schedule_greedy.json", greedy)
    dump_json(outdir / "report_baseline.json", rep_base.to_dict())
    dump_json(outdir / "report_greedy.json", rep_greedy.to_dict())
    summary = {
        "instance": inst,
        "reports": {"baseline": rep_base.to_dict(), "greedy": rep_greedy.to_dict()},
        "comparison": comp,
        "artifacts": {
            "instance": "instance.json",
            "schedule_baseline": "schedule_baseline.json",
            "schedule_greedy": "schedule_greedy.json",
            "report_baseline": "report_baseline.json",
            "report_greedy": "report_greedy.json",
            "report_markdown": "report.md",
            "report_html": "report.html",
        },
    }
    dump_json(outdir / "summary.json", summary)
    write_reports(outdir, summary)

    print(f"Copy-Space Guard analysis written to: {outdir}")
    print(f"baseline: status={rep_base.status} ticks={rep_base.ticks_total} lb={rep_base.lower_bound_ticks} gap={rep_base.gap_to_lower_bound:.6f} util={rep_base.utilization:.4f}")
    print(f"greedy:   status={rep_greedy.status} ticks={rep_greedy.ticks_total} lb={rep_greedy.lower_bound_ticks} gap={rep_greedy.gap_to_lower_bound:.6f} util={rep_greedy.utilization:.4f}")
    print(f"saved_ticks={comp['saved_ticks']} estimated_savings={comp['estimated_savings']:.2f}")
    return 0 if rep_base.status == "PASS" and rep_greedy.status == "PASS" else 2


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
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
