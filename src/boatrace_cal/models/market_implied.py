"""Market-implied probability baseline from pre-race odds snapshots."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId
from boatrace_cal.ingestion.odds import OddsSnapshotRecord, latest_odds_by_combination


@dataclass(frozen=True, slots=True)
class MarketImpliedProbability:
    """Probability assigned to one combination by normalized inverse odds."""

    combination: BetCombination
    probability: Decimal
    odds: Decimal

    def __post_init__(self) -> None:
        if type(self.combination) is not BetCombination:
            raise TypeError("combination must be a BetCombination")
        if type(self.probability) is not Decimal or not self.probability.is_finite():
            raise TypeError("probability must be a finite Decimal")
        if not Decimal("0") <= self.probability <= Decimal("1"):
            raise ValueError("probability must be between 0 and 1")
        if type(self.odds) is not Decimal or not self.odds.is_finite():
            raise TypeError("odds must be a finite Decimal")
        if self.odds <= Decimal("0"):
            raise ValueError("odds must be positive")


@dataclass(frozen=True, slots=True)
class MarketImpliedModel:
    """Market baseline fitted from latest available odds for one race."""

    race_id: RaceId
    bet_type: BetType
    as_of: datetime
    snapshot_count: int
    probabilities: tuple[MarketImpliedProbability, ...]

    def __post_init__(self) -> None:
        if type(self.race_id) is not RaceId:
            raise TypeError("race_id must be a RaceId")
        if type(self.bet_type) is not BetType:
            raise TypeError("bet_type must be a BetType")
        _require_aware_datetime(self.as_of, "as_of")
        if type(self.snapshot_count) is not int or self.snapshot_count < 0:
            raise ValueError("snapshot_count must be a non-negative integer")
        if type(self.probabilities) is not tuple or any(
            type(item) is not MarketImpliedProbability for item in self.probabilities
        ):
            raise TypeError("probabilities must be a tuple of MarketImpliedProbability")
        if len(self.probabilities) != self.snapshot_count:
            raise ValueError("snapshot_count must match probabilities length")
        if any(item.combination.bet_type is not self.bet_type for item in self.probabilities):
            raise ValueError("all combinations must match bet_type")

    def probability_for(self, combination: BetCombination) -> Decimal:
        """Return probability for one market combination."""

        if type(combination) is not BetCombination:
            raise TypeError("combination must be a BetCombination")
        probabilities_by_lanes = {
            item.combination.lanes: item.probability for item in self.probabilities
        }
        return probabilities_by_lanes[combination.lanes]


def build_market_implied_model(
    odds: Iterable[OddsSnapshotRecord],
    *,
    race_id: RaceId,
    bet_type: BetType,
    as_of: datetime,
) -> MarketImpliedModel:
    """Build a normalized market-implied probability baseline for one race."""

    if type(race_id) is not RaceId:
        raise TypeError("race_id must be a RaceId")
    if type(bet_type) is not BetType:
        raise TypeError("bet_type must be a BetType")
    _require_aware_datetime(as_of, "as_of")

    latest = tuple(
        record
        for combination, record in latest_odds_by_combination(odds, race_id, as_of).items()
        if combination.bet_type is bet_type
    )
    if not latest:
        raise ValueError("market implied model requires available odds")

    implied_values = tuple((record, Decimal("1") / record.odds) for record in latest)
    denominator = sum((value for _, value in implied_values), start=Decimal("0"))
    probabilities = tuple(
        MarketImpliedProbability(
            combination=record.combination,
            probability=implied_value / denominator,
            odds=record.odds,
        )
        for record, implied_value in implied_values
    )
    return MarketImpliedModel(
        race_id=race_id,
        bet_type=bet_type,
        as_of=as_of,
        snapshot_count=len(probabilities),
        probabilities=probabilities,
    )


def _require_aware_datetime(value: datetime, name: str) -> None:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
