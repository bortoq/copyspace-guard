from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from copyspace_guard import cli  # noqa: E402
from copyspace_guard.core import (  # noqa: E402
    Report,
    compare_reports,
    compute_roi,
    exact_optimal_ticks,
    instance_from_csv,
    iter_baseline,
    iter_greedy,
    iter_schedule_csv_ticks,
    load_config,
    read_demands_csv,
    roi_cost_per_tick,
    schedule_from_csv,
    solve_baseline,
    solve_greedy,
    validate_artifact_contract,
    validate_instance,
    validate_report_contract,
    validate_schedule,
    validate_schedule_contract,
    validate_schedule_csv,
    validate_summary_contract,
    validate_ticks_iter,
)
from copyspace_guard.anonymize import anonymize_demands_csv, anonymize_schedule_csv  # noqa: E402
from copyspace_guard.report import bounds_warning_section, metric_table, money, pct, render_html, render_markdown, roi_section  # noqa: E402
import tools.release_artifacts as release_artifacts  # noqa: E402


def run_main(args: list[str]) -> tuple[int, str, str]:
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = cli.main(args)
    return rc, out.getvalue(), err.getvalue()


def tiny_instance(model: str = "STRICT1") -> dict:
    return {
        "version": 0,
        "model": model,
        "slots": 3,
        "copy_bw_bits_per_tick": 2,
        "demands": [
            {"src_slot": 0, "dst_slot": 1, "bits_total": 3},
            {"src_slot": 1, "dst_slot": 2, "bits_total": 2},
        ],
    }


class CliInProcessTests(unittest.TestCase):
    def test_validate_gate_report_and_schedule_conversion_commands(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inst = instance_from_csv(ROOT / "examples" / "ring15.csv", bw=256)
            sched = solve_greedy(inst)
            inst_path = root / "instance.json"
            sched_path = root / "schedule.json"
            report_path = root / "report.json"
            inst_path.write_text(json.dumps(inst), encoding="utf-8")
            sched_path.write_text(json.dumps(sched), encoding="utf-8")

            rc, out, err = run_main(["validate", str(inst_path), str(sched_path), "--report", str(report_path)])
            self.assertEqual(rc, 0, err)
            self.assertIn("PASS", out)
            self.assertTrue(report_path.exists())

            outdir = root / "analysis"
            rc, _out, err = run_main(["analyze", "--csv", str(ROOT / "examples" / "ring15.csv"), "--bw", "256", "--summary-only", "--outdir", str(outdir)])
            self.assertEqual(rc, 0, err)
            rc, out, err = run_main(["gate", str(outdir / "summary.json"), "--report", "greedy", "--max-gap", "0.01"])
            self.assertEqual(rc, 0, err)
            self.assertIn("GATE PASS", out)
            rc, _out, err = run_main(["gate", str(outdir / "summary.json"), "--max-ticks", "1"])
            self.assertEqual(rc, 2)
            self.assertIn("GATE FAIL", err)

            report_out = root / "reports"
            rc, out, err = run_main(["report", str(outdir / "summary.json"), "--outdir", str(report_out)])
            self.assertEqual(rc, 0, err)
            self.assertIn("reports written", out)
            self.assertTrue((report_out / "report.html").exists())

            sched_csv = root / "schedule.csv"
            sched_csv.write_text("tick,src_slot,dst_slot,len_bits\n1,0,1,2\n", encoding="utf-8")
            converted = root / "converted.json"
            rc, out, err = run_main(["schedule-csv-to-json", "--csv", str(sched_csv), "--out", str(converted), "--compact-ticks"])
            self.assertEqual(rc, 0, err)
            self.assertIn("schedule JSON written", out)
            self.assertEqual(len(json.loads(converted.read_text(encoding="utf-8"))["ticks"]), 1)

    def test_analyze_validate_artifact_bench_doctor_and_anonymize_commands(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            outdir = root / "full"
            rc, out, err = run_main(["analyze", "--csv", str(ROOT / "examples" / "ring15.csv"), "--bw", "256", "--roi", str(ROOT / "examples" / "roi.yml"), "--outdir", str(outdir)])
            self.assertEqual(rc, 0, err)
            self.assertIn("Copy-Space Guard analysis written", out)
            self.assertTrue((outdir / "schedule_greedy.csv").exists())

            rc, out, err = run_main(["validate-artifact", "--kind", "summary", str(outdir / "summary.json")])
            self.assertEqual(rc, 0, err)
            self.assertIn("summary artifact is valid", out)

            bench_dir = root / "bench"
            rc, out, err = run_main(["bench", "--slots", "4", "--bits-per-edge", "8", "--bw", "4", "--outdir", str(bench_dir)])
            self.assertEqual(rc, 0, err)
            self.assertIn("bench elapsed", out)

            suite_dir = root / "suite"
            rc, out, err = run_main(["bench-suite", "--outdir", str(suite_dir), "--max-total-seconds", "30"])
            self.assertEqual(rc, 0, err)
            self.assertIn("bench-suite elapsed", out)

            rc, out, err = run_main(["doctor", "--root", str(ROOT), "--json"])
            self.assertEqual(rc, 0, err)
            self.assertEqual(json.loads(out)["status"], "PASS")

            demand_out = root / "anon_demands.csv"
            mapping = root / "mapping.json"
            rc, out, err = run_main(["anonymize", "--kind", "demands", "--csv", str(ROOT / "examples" / "demo_bad_current_demands.csv"), "--out", str(demand_out), "--mapping", str(mapping)])
            self.assertEqual(rc, 0, err)
            self.assertIn("unique_slots", out)

    def test_cli_error_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            rc, _out, err = run_main(["analyze", "--csv", str(ROOT / "examples" / "ring15.csv"), "--bw", "256", "--max-errors", "-1", "--outdir", str(root / "out")])
            self.assertEqual(rc, 1)
            self.assertIn("--max-errors must be >= 0", err)

            with mock.patch("copyspace_guard.cli.cmd_doctor", side_effect=KeyboardInterrupt):
                rc, _out, err = run_main(["doctor"])
            self.assertEqual(rc, 130)
            self.assertIn("interrupted", err)


class IoCsvEdgeTests(unittest.TestCase):
    def test_demands_csv_errors_and_instance_validation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            empty = root / "empty.csv"
            empty.write_text("\n\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "no demands"):
                read_demands_csv(empty)

            bad_header = root / "bad_header.csv"
            bad_header.write_text("src_slot,dst_slot,bits_total\n0,x,1\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "bad CSV row"):
                read_demands_csv(bad_header)

            short = root / "short.csv"
            short.write_text("0,1\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "expected 3 columns"):
                read_demands_csv(short)

            bad_plain = root / "bad_plain.csv"
            bad_plain.write_text("0,one,1\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "bad CSV row"):
                read_demands_csv(bad_plain)

            good = root / "good.csv"
            good.write_text("src_slot,dst_slot,bits_total\n0,1,1\n", encoding="utf-8")
            for kwargs, msg in [
                ({"bw": 0}, "bandwidth"),
                ({"bw": 1, "model": "NOPE"}, "unsupported model"),
                ({"bw": 1, "slots": 0}, "slots"),
            ]:
                with self.assertRaisesRegex(ValueError, msg):
                    instance_from_csv(good, **kwargs)

            for text, msg in [
                ("src_slot,dst_slot,bits_total\n0,3,1\n", "out of bounds"),
                ("src_slot,dst_slot,bits_total\n0,0,1\n", "equals dst"),
                ("src_slot,dst_slot,bits_total\n0,1,0\n", "bits_total"),
            ]:
                p = root / "case.csv"
                p.write_text(text, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, msg):
                    instance_from_csv(p, bw=1, slots=2)

    def test_validate_instance_and_config_errors(self) -> None:
        for obj, msg in [
            (None, "object"),
            ({"version": 1}, "version"),
            ({"version": 0, "model": "BAD"}, "model"),
            ({"version": 0, "model": "STRICT1", "slots": "2", "copy_bw_bits_per_tick": 1, "demands": []}, "slots"),
            ({"version": 0, "model": "STRICT1", "slots": 2, "copy_bw_bits_per_tick": 0, "demands": []}, "copy_bw"),
            ({"version": 0, "model": "STRICT1", "slots": 2, "copy_bw_bits_per_tick": 1, "demands": {}}, "demands"),
            ({"version": 0, "model": "STRICT1", "slots": 2, "copy_bw_bits_per_tick": 1, "demands": [{"src_slot": 0, "dst_slot": 2, "bits_total": 1}]}, "bad demand"),
        ]:
            with self.assertRaisesRegex(ValueError, msg):
                validate_instance(obj)  # type: ignore[arg-type]

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "config.json"
            cfg.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "config JSON"):
                load_config(cfg)
            bad_yaml = root / "bad.yml"
            bad_yaml.write_text("not a mapping line\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "expected key"):
                load_config(bad_yaml)
            empty_key = root / "empty_key.yml"
            empty_key.write_text(": value\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "empty key"):
                load_config(empty_key)

    def test_schedule_csv_streaming_errors_and_no_header(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            empty = root / "empty.csv"
            empty.write_text("\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "no schedule"):
                list(iter_schedule_csv_ticks(empty))

            cases = [
                ("tick,src_slot,dst_slot,len_bits\n0,1,x,1\n", "bad schedule CSV row"),
                ("tick,src_slot,dst_slot,len_bits\n-1,0,1,1\n", "tick must be >= 0"),
                ("tick,src_slot,dst_slot,len_bits\n1,0,1,1\n0,1,2,1\n", "sorted"),
                ("0,1,2\n", "expected 4 columns"),
                ("0,1,x,1\n", "bad schedule CSV row"),
                ("-1,0,1,1\n", "tick must be >= 0"),
                ("1,0,1,1\n0,1,2,1\n", "sorted"),
            ]
            for text, msg in cases:
                p = root / "sched.csv"
                p.write_text(text, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, msg):
                    list(iter_schedule_csv_ticks(p))

            p = root / "compact.csv"
            p.write_text("2,0,1,1\n", encoding="utf-8")
            self.assertEqual(list(iter_schedule_csv_ticks(p, fill_empty_ticks=False)), [[{"src_slot": 0, "dst_slot": 1, "len_bits": 1}]])
            with self.assertRaisesRegex(ValueError, "unsupported model"):
                schedule_from_csv(p, model="BAD")


class ValidatorAndSchemaEdgeTests(unittest.TestCase):
    def test_validate_schedule_structural_errors(self) -> None:
        inst = tiny_instance()
        for sched, msg in [
            (None, "schedule must be an object"),
            ({"version": 1, "model": "STRICT1", "ticks": []}, "version"),
            ({"version": 0, "model": "READ1_WRITE1", "ticks": []}, "model"),
            ({"version": 0, "model": "STRICT1", "ticks": {}}, "ticks"),
        ]:
            rep = validate_schedule(inst, sched)  # type: ignore[arg-type]
            self.assertEqual(rep.status, "FAIL")
            self.assertIn(msg, rep.errors[0]["msg"])

        rep = validate_ticks_iter(inst, ["not-list", [object(), {"src_slot": "x"}]])  # type: ignore[list-item]
        self.assertEqual(rep.status, "FAIL")
        self.assertGreaterEqual(rep.total_errors, 3)
        self.assertTrue({"STRUCT", "COVERAGE"}.issubset({e["kind"] for e in rep.errors}))

    def test_validate_schedule_all_error_kinds(self) -> None:
        inst = {
            "version": 0,
            "model": "READ1_WRITE1",
            "slots": 3,
            "copy_bw_bits_per_tick": 2,
            "demands": [{"src_slot": 0, "dst_slot": 1, "bits_total": 1}],
        }
        sched = {
            "version": 0,
            "model": "READ1_WRITE1",
            "ticks": [[
                {"src_slot": 0, "dst_slot": 1, "len_bits": 1},
                {"src_slot": 0, "dst_slot": 2, "len_bits": 1},
                {"src_slot": 2, "dst_slot": 1, "len_bits": 1},
                {"src_slot": 2, "dst_slot": 2, "len_bits": 0},
                {"src_slot": -1, "dst_slot": 2, "len_bits": 1},
            ], [{"src_slot": 2, "dst_slot": 0, "len_bits": 1}]],
        }
        rep = validate_schedule(inst, sched)
        kinds = {e["kind"] for e in rep.errors}
        self.assertIn("READ1_WRITE1", kinds)
        self.assertIn("STRUCT", kinds)
        self.assertIn("BANDWIDTH", kinds)
        self.assertIn("EXTRAS", kinds)

    def test_validate_schedule_csv_and_bad_instance_fail_reports(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sched.csv"
            p.write_text("tick,src_slot,dst_slot,len_bits\n0,0,1,1\n", encoding="utf-8")
            rep = validate_schedule_csv(tiny_instance(), str(p), fill_empty_ticks=False)
            self.assertEqual(rep.status, "FAIL")
            bad_inst = {"version": 1}
            self.assertEqual(validate_ticks_iter(bad_inst, []).errors[0]["kind"], "INSTANCE")  # type: ignore[arg-type]

    def test_schema_contract_negative_cases(self) -> None:
        with self.assertRaisesRegex(ValueError, "schedule must be an object"):
            validate_schedule_contract(None)
        for obj, msg in [
            ({"version": 1, "model": "STRICT1", "ticks": []}, "version"),
            ({"version": 0, "model": "BAD", "ticks": []}, "model"),
            ({"version": 0, "model": "STRICT1", "ticks": {}}, "ticks"),
            ({"version": 0, "model": "STRICT1", "ticks": [None]}, "ticks\\[0\\]"),
            ({"version": 0, "model": "STRICT1", "ticks": [[None]]}, "object"),
            ({"version": 0, "model": "STRICT1", "ticks": [[{"src_slot": -1, "dst_slot": 0, "len_bits": 1}]]}, "src_slot"),
            ({"version": 0, "model": "STRICT1", "ticks": [[{"src_slot": 0, "dst_slot": 1, "len_bits": 0}]]}, "len_bits"),
        ]:
            with self.assertRaisesRegex(ValueError, msg):
                validate_schedule_contract(obj)

        good = validate_schedule(tiny_instance(), solve_greedy(tiny_instance())).to_dict()
        for obj, msg in [
            ({}, "missing"),
            ({**good, "status": "BAD"}, "status"),
            ({**good, "version": 1}, "version"),
            ({**good, "model": "BAD"}, "model"),
            ({**good, "errors": {}}, "errors"),
            ({**good, "total_errors": -1}, "total_errors"),
            ({**good, "errors_truncated": "no"}, "errors_truncated"),
        ]:
            with self.assertRaisesRegex(ValueError, msg):
                validate_report_contract(obj)

        summary = {
            "instance": tiny_instance(),
            "current_label": "baseline",
            "candidate_label": "greedy",
            "reports": {"baseline": good, "greedy": good},
            "comparison": {"comparable": True, "comparison_note": "OK"},
            "roi": {},
            "artifacts": {},
        }
        with self.assertRaisesRegex(ValueError, "summary.comparison missing"):
            validate_summary_contract(summary)
        summary["comparison"] = {
            "comparable": True,
            "comparison_note": "OK",
            "saved_ticks": 0,
            "saved_ticks_pct": 0.0,
            "gap_reduction_ticks": 0,
            "utilization_delta": 0.0,
            "estimated_savings": 0.0,
            "cost_per_tick": 0.0,
        }
        with self.assertRaisesRegex(ValueError, "summary.artifacts missing"):
            validate_summary_contract(summary)
        with self.assertRaisesRegex(ValueError, "unsupported"):
            validate_artifact_contract("nope", {})


class RoiSolverReportAndReleaseTests(unittest.TestCase):
    def test_roi_cost_and_compare_branches(self) -> None:
        self.assertEqual(roi_cost_per_tick({"cost_per_tick": 7}), 7.0)
        self.assertAlmostEqual(roi_cost_per_tick({"tick_seconds": 2, "gpu_count_blocked": 4, "gpu_hour_cost_usd": 3, "node_count_blocked": 2, "node_hour_cost_usd": 5}), 44 / 3600)

        current = Report(status="FAIL", version=0, model="STRICT1", errors=[{"kind": "x"}], total_errors=1)
        candidate = Report(status="PASS", version=0, model="STRICT1", errors=[], ticks_total=0, gap_ticks=0, utilization=0.0)
        self.assertFalse(compare_reports(current, candidate)["comparable"])

        current = Report(status="PASS", version=0, model="STRICT1", errors=[], ticks_total=0, gap_ticks=0, utilization=0.1)
        candidate = Report(status="PASS", version=0, model="STRICT1", errors=[], ticks_total=0, gap_ticks=-1, utilization=0.2)
        comp = compare_reports(current, candidate, cost_per_tick=5)
        self.assertEqual(comp["saved_ticks_pct"], 0.0)
        self.assertEqual(comp["estimated_savings"], 0)
        self.assertEqual(compute_roi({"comparable": False, "saved_ticks": 9}, {"cost_per_tick": 10})["saved_ticks_per_run"], 0)

    def test_solver_branches_and_exact_limits(self) -> None:
        inst = tiny_instance()
        baseline = solve_baseline(inst)
        self.assertEqual(validate_schedule(inst, baseline).status, "PASS")
        self.assertGreaterEqual(len(list(iter_baseline(inst))), 2)

        rw = tiny_instance("READ1_WRITE1")
        greedy_ticks = list(iter_greedy(rw))
        self.assertEqual(validate_schedule(rw, {"version": 0, "model": "READ1_WRITE1", "ticks": greedy_ticks}).status, "PASS")
        with self.assertRaisesRegex(ValueError, "at most"):
            exact_optimal_ticks(inst, max_chunks=1)
        empty = {**inst, "demands": []}
        self.assertEqual(exact_optimal_ticks(empty), 0)

    def test_report_helper_branches(self) -> None:
        rep = Report(
            status="FAIL",
            version=0,
            model="STRICT1",
            errors=[{"kind": "STRUCT", "msg": "bad", "tick": 0}],
            bounds_complete=False,
            ticks_total=1,
            gap_to_lower_bound=0.0,
            utilization=0.5,
            total_errors=1,
            errors_truncated=True,
        )
        self.assertEqual(pct(0.125), "12.50%")
        self.assertEqual(money(12.5), "$12.50")
        self.assertIn("not comparable", metric_table(rep, rep, {"comparable": False, "comparison_note": "bad"}, "a", "b"))
        self.assertIn("Cost per tick", roi_section({"roi": {"cost_per_tick": 2, "saved_seconds_per_run": 1, "saved_hours_per_run": 1, "savings_per_run_usd": 2, "runs_per_day": 1, "savings_per_month_usd": 3, "savings_per_year_usd": 4}}))
        self.assertIn("Bound completeness", bounds_warning_section(rep, rep))
        html = render_html({
            "instance": tiny_instance(),
            "current_label": "baseline",
            "candidate_label": "greedy",
            "reports": {"baseline": rep.to_dict(), "greedy": rep.to_dict()},
            "comparison": {"comparable": False, "comparison_note": "bad", "saved_ticks": 0, "saved_ticks_pct": 0.0, "gap_reduction_ticks": 0, "utilization_delta": 0.0, "estimated_savings": 0.0, "cost_per_tick": 0.0},
            "roi": {},
            "artifacts": {},
        })
        self.assertIn("<h3>", html)

    def test_render_markdown_escapes_user_controlled_text(self) -> None:
        current = Report(
            status="FAIL",
            version=0,
            model="STRICT1",
            errors=[{"kind": "k<script>", "msg": "bad <b>& value", "path": "a|b"}],
            total_errors=1,
            errors_truncated=False,
        )
        candidate = Report(
            status="PASS",
            version=0,
            model="STRICT1",
            errors=[],
            ticks_total=0,
            gap_to_lower_bound=0.0,
            utilization=0.0,
        )
        summary = {
            "instance": {
                "version": 0,
                "id": "trace <script>&|",
                "model": "STRICT1",
                "slots": 2,
                "copy_bw_bits_per_tick": 1,
                "demands": [],
            },
            "current_label": "cur<script>&|",
            "candidate_label": "cand<script>&|",
            "reports": {"cur<script>&|": current.to_dict(), "cand<script>&|": candidate.to_dict()},
            "comparison": {"comparable": False, "comparison_note": "note <script>&|"},
            "roi": {},
        }
        md = render_markdown(summary)
        self.assertNotIn("<script>", md)
        self.assertIn("&lt;script&gt;", md)
        self.assertIn("&#124;", md)
        self.assertIn("&amp;", md)

    def test_anonymize_header_errors(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bad_demands = root / "bad_demands.csv"
            bad_demands.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "anonymize currently expects"):
                anonymize_demands_csv(bad_demands, root / "out.csv")
            bad_sched = root / "bad_sched.csv"
            bad_sched.write_text("tick,src_slot,dst_slot\n0,a,b\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "schedule anonymize expects"):
                anonymize_schedule_csv(bad_sched, root / "out.csv")

    def test_release_artifact_helpers_and_main(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dist = root / "dist"
            dist.mkdir()
            wheel = dist / "pkg-1.0-py3-none-any.whl"
            wheel.write_text("wheel", encoding="utf-8")
            sdist = dist / "pkg-1.0.tar.gz"
            sdist.write_text("sdist", encoding="utf-8")

            self.assertEqual(len(release_artifacts.sha256(wheel)), 64)
            checksums = release_artifacts.write_checksums(dist, root, [wheel, sdist])
            self.assertIn(wheel.name, checksums.read_text(encoding="utf-8"))
            sbom = release_artifacts.write_sbom(root, "copyspace-guard", "1.0", ["dep>=1"], [wheel])
            sbom_data = json.loads(sbom.read_text(encoding="utf-8"))
            self.assertEqual(sbom_data["bomFormat"], "CycloneDX")
            self.assertEqual(sbom_data["components"][1]["name"], "dep>=1")

            with mock.patch.object(release_artifacts, "ROOT", ROOT):
                project, version, deps = release_artifacts.read_project_metadata()
            self.assertEqual(project, "copyspace-guard")
            self.assertIsInstance(version, str)
            self.assertEqual(deps, [])

            with mock.patch.object(sys, "argv", ["release_artifacts.py", "--dist", str(dist), "--out", str(root)]), mock.patch.object(release_artifacts, "ROOT", ROOT):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    self.assertEqual(release_artifacts.main(), 0)
                self.assertIn("release_manifest.csv", out.getvalue())

            empty = root / "empty_dist"
            empty.mkdir()
            with mock.patch.object(sys, "argv", ["release_artifacts.py", "--dist", str(empty), "--out", str(root)]):
                with self.assertRaises(SystemExit):
                    release_artifacts.main()
