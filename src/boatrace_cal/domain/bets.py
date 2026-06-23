"""Canonical settlement types and lane combinations for bets."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class BetType(StrEnum):
    """Supported bet settlement types."""

    TRIFECTA_ORDERED = "trifecta_ordered"
    TRIFECTA_BOX = "trifecta_box"
    EXACTA_ORDERED = "exacta_ordered"
    EXACTA_BOX = "exacta_box"
    WIDE_BOX = "wide_box"

    @property
    def lane_count(self) -> int:
        return 3 if self in {self.TRIFECTA_ORDERED, self.TRIFECTA_BOX} else 2

    @property
    def ordered(self) -> bool:
        return self in {self.TRIFECTA_ORDERED, self.EXACTA_ORDERED}


@dataclass(frozen=True, slots=True)
class BetCombination:
    """Validated and normalized lane combination for one settlement type."""

    bet_type: BetType
    lanes: tuple[int, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.bet_type, BetType):
            raise ValueError("bet type must be a BetType")
        if isinstance(self.lanes, (str, bytes, bytearray)):
            raise ValueError("bet lanes must be an iterable of integers")
        try:
            lanes = tuple(self.lanes)
        except TypeError as exc:
            raise ValueError("bet lanes must be an iterable of integers") from exc
        object.__setattr__(self, "lanes", lanes)
        if len(self.lanes) != self.bet_type.lane_count:
            raise ValueError(f"{self.bet_type} requires {self.bet_type.lane_count} lanes")
        if any(type(lane) is not int for lane in self.lanes):
            raise ValueError("bet lanes must be integers")
        if len(set(self.lanes)) != len(self.lanes):
            raise ValueError("bet lanes must be unique")
        if any(not 1 <= lane <= 6 for lane in self.lanes):
            raise ValueError("bet lanes must be between 1 and 6")
        if not self.bet_type.ordered:
            object.__setattr__(self, "lanes", tuple(sorted(self.lanes)))

    @classmethod
    def create(cls, bet_type: BetType, lanes: Iterable[int]) -> "BetCombination":
        return cls(bet_type=bet_type, lanes=lanes)  # type: ignore[arg-type]

    @property
    def key(self) -> str:
        return "-".join(str(lane) for lane in self.lanes)
