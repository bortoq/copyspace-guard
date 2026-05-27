import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args, check=True):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    cmd = [sys.executable, "-m", "copyspace_guard.cli", *args]
    return subprocess.run(cmd, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)


class CliTests(unittest.TestCase):
    def test_version_command(self):
        rc = run_cli("--version")
        self.assertEqual(rc.returncode, 0)
        self.assertIn("copyspace-guard", rc.stdout)
        self.assertIn("0.2.4", rc.stdout)

    def test_doctor_command(self):
        rc = run_cli("doctor", "--root", str(ROOT))
        self.assertEqual(rc.returncode, 0)
        self.assertIn("doctor passed", rc.stdout)

    def test_doctor_json_command(self):
        rc = run_cli("doctor", "--root", str(ROOT), "--json")
        self.assertEqual(rc.returncode, 0)
        data = json.loads(rc.stdout)
        self.assertEqual(data["status"], "PASS")
        self.assertGreaterEqual(len(data["checks"]), 1)

    def test_summary_only_does_not_emit_schedules(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            run_cli("analyze", "--csv", "examples/ring15.csv", "--bw", "256", "--roi", "examples/roi.yml", "--summary-only", "--outdir", str(out))
            self.assertTrue((out / "summary.json").exists())
            self.assertTrue((out / "report.md").exists())
            self.assertFalse((out / "schedule_greedy.json").exists())
            data = json.loads((out / "summary.json").read_text())
            self.assertEqual(data["reports"]["greedy"]["gap_ticks"], 0)

    def test_read1_write1_summary_preserves_report_model(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            run_cli("analyze", "--csv", "examples/ring15.csv", "--bw", "256", "--model", "READ1_WRITE1", "--summary-only", "--outdir", str(out))
            data = json.loads((out / "summary.json").read_text())
            self.assertEqual(data["instance"]["model"], "READ1_WRITE1")
            self.assertEqual(data["reports"]["baseline"]["model"], "READ1_WRITE1")
            self.assertEqual(data["reports"]["greedy"]["model"], "READ1_WRITE1")

    def test_customer_current_artifact_contract(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            run_cli(
                "analyze",
                "--csv", "examples/demo_bad_current_demands.csv",
                "--bw", "256",
                "--current-schedule-csv", "examples/demo_bad_current_schedule.csv",
                "--outdir", str(out),
            )
            data = json.loads((out / "summary.json").read_text())
            self.assertEqual(data["current_label"], "customer_current")
            self.assertNotIn("baseline", data["reports"])
            self.assertIn("current", data["reports"])
            self.assertTrue((out / "schedule_customer_current.json").exists())
            self.assertTrue((out / "schedule_customer_current.csv").exists())
            self.assertTrue((out / "report_customer_current.json").exists())
            self.assertEqual(data["artifacts"]["schedule_current"], "schedule_customer_current.json")
            self.assertEqual(data["artifacts"]["report_current"], "report_customer_current.json")
            self.assertIn("audit", data)
            self.assertIn("audit_note", data["audit"])
            self.assertIn("gap_vs_greedy", data["audit"])

    def test_validate_artifact_command(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            run_cli("analyze", "--csv", "examples/ring15.csv", "--bw", "256", "--summary-only", "--outdir", str(out))
            rc = run_cli("validate-artifact", "--kind", "summary", str(out / "summary.json"))
            self.assertEqual(rc.returncode, 0)

    def test_file_output_guardrails_apply_to_cli_writes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inst = root / "instance.json"
            sched = root / "schedule.json"
            inst.write_text(json.dumps({
                "version": 0,
                "model": "STRICT1",
                "slots": 2,
                "copy_bw_bits_per_tick": 1,
                "demands": [{"src_slot": 0, "dst_slot": 1, "bits_total": 1}],
            }), encoding="utf-8")
            sched.write_text(json.dumps({"version": 0, "model": "STRICT1", "ticks": [[{"src_slot": 0, "dst_slot": 1, "len_bits": 1}]]}), encoding="utf-8")

            rc = run_cli("validate", str(inst), str(sched), "--report", "../escape.json", check=False)
            self.assertEqual(rc.returncode, 1)
            self.assertIn("parent directory traversal", rc.stderr)

            rc = run_cli("schedule-csv-to-json", "--csv", "examples/demo_bad_current_schedule.csv", "--out", "../escape.json", check=False)
            self.assertEqual(rc.returncode, 1)
            self.assertIn("parent directory traversal", rc.stderr)

            rc = run_cli("anonymize", "--kind", "demands", "--csv", "examples/demo_bad_current_demands.csv", "--out", "../escape.csv", check=False)
            self.assertEqual(rc.returncode, 1)
            self.assertIn("parent directory traversal", rc.stderr)

    def test_anonymize_limits_are_enforced(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_path = root / "input.csv"
            csv_path.write_text("src_slot,dst_slot,bits_total\n0,1,1\n1,2,1\n", encoding="utf-8")

            rc = run_cli("anonymize", "--kind", "demands", "--csv", str(csv_path), "--out", str(root / "out.csv"), "--max-rows", "1", check=False)
            self.assertEqual(rc.returncode, 1)
            self.assertIn("--max-rows", rc.stderr)

            rc = run_cli("anonymize", "--kind", "demands", "--csv", str(csv_path), "--out", str(root / "out2.csv"), "--max-file-size", "1", check=False)
            self.assertEqual(rc.returncode, 1)
            self.assertIn("--max-file-size", rc.stderr)

    def test_anonymize_unique_slot_limit_is_enforced(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_path = root / "input.csv"
            csv_path.write_text("src_slot,dst_slot,bits_total\n0,1,1\n1,2,1\n", encoding="utf-8")

            rc = run_cli("anonymize", "--kind", "demands", "--csv", str(csv_path), "--out", str(root / "out.csv"), "--max-unique-slots", "2", check=False)
            self.assertEqual(rc.returncode, 1)
            self.assertIn("--max-unique-slots", rc.stderr)

    def test_ring15_summary_golden_contract(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            run_cli("analyze", "--csv", "examples/ring15.csv", "--bw", "256", "--roi", "examples/roi.yml", "--summary-only", "--outdir", str(out))
            data = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            golden = json.loads((ROOT / "tests" / "golden" / "ring15_summary_subset.json").read_text(encoding="utf-8"))
            actual = {
                "current_label": data["current_label"],
                "candidate_label": data["candidate_label"],
                "model": data["instance"]["model"],
                "slots": data["instance"]["slots"],
                "baseline_ticks": data["reports"]["baseline"]["ticks_total"],
                "greedy_ticks": data["reports"]["greedy"]["ticks_total"],
                "greedy_lower_bound_ticks": data["reports"]["greedy"]["lower_bound_ticks"],
                "greedy_gap_ticks": data["reports"]["greedy"]["gap_ticks"],
                "saved_ticks": data["comparison"]["saved_ticks"],
                "artifacts": data["artifacts"],
            }
            self.assertEqual(actual, golden)

    def test_guardrails_fail_cleanly(self):
        with tempfile.TemporaryDirectory() as td:
            rc = run_cli("analyze", "--csv", "examples/ring15.csv", "--bw", "256", "--max-slots", "2", "--outdir", str(Path(td) / "out"), check=False)
            self.assertEqual(rc.returncode, 1)
            self.assertIn("exceeds --max-slots", rc.stderr)

    def test_outdir_parent_traversal_is_rejected(self):
        rc = run_cli("analyze", "--csv", "examples/ring15.csv", "--bw", "256", "--outdir", "../copyspace-guard-escape", check=False)
        self.assertEqual(rc.returncode, 1)
        self.assertIn("parent directory traversal", rc.stderr)

    def test_invalid_current_is_not_comparable(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            rc = run_cli(
                "analyze",
                "--csv", "examples/demo_conflict_demands.csv",
                "--bw", "256",
                "--current-schedule-csv", "examples/demo_conflict_schedule.csv",
                "--summary-only",
                "--outdir", str(out),
                check=False,
            )
            self.assertEqual(rc.returncode, 2)
            data = json.loads((out / "summary.json").read_text())
            self.assertFalse(data["comparison"]["comparable"])
            self.assertEqual(data["comparison"]["saved_ticks"], 0)

    def test_gate_max_gap_vs_greedy(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            run_cli(
                "analyze",
                "--csv", "examples/ring15.csv",
                "--bw", "256",
                "--current-schedule-csv", "examples/current_schedule.csv",
                "--summary-only",
                "--outdir", str(out),
            )
            rc = run_cli("gate", str(out / "summary.json"), "--report", "customer_current", "--max-gap-vs-greedy", "0.4")
            self.assertEqual(rc.returncode, 0)
            self.assertIn("gap_vs_greedy", rc.stdout)
            rc = run_cli("gate", str(out / "summary.json"), "--report", "customer_current", "--max-gap-vs-greedy", "0.2", check=False)
            self.assertEqual(rc.returncode, 2)
            self.assertIn("max_gap_vs_greedy", rc.stderr)

    def test_gate_bounds_complete_warning_is_visible(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            run_cli(
                "analyze",
                "--csv", "examples/ring15.csv",
                "--bw", "256",
                "--slots", "32",
                "--summary-only",
                "--outdir", str(out),
            )
            rc = run_cli("gate", str(out / "summary.json"), "--report", "greedy", "--max-gap", "1.0", check=False)
            self.assertEqual(rc.returncode, 2)
            self.assertIn("bounds_complete=false", rc.stderr)

    def test_anonymize_schedule(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "sched.csv"
            mapping = Path(td) / "mapping.json"
            run_cli("anonymize", "--kind", "schedule", "--csv", "examples/demo_bad_current_schedule.csv", "--out", str(out), "--mapping", str(mapping))
            self.assertTrue(out.exists())
            self.assertTrue(mapping.exists())

    def test_anonymize_reuses_mapping(self):
        with tempfile.TemporaryDirectory() as td:
            demand_out = Path(td) / "demands.csv"
            sched_out = Path(td) / "sched.csv"
            mapping = Path(td) / "mapping.json"
            run_cli("anonymize", "--kind", "demands", "--csv", "examples/demo_bad_current_demands.csv", "--out", str(demand_out), "--mapping", str(mapping))
            run_cli("anonymize", "--kind", "schedule", "--csv", "examples/demo_bad_current_schedule.csv", "--out", str(sched_out), "--mapping-in", str(mapping), "--mapping", str(mapping))
            data = json.loads(mapping.read_text())
            self.assertEqual(data["0"], 0)
            self.assertEqual(data["3"], 3)


if __name__ == "__main__":
    unittest.main()

class CliErrorTests(unittest.TestCase):
    def test_unsorted_schedule_csv_is_clean_error(self):
        with tempfile.TemporaryDirectory() as td:
            sched = Path(td) / "bad.csv"
            sched.write_text("tick,src_slot,dst_slot,len_bits\n1,0,1,1\n0,1,2,1\n", encoding="utf-8")
            demands = Path(td) / "demands.csv"
            demands.write_text("src_slot,dst_slot,bits_total\n0,1,1\n1,2,1\n", encoding="utf-8")
            rc = run_cli("analyze", "--csv", str(demands), "--bw", "1", "--current-schedule-csv", str(sched), "--summary-only", "--outdir", str(Path(td) / "out"), check=False)
            self.assertEqual(rc.returncode, 1)
            self.assertIn("ERROR:", rc.stderr)
            self.assertNotIn("Traceback", rc.stderr)

    def test_bench_command(self):
        with tempfile.TemporaryDirectory() as td:
            rc = run_cli("bench", "--slots", "8", "--bits-per-edge", "1024", "--bw", "256", "--outdir", td)
            self.assertEqual(rc.returncode, 0)
            self.assertTrue((Path(td) / "bench.json").exists())

    def test_bench_suite_command(self):
        with tempfile.TemporaryDirectory() as td:
            rc = run_cli("bench-suite", "--outdir", td, "--max-total-seconds", "30")
            self.assertEqual(rc.returncode, 0)
            data = json.loads((Path(td) / "bench_suite.json").read_text(encoding="utf-8"))
            self.assertEqual(data["case_count"], 3)
            self.assertEqual(data["failures"], [])

    def test_bench_bounds_command(self):
        with tempfile.TemporaryDirectory() as td:
            rc = run_cli(
                "bench-bounds",
                "--outdir", td,
                "--min-slots", "32",
                "--max-slots", "64",
                "--step-slots", "32",
                "--max-total-seconds", "30",
            )
            self.assertEqual(rc.returncode, 0)
            data = json.loads((Path(td) / "bench_bounds.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(data["case_count"], 2)
            self.assertEqual(data["failures"], [])

    def test_import_csv_with_mapping(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "custom.csv"
            out = Path(td) / "schedule.json"
            src.write_text("step,from,to,bits\n0,0,1,256\n1,1,2,256\n", encoding="utf-8")
            rc = run_cli(
                "import-csv",
                "--csv", str(src),
                "--map", "tick=step",
                "--map", "src=from",
                "--map", "dst=to",
                "--map", "len=bits",
                "--out", str(out),
            )
            self.assertEqual(rc.returncode, 0)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["ticks"][0][0]["src_slot"], 0)
            self.assertEqual(data["ticks"][1][0]["dst_slot"], 2)

    def test_import_taccl_json(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "taccl.json"
            out = Path(td) / "schedule.json"
            src.write_text(json.dumps({"ops": [{"step": 0, "from": 0, "to": 1, "bits": 128}]}), encoding="utf-8")
            rc = run_cli("import-taccl", str(src), "--out", str(out))
            self.assertEqual(rc.returncode, 0)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["ticks"][0][0]["len_bits"], 128)

    def test_import_sample_files_from_examples(self):
        with tempfile.TemporaryDirectory() as td:
            out_xml = Path(td) / "from_xml.json"
            out_json = Path(td) / "from_taccl.json"
            rc = run_cli("import-msccl", "examples/sample_msccl.xml", "--out", str(out_xml))
            self.assertEqual(rc.returncode, 0)
            rc = run_cli("import-taccl", "examples/sample_taccl.json", "--out", str(out_json))
            self.assertEqual(rc.returncode, 0)

    def test_import_msccl_xml(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "algo.xml"
            out = Path(td) / "schedule.json"
            src.write_text("<algo><op step='0' src='0' dst='1' cnt='64' /></algo>", encoding="utf-8")
            rc = run_cli("import-msccl", str(src), "--out", str(out))
            self.assertEqual(rc.returncode, 0)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["ticks"][0][0]["len_bits"], 64)

    def test_audit_command(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "audit"
            rc = run_cli(
                "audit",
                "--demands", "examples/ring15.csv",
                "--bw", "256",
                "--schedule", "examples/current_schedule.csv",
                "--outdir", str(out),
            )
            self.assertEqual(rc.returncode, 0)
            data = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(data["current_label"], "customer_current")
            self.assertEqual(data["candidate_label"], "customer_current")
            self.assertTrue((out / "report.md").exists())
            self.assertIn("gap_vs_greedy", data.get("audit", {}))

    def test_audit_max_gap_vs_greedy_threshold(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "audit"
            rc = run_cli(
                "audit",
                "--demands", "examples/ring15.csv",
                "--bw", "256",
                "--schedule", "examples/current_schedule.csv",
                "--max-gap-vs-greedy", "0.4",
                "--outdir", str(out),
            )
            self.assertEqual(rc.returncode, 0)
            rc = run_cli(
                "audit",
                "--demands", "examples/ring15.csv",
                "--bw", "256",
                "--schedule", "examples/current_schedule.csv",
                "--max-gap-vs-greedy", "0.2",
                "--outdir", str(out),
                check=False,
            )
            self.assertEqual(rc.returncode, 2)
            self.assertIn("max-gap-vs-greedy", rc.stderr)

    def test_audit_max_gap_vs_greedy_pass(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "audit"
            rc = run_cli(
                "audit",
                "--demands", "examples/ring15.csv",
                "--bw", "256",
                "--schedule", "examples/current_schedule.csv",
                "--max-gap-vs-greedy", "0.99",
                "--outdir", str(out),
            )
            self.assertEqual(rc.returncode, 0)

    def test_audit_max_gap_threshold(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "audit"
            rc = run_cli(
                "audit",
                "--demands", "examples/ring15.csv",
                "--bw", "256",
                "--schedule", "examples/current_schedule.csv",
                "--max-gap", "0.5",
                "--outdir", str(out),
            )
            self.assertEqual(rc.returncode, 0)
            rc = run_cli(
                "audit",
                "--demands", "examples/ring15.csv",
                "--bw", "256",
                "--schedule", "examples/current_schedule.csv",
                "--max-gap", "0.1",
                "--outdir", str(out),
                check=False,
            )
            self.assertEqual(rc.returncode, 2)
            self.assertIn("--max-gap", rc.stderr)

    def test_audit_max_gap_rejected_when_bounds_incomplete(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "audit"
            rc = run_cli(
                "audit",
                "--demands", "examples/ring15.csv",
                "--bw", "256",
                "--slots", "32",
                "--schedule", "examples/current_schedule.csv",
                "--max-gap", "0.5",
                "--outdir", str(out),
                check=False,
            )
            self.assertEqual(rc.returncode, 2)
            self.assertIn("bounds_complete=false", rc.stderr)

    def test_audit_accumulates_multiple_gate_reasons(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "audit"
            rc = run_cli(
                "audit",
                "--demands", "examples/ring15.csv",
                "--bw", "256",
                "--slots", "32",
                "--schedule", "examples/current_schedule.csv",
                "--max-gap", "0.01",
                "--max-gap-vs-greedy", "0.2",
                "--outdir", str(out),
                check=False,
            )
            self.assertEqual(rc.returncode, 2)
            self.assertIn("AUDIT GATE FAIL", rc.stderr)
            self.assertIn("bounds_complete=false", rc.stderr)

    def test_compare_command(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "compare"
            rc = run_cli(
                "compare",
                "--demands", "examples/ring15.csv",
                "--bw", "256",
                "--schedule-a", "examples/current_schedule.csv",
                "--schedule-b", "examples/current_schedule.csv",
                "--outdir", str(out),
            )
            self.assertEqual(rc.returncode, 0)
            data = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(data["current_label"], "schedule_a")
            self.assertEqual(data["candidate_label"], "schedule_b")
            self.assertTrue((out / "report_schedule_a.json").exists())
            self.assertTrue((out / "report_schedule_b.json").exists())

    def test_compare_command_csv_schedules(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "compare"
            rc = run_cli(
                "compare",
                "--demands", "examples/ring15.csv",
                "--bw", "256",
                "--schedule-a", "examples/current_schedule.csv",
                "--schedule-b", "examples/current_schedule.csv",
                "--outdir", str(out),
            )
            self.assertEqual(rc.returncode, 0)
            data = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(data["comparison"]["saved_ticks"], 0)

    def test_audit_requires_schedule(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "audit"
            rc = run_cli(
                "audit",
                "--demands", "examples/ring15.csv",
                "--bw", "256",
                "--outdir", str(out),
                check=False,
            )
            self.assertNotEqual(rc.returncode, 0)

    def test_import_commands_limits_and_errors(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_path = root / "custom.csv"
            csv_path.write_text("step,from,to,bits\n0,0,1,8\n1,1,2,8\n", encoding="utf-8")
            rc = run_cli(
                "import-csv",
                "--csv", str(csv_path),
                "--map", "tick=step",
                "--map", "src=from",
                "--map", "dst=to",
                "--map", "len=bits",
                "--max-rows", "1",
                "--out", str(root / "out.json"),
                check=False,
            )
            self.assertEqual(rc.returncode, 1)
            self.assertIn("--max-rows", rc.stderr)

            bad_xml = root / "bad.xml"
            bad_xml.write_text("<algo><op></algo>", encoding="utf-8")
            rc = run_cli("import-msccl", str(bad_xml), "--out", str(root / "x.json"), check=False)
            self.assertEqual(rc.returncode, 1)
            self.assertIn("ERROR:", rc.stderr)
