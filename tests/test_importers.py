from __future__ import annotations

import json
import sys
import tempfile
import unittest
from xml.parsers.expat import ExpatError
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from copyspace_guard.importers import _schedule_from_rows, import_csv_with_map, import_msccl_xml, import_taccl_json  # noqa: E402
from copyspace_guard.importers import import_nccl_log_demands, import_pytorch_trace_demands  # noqa: E402


class ImportersTests(unittest.TestCase):
    def test_import_csv_with_map_happy_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "ok.csv"
            p.write_text("step,from,to,bits\n0,0,1,8\n1,1,2,4\n", encoding="utf-8")
            sched = import_csv_with_map(p, tick="step", src="from", dst="to", length="bits")
            self.assertEqual(sched["ticks"][0][0]["src_slot"], 0)
            self.assertEqual(sched["ticks"][0][0]["len_bits"], 8)

    def test_import_taccl_json_happy_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "ok.json"
            p.write_text(json.dumps({"ops": [{"step": 0, "from": 0, "to": 1, "bits": 8}, {"step": 1, "from": 1, "to": 2, "bits": 4}]}), encoding="utf-8")
            sched = import_taccl_json(p)
            self.assertEqual(sched["version"], 0)
            self.assertEqual(sched["ticks"][0][0]["src_slot"], 0)
            self.assertEqual(sched["ticks"][1][0]["dst_slot"], 2)

    def test_import_taccl_json_custom_model(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "ok.json"
            p.write_text(json.dumps({"ops": [{"step": 0, "from": 0, "to": 1, "bits": 8}]}), encoding="utf-8")
            sched = import_taccl_json(p, model="READ1_WRITE1")
            self.assertEqual(sched["model"], "READ1_WRITE1")

    def test_import_msccl_xml_happy_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "ok.xml"
            p.write_text("<algorithm><op step='0' src='0' dst='1' cnt='8'/><op step='1' src='1' dst='2' cnt='4'/></algorithm>", encoding="utf-8")
            sched = import_msccl_xml(p)
            self.assertEqual(sched["version"], 0)
            self.assertEqual(sched["ticks"][0][0]["len_bits"], 8)
            self.assertEqual(sched["ticks"][1][0]["src_slot"], 1)

    def test_import_csv_with_map_errors(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "custom.csv"
            p.write_text("step,from,to,bits\n0,0,1,8\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing CSV columns"):
                import_csv_with_map(p, tick="tick", src="from", dst="to", length="bits")

    def test_import_taccl_json_empty_or_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            empty = root / "empty.json"
            empty.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "no schedule rows found"):
                import_taccl_json(empty)

            bad = root / "bad.json"
            bad.write_text("{", encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                import_taccl_json(bad)

    def test_import_msccl_xml_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bad = root / "bad.xml"
            bad.write_text("<algo><op></algo>", encoding="utf-8")
            with self.assertRaises(ExpatError):
                import_msccl_xml(bad)

    def test_importers_limits(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_path = root / "custom.csv"
            csv_path.write_text("step,from,to,bits\n0,0,1,8\n1,1,2,8\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "--max-rows"):
                import_csv_with_map(csv_path, tick="step", src="from", dst="to", length="bits", max_rows=1)
            with self.assertRaisesRegex(ValueError, "--max-file-size"):
                import_csv_with_map(csv_path, tick="step", src="from", dst="to", length="bits", max_file_size=1)

            xml_path = root / "algo.xml"
            xml_path.write_text("<algo><op step='0' src='0' dst='1' cnt='1'/><op step='1' src='1' dst='2' cnt='1'/></algo>", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "--max-rows"):
                import_msccl_xml(xml_path, max_rows=1)

            json_path = root / "taccl.json"
            json_path.write_text(json.dumps({"ops": [{"step": 0, "from": 0, "to": 1, "bits": 1}, {"step": 1, "from": 1, "to": 2, "bits": 1}]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "--max-rows"):
                import_taccl_json(json_path, max_rows=1)

    def test_schedule_from_rows_sorts_ticks(self) -> None:
        sched = _schedule_from_rows([(2, 1, 2, 4), (0, 0, 1, 8)])
        self.assertEqual(sched["ticks"][0][0]["src_slot"], 0)
        self.assertEqual(len(sched["ticks"]), 3)
        self.assertEqual(sched["ticks"][1], [])
        self.assertEqual(sched["version"], 0)

    def test_import_nccl_log_demands(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "nccl.log"
            p.write_text(
                "ring: rank 0 -> rank 1, bytes=4\n"
                "ring: rank 1 -> rank 2, bytes=8\n"
                "ring: rank 0 -> rank 1, bytes=2\n",
                encoding="utf-8",
            )
            rows = import_nccl_log_demands(p)
            self.assertEqual(rows, [(0, 1, 48), (1, 2, 64)])

    def test_import_pytorch_trace_demands(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "trace.json"
            p.write_text(
                json.dumps(
                    {
                        "traceEvents": [
                            {"name": "ncclAllReduce", "args": {"bytes": 16, "ranks": [0, 1, 2]}},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            rows = import_pytorch_trace_demands(p)
            self.assertEqual(rows, [(0, 1, 128), (0, 2, 128), (1, 2, 128)])


if __name__ == "__main__":
    unittest.main()
