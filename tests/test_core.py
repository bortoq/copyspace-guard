import json
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from copyspace_guard.core import (  # noqa: E402
    MAX_EXHAUSTIVE_SUBSET_LIMIT,
    compute_roi,
    exact_optimal_ticks,
    gate_report,
    instance_from_csv,
    validate_artifact_contract,
    lower_bound_components,
    schedule_from_csv,
    solve_greedy,
    validate_schedule,
    validate_summary_contract,
)
from copyspace_guard.types import Report  # noqa: E402
from copyspace_guard.anonymize import anonymize_demands_csv, anonymize_schedule_csv  # noqa: E402
from copyspace_guard.io import csv_safe_cell, dump_json, iter_schedule_csv_ticks, load_config, load_json, read_demands_csv, write_schedule_csv  # noqa: E402
from copyspace_guard.report import render_html, render_markdown, write_reports  # noqa: E402
from copyspace_guard.schema import validate_report_contract, validate_schedule_contract  # noqa: E402
import tools.release_artifacts as release_artifacts  # noqa: E402


class CoreTests(unittest.TestCase):
    def test_ring15_uses_capacity_lower_bound(self):
        inst = instance_from_csv(ROOT / "examples" / "ring15.csv", bw=256)
        lbs = lower_bound_components(inst)
        self.assertEqual(lbs["degree_lower_bound"], 512)
        self.assertEqual(lbs["capacity_lower_bound"], 549)
        self.assertEqual(lbs["density_lower_bound"], 549)
        self.assertEqual(lbs["lower_bound_ticks"], 549)
        rep = validate_schedule(inst, solve_greedy(inst))
        self.assertEqual(rep.status, "PASS")
        self.assertEqual(rep.lower_bound_ticks, 549)
        self.assertEqual(rep.gap_ticks, 0)
        self.assertEqual(rep.gap_to_lower_bound, 0.0)

    def test_subset_density_lower_bound_triangle(self):
        inst = {
            "version": 0,
            "model": "STRICT1",
            "slots": 3,
            "copy_bw_bits_per_tick": 1,
            "demands": [
                {"src_slot": 0, "dst_slot": 1, "bits_total": 2},
                {"src_slot": 1, "dst_slot": 2, "bits_total": 2},
                {"src_slot": 0, "dst_slot": 2, "bits_total": 2},
            ],
        }
        lbs = lower_bound_components(inst)
        self.assertEqual(lbs["degree_lower_bound"], 4)
        self.assertEqual(lbs["density_lower_bound"], 6)
        self.assertEqual(lbs["lower_bound_ticks"], 6)

    def test_validator_collects_multiple_errors(self):
        inst = {
            "version": 0,
            "model": "STRICT1",
            "slots": 4,
            "copy_bw_bits_per_tick": 10,
            "demands": [
                {"src_slot": 0, "dst_slot": 1, "bits_total": 10},
                {"src_slot": 2, "dst_slot": 3, "bits_total": 10},
            ],
        }
        sched = {"version": 0, "model": "STRICT1", "ticks": [[
            {"src_slot": 0, "dst_slot": 1, "len_bits": 11},
            {"src_slot": 0, "dst_slot": 2, "len_bits": 5},
        ]]}
        rep = validate_schedule(inst, sched)
        self.assertEqual(rep.status, "FAIL")
        self.assertGreater(rep.ticks_total, 0)
        kinds = {e["kind"] for e in rep.errors}
        self.assertIn("BANDWIDTH", kinds)
        self.assertIn("STRICT1", kinds)
        self.assertIn("COVERAGE", kinds)

    def test_schedule_csv_import(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "schedule.csv"
            p.write_text("tick,src_slot,dst_slot,len_bits\n0,0,1,10\n2,2,3,10\n", encoding="utf-8")
            sched = schedule_from_csv(p)
            self.assertEqual(len(sched["ticks"]), 3)
            self.assertEqual(sched["ticks"][1], [])

    def test_gate_and_roi(self):
        inst = instance_from_csv(ROOT / "examples" / "ring15.csv", bw=256)
        rep = validate_schedule(inst, solve_greedy(inst))
        ok, reasons = gate_report(rep, max_gap=0.01, min_utilization=0.9)
        self.assertTrue(ok, reasons)
        ok, _reasons = gate_report(rep, max_gap=-0.1)
        self.assertFalse(ok)
        roi = compute_roi({"comparable": True, "saved_ticks": 219}, {"tick_seconds": 1, "gpu_count_blocked": 64, "gpu_hour_cost_usd": 2.5, "runs_per_day": 12, "days_per_month": 30})
        self.assertAlmostEqual(roi["savings_per_run_usd"], 9.7333333333, places=6)
        self.assertAlmostEqual(roi["savings_per_year_usd"], 42048.0, places=2)


if __name__ == "__main__":
    unittest.main()

class ModelExtensionTests(unittest.TestCase):
    def test_fractional_exact_mode_small_instance(self):
        inst = {
            "version": 0,
            "model": "STRICT1",
            "slots": 5,
            "copy_bw_bits_per_tick": 1,
            "demands": [
                {"src_slot": 0, "dst_slot": 1, "bits_total": 1},
                {"src_slot": 0, "dst_slot": 2, "bits_total": 1},
                {"src_slot": 0, "dst_slot": 3, "bits_total": 1},
                {"src_slot": 0, "dst_slot": 4, "bits_total": 1},
                {"src_slot": 1, "dst_slot": 2, "bits_total": 1},
                {"src_slot": 1, "dst_slot": 3, "bits_total": 1},
                {"src_slot": 1, "dst_slot": 4, "bits_total": 1},
                {"src_slot": 2, "dst_slot": 3, "bits_total": 1},
                {"src_slot": 2, "dst_slot": 4, "bits_total": 1},
                {"src_slot": 3, "dst_slot": 4, "bits_total": 1},
            ],
        }
        lbs = lower_bound_components(inst, strict1_bounds_mode="fractional_exact")
        self.assertEqual(lbs["density_lower_bound"], 5)
        self.assertEqual(lbs["lower_bound_ticks"], 5)
        self.assertEqual(lbs["strict1_bounds_mode"], "fractional_exact")
        self.assertIn(lbs["lower_bound_witness"]["kind"], {"full_graph_capacity", "fractional_exact_odd_subset"})

    def test_fractional_exact_mode_rejects_too_many_slots(self):
        inst = {
            "version": 0,
            "model": "STRICT1",
            "slots": 30,
            "copy_bw_bits_per_tick": 1,
            "demands": [{"src_slot": 0, "dst_slot": 1, "bits_total": 1}],
        }
        with self.assertRaisesRegex(ValueError, "fractional_exact is limited"):
            lower_bound_components(inst, strict1_bounds_mode="fractional_exact")

    def test_large_strict1_bounds_are_deterministic(self):
        demands = []
        for i in range(12):
            demands.append({"src_slot": i, "dst_slot": 28 + i, "bits_total": 13})
        clique = [20, 21, 22, 23, 24]
        for i in range(len(clique)):
            for j in range(i + 1, len(clique)):
                demands.append({"src_slot": clique[i], "dst_slot": clique[j], "bits_total": 3})
        inst = {
            "version": 0,
            "model": "STRICT1",
            "slots": 40,
            "copy_bw_bits_per_tick": 1,
            "demands": demands,
        }
        a = lower_bound_components(inst)
        b = lower_bound_components(inst)
        self.assertEqual(a["lower_bound_ticks"], b["lower_bound_ticks"])
        self.assertEqual(a["density_lower_bound"], b["density_lower_bound"])
        self.assertEqual(a["lower_bound_witness"], b["lower_bound_witness"])

    def test_read1_write1_allows_send_and_receive_same_tick(self):
        inst = {
            "version": 0,
            "model": "READ1_WRITE1",
            "slots": 3,
            "copy_bw_bits_per_tick": 1,
            "demands": [
                {"src_slot": 0, "dst_slot": 1, "bits_total": 1},
                {"src_slot": 1, "dst_slot": 2, "bits_total": 1},
            ],
        }
        sched = {"version": 0, "model": "READ1_WRITE1", "ticks": [[
            {"src_slot": 0, "dst_slot": 1, "len_bits": 1},
            {"src_slot": 1, "dst_slot": 2, "len_bits": 1},
        ]]}
        rep = validate_schedule(inst, sched)
        self.assertEqual(rep.status, "PASS", rep.errors)
        self.assertEqual(rep.ticks_total, 1)
        self.assertEqual(rep.model, "READ1_WRITE1")

    def test_bounds_incomplete_for_large_strict1(self):
        inst = {
            "version": 0,
            "model": "STRICT1",
            "slots": 21,
            "copy_bw_bits_per_tick": 1,
            "demands": [{"src_slot": 0, "dst_slot": 1, "bits_total": 1}],
        }
        lbs = lower_bound_components(inst)
        self.assertFalse(lbs["bounds_complete"])
        self.assertIn(
            lbs["lower_bound_witness"]["kind"],
            {"full_graph_capacity", "subset_density_heuristic"},
        )

    def test_bounds_limit_has_hard_cap(self):
        inst = {
            "version": 0,
            "model": "STRICT1",
            "slots": 2,
            "copy_bw_bits_per_tick": 1,
            "demands": [{"src_slot": 0, "dst_slot": 1, "bits_total": 1}],
        }
        with self.assertRaisesRegex(ValueError, "hard cap"):
            lower_bound_components(inst, exhaustive_subset_limit=MAX_EXHAUSTIVE_SUBSET_LIMIT + 1)

    def test_gate_warns_when_bounds_incomplete_and_max_gap_set(self):
        rep = Report(
            status="PASS",
            version=0,
            model="STRICT1",
            errors=[],
            ticks_total=10,
            bits_total=10,
            bits_per_tick=1.0,
            expected_bits_per_tick=1,
            utilization=1.0,
            degree_lower_bound=8,
            capacity_lower_bound=8,
            density_lower_bound=8,
            lower_bound_ticks=8,
            gap_ticks=2,
            gap_to_lower_bound=0.25,
            bounds_complete=False,
            total_errors=0,
            errors_truncated=False,
        )
        ok, reasons = gate_report(rep, max_gap=0.5)
        self.assertFalse(ok)
        self.assertTrue(any("bounds_complete=false" in r for r in reasons))

    def test_fractional_relaxation_improves_large_strict1_bound(self):
        demands = []
        # 12 disjoint heavy pairs with degree 13 (dominate top-degree seeds).
        for i in range(12):
            demands.append({"src_slot": i, "dst_slot": 28 + i, "bits_total": 13})
        # Hidden odd dense subset K5 with chunk weight 3 on each edge -> odd-set LB 15.
        clique = [20, 21, 22, 23, 24]
        for i in range(len(clique)):
            for j in range(i + 1, len(clique)):
                demands.append({"src_slot": clique[i], "dst_slot": clique[j], "bits_total": 3})
        inst = {
            "version": 0,
            "model": "STRICT1",
            "slots": 40,
            "copy_bw_bits_per_tick": 1,
            "demands": demands,
        }
        lbs = lower_bound_components(inst)
        self.assertFalse(lbs["bounds_complete"])
        self.assertGreaterEqual(lbs["lower_bound_ticks"], 15)
        self.assertIn(
            lbs["lower_bound_witness"]["kind"],
            {"subset_density_heuristic", "fractional_relaxation_odd_subset", "lp_relaxation_core_odd_subset"},
        )

    def test_lp_core_relaxation_witness_is_available_for_large_strict1(self):
        demands = []
        # Keep several higher-degree distractors first in ranking.
        for i in range(9):
            demands.append({"src_slot": i, "dst_slot": 30 + i, "bits_total": 14})
        # Dense odd core subset that should be picked up by core LP scan.
        core = [20, 21, 22, 23, 24]
        for i in range(len(core)):
            for j in range(i + 1, len(core)):
                demands.append({"src_slot": core[i], "dst_slot": core[j], "bits_total": 4})
        inst = {
            "version": 0,
            "model": "STRICT1",
            "slots": 42,
            "copy_bw_bits_per_tick": 1,
            "demands": demands,
        }
        lbs = lower_bound_components(inst)
        self.assertFalse(lbs["bounds_complete"])
        self.assertGreaterEqual(lbs["lower_bound_ticks"], 20)
        self.assertIn(
            lbs["lower_bound_witness"]["kind"],
            {"subset_density_heuristic", "fractional_relaxation_odd_subset", "lp_relaxation_core_odd_subset"},
        )

    def test_exact_optimal_ticks_small_oracle(self):
        inst = {
            "version": 0,
            "model": "STRICT1",
            "slots": 3,
            "copy_bw_bits_per_tick": 1,
            "demands": [
                {"src_slot": 0, "dst_slot": 1, "bits_total": 1},
                {"src_slot": 1, "dst_slot": 2, "bits_total": 1},
                {"src_slot": 0, "dst_slot": 2, "bits_total": 1},
            ],
        }
        self.assertEqual(exact_optimal_ticks(inst), 3)

    def test_validator_truncates_stored_errors(self):
        inst = {
            "version": 0,
            "model": "STRICT1",
            "slots": 3,
            "copy_bw_bits_per_tick": 1,
            "demands": [{"src_slot": 0, "dst_slot": 1, "bits_total": 1}],
        }
        sched = {"version": 0, "model": "STRICT1", "ticks": [[
            {"src_slot": 0, "dst_slot": 1, "len_bits": 2},
            {"src_slot": 0, "dst_slot": 2, "len_bits": 2},
        ]]}
        rep = validate_schedule(inst, sched, max_errors=1)
        self.assertEqual(rep.status, "FAIL")
        self.assertGreater(rep.total_errors, 1)
        self.assertEqual(len(rep.errors), 1)
        self.assertTrue(rep.errors_truncated)

class SchemaFilesTests(unittest.TestCase):
    def test_schema_files_are_valid_json(self):
        for name in ["instance_v0.schema.json", "report_v0.schema.json", "schedule_v0.schema.json", "summary_v0.schema.json"]:
            data = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
            self.assertIn("$schema", data)
            self.assertIn("title", data)

    def test_generated_artifacts_validate_against_json_schemas_when_available(self):
        try:
            from jsonschema import Draft202012Validator
        except Exception:
            self.skipTest("jsonschema is not installed")

        inst = instance_from_csv(ROOT / "examples" / "ring15.csv", bw=256)
        sched = solve_greedy(inst)
        rep = validate_schedule(inst, sched)
        summary = {
            "instance": inst,
            "current_label": "baseline",
            "candidate_label": "greedy",
            "reports": {"baseline": rep.to_dict(), "greedy": rep.to_dict()},
            "comparison": {
                "comparable": True,
                "comparison_note": "OK",
                "saved_ticks": 0,
                "saved_ticks_pct": 0.0,
                "gap_reduction_ticks": 0,
                "utilization_delta": 0.0,
                "estimated_savings": 0.0,
                "cost_per_tick": 0.0,
            },
            "roi": compute_roi({"comparable": True, "saved_ticks": 0}, {}),
            "artifacts": {
                "instance": "instance.json",
                "schedule_current": "schedule_baseline.json",
                "schedule_current_csv": "schedule_baseline.csv",
                "schedule_greedy": "schedule_greedy.json",
                "schedule_greedy_csv": "schedule_greedy.csv",
                "report_current": "report_baseline.json",
                "report_greedy": "report_greedy.json",
                "report_markdown": "report.md",
                "report_html": "report.html",
            },
        }
        cases = [
            ("instance_v0.schema.json", inst),
            ("report_v0.schema.json", rep.to_dict()),
            ("schedule_v0.schema.json", sched),
            ("summary_v0.schema.json", summary),
        ]
        for schema_name, obj in cases:
            schema = json.loads((ROOT / "schemas" / schema_name).read_text(encoding="utf-8"))
            Draft202012Validator(schema).validate(obj)


class IoAndContractTests(unittest.TestCase):
    def test_csv_safe_cell_escapes_spreadsheet_formula_prefixes(self):
        for value in ["=cmd", "+cmd", "-cmd", "@cmd", "\tcmd", "\rcmd", "\ncmd"]:
            self.assertEqual(csv_safe_cell(value), "'" + value)
        self.assertEqual(csv_safe_cell("safe"), "safe")
        self.assertEqual(csv_safe_cell(123), 123)

    def test_json_config_and_csv_helpers(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            json_path = root / "obj.json"
            dump_json(json_path, {"b": 2, "a": 1})
            self.assertEqual(load_json(json_path), {"a": 1, "b": 2})

            cfg = root / "config.yml"
            cfg.write_text(
                "roi:\n"
                "  tick_seconds: 1\n"
                "  enabled: true\n"
                "  note: 'pilot'\n"
                "  nothing: null\n",
                encoding="utf-8",
            )
            self.assertEqual(load_config(cfg)["roi"]["note"], "pilot")
            self.assertIsNone(load_config(cfg)["roi"]["nothing"])

            no_header = root / "demands.csv"
            no_header.write_text("0,1,5\n\n1,2,7\n", encoding="utf-8")
            self.assertEqual(read_demands_csv(no_header), [(0, 1, 5), (1, 2, 7)])

            quoted = root / "quoted.csv"
            quoted.write_text('src_slot,dst_slot,bits_total,note\n"0","1","5","contains src_slot text"\n', encoding="utf-8")
            self.assertEqual(read_demands_csv(quoted), [(0, 1, 5)])

            leading_blank = root / "leading_blank_schedule.csv"
            leading_blank.write_text("\n\ntick,src_slot,dst_slot,len_bits\n0,0,1,5\n", encoding="utf-8")
            self.assertEqual(list(iter_schedule_csv_ticks(leading_blank)), [[{"src_slot": 0, "dst_slot": 1, "len_bits": 5}]])

            sched = {"version": 0, "model": "STRICT1", "ticks": [[{"src_slot": 0, "dst_slot": 1, "len_bits": 5}], [], [{"src_slot": 1, "dst_slot": 2, "len_bits": 7}]]}
            sched_path = root / "schedule.csv"
            write_schedule_csv(sched_path, sched)
            self.assertEqual(schedule_from_csv(sched_path), sched)
            self.assertEqual(len(list(iter_schedule_csv_ticks(sched_path, fill_empty_ticks=False))), 2)

    def test_contract_validators_accept_and_reject_artifacts(self):
        inst = instance_from_csv(ROOT / "examples" / "ring15.csv", bw=256)
        sched = solve_greedy(inst)
        rep = validate_schedule(inst, sched)
        validate_artifact_contract("instance", inst)
        validate_schedule_contract(sched)
        validate_report_contract(rep.to_dict())

        summary = {
            "instance": inst,
            "current_label": "baseline",
            "candidate_label": "greedy",
            "reports": {"baseline": rep.to_dict(), "greedy": rep.to_dict()},
            "comparison": {
                "comparable": True,
                "comparison_note": "ok",
                "saved_ticks": 0,
                "saved_ticks_pct": 0.0,
                "gap_reduction_ticks": 0,
                "utilization_delta": 0.0,
                "estimated_savings": None,
                "cost_per_tick": None,
            },
            "roi": {},
            "artifacts": {
                "instance": "instance.json",
                "schedule_current": "schedule_baseline.json",
                "schedule_current_csv": "schedule_baseline.csv",
                "schedule_greedy": "schedule_greedy.json",
                "schedule_greedy_csv": "schedule_greedy.csv",
                "report_current": "report_baseline.json",
                "report_greedy": "report_greedy.json",
                "report_markdown": "report.md",
                "report_html": "report.html",
            },
        }
        validate_summary_contract(summary)
        with self.assertRaisesRegex(ValueError, "candidate_label"):
            broken = dict(summary)
            broken["candidate_label"] = "missing"
            validate_summary_contract(broken)
        with self.assertRaisesRegex(ValueError, "unsupported"):
            validate_artifact_contract("bogus", {})


class AnonymizeTests(unittest.TestCase):
    def test_anonymize_helpers_reuse_and_validate_mapping(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            demands = root / "demands.csv"
            demands.write_text('src_slot,dst_slot,bits_total,tag\nrack-a,rack-b,10,"=SUM(1,1)"\nrack-b,rack-c,20,+cmd\n', encoding="utf-8")
            mapping = root / "mapping.json"
            demand_out = root / "anon_demands.csv"
            out_map = anonymize_demands_csv(demands, demand_out, mapping)
            self.assertEqual(out_map, {"rack-a": 0, "rack-b": 1, "rack-c": 2})
            with demand_out.open("r", encoding="utf-8", newline="") as f:
                demand_rows = list(csv.DictReader(f))
            self.assertEqual(demand_rows[0]["tag"], "'=SUM(1,1)")
            self.assertEqual(demand_rows[1]["tag"], "'+cmd")

            schedule = root / "schedule.csv"
            schedule.write_text("tick,src_slot,dst_slot,len_bits,note\n0,rack-c,rack-a,10,@note\n", encoding="utf-8")
            sched_out = root / "anon_schedule.csv"
            reused = anonymize_schedule_csv(schedule, sched_out, mapping, mapping_in=mapping)
            self.assertEqual(reused, out_map)
            self.assertIn("2,0", sched_out.read_text(encoding="utf-8"))
            with sched_out.open("r", encoding="utf-8", newline="") as f:
                sched_rows = list(csv.DictReader(f))
            self.assertEqual(sched_rows[0]["note"], "'@note")

            bad_mapping = root / "bad_mapping.json"
            bad_mapping.write_text('{"rack-a": -1}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "mapping input"):
                anonymize_demands_csv(demands, root / "bad.csv", mapping_in=bad_mapping)

    def test_anonymize_unique_slot_limit_is_enforced(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            demands = root / "demands.csv"
            demands.write_text("src_slot,dst_slot,bits_total\nrack-a,rack-b,10\nrack-b,rack-c,20\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "max-unique-slots"):
                anonymize_demands_csv(demands, root / "anon.csv", max_unique_slots=2)


class ReleaseArtifactTests(unittest.TestCase):
    def test_release_manifest_escapes_formula_like_cells(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dist = root / "dist"
            dist.mkdir()
            bad = dist / "=evil.tar.gz"
            bad.write_text("x", encoding="utf-8")
            manifest = release_artifacts.write_manifest(root, "=proj", "=1.0", [bad])
            with manifest.open("r", encoding="utf-8", newline="") as f:
                rows = list(csv.reader(f))
            self.assertEqual(rows[1][0], "'=proj")
            self.assertEqual(rows[1][1], "'=1.0")
            self.assertEqual(rows[1][2], "'=evil.tar.gz")


class ReportRenderingTests(unittest.TestCase):
    def test_markdown_report_includes_grouped_diagnostics(self):
        inst = {
            "version": 0,
            "model": "STRICT1",
            "slots": 2,
            "copy_bw_bits_per_tick": 1,
            "demands": [{"src_slot": 0, "dst_slot": 1, "bits_total": 1}],
        }
        bad = {"version": 0, "model": "STRICT1", "ticks": [[{"src_slot": 0, "dst_slot": 1, "len_bits": 2}]]}
        current = validate_schedule(inst, bad)
        candidate = validate_schedule(inst, solve_greedy(inst))
        summary = {
            "instance": inst,
            "current_label": "customer_current",
            "candidate_label": "greedy",
            "reports": {"customer_current": current.to_dict(), "greedy": candidate.to_dict()},
            "comparison": {
                "comparable": False,
                "comparison_note": "validation failed",
                "saved_ticks": 0,
                "saved_ticks_pct": 0.0,
                "gap_reduction_ticks": 0,
                "utilization_delta": 0.0,
                "estimated_savings": 0.0,
                "cost_per_tick": 0.0,
            },
            "roi": {},
            "artifacts": {},
        }
        md = render_markdown(summary)
        self.assertIn("Validation diagnostics", md)
        self.assertIn("BANDWIDTH", md)

    def test_html_report_renders_inline_markup_and_files(self):
        inst = instance_from_csv(ROOT / "examples" / "ring15.csv", bw=256)
        rep = validate_schedule(inst, solve_greedy(inst))
        summary = {
            "instance": inst,
            "current_label": "baseline",
            "candidate_label": "greedy",
            "reports": {"baseline": rep.to_dict(), "greedy": rep.to_dict()},
            "comparison": {
                "comparable": True,
                "comparison_note": "OK",
                "saved_ticks": 0,
                "saved_ticks_pct": 0.0,
                "gap_reduction_ticks": 0,
                "utilization_delta": 0.0,
                "estimated_savings": 0.0,
                "cost_per_tick": 0.0,
            },
            "roi": compute_roi({"comparable": True, "saved_ticks": 0}, {}),
            "artifacts": {},
        }
        html = render_html(summary)
        self.assertIn("<code>baseline</code>", html)
        self.assertIn("<ol>", html)
        with tempfile.TemporaryDirectory() as td:
            write_reports(td, summary)
            self.assertTrue((Path(td) / "report.md").exists())
            self.assertTrue((Path(td) / "report.html").exists())
