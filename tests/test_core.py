import argparse
import json
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from copyspace_guard.cli import _load_roi_config_and_compute  # noqa: E402
from copyspace_guard.core import (  # noqa: E402
    BOUNDS_REASON_AUTO_EXHAUSTIVE,
    BOUNDS_REASON_AUTO_PARTIAL,
    BOUNDS_REASON_FRACTIONAL_ODD_SUBSET,
    BOUNDS_REASON_FRACTIONAL_HEURISTIC_PARTIAL,
    BOUNDS_REASON_READ1_WRITE1_COMPLETE,
    MAX_EXHAUSTIVE_SUBSET_LIMIT,
    compare_reports,
    compute_roi,
    exact_optimal_ticks,
    gate_report,
    instance_from_csv,
    validate_artifact_contract,
    lower_bound_components,
    schedule_from_csv,
    solve_baseline,
    solve_greedy,
    validate_schedule,
    validate_summary_contract,
)
from copyspace_guard.types import Report  # noqa: E402
from copyspace_guard.anonymize import anonymize_demands_csv, anonymize_schedule_csv  # noqa: E402
from copyspace_guard.io import csv_safe_cell, dump_json, iter_schedule_csv_ticks, load_config, load_json, read_demands_csv, write_schedule_csv  # noqa: E402
from copyspace_guard.report import _inline_html, render_html, render_markdown, write_reports  # noqa: E402
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
        self.assertIn("EXTRAS", kinds)
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

    def test_ring15_saved_ticks(self):
        # ring15 with bw=256: 15 nodes in a ring, each edge = 65536 bits
        # baseline = 768 ticks (serial), greedy = 549 ticks (parallel matchings)
        # saved_ticks = 768 - 549 = 219
        inst = instance_from_csv(ROOT / "examples" / "ring15.csv", bw=256)
        baseline = solve_baseline(inst)
        greedy = solve_greedy(inst)
        rep_b = validate_schedule(inst, baseline)
        rep_g = validate_schedule(inst, greedy)
        comp = compare_reports(rep_b, rep_g)
        self.assertEqual(comp["saved_ticks"], 219)

    def test_industry_demo_greedy_is_valid(self):
        # bw values match the documented --bw in README Industry demos section
        for name, bw, slots in [
            ("gpt2_ddp_allreduce", 25_000_000_000, 8),
            ("kv_cache_disagg", 50_000_000_000, 8),
        ]:
            inst = instance_from_csv(ROOT / "examples" / name / "demands.csv", bw=bw, slots=slots)
            greedy = solve_greedy(inst)
            rep = validate_schedule(inst, greedy)
            self.assertEqual(rep.status, "PASS", f"{name} greedy should be valid")


if __name__ == "__main__":
    unittest.main()

class ModelExtensionTests(unittest.TestCase):
    def test_fractional_odd_subset_mode_small_instance(self):
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
        lbs = lower_bound_components(inst, strict1_bounds_mode="fractional_odd_subset")
        self.assertEqual(lbs["density_lower_bound"], 5)
        self.assertEqual(lbs["lower_bound_ticks"], 5)
        self.assertEqual(lbs["strict1_bounds_mode"], "fractional_odd_subset")
        self.assertIn(lbs["lower_bound_witness"]["kind"], {"full_graph_capacity", "fractional_odd_subset"})

    def test_fractional_odd_subset_mode_rejects_too_many_slots(self):
        inst = {
            "version": 0,
            "model": "STRICT1",
            "slots": 30,
            "copy_bw_bits_per_tick": 1,
            "demands": [{"src_slot": 0, "dst_slot": 1, "bits_total": 1}],
        }
        with self.assertRaisesRegex(ValueError, "fractional_odd_subset is limited"):
            lower_bound_components(inst, strict1_bounds_mode="fractional_odd_subset")

    def test_fractional_odd_subset_lb_does_not_exceed_exact_optimal(self):
        inst = {
            "version": 0,
            "model": "STRICT1",
            "slots": 6,
            "copy_bw_bits_per_tick": 1,
            "demands": [
                {"src_slot": 0, "dst_slot": 1, "bits_total": 1},
                {"src_slot": 0, "dst_slot": 2, "bits_total": 1},
                {"src_slot": 1, "dst_slot": 3, "bits_total": 1},
                {"src_slot": 2, "dst_slot": 4, "bits_total": 1},
                {"src_slot": 3, "dst_slot": 5, "bits_total": 1},
                {"src_slot": 4, "dst_slot": 5, "bits_total": 1},
            ],
        }
        lbs = lower_bound_components(inst, strict1_bounds_mode="fractional_odd_subset")
        opt = exact_optimal_ticks(inst)
        self.assertLessEqual(lbs["lower_bound_ticks"], opt)

    def test_fractional_odd_subset_ge_auto(self):
        inst = {
            "version": 0,
            "model": "STRICT1",
            "slots": 8,
            "copy_bw_bits_per_tick": 1,
            "demands": [
                {"src_slot": 0, "dst_slot": 1, "bits_total": 1},
                {"src_slot": 0, "dst_slot": 2, "bits_total": 1},
                {"src_slot": 1, "dst_slot": 3, "bits_total": 1},
                {"src_slot": 2, "dst_slot": 3, "bits_total": 1},
                {"src_slot": 4, "dst_slot": 5, "bits_total": 1},
                {"src_slot": 5, "dst_slot": 6, "bits_total": 1},
                {"src_slot": 6, "dst_slot": 7, "bits_total": 1},
            ],
        }
        lbs_auto = lower_bound_components(inst, strict1_bounds_mode="auto")
        lbs_frac = lower_bound_components(inst, strict1_bounds_mode="fractional_odd_subset")
        self.assertGreaterEqual(lbs_frac["density_lower_bound"], lbs_auto["density_lower_bound"])

    def test_invalid_strict1_bounds_mode_rejected(self):
        inst = {
            "version": 0,
            "model": "STRICT1",
            "slots": 2,
            "copy_bw_bits_per_tick": 1,
            "demands": [{"src_slot": 0, "dst_slot": 1, "bits_total": 1}],
        }
        with self.assertRaisesRegex(ValueError, "unsupported strict1_bounds_mode"):
            lower_bound_components(inst, strict1_bounds_mode="invalid")

    def test_fractional_heuristic_mode_available(self):
        inst = {
            "version": 0,
            "model": "STRICT1",
            "slots": 30,
            "copy_bw_bits_per_tick": 1,
            "demands": [{"src_slot": 0, "dst_slot": 1, "bits_total": 1}],
        }
        lbs = lower_bound_components(inst, strict1_bounds_mode="fractional_heuristic")
        self.assertFalse(lbs["bounds_complete"])
        self.assertEqual(lbs["bounds_complete_reason"], BOUNDS_REASON_FRACTIONAL_HEURISTIC_PARTIAL)

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

    def test_bounds_complete_reason_all_paths(self):
        strict_small = {
            "version": 0,
            "model": "STRICT1",
            "slots": 4,
            "copy_bw_bits_per_tick": 1,
            "demands": [{"src_slot": 0, "dst_slot": 1, "bits_total": 1}],
        }
        auto_exhaustive = lower_bound_components(strict_small, strict1_bounds_mode="auto")
        self.assertTrue(auto_exhaustive["bounds_complete"])
        self.assertEqual(auto_exhaustive["bounds_complete_reason"], "auto_exhaustive")

        strict_large = {
            "version": 0,
            "model": "STRICT1",
            "slots": 32,
            "copy_bw_bits_per_tick": 1,
            "demands": [{"src_slot": 0, "dst_slot": 1, "bits_total": 1}],
        }
        auto_partial = lower_bound_components(strict_large, strict1_bounds_mode="auto")
        self.assertFalse(auto_partial["bounds_complete"])
        self.assertEqual(auto_partial["bounds_complete_reason"], "auto_partial")

        frac_odd = lower_bound_components(strict_small, strict1_bounds_mode="fractional_odd_subset")
        self.assertTrue(frac_odd["bounds_complete"])
        self.assertEqual(frac_odd["bounds_complete_reason"], "fractional_odd_subset")

        frac_heur = lower_bound_components(strict_large, strict1_bounds_mode="fractional_heuristic")
        self.assertFalse(frac_heur["bounds_complete"])
        self.assertEqual(frac_heur["bounds_complete_reason"], "fractional_heuristic_partial")

        rw1 = {
            "version": 0,
            "model": "READ1_WRITE1",
            "slots": 4,
            "copy_bw_bits_per_tick": 1,
            "demands": [{"src_slot": 0, "dst_slot": 1, "bits_total": 1}],
        }
        rw1_lbs = lower_bound_components(rw1, strict1_bounds_mode="auto")
        self.assertTrue(rw1_lbs["bounds_complete"])
        self.assertEqual(rw1_lbs["bounds_complete_reason"], "read1_write1_complete")

    def test_report_contains_bounds_mode_and_reason(self):
        inst = {
            "version": 0,
            "model": "STRICT1",
            "slots": 4,
            "copy_bw_bits_per_tick": 1,
            "demands": [{"src_slot": 0, "dst_slot": 1, "bits_total": 1}],
        }
        rep = validate_schedule(inst, solve_greedy(inst), strict1_bounds_mode="auto")
        self.assertEqual(rep.bounds_mode, "auto")
        self.assertEqual(rep.bounds_complete_reason, "auto_exhaustive")
        data = rep.to_dict()
        self.assertIn("bounds_mode", data)
        self.assertIn("bounds_complete_reason", data)

    def test_reason_complete_invariant(self):
        expected = {
            BOUNDS_REASON_AUTO_EXHAUSTIVE: True,
            BOUNDS_REASON_AUTO_PARTIAL: False,
            BOUNDS_REASON_FRACTIONAL_ODD_SUBSET: True,
            BOUNDS_REASON_FRACTIONAL_HEURISTIC_PARTIAL: False,
            BOUNDS_REASON_READ1_WRITE1_COMPLETE: True,
        }
        cases = [
            (
                {
                    "version": 0,
                    "model": "STRICT1",
                    "slots": 4,
                    "copy_bw_bits_per_tick": 1,
                    "demands": [{"src_slot": 0, "dst_slot": 1, "bits_total": 1}],
                },
                "auto",
            ),
            (
                {
                    "version": 0,
                    "model": "STRICT1",
                    "slots": 32,
                    "copy_bw_bits_per_tick": 1,
                    "demands": [{"src_slot": 0, "dst_slot": 1, "bits_total": 1}],
                },
                "auto",
            ),
            (
                {
                    "version": 0,
                    "model": "STRICT1",
                    "slots": 4,
                    "copy_bw_bits_per_tick": 1,
                    "demands": [{"src_slot": 0, "dst_slot": 1, "bits_total": 1}],
                },
                "fractional_odd_subset",
            ),
            (
                {
                    "version": 0,
                    "model": "READ1_WRITE1",
                    "slots": 4,
                    "copy_bw_bits_per_tick": 1,
                    "demands": [{"src_slot": 0, "dst_slot": 1, "bits_total": 1}],
                },
                "auto",
            ),
        ]
        for inst, mode in cases:
            lbs = lower_bound_components(inst, strict1_bounds_mode=mode)
            reason = lbs["bounds_complete_reason"]
            self.assertEqual(lbs["bounds_complete"], expected[reason])

    def test_bounds_reason_constants_in_public_api(self):
        import copyspace_guard as cg

        expected = [
            "BOUNDS_REASON_AUTO_EXHAUSTIVE",
            "BOUNDS_REASON_AUTO_PARTIAL",
            "BOUNDS_REASON_FRACTIONAL_ODD_SUBSET",
            "BOUNDS_REASON_FRACTIONAL_HEURISTIC_PARTIAL",
            "BOUNDS_REASON_READ1_WRITE1_COMPLETE",
        ]
        for name in expected:
            self.assertIn(name, cg.__all__)
            self.assertIsInstance(getattr(cg, name), str)

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

    def test_bounds_reason_schema_enum_matches_constants(self):
        from copyspace_guard.bounds_reason import BoundsReason
        reasons = list(BoundsReason)
        expected = [e.value for e in reasons] + [None]
        report_schema = json.loads((ROOT / "schemas" / "report_v0.schema.json").read_text(encoding="utf-8"))
        report_enum = report_schema["properties"]["bounds_complete_reason"]["enum"]
        self.assertCountEqual(report_enum, expected)

        summary_schema = json.loads((ROOT / "schemas" / "summary_v0.schema.json").read_text(encoding="utf-8"))
        summary_enum = summary_schema["$defs"]["report"]["properties"]["bounds_complete_reason"]["enum"]
        self.assertCountEqual(summary_enum, expected)


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

    def test_gate_report_handles_none_thresholds(self):
        rep = Report(**{"status": "PASS", "version": 0, "model": "STRICT1", "ticks_total": 10, "utilization": 0.8, "gap_to_lower_bound": 0.5, "lower_bound_ticks": 5, "max_degree_chunks": 3, "bits_total": 100, "bits_per_tick": 20, "expected_bits_per_tick": 100, "gap_reliability": "estimate", "errors": []})
        self.assertEqual(gate_report(rep), (True, []))

    def test_gate_report_accepts_passing_max_gap(self):
        rep = Report(**{"status": "PASS", "version": 0, "model": "STRICT1", "ticks_total": 10, "gap_to_lower_bound": 0.1, "utilization": 0.9, "gap_reliability": "exact", "lower_bound_ticks": 5, "max_degree_chunks": 3, "bits_total": 100, "bits_per_tick": 20, "expected_bits_per_tick": 100, "errors": []})
        ok, reasons = gate_report(rep, max_gap=0.2)
        self.assertTrue(ok)
        self.assertEqual(reasons, [])

    def test_gate_report_rejects_exceeding_max_gap(self):
        rep = Report(**{"status": "PASS", "version": 0, "model": "STRICT1", "ticks_total": 10, "gap_to_lower_bound": 0.5, "utilization": 0.9, "gap_reliability": "exact", "lower_bound_ticks": 5, "max_degree_chunks": 3, "bits_total": 100, "bits_per_tick": 20, "expected_bits_per_tick": 100, "errors": []})
        ok, reasons = gate_report(rep, max_gap=0.2)
        self.assertFalse(ok)
        self.assertGreater(len(reasons), 0)

    def test_gate_report_max_gap_vs_greedy(self):
        from copyspace_guard.validate import gate_report as validate_report
        rep = Report(**{"status": "PASS", "version": 0, "model": "STRICT1", "ticks_total": 10, "gap_to_lower_bound": 0.3, "utilization": 0.9, "gap_reliability": "estimate", "lower_bound_ticks": 5, "max_degree_chunks": 3, "bits_total": 100, "bits_per_tick": 20, "expected_bits_per_tick": 100, "errors": []})
        ok, reasons = validate_report(rep, max_gap=0.2)
        self.assertFalse(ok)
        self.assertGreater(len(reasons), 0)

    def test_report_svg_inline_visualization_is_valid_svg(self):
        test_summary = {
            "instance": {"id": "test", "model": "STRICT1", "slots": 4, "copy_bw_bits_per_tick": 256},
            "current_label": "baseline",
            "candidate_label": "greedy",
            "reports": {
                "greedy": {"status": "PASS", "version": 0, "model": "STRICT1", "ticks_total": 5, "bits_total": 1024, "bits_per_tick": 204.8, "utilization": 0.8, "lower_bound_ticks": 4, "gap_to_lower_bound": 0.25, "gap_reliability": "exact", "max_degree_chunks": 3, "errors": []},
                "baseline": {"status": "PASS", "version": 0, "model": "STRICT1", "ticks_total": 5, "bits_total": 1024, "bits_per_tick": 204.8, "utilization": 0.8, "lower_bound_ticks": 4, "gap_to_lower_bound": 0.25, "gap_reliability": "exact", "max_degree_chunks": 3, "errors": []},
            },
            "comparison": {"comparable": True, "saved_ticks": 0, "saved_ticks_pct": 0.0, "gap_reduction_ticks": 0, "utilization_delta": 0.0},
            "roi": {},
            "artifacts": {},
        }
        html = render_html(test_summary)
        self.assertIn("<svg", html)
        self.assertIn("</svg>", html)

    def test_html_report_no_xss_injection(self):
        test_summary = {
            "instance": {"id": "<script>alert(1)</script>", "model": "STRICT1", "slots": 4, "copy_bw_bits_per_tick": 256, "demands": [{"src_slot": 0, "dst_slot": 1, "bits_total": 100}]},
            "current_label": "baseline",
            "candidate_label": "greedy",
            "reports": {
                "greedy": {"status": "PASS", "version": 0, "model": "STRICT1", "ticks_total": 1, "bits_total": 100, "bits_per_tick": 100, "utilization": 1.0, "lower_bound_ticks": 1, "gap_to_lower_bound": 0.0, "gap_reliability": "exact", "max_degree_chunks": 1, "errors": []},
                "baseline": {"status": "PASS", "version": 0, "model": "STRICT1", "ticks_total": 1, "bits_total": 100, "bits_per_tick": 100, "utilization": 1.0, "lower_bound_ticks": 1, "gap_to_lower_bound": 0.0, "gap_reliability": "exact", "max_degree_chunks": 1, "errors": []},
            },
            "comparison": {"comparable": True, "saved_ticks": 0, "saved_ticks_pct": 0.0, "gap_reduction_ticks": 0, "utilization_delta": 0.0},
            "roi": {"savings_kind": "baseline_comparison"},
            "artifacts": {},
        }
        html = render_html(test_summary)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_inline_html_rejects_raw_angle_brackets(self):
        with self.assertRaises(ValueError):
            _inline_html("<script>")
        with self.assertRaises(ValueError):
            _inline_html("a < b")
        _inline_html("safe `code` text")
        _inline_html("no angle at all")

    def test_load_roi_config_and_compute_works(self):
        inst = instance_from_csv(ROOT / "examples" / "ring15.csv", bw=256)
        rep = validate_schedule(inst, solve_greedy(inst))
        ns = argparse.Namespace(roi=str(ROOT / "examples" / "roi.yml"), cost_per_tick=0.0)
        comp, roi = _load_roi_config_and_compute(ns, rep, rep, kind="baseline_vs_greedy")
        self.assertTrue(comp["comparable"])
        self.assertEqual(roi["savings_kind"], "baseline_comparison")
        self.assertGreater(roi["cost_per_tick"], 0)

    def test_fractional_heuristic_report_bounds_mode_and_reason(self):
        inst = {
            "version": 0,
            "model": "STRICT1",
            "slots": 32,
            "copy_bw_bits_per_tick": 1,
            "demands": [{"src_slot": 0, "dst_slot": 1, "bits_total": 1}],
        }
        rep = validate_schedule(inst, solve_greedy(inst), strict1_bounds_mode="fractional_heuristic")
        self.assertEqual(rep.bounds_mode, "fractional_heuristic")
        self.assertEqual(rep.bounds_complete_reason, "fractional_heuristic_partial")
        self.assertFalse(rep.bounds_complete)

    def test_html_report_xss_table_cells_escaped(self):
        test_summary = {
            "instance": {"id": "safe", "model": "STRICT1", "slots": 4, "copy_bw_bits_per_tick": 256, "demands": [{"src_slot": 0, "dst_slot": 1, "bits_total": 100}]},
            "current_label": "<script>alert('cur')</script>",
            "candidate_label": "greedy",
            "reports": {
                "greedy": {"status": "PASS", "version": 0, "model": "STRICT1", "ticks_total": 1, "bits_total": 100, "bits_per_tick": 100, "utilization": 1.0, "lower_bound_ticks": 1, "gap_to_lower_bound": 0.0, "gap_reliability": "exact", "max_degree_chunks": 1, "errors": []},
                "baseline": {"status": "PASS", "version": 0, "model": "STRICT1", "ticks_total": 1, "bits_total": 100, "bits_per_tick": 100, "utilization": 1.0, "lower_bound_ticks": 1, "gap_to_lower_bound": 0.0, "gap_reliability": "exact", "max_degree_chunks": 1, "errors": []},
            },
            "comparison": {"comparable": True, "saved_ticks": 0, "saved_ticks_pct": 0.0, "gap_reduction_ticks": 0, "utilization_delta": 0.0},
            "roi": {},
            "artifacts": {},
        }
        html = render_html(test_summary)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("alert(&#x27;cur&#x27;)", html)
