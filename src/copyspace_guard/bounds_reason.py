from __future__ import annotations

from enum import Enum


class BoundsReason(str, Enum):
    AUTO_EXHAUSTIVE = "auto_exhaustive"
    AUTO_PARTIAL = "auto_partial"
    FRACTIONAL_ODD_SUBSET = "fractional_odd_subset"
    FRACTIONAL_HEURISTIC_PARTIAL = "fractional_heuristic_partial"
    READ1_WRITE1_COMPLETE = "read1_write1_complete"
