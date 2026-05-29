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
        self.assertIn("0.2.5", rc.stdout)

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

    def test_doctor_recommendations_for_large_instance(self):
        rc = run_cli(
            "doctor",
            "--root",
            str(ROOT),
            "--demands",
            "examples/ring15.csv",
            "--bw",
            "256",
            "--slots",
            "256",
            "--json",
        )
        self.assertEqual(rc.returncode, 0)
        data = json.loads(rc.stdout)
        joined = "\n".join(data.get("recommendations", []))
        self.assertIn("--max-gap-vs-greedy", joined)
        self.assertIn("fractional_heuristic", joined)

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

    def test_industry_demo_gpt2_saved_ticks_via_cli(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            run_cli(
                "analyze",
                "--csv", "examples/gpt2_ddp_allreduce/demands.csv",
                "--bw", "25000000000",
                "--slots", "8",
                "--current-schedule-csv", "examples/gpt2_ddp_allreduce/naive_schedule.csv",
                "--summary-only",
                "--outdir", str(out),
            )
            data = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            greedy = data["reports"]["greedy"]["ticks_total"]
            current = data["reports"]["customer_current"]["ticks_total"]
            self.assertGreater(current, greedy)
            self.assertEqual(data["comparison"]["saved_ticks"], current - greedy)

    def test_industry_demo_kv_cache_saved_ticks_via_cli(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            run_cli(
                "analyze",
                "--csv", "examples/kv_cache_disagg/demands.csv",
                "--bw", "50000000000",
                "--slots", "8",
                "--current-schedule-csv", "examples/kv_cache_disagg/naive_schedule.csv",
                "--summary-only",
                "--outdir", str(out),
            )
            data = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            greedy = data["reports"]["greedy"]["ticks_total"]
            current = data["reports"]["customer_current"]["ticks_total"]
            self.assertGreater(current, greedy)
            self.assertEqual(data["comparison"]["saved_ticks"], current - greedy)

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
            self.assertIn("auto_partial", rc.stderr)
            self.assertIn("--max-gap-vs-greedy", rc.stderr)

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

    def test_validate_common_args_rejects_negative_values(self):
        from copyspace_guard.cli import _validate_common_args
        import argparse

        ns = argparse.Namespace(max_errors=None, bounds_subset_limit=0)
        _validate_common_args(ns)  # should not raise

        ns = argparse.Namespace(max_errors=-1, bounds_subset_limit=0)
        with self.assertRaisesRegex(ValueError, "--max-errors"):
            _validate_common_args(ns)

        ns = argparse.Namespace(max_errors=0, bounds_subset_limit=-5)
        with self.assertRaisesRegex(ValueError, "--bounds-subset-limit"):
            _validate_common_args(ns)

    def test_schedule_csv_to_json_smoke(self):
        with tempfile.TemporaryDirectory() as td:
            csv = Path(td) / "simple.csv"
            csv.write_text("tick,src_slot,dst_slot,len_bits\n0,0,1,8\n0,2,3,8\n", encoding="utf-8")
            out = Path(td) / "sched.json"
            rc = run_cli("schedule-csv-to-json", "--csv", str(csv), "--out", str(out))
            self.assertEqual(rc.returncode, 0)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["version"], 0)
            self.assertEqual(len(data["ticks"][0]), 2)

    def test_cmd_validate_accepts_valid_schedule(self):
        with tempfile.TemporaryDirectory() as td:
            inst = Path(td) / "instance.json"
            sched = Path(td) / "schedule.json"
            inst.write_text(json.dumps({
                "version": 0,
                "model": "STRICT1",
                "slots": 2,
                "copy_bw_bits_per_tick": 1,
                "demands": [{"src_slot": 0, "dst_slot": 1, "bits_total": 1}],
            }), encoding="utf-8")
            sched.write_text(json.dumps({
                "version": 0,
                "model": "STRICT1",
                "ticks": [[{"src_slot": 0, "dst_slot": 1, "len_bits": 1}]],
            }), encoding="utf-8")
            rc = run_cli("validate", str(inst), str(sched))
            self.assertEqual(rc.returncode, 0)
            self.assertIn("PASS", rc.stdout)
            self.assertIn("ticks=", rc.stdout)


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

    def test_import_nccl_log_and_pytorch_trace(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nccl = root / "nccl.log"
            nccl.write_text("ring: rank 0 -> rank 1, bytes=4\n", encoding="utf-8")
            out_demands = root / "demands_from_nccl.csv"
            rc = run_cli("import-nccl-log", str(nccl), "--out", str(out_demands))
            self.assertEqual(rc.returncode, 0)
            self.assertIn("src_slot,dst_slot,bits_total", out_demands.read_text(encoding="utf-8"))

            trace = root / "trace.json"
            trace.write_text(
                json.dumps({"traceEvents": [{"name": "ncclAllReduce", "args": {"bytes": 4, "ranks": [0, 1]}}]}),
                encoding="utf-8",
            )
            out_trace = root / "demands_from_trace.csv"
            rc = run_cli("import-pytorch-trace", str(trace), "--out", str(out_trace))
            self.assertEqual(rc.returncode, 0)
            self.assertIn("src_slot,dst_slot,bits_total", out_trace.read_text(encoding="utf-8"))

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
            rep = json.loads((out / "report_customer_current.json").read_text(encoding="utf-8"))
            self.assertIn("gap_reliability", rep)
            self.assertIn("gap_practical", rep)
            self.assertIsInstance(rep["gap_practical"], float)
            self.assertIn("practical", data.get("roi", {}))
            self.assertIn("theoretical_max", data.get("roi", {}))
            self.assertIn("practical_gap=", rc.stdout)
            self.assertIn("theoretical_gap=", rc.stdout)

    def test_audit_solver_plugin(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plugin = root / "plugin.py"
            plugin.write_text(
                "import json,sys\n"
                "inst=json.load(sys.stdin)\n"
                "sched={'version':0,'model':inst['model'],'ticks':[[{'src_slot':0,'dst_slot':1,'len_bits':256}]]}\n"
                "json.dump(sched,sys.stdout)\n",
                encoding="utf-8",
            )
            out = root / "audit"
            rc = run_cli(
                "audit",
                "--demands", "examples/ring15.csv",
                "--bw", "256",
                "--solver-plugin", str(plugin),
                "--outdir", str(out),
                check=False,
            )
            self.assertEqual(rc.returncode, 2)
            self.assertTrue((out / "report_customer_current.json").exists())

    def test_audit_bounds_mode_fractional_odd_subset(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "audit"
            rc = run_cli(
                "audit",
                "--demands", "examples/ring15.csv",
                "--bw", "256",
                "--schedule", "examples/current_schedule.csv",
                "--bounds-mode", "fractional_odd_subset",
                "--outdir", str(out),
            )
            self.assertEqual(rc.returncode, 0)

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

    def test_audit_fractional_odd_subset_rejects_slots_above_limit(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "audit"
            rc = run_cli(
                "audit",
                "--demands", "examples/ring15.csv",
                "--bw", "256",
                "--slots", "30",
                "--schedule", "examples/current_schedule.csv",
                "--bounds-mode", "fractional_odd_subset",
                "--outdir", str(out),
                check=False,
            )
            self.assertEqual(rc.returncode, 1)
            self.assertIn("fractional_odd_subset is limited", rc.stderr)

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

    def test_analyze_bounds_mode_fractional_odd_subset(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            rc = run_cli(
                "analyze",
                "--csv", "examples/ring15.csv",
                "--bw", "256",
                "--bounds-mode", "fractional_odd_subset",
                "--summary-only",
                "--outdir", str(out),
            )
            self.assertEqual(rc.returncode, 0)
            data = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertIn(
                data["reports"]["greedy"]["lower_bound_witness"]["kind"],
                {"full_graph_capacity", "fractional_odd_subset"},
            )

    def test_analyze_bounds_mode_fractional_heuristic(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            rc = run_cli(
                "analyze",
                "--csv", "examples/ring15.csv",
                "--bw", "256",
                "--bounds-mode", "fractional_heuristic",
                "--summary-only",
                "--outdir", str(out),
            )
            self.assertEqual(rc.returncode, 0)

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

    def test_fractional_exact_alias_works(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            rc = run_cli(
                "analyze",
                "--csv", "examples/ring15.csv",
                "--bw", "256",
                "--bounds-mode", "fractional_exact",
                "--summary-only",
                "--outdir", str(out),
                check=False,
            )
            self.assertEqual(rc.returncode, 0)
            self.assertIn("fractional_exact is deprecated", rc.stderr)

    def test_fractional_odd_subset_still_works(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            rc = run_cli(
                "analyze",
                "--csv", "examples/ring15.csv",
                "--bw", "256",
                "--bounds-mode", "fractional_odd_subset",
                "--summary-only",
                "--outdir", str(out),
                check=False,
            )
            self.assertEqual(rc.returncode, 0)

    def test_infer_nccl_log(self):
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "nccl.log"
            log.write_text("rank 0 -> rank 1, bytes=134217728\nrank 1 -> rank 2, bytes=67108864\n", encoding="utf-8")
            rc = run_cli("infer", str(log), check=False)
            self.assertEqual(rc.returncode, 0)
            self.assertIn("inferred:", rc.stdout)
            self.assertIn("slots=3", rc.stdout)
            self.assertIn("bw=", rc.stdout)
            self.assertIn("use actual NIC bandwidth", rc.stdout)

    def test_validate_common_args_rejects_negative_max_errors(self):
        rc = run_cli("analyze", "--csv", "examples/ring15.csv", "--bw", "256", "--max-errors", "-1", "--summary-only", "--outdir", "/tmp/_x", check=False)
        self.assertNotEqual(rc.returncode, 0)

    def test_validate_common_args_rejects_negative_bounds_subset_limit(self):
        rc = run_cli("analyze", "--csv", "examples/ring15.csv", "--bw", "256", "--bounds-subset-limit", "-1", "--summary-only", "--outdir", "/tmp/_x", check=False)
        self.assertNotEqual(rc.returncode, 0)

    def test_analyze_output_contains_savings_kind(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            rc = run_cli(
                "analyze",
                "--csv", "examples/ring15.csv",
                "--bw", "256",
                "--summary-only",
                "--outdir", str(out),
            )
            self.assertEqual(rc.returncode, 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertIn("savings_kind", summary["roi"])
            self.assertEqual(summary["roi"]["savings_kind"], "baseline_comparison")


class SecurityCliTests(unittest.TestCase):
    def test_outdir_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "sub" / ".." / ".." / "etc"
            rc = run_cli(
                "analyze", "--csv", "examples/ring15.csv", "--bw", "256",
                "--summary-only", "--outdir", str(bad), check=False,
            )
            self.assertNotEqual(rc.returncode, 0)

    def test_outdir_path_traversal_with_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            link = Path(td) / "outlink"
            link.symlink_to(Path(td) / ".." / "etc", target_is_directory=True)
            rc = run_cli(
                "analyze", "--csv", "examples/ring15.csv", "--bw", "256",
                "--summary-only", "--outdir", str(link), check=False,
            )
            self.assertNotEqual(rc.returncode, 0)

    def test_formula_injection_in_csv_escaped(self):
        from copyspace_guard.io import csv_safe_cell
        self.assertEqual(csv_safe_cell("=cmd"), "'=cmd")
        self.assertEqual(csv_safe_cell("+cmd"), "'+cmd")
        self.assertEqual(csv_safe_cell("-cmd"), "'-cmd")
        self.assertEqual(csv_safe_cell("@cmd"), "'@cmd")
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "nccl.log"
            log.write_text('rank 0 -> rank 1, bytes=100\n', encoding="utf-8")
            out = Path(td) / "demands.csv"
            rc = run_cli(
                "import-nccl-log", str(log),
                "--out", str(out), check=False,
            )
            self.assertEqual(rc.returncode, 0)
            content = out.read_text(encoding="utf-8")
            self.assertIn("src_slot,dst_slot,bits_total", content)

    def test_xxe_in_msccl_xml_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            bad_xml = Path(td) / "evil.xml"
            bad_xml.write_text(
                '<?xml version="1.0" encoding="utf-8"?>\n'
                '<!DOCTYPE foo [\n'
                '  <!ENTITY xxe SYSTEM "file:///etc/passwd">\n'
                ']>\n'
                '<algo><op tick="1" src="0" dst="1" len_bits="&xxe;"/></algo>',
                encoding="utf-8",
            )
            rc = run_cli("import-msccl", str(bad_xml), "--out", str(Path(td) / "x.json"), check=False)
            self.assertNotEqual(rc.returncode, 0)

    def test_max_rows_limit_enforced(self):
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "nccl.log"
            log.write_text('rank 0 -> rank 1, bytes=100\nrank 1 -> rank 2, bytes=200\n', encoding="utf-8")
            rc = run_cli(
                "import-nccl-log", str(log),
                "--max-rows", "1", "--out", str(Path(td) / "o.csv"), check=False,
            )
            self.assertNotEqual(rc.returncode, 0)
            self.assertIn("--max-rows", rc.stderr)

    def test_max_file_size_limit_enforced(self):
        with tempfile.TemporaryDirectory() as td:
            big = Path(td) / "big.log"
            big.write_text("rank 0 -> rank 1, bytes=8\n" * 10000, encoding="utf-8")
            rc = run_cli(
                "import-nccl-log", str(big),
                "--max-file-size", "100", "--out", str(Path(td) / "o.csv"), check=False,
            )
            self.assertNotEqual(rc.returncode, 0)
            self.assertIn("--max-file-size", rc.stderr)


class IntegrationCliTests(unittest.TestCase):
    def test_analyze_then_gate_full_workflow(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            rc = run_cli(
                "analyze", "--csv", "examples/ring15.csv", "--bw", "256",
                "--summary-only", "--outdir", str(out),
            )
            self.assertEqual(rc.returncode, 0)
            summary = out / "summary.json"
            rc2 = run_cli("gate", str(summary), check=False)
            self.assertEqual(rc2.returncode, 0)

    def test_analyze_then_gate_with_max_gap_rejects(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            rc = run_cli(
                "analyze", "--csv", "examples/ring15.csv", "--bw", "256",
                "--summary-only", "--outdir", str(out),
            )
            self.assertEqual(rc.returncode, 0)
            summary = out / "summary.json"
            rc2 = run_cli("gate", str(summary), "--report", "baseline", "--max-gap", "0.1", check=False)
            self.assertNotEqual(rc2.returncode, 0)

    def test_solver_plugin_works(self):
        with tempfile.TemporaryDirectory() as td:
            plugin = Path(td) / "plugin.py"
            plugin.write_text(
                "import json, sys\n"
                "inst = json.load(sys.stdin)\n"
                "slots = inst['slots']\n"
                "sched = {'version': 0, 'model': 'STRICT1', 'ticks': [[{'src_slot': 0, 'dst_slot': 1, 'len_bits': 100}]]}\n"
                "json.dump(sched, sys.stdout)\n",
                encoding="utf-8",
            )
            out = Path(td) / "audit"
            rc = run_cli(
                "audit", "--demands", "examples/ring15.csv", "--bw", "256",
                "--slots", "15", "--solver-plugin", str(plugin),
                "--outdir", str(out), check=False,
            )
            self.assertIn("customer_current", rc.stdout)
            report = json.loads((out / "report_customer_current.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "FAIL")

    def test_solver_plugin_timeout_respected(self):
        with tempfile.TemporaryDirectory() as td:
            plugin = Path(td) / "sleepy_plugin.py"
            plugin.write_text(
                "import json, sys, time\n"
                "inst = json.load(sys.stdin)\n"
                "time.sleep(999)\n",
                encoding="utf-8",
            )
            rc = run_cli(
                "audit", "--demands", "examples/ring15.csv", "--bw", "256",
                "--slots", "15", "--solver-plugin", str(plugin),
                "--solver-plugin-timeout", "1",
                "--outdir", str(Path(td) / "out"), check=False,
            )
            self.assertNotEqual(rc.returncode, 0)

    def test_solver_plugin_max_output_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            plugin = Path(td) / "chatty_plugin.py"
            plugin.write_text(
                "import json, sys\n"
                "inst = json.load(sys.stdin)\n"
                "sys.stdout.write('x' * 10000)\n",
                encoding="utf-8",
            )
            rc = run_cli(
                "audit", "--demands", "examples/ring15.csv", "--bw", "256",
                "--slots", "15", "--solver-plugin", str(plugin),
                "--solver-plugin-max-output-bytes", "100",
                "--outdir", str(Path(td) / "out"), check=False,
            )
            self.assertNotEqual(rc.returncode, 0)

    def test_infer_nccl_log_emits_runnable_command(self):
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "nccl.log"
            log.write_text("rank 0 -> rank 1, bytes=1048576\nrank 1 -> rank 2, bytes=1048576\n", encoding="utf-8")
            rc = run_cli("infer", str(log), check=False)
            self.assertEqual(rc.returncode, 0)
            self.assertIn("inferred:", rc.stdout)
            self.assertIn("--bw", rc.stdout)
            self.assertIn("--slots", rc.stdout)

    def test_infer_pytorch_trace_emits_runnable_command(self):
        import json as _json
        with tempfile.TemporaryDirectory() as td:
            trace = Path(td) / "trace.json"
            trace.write_text(
                _json.dumps({"traceEvents": [{"name": "ncclAllReduce", "args": {"bytes": 16, "ranks": [0, 1, 2]}}]}),
                encoding="utf-8",
            )
            rc = run_cli("infer", str(trace), check=False)
            self.assertEqual(rc.returncode, 0)
            self.assertIn("inferred:", rc.stdout)
            self.assertIn("slots=3", rc.stdout)

    def test_infer_with_out_writes_csv(self):
        import json as _json
        with tempfile.TemporaryDirectory() as td:
            trace = Path(td) / "trace.json"
            trace.write_text(
                _json.dumps({"traceEvents": [{"name": "ncclAllReduce", "args": {"bytes": 8, "ranks": [0, 1]}}]}),
                encoding="utf-8",
            )
            csv_out = Path(td) / "demands.csv"
            rc = run_cli("infer", str(trace), "--out", str(csv_out), check=False)
            self.assertEqual(rc.returncode, 0)
            self.assertTrue(csv_out.exists())
            self.assertIn("src_slot", csv_out.read_text(encoding="utf-8"))

    def test_anonymize_demands_roundtrip(self):
        import json as _json
        with tempfile.TemporaryDirectory() as td:
            csv_in = Path(td) / "in.csv"
            csv_in.write_text("src_slot,dst_slot,bits_total\n0,1,100\n2,3,200\n", encoding="utf-8")
            csv_out = Path(td) / "out.csv"
            map_out = Path(td) / "map.json"
            rc = run_cli(
                "anonymize", "--kind", "demands",
                "--csv", str(csv_in), "--out", str(csv_out),
                "--mapping", str(map_out), check=False,
            )
            self.assertEqual(rc.returncode, 0)
            self.assertTrue(csv_out.exists())
            mapping = _json.loads(map_out.read_text(encoding="utf-8"))
            self.assertEqual(len(mapping), 4)

    def test_anonymize_schedule_roundtrip(self):
        import json as _json
        with tempfile.TemporaryDirectory() as td:
            csv_in = Path(td) / "in.csv"
            csv_in.write_text("tick,src_slot,dst_slot,len_bits\n0,0,1,8\n", encoding="utf-8")
            csv_out = Path(td) / "out.csv"
            map_out = Path(td) / "map.json"
            rc = run_cli(
                "anonymize", "--kind", "schedule",
                "--csv", str(csv_in), "--out", str(csv_out),
                "--mapping", str(map_out), check=False,
            )
            self.assertEqual(rc.returncode, 0)
            self.assertTrue(csv_out.exists())
            mapping = _json.loads(map_out.read_text(encoding="utf-8"))
            self.assertEqual(len(mapping), 2)
