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

    @classmethod
    def create(cls, bet_type: BetType, lanes: Iterable[int]) -> "BetCombination":
        materialized_lanes = tuple(lanes)
        if len(materialized_lanes) != bet_type.lane_count:
            raise ValueError(f"{bet_type} requires {bet_type.lane_count} lanes")
        if len(set(materialized_lanes)) != len(materialized_lanes):
            raise ValueError("bet lanes must be unique")
        if any(not 1 <= lane <= 6 for lane in materialized_lanes):
            raise ValueError("bet lanes must be between 1 and 6")
        if not bet_type.ordered:
            materialized_lanes = tuple(sorted(materialized_lanes))
        return cls(bet_type=bet_type, lanes=materialized_lanes)

    @property
    def key(self) -> str:
        return "-".join(str(lane) for lane in self.lanes)
