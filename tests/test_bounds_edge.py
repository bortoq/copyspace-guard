from __future__ import annotations

import unittest
from pathlib import Path

from copyspace_guard.core import (
    lower_bound_components,
    solve_baseline,
    solve_greedy,
    validate_schedule,
)

ROOT = Path(__file__).resolve().parents[1]


def _make_inst(
    slots: int = 4,
    bw: int = 1024,
    demands: list[tuple[int, int, int]] | None = None,
    model: str = "STRICT1",
) -> dict:
    if demands is None:
        demands = [(0, 1, 100)]
    return {
        "version": 0,
        "model": model,
        "slots": slots,
        "copy_bw_bits_per_tick": bw,
        "demands": [{"src_slot": s, "dst_slot": d, "bits_total": b} for s, d, b in demands],
    }


class BoundsEdgeTests(unittest.TestCase):
    def test_slots_zero_raises(self):
        inst = _make_inst(slots=0, demands=[(0, 1, 100)])
        with self.assertRaises(ValueError):
            lower_bound_components(inst)

    def test_slots_one_handled(self):
        inst = _make_inst(slots=1, demands=[])
        lbs = lower_bound_components(inst)
        self.assertGreaterEqual(lbs["lower_bound_ticks"], 0)

    def test_empty_demands_handled(self):
        inst = _make_inst(slots=4, demands=[])
        lbs = lower_bound_components(inst)
        self.assertGreaterEqual(lbs["lower_bound_ticks"], 0)

    def test_self_loop_demands_rejected_by_validation(self):
        inst = _make_inst(slots=4, demands=[(0, 0, 100), (1, 1, 200)])
        with self.assertRaises(ValueError):
            from copyspace_guard.io import validate_instance
            validate_instance(inst)

    def test_duplicate_demands_sum(self):
        inst = _make_inst(slots=4, demands=[(0, 1, 100), (0, 1, 50), (0, 1, 25)])
        lbs = lower_bound_components(inst)
        self.assertGreater(lbs["lower_bound_ticks"], 0)

    def test_large_bits_value_does_not_overflow(self):
        inst = _make_inst(slots=4, demands=[(0, 1, 10**15), (2, 3, 10**15)])
        lbs = lower_bound_components(inst)
        self.assertGreater(lbs["lower_bound_ticks"], 0)

    def test_very_large_slot_count_does_not_hang(self):
        inst = _make_inst(slots=256, demands=[(i, (i + 1) % 256, 100) for i in range(256)])
        lbs = lower_bound_components(inst)
        self.assertGreater(lbs["lower_bound_ticks"], 0)

    def test_bounds_non_negative_all_components(self):
        inst = _make_inst(slots=4, demands=[(0, 1, 50), (1, 2, 100), (2, 3, 75)])
        lbs = lower_bound_components(inst)
        self.assertGreaterEqual(lbs["degree_lower_bound"], 0)
        self.assertGreaterEqual(lbs["capacity_lower_bound"], 0)
        self.assertGreaterEqual(lbs["density_lower_bound"], 0)
        self.assertGreaterEqual(lbs["lower_bound_ticks"], 0)

    def test_read1_write1_single_slot(self):
        inst = _make_inst(slots=1, demands=[], model="READ1_WRITE1")
        lbs = lower_bound_components(inst)
        self.assertGreaterEqual(lbs["lower_bound_ticks"], 0)
        lbs = lower_bound_components(inst)
        self.assertGreaterEqual(lbs["lower_bound_ticks"], 0)

    def test_lower_bound_monotonic_with_demands(self):
        base = [(0, 1, 100), (2, 3, 100)]
        larger = base + [(1, 2, 100)]
        inst_base = _make_inst(slots=4, demands=base)
        inst_larger = _make_inst(slots=4, demands=larger)
        lbs_base = lower_bound_components(inst_base)
        lbs_larger = lower_bound_components(inst_larger)
        self.assertGreaterEqual(lbs_larger["lower_bound_ticks"], lbs_base["lower_bound_ticks"])

    def test_greedy_ticks_at_least_lower_bound(self):
        inst = _make_inst(slots=4, demands=[(0, 1, 100), (1, 2, 200), (2, 3, 150)])
        sched = solve_greedy(inst)
        rep = validate_schedule(inst, sched)
        lbs = lower_bound_components(inst)
        self.assertGreaterEqual(rep.ticks_total, lbs["lower_bound_ticks"])

    def test_schedule_valid_on_ring_instance(self):
        inst = _make_inst(slots=6, demands=[(i, (i + 1) % 6, 64) for i in range(6)])
        sched = solve_greedy(inst)
        rep = validate_schedule(inst, sched)
        self.assertEqual(rep.status, "PASS")

    def test_baseline_schedule_is_valid(self):
        inst = _make_inst(slots=4, demands=[(0, 1, 100), (1, 2, 200), (2, 3, 150)])
        sched = solve_baseline(inst)
        rep = validate_schedule(inst, sched)
        self.assertEqual(rep.status, "PASS")

    def test_bounds_with_single_demand(self):
        inst = _make_inst(slots=16, demands=[(0, 1, 1024)])
        lbs = lower_bound_components(inst)
        self.assertEqual(lbs["lower_bound_ticks"], 1)

    def test_bounds_with_max_slot_demands(self):
        demands = [(i, (i + 1) % 24, 100) for i in range(24)]
        inst = _make_inst(slots=24, demands=demands)
        lbs = lower_bound_components(inst)
        self.assertGreater(lbs["lower_bound_ticks"], 0)

    def test_bounds_exhaustive_limit_cap(self):
        inst = _make_inst(slots=8, demands=[(0, 1, 100), (2, 3, 100), (4, 5, 100)])
        lbs = lower_bound_components(inst)
        self.assertGreater(lbs["lower_bound_ticks"], 0)

    def test_bounds_component_consistency(self):
        inst = _make_inst(slots=6, demands=[(0, 1, 50), (2, 3, 100), (4, 5, 75)])
        lbs = lower_bound_components(inst)
        self.assertEqual(lbs["lower_bound_ticks"], max(lbs["degree_lower_bound"], lbs["capacity_lower_bound"], lbs["density_lower_bound"]))

    def test_fractional_odd_subset_mode_edge_slots(self):
        from copyspace_guard.core import lower_bound_components
        for n in [3, 5, 7, 9, 23]:
            inst = _make_inst(slots=n, demands=[(i, (i + 1) % n, 100) for i in range(n)])
            lbs = lower_bound_components(inst)
            self.assertGreaterEqual(lbs["lower_bound_ticks"], 0)


if __name__ == "__main__":
    unittest.main()
