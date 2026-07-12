from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.domain.recommendations import ConfidenceLevel, Decision, PlanStage
from boatrace_cal.domain.versions import ArtifactVersions
from boatrace_cal.strategies.value import (
    StrategyCandidate,
    ValueStrategyConfig,
    build_value_recommendation,
    conservative_expected_value,
    expected_value,
    implied_probability,
)


def make_candidate(**overrides: object) -> StrategyCandidate:
    values: dict[str, object] = {
        "recommendation_id": "strategy-rec-1",
        "race_id": RaceId(date(2026, 7, 12), VenueCode("01"), 1),
        "combination": BetCombination(BetType.TRIFECTA_ORDERED, (1, 2, 3)),
        "probability": Decimal("0.25"),
        "odds": Decimal("5.2"),
        "confidence": ConfidenceLevel.HIGH,
        "as_of": datetime(2026, 7, 12, 9, 45, tzinfo=timezone.utc),
        "versions": ArtifactVersions("data-v1", "feature-v1", "model-v1", "strategy-v1"),
        "reason_codes": ("model_signal",),
    }
    values.update(overrides)
    return StrategyCandidate(**values)  # type: ignore[arg-type]


def test_market_value_helpers_compute_implied_probability_and_ev() -> None:
    ev = expected_value(Decimal("0.25"), Decimal("5.2"))

    assert implied_probability(Decimal("5")) == Decimal("0.2")
    assert ev == Decimal("0.300")
    assert conservative_expected_value(ev, Decimal("0.05")) == Decimal("0.250")


def test_value_strategy_selects_when_ev_survives_conservative_gate() -> None:
    recommendation = build_value_recommendation(
        make_candidate(),
        ValueStrategyConfig(
            min_expected_value=Decimal("0.20"),
            conservative_margin=Decimal("0.05"),
            min_conservative_expected_value=Decimal("0.10"),
        ),
    )

    assert recommendation.stage is PlanStage.FINAL
    assert recommendation.decision is Decision.SELECT
    assert recommendation.stake_units == 1
    assert recommendation.odds == Decimal("5.2")
    assert recommendation.expected_value == Decimal("0.300")
    assert recommendation.reason_codes == (
        "model_signal",
        "positive_ev",
        "conservative_ev_ok",
        "risk_ok",
    )


def test_value_strategy_passes_without_odds_and_does_not_claim_ev() -> None:
    recommendation = build_value_recommendation(make_candidate(odds=None))

    assert recommendation.decision is Decision.PASS
    assert recommendation.stake_units == 0
    assert recommendation.odds is None
    assert recommendation.expected_value is None
    assert recommendation.reason_codes == ("model_signal", "odds_unavailable")


def test_value_strategy_passes_when_conservative_ev_fails_threshold() -> None:
    recommendation = build_value_recommendation(
        make_candidate(probability=Decimal("0.22"), odds=Decimal("5.0")),
        ValueStrategyConfig(
            min_expected_value=Decimal("0.05"),
            conservative_margin=Decimal("0.08"),
            min_conservative_expected_value=Decimal("0.05"),
        ),
    )

    assert recommendation.decision is Decision.PASS
    assert recommendation.stake_units == 0
    assert recommendation.expected_value == Decimal("0.100")
    assert recommendation.reason_codes == (
        "model_signal",
        "conservative_ev_below_threshold",
    )


def test_value_strategy_passes_when_probability_is_below_minimum() -> None:
    recommendation = build_value_recommendation(
        make_candidate(probability=Decimal("0.08"), odds=Decimal("20")),
        ValueStrategyConfig(min_probability=Decimal("0.10")),
    )

    assert recommendation.decision is Decision.PASS
    assert recommendation.expected_value == Decimal("0.60")
    assert recommendation.reason_codes == ("model_signal", "probability_below_threshold")


@pytest.mark.parametrize("odds", [Decimal("0"), Decimal("-1")])
def test_implied_probability_rejects_non_positive_odds(odds: Decimal) -> None:
    with pytest.raises(ValueError, match="odds"):
        implied_probability(odds)
