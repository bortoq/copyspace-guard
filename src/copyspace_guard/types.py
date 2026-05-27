from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

STRICT1 = "STRICT1"
READ1_WRITE1 = "READ1_WRITE1"
MODELS = {STRICT1, READ1_WRITE1}
MODEL = STRICT1  # backward-compatible default model name

Demand = Dict[str, int]
Chunk = Dict[str, int]
Schedule = Dict[str, Any]
Instance = Dict[str, Any]


@dataclass(frozen=True)
class Report:
    status: str
    version: int
    model: str
    errors: List[Dict[str, Any]]
    ticks_total: int = 0
    bits_total: int = 0
    bits_per_tick: float = 0.0
    expected_bits_per_tick: int = 0
    utilization: float = 0.0
    degree_lower_bound: int = 0
    capacity_lower_bound: int = 0
    density_lower_bound: int = 0
    max_degree_chunks: int = 0  # v0 compatibility; equals degree_lower_bound
    lower_bound_ticks: int = 0
    gap_ticks: int = 0
    gap_to_lower_bound: float = 0.0
    gap_reliability: str | None = None
    gap_practical: float | None = None
    lower_bound_witness: Dict[str, Any] = field(default_factory=dict)
    bounds_complete: bool = True
    bounds_mode: str | None = None
    bounds_complete_reason: str | None = None
    bounds_exhaustive_subset_limit: int | None = None
    total_errors: int = 0
    errors_truncated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
