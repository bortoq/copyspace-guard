from __future__ import annotations

from enum import Enum


class BoundsReason(str, Enum):
    AUTO_EXHAUSTIVE = "auto_exhaustive"
    AUTO_PARTIAL = "auto_partial"
    EXACT_FRACTIONAL_MODE = "exact_fractional_mode"
    FRACTIONAL_HEURISTIC_PARTIAL = "fractional_heuristic_partial"
    READ1_WRITE1_COMPLETE = "read1_write1_complete"
