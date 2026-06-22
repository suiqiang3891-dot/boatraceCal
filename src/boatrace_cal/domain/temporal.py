"""Prediction-time availability contracts."""

from dataclasses import dataclass
from datetime import datetime


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class AvailableRecord:
    """A record whose use is constrained by its prediction-time availability."""

    available_at: datetime

    def __post_init__(self) -> None:
        _require_aware(self.available_at, "available_at")

    def assert_usable_at(self, as_of: datetime) -> None:
        """Raise when this record was not available at the prediction time."""
        _require_aware(as_of, "as_of")
        if self.available_at > as_of:
            raise ValueError("record is not available at the prediction time")
