"""Copy-Space Guard: deterministic data-movement audit and CI gate."""

__version__ = "0.2.5"

from .core import (  # noqa: F401
    BOUNDS_REASON_AUTO_EXHAUSTIVE,
    BOUNDS_REASON_AUTO_PARTIAL,
    BOUNDS_REASON_EXACT_FRACTIONAL_MODE,
    BOUNDS_REASON_READ1_WRITE1_COMPLETE,
)

__all__ = [
    "__version__",
    "BOUNDS_REASON_AUTO_EXHAUSTIVE",
    "BOUNDS_REASON_AUTO_PARTIAL",
    "BOUNDS_REASON_EXACT_FRACTIONAL_MODE",
    "BOUNDS_REASON_READ1_WRITE1_COMPLETE",
]
