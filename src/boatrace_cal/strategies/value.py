"""Conservative value gates for fixed-unit paper recommendations."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from boatrace_cal.domain.bets import BetCombination
from boatrace_cal.domain.races import RaceId
from boatrace_cal.domain.recommendations import (
    ConfidenceLevel,
    Decision,
    PlanStage,
    Recommendation,
)
from boatrace_cal.domain.versions import ArtifactVersions


@dataclass(frozen=True, slots=True)
class ValueStrategyConfig:
    """Thresholds for the first fixed-unit SELECT/PASS strategy."""

    min_probability: Decimal = Decimal("0")
    min_expected_value: Decimal = Decimal("0")
    conservative_margin: Decimal = Decimal("0.05")
    min_conservative_expected_value: Decimal = Decimal("0")
    max_odds: Decimal | None = None

    def __post_init__(self) -> None:
        _require_probability(self.min_probability, "min_probability")
        _require_decimal(self.min_expected_value, "min_expected_value")
        _require_non_negative_decimal(self.conservative_margin, "conservative_margin")
        _require_decimal(
            self.min_conservative_expected_value,
            "min_conservative_expected_value",
        )
        if self.max_odds is not None:
            _require_positive_decimal(self.max_odds, "max_odds")


@dataclass(frozen=True, slots=True)
class StrategyCandidate:
    """One model probability plus optional market odds for strategy evaluation."""

    recommendation_id: str
    race_id: RaceId
    combination: BetCombination
    probability: Decimal
    odds: Decimal | None
    confidence: ConfidenceLevel
    as_of: datetime
    versions: ArtifactVersions
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.recommendation_id) is not str:
            raise ValueError("recommendation id must be a string")
        recommendation_id = self.recommendation_id.strip()
        if not recommendation_id:
            raise ValueError("recommendation id must not be empty")
        object.__setattr__(self, "recommendation_id", recommendation_id)

        if type(self.race_id) is not RaceId:
            raise ValueError("race id must be a RaceId")
        if type(self.combination) is not BetCombination:
            raise ValueError("combination must be a BetCombination")
        if type(self.confidence) is not ConfidenceLevel:
            raise ValueError("confidence must be a ConfidenceLevel")
        if type(self.versions) is not ArtifactVersions:
            raise ValueError("versions must be ArtifactVersions")
        if type(self.as_of) is not datetime:
            raise ValueError("as_of must be a datetime")
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        if type(self.reason_codes) is not tuple or any(
            type(reason) is not str for reason in self.reason_codes
        ):
            raise ValueError("reason codes must be a tuple of strings")
        normalized_reasons = tuple(reason.strip() for reason in self.reason_codes)
        if any(not reason for reason in normalized_reasons):
            raise ValueError("reason codes must not contain empty values")
        object.__setattr__(self, "reason_codes", normalized_reasons)

        _require_probability(self.probability, "probability")
        if self.odds is not None:
            _require_positive_decimal(self.odds, "odds")


def implied_probability(odds: Decimal) -> Decimal:
    """Return the market implied probability for decimal odds."""

    _require_positive_decimal(odds, "odds")
    return Decimal("1") / odds


def expected_value(probability: Decimal, odds: Decimal) -> Decimal:
    """Return expected value per one unit stake."""

    _require_probability(probability, "probability")
    _require_positive_decimal(odds, "odds")
    return probability * odds - Decimal("1")


def conservative_expected_value(value: Decimal, margin: Decimal) -> Decimal:
    """Apply a fixed haircut to expected value before selecting."""

    _require_decimal(value, "expected_value")
    _require_non_negative_decimal(margin, "conservative_margin")
    return value - margin


def build_value_recommendation(
    candidate: StrategyCandidate,
    config: ValueStrategyConfig | None = None,
) -> Recommendation:
    """Build a final fixed-unit recommendation from model probability and odds."""

    if type(candidate) is not StrategyCandidate:
        raise TypeError("candidate must be a StrategyCandidate")
    strategy_config = ValueStrategyConfig() if config is None else config
    if type(strategy_config) is not ValueStrategyConfig:
        raise TypeError("config must be a ValueStrategyConfig")

    if candidate.odds is None:
        return _recommendation(
            candidate,
            decision=Decision.PASS,
            odds=None,
            ev=None,
            reason_codes=_reasons(candidate, "odds_unavailable"),
        )

    ev = expected_value(candidate.probability, candidate.odds)
    conservative_ev = conservative_expected_value(ev, strategy_config.conservative_margin)

    if strategy_config.max_odds is not None and candidate.odds > strategy_config.max_odds:
        return _pass_with_market(candidate, ev, "odds_above_limit")
    if candidate.probability < strategy_config.min_probability:
        return _pass_with_market(candidate, ev, "probability_below_threshold")
    if ev < strategy_config.min_expected_value:
        return _pass_with_market(candidate, ev, "expected_value_below_threshold")
    if conservative_ev < strategy_config.min_conservative_expected_value:
        return _pass_with_market(candidate, ev, "conservative_ev_below_threshold")

    return _recommendation(
        candidate,
        decision=Decision.SELECT,
        odds=candidate.odds,
        ev=ev,
        reason_codes=_reasons(
            candidate,
            "positive_ev",
            "conservative_ev_ok",
            "risk_ok",
        ),
    )


def _pass_with_market(
    candidate: StrategyCandidate,
    ev: Decimal,
    reason_code: str,
) -> Recommendation:
    return _recommendation(
        candidate,
        decision=Decision.PASS,
        odds=candidate.odds,
        ev=ev,
        reason_codes=_reasons(candidate, reason_code),
    )


def _recommendation(
    candidate: StrategyCandidate,
    *,
    decision: Decision,
    odds: Decimal | None,
    ev: Decimal | None,
    reason_codes: tuple[str, ...],
) -> Recommendation:
    return Recommendation(
        recommendation_id=candidate.recommendation_id,
        race_id=candidate.race_id,
        combination=candidate.combination,
        stage=PlanStage.FINAL,
        decision=decision,
        confidence=candidate.confidence,
        probability=candidate.probability,
        odds=odds,
        expected_value=ev,
        as_of=candidate.as_of,
        stake_units=1 if decision is Decision.SELECT else 0,
        versions=candidate.versions,
        reason_codes=reason_codes,
    )


def _reasons(candidate: StrategyCandidate, *reason_codes: str) -> tuple[str, ...]:
    return candidate.reason_codes + reason_codes


def _require_probability(value: Decimal, name: str) -> None:
    _require_decimal(value, name)
    if not Decimal("0") <= value <= Decimal("1"):
        raise ValueError(f"{name} must be between 0 and 1")


def _require_positive_decimal(value: Decimal, name: str) -> None:
    _require_decimal(value, name)
    if value <= Decimal("0"):
        raise ValueError(f"{name} must be positive")


def _require_non_negative_decimal(value: Decimal, name: str) -> None:
    _require_decimal(value, name)
    if value < Decimal("0"):
        raise ValueError(f"{name} must not be negative")


def _require_decimal(value: Decimal, name: str) -> None:
    if type(value) is not Decimal or not value.is_finite():
        raise ValueError(f"{name} must be a finite Decimal")
