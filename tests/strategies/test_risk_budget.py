from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.domain.recommendations import (
    ConfidenceLevel,
    Decision,
    PlanStage,
    Recommendation,
)
from boatrace_cal.domain.versions import ArtifactVersions
from boatrace_cal.strategies.risk_budget import (
    RiskBudgetConfig,
    apply_risk_budget,
)


def make_recommendation(**overrides: object) -> Recommendation:
    values: dict[str, object] = {
        "recommendation_id": "rec-1",
        "race_id": RaceId(date(2026, 7, 12), VenueCode("01"), 1),
        "combination": BetCombination(BetType.TRIFECTA_ORDERED, (1, 2, 3)),
        "stage": PlanStage.FINAL,
        "decision": Decision.SELECT,
        "confidence": ConfidenceLevel.HIGH,
        "probability": Decimal("0.25"),
        "odds": Decimal("5.2"),
        "expected_value": Decimal("0.30"),
        "as_of": datetime(2026, 7, 12, 9, 45, tzinfo=timezone.utc),
        "stake_units": 1,
        "versions": ArtifactVersions("data-v1", "feature-v1", "model-v1", "strategy-v1"),
        "reason_codes": ("positive_ev", "conservative_ev_ok", "risk_ok"),
    }
    values.update(overrides)
    return Recommendation(**values)  # type: ignore[arg-type]


def test_risk_budget_keeps_highest_ev_select_per_race_and_demotes_the_rest() -> None:
    race_id = RaceId(date(2026, 7, 12), VenueCode("01"), 1)
    recommendations = (
        make_recommendation(
            recommendation_id="low-ev",
            race_id=race_id,
            combination=BetCombination(BetType.TRIFECTA_ORDERED, (1, 2, 3)),
            expected_value=Decimal("0.20"),
        ),
        make_recommendation(
            recommendation_id="high-ev",
            race_id=race_id,
            combination=BetCombination(BetType.TRIFECTA_ORDERED, (1, 3, 2)),
            expected_value=Decimal("0.45"),
        ),
        make_recommendation(
            recommendation_id="already-pass",
            race_id=race_id,
            combination=BetCombination(BetType.TRIFECTA_ORDERED, (2, 1, 3)),
            decision=Decision.PASS,
            expected_value=Decimal("0.10"),
            stake_units=0,
            reason_codes=("expected_value_below_threshold",),
        ),
    )

    budgeted = apply_risk_budget(
        recommendations,
        RiskBudgetConfig(max_selects_per_race=1),
    )

    assert [record.recommendation_id for record in budgeted] == [
        "low-ev",
        "high-ev",
        "already-pass",
    ]
    assert budgeted[0].decision is Decision.PASS
    assert budgeted[0].stake_units == 0
    assert budgeted[0].reason_codes == (
        "positive_ev",
        "conservative_ev_ok",
        "race_risk_limit",
    )
    assert budgeted[1].decision is Decision.SELECT
    assert budgeted[1].stake_units == 1
    assert budgeted[1].reason_codes == (
        "positive_ev",
        "conservative_ev_ok",
        "risk_ok",
    )
    assert budgeted[2] is recommendations[2]


def test_risk_budget_applies_daily_unit_cap_after_race_cap() -> None:
    race_1 = RaceId(date(2026, 7, 12), VenueCode("01"), 1)
    race_2 = RaceId(date(2026, 7, 12), VenueCode("01"), 2)
    race_3 = RaceId(date(2026, 7, 12), VenueCode("02"), 1)
    recommendations = (
        make_recommendation(
            recommendation_id="race-1-kept",
            race_id=race_1,
            expected_value=Decimal("0.50"),
        ),
        make_recommendation(
            recommendation_id="race-2-demoted",
            race_id=race_2,
            expected_value=Decimal("0.30"),
        ),
        make_recommendation(
            recommendation_id="race-3-kept",
            race_id=race_3,
            expected_value=Decimal("0.60"),
        ),
    )

    budgeted = apply_risk_budget(
        recommendations,
        RiskBudgetConfig(max_selects_per_race=1, max_daily_stake_units=2),
    )

    assert [record.decision for record in budgeted] == [
        Decision.SELECT,
        Decision.PASS,
        Decision.SELECT,
    ]
    assert budgeted[1].reason_codes == (
        "positive_ev",
        "conservative_ev_ok",
        "daily_risk_limit",
    )


def test_risk_budget_applies_daily_unit_cap_per_race_date() -> None:
    day_1 = RaceId(date(2026, 7, 12), VenueCode("01"), 1)
    day_2 = RaceId(date(2026, 7, 13), VenueCode("01"), 1)
    recommendations = (
        make_recommendation(
            recommendation_id="day-1-kept",
            race_id=day_1,
            expected_value=Decimal("0.50"),
        ),
        make_recommendation(
            recommendation_id="day-2-kept",
            race_id=day_2,
            expected_value=Decimal("0.40"),
        ),
    )

    budgeted = apply_risk_budget(
        recommendations,
        RiskBudgetConfig(max_daily_stake_units=1),
    )

    assert [record.decision for record in budgeted] == [
        Decision.SELECT,
        Decision.SELECT,
    ]


def test_risk_budget_config_rejects_negative_limits() -> None:
    with pytest.raises(ValueError, match="max_selects_per_race"):
        RiskBudgetConfig(max_selects_per_race=-1)
