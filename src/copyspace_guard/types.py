from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

MODEL = "STRICT1"

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
    lower_bound_witness: Dict[str, Any] = field(default_factory=dict)
    bounds_complete: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
