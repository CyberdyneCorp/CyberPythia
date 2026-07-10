"""Readiness gate time-series snapshot (spec: engineering-intelligence)."""

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

# Gate ordering for regression detection: a drop to a lower rank is a regression.
GATE_RANK = {"MVP": 0, "READY": 1, "DONE": 2}


@dataclass(frozen=True, slots=True)
class ReadinessSnapshot:
    repository_id: UUID
    captured_on: date  # one row per repository per UTC day
    captured_at: datetime
    gate: str  # MVP | READY | DONE
