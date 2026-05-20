import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from copyspace_guard.core import (  # noqa: E402
    compute_roi,
    gate_report,
    instance_from_csv,
    lower_bound_components,
    schedule_from_csv,
    solve_greedy,
    validate_schedule,
)


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

class SchemaFilesTests(unittest.TestCase):
    def test_schema_files_are_valid_json(self):
        import json
        for name in ["instance_v0.schema.json", "schedule_v0.schema.json", "summary_v0.schema.json"]:
            data = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
            self.assertIn("$schema", data)
            self.assertIn("title", data)
