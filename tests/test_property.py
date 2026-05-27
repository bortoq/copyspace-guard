from __future__ import annotations

import unittest
from typing import Any

from copyspace_guard.core import (
    BOUNDS_REASON_AUTO_EXHAUSTIVE,
    BOUNDS_REASON_AUTO_PARTIAL,
    BOUNDS_REASON_EXACT_FRACTIONAL_MODE,
    BOUNDS_REASON_READ1_WRITE1_COMPLETE,
    exact_optimal_ticks,
    lower_bound_components,
    solve_greedy,
    validate_schedule,
)

try:
    from hypothesis import HealthCheck, assume, given, settings, strategies as st
except ImportError:  # pragma: no cover - exercised when hypothesis is absent locally
    st = None


if st is None:
    class PropertyTests(unittest.TestCase):
        @unittest.skip("hypothesis is not installed")
        def test_hypothesis_unavailable(self) -> None:
            pass
else:
    @st.composite
    def instance_strategy(draw: Any, *, max_slots: int = 5, max_demands: int = 6, max_bits: int = 4) -> dict[str, Any]:
        slots = draw(st.integers(min_value=2, max_value=max_slots))
        model = draw(st.sampled_from(["STRICT1", "READ1_WRITE1"]))
        bw = draw(st.integers(min_value=1, max_value=max_bits))
        demand_count = draw(st.integers(min_value=1, max_value=max_demands))
        demands: list[dict[str, int]] = []
        for _ in range(demand_count):
            src = draw(st.integers(min_value=0, max_value=slots - 1))
            dst = draw(st.integers(min_value=0, max_value=slots - 2))
            if dst >= src:
                dst += 1
            bits = draw(st.integers(min_value=1, max_value=bw * 2))
            demands.append({"src_slot": src, "dst_slot": dst, "bits_total": bits})
        return {
            "version": 0,
            "model": model,
            "slots": slots,
            "copy_bw_bits_per_tick": bw,
            "demands": demands,
        }


    class PropertyTests(unittest.TestCase):
        @settings(max_examples=75, deadline=None, suppress_health_check=[HealthCheck.too_slow])
        @given(instance_strategy())
        def test_greedy_schedule_valid_for_generated_instances(self, inst: dict[str, Any]) -> None:
            rep = validate_schedule(inst, solve_greedy(inst))
            self.assertEqual(rep.status, "PASS", rep.errors)
            self.assertLessEqual(rep.lower_bound_ticks, rep.ticks_total)

        @settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
        @given(instance_strategy(max_slots=4, max_demands=4, max_bits=3))
        def test_exact_oracle_bounds_greedy_on_tiny_instances(self, inst: dict[str, Any]) -> None:
            bw = int(inst["copy_bw_bits_per_tick"])
            total_chunks = sum((int(d["bits_total"]) + bw - 1) // bw for d in inst["demands"])
            assume(total_chunks <= 8)
            rep = validate_schedule(inst, solve_greedy(inst))
            opt = exact_optimal_ticks(inst, max_chunks=16)
            lbs = lower_bound_components(inst)
            self.assertLessEqual(lbs["lower_bound_ticks"], opt)
            self.assertLessEqual(opt, rep.ticks_total)

        @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
        @given(instance_strategy(max_slots=40, max_demands=20, max_bits=8))
        def test_large_strict1_lower_bound_not_above_greedy(self, inst: dict[str, Any]) -> None:
            assume(int(inst["slots"]) > 24)
            assume(inst["model"] == "STRICT1")
            rep = validate_schedule(inst, solve_greedy(inst))
            lbs = lower_bound_components(inst)
            self.assertLessEqual(lbs["lower_bound_ticks"], rep.ticks_total)

        @settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
        @given(instance_strategy(max_slots=50, max_demands=20, max_bits=8))
        def test_bounds_witness_deterministic(self, inst: dict[str, Any]) -> None:
            assume(int(inst["slots"]) > 24)
            assume(inst["model"] == "STRICT1")
            lbs1 = lower_bound_components(inst)
            lbs2 = lower_bound_components(inst)
            self.assertEqual(lbs1["lower_bound_witness"], lbs2["lower_bound_witness"])
            self.assertEqual(lbs1["lower_bound_ticks"], lbs2["lower_bound_ticks"])

        @settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
        @given(instance_strategy(max_slots=50, max_demands=20, max_bits=8))
        def test_reason_complete_invariant_auto_mode(self, inst: dict[str, Any]) -> None:
            expected = {
                BOUNDS_REASON_AUTO_EXHAUSTIVE: True,
                BOUNDS_REASON_AUTO_PARTIAL: False,
                BOUNDS_REASON_READ1_WRITE1_COMPLETE: True,
            }
            lbs = lower_bound_components(inst, strict1_bounds_mode="auto")
            self.assertEqual(lbs["bounds_complete"], expected[lbs["bounds_complete_reason"]])

        @settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
        @given(instance_strategy(max_slots=24, max_demands=16, max_bits=8))
        def test_reason_complete_invariant_fractional_exact_mode(self, inst: dict[str, Any]) -> None:
            assume(inst["model"] == "STRICT1")
            lbs = lower_bound_components(inst, strict1_bounds_mode="fractional_exact")
            self.assertEqual(lbs["bounds_complete_reason"], BOUNDS_REASON_EXACT_FRACTIONAL_MODE)
            self.assertTrue(lbs["bounds_complete"])


if __name__ == "__main__":
    unittest.main()
