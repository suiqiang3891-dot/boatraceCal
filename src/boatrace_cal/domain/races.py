"""Canonical identifiers for venues and races."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class VenueCode:
    """Official BOAT RACE venue code."""

    value: str

    def __post_init__(self) -> None:
        if (
            not self.value.isascii()
            or not self.value.isdigit()
            or len(self.value) > 2
            or not 1 <= int(self.value) <= 24
        ):
            raise ValueError("venue code must be between 01 and 24")
        object.__setattr__(self, "value", self.value.zfill(2))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class RaceId:
    """Canonical identity of a race on a given date."""

    race_date: date
    venue: VenueCode
    race_no: int

    def __post_init__(self) -> None:
        if not 1 <= self.race_no <= 12:
            raise ValueError("race number must be between 1 and 12")

    def __str__(self) -> str:
        return f"{self.race_date:%Y%m%d}-{self.venue}-{self.race_no:02d}"
