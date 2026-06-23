"""Prediction-time availability contracts."""

from dataclasses import dataclass
from datetime import datetime, timezone


def _require_aware(value: object, name: str) -> None:
    if type(value) is not datetime:
        raise ValueError(f"{name} must be a datetime")
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
        available_at_utc = self.available_at.astimezone(timezone.utc)
        as_of_utc = as_of.astimezone(timezone.utc)
        if available_at_utc > as_of_utc:
            raise ValueError("record is not available at the prediction time")
