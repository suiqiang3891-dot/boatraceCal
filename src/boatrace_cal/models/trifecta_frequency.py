"""Smoothed historical frequency baseline for ordered trifecta combinations."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from itertools import permutations

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.ingestion.results import RaceResultRecord


@dataclass(frozen=True, slots=True)
class TrifectaProbability:
    """Probability assigned to one ordered trifecta combination."""

    combination: BetCombination
    probability: Decimal

    def __post_init__(self) -> None:
        if type(self.combination) is not BetCombination:
            raise TypeError("combination must be a BetCombination")
        if self.combination.bet_type is not BetType.TRIFECTA_ORDERED:
            raise ValueError("combination must be trifecta_ordered")
        if type(self.probability) is not Decimal or not self.probability.is_finite():
            raise TypeError("probability must be a finite Decimal")
        if not Decimal("0") <= self.probability <= Decimal("1"):
            raise ValueError("probability must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class TrifectaFrequencyModel:
    """Fitted frequency model with a probability for every ordered trifecta."""

    as_of: datetime
    smoothing: Decimal
    training_race_count: int
    probabilities: tuple[TrifectaProbability, ...]

    def __post_init__(self) -> None:
        _require_aware_datetime(self.as_of, "as_of")
        _require_positive_decimal(self.smoothing, "smoothing")
        if type(self.training_race_count) is not int or self.training_race_count < 0:
            raise ValueError("training_race_count must be a non-negative integer")
        if type(self.probabilities) is not tuple or any(
            type(item) is not TrifectaProbability for item in self.probabilities
        ):
            raise TypeError("probabilities must be a tuple of TrifectaProbability")
        if len(self.probabilities) != 120:
            raise ValueError("probabilities must cover 120 ordered trifecta combinations")

    def probability_for(self, combination: BetCombination) -> Decimal:
        """Return probability for one ordered trifecta combination."""

        if type(combination) is not BetCombination:
            raise TypeError("combination must be a BetCombination")
        if combination.bet_type is not BetType.TRIFECTA_ORDERED:
            raise ValueError("combination must be trifecta_ordered")
        probabilities_by_key = {
            item.combination.lanes: item.probability for item in self.probabilities
        }
        return probabilities_by_key[combination.lanes]


def fit_trifecta_frequency_model(
    results: Iterable[RaceResultRecord],
    *,
    as_of: datetime,
    smoothing: Decimal = Decimal("1"),
) -> TrifectaFrequencyModel:
    """Fit a smoothed lane-order frequency model using only then-available results."""

    _require_aware_datetime(as_of, "as_of")
    _require_positive_decimal(smoothing, "smoothing")
    counts = {combination.lanes: smoothing for combination in _all_trifecta_combinations()}
    training_race_count = 0

    for result in results:
        if type(result) is not RaceResultRecord:
            raise TypeError("results must contain only RaceResultRecord instances")
        if result.available_at > as_of:
            continue
        training_race_count += 1
        counts[result.finish_order] += Decimal("1")

    denominator = sum(counts.values())
    probabilities = tuple(
        TrifectaProbability(
            combination=combination,
            probability=counts[combination.lanes] / denominator,
        )
        for combination in _all_trifecta_combinations()
    )
    return TrifectaFrequencyModel(
        as_of=as_of,
        smoothing=smoothing,
        training_race_count=training_race_count,
        probabilities=probabilities,
    )


def _all_trifecta_combinations() -> tuple[BetCombination, ...]:
    return tuple(
        BetCombination(BetType.TRIFECTA_ORDERED, lanes)
        for lanes in permutations((1, 2, 3, 4, 5, 6), 3)
    )


def _require_aware_datetime(value: datetime, name: str) -> None:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _require_positive_decimal(value: Decimal, name: str) -> None:
    if type(value) is not Decimal or not value.is_finite():
        raise ValueError(f"{name} must be a finite Decimal")
    if value <= Decimal("0"):
        raise ValueError(f"{name} must be positive")
