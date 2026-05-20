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
    def test_summary_only_does_not_emit_schedules(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            run_cli("analyze", "--csv", "examples/ring15.csv", "--bw", "256", "--roi", "examples/roi.yml", "--summary-only", "--outdir", str(out))
            self.assertTrue((out / "summary.json").exists())
            self.assertTrue((out / "report.md").exists())
            self.assertFalse((out / "schedule_greedy.json").exists())
            data = json.loads((out / "summary.json").read_text())
            self.assertEqual(data["reports"]["greedy"]["gap_ticks"], 0)

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

    def test_anonymize_schedule(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "sched.csv"
            mapping = Path(td) / "mapping.json"
            run_cli("anonymize", "--kind", "schedule", "--csv", "examples/demo_bad_current_schedule.csv", "--out", str(out), "--mapping", str(mapping))
            self.assertTrue(out.exists())
            self.assertTrue(mapping.exists())


if __name__ == "__main__":
    unittest.main()
