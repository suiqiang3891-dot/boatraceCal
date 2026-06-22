from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.domain.recommendations import Decision, PlanStage, Recommendation
from boatrace_cal.domain.versions import ArtifactVersions


def make_recommendation(**overrides: object) -> Recommendation:
    values: dict[str, object] = {
        "recommendation_id": "rec-1",
        "race_id": RaceId(date(2026, 6, 23), VenueCode("01"), 1),
        "combination": BetCombination(BetType.TRIFECTA_ORDERED, (1, 2, 3)),
        "stage": PlanStage.FINAL,
        "decision": Decision.SELECT,
        "probability": Decimal("0.25"),
        "odds": Decimal("5.2"),
        "expected_value": Decimal("0.30"),
        "as_of": datetime(2026, 6, 23, 10, tzinfo=timezone.utc),
        "stake_units": 1,
        "versions": ArtifactVersions("data-v1", "feature-v1", "model-v1", "strategy-v1"),
        "reason_codes": ("positive_ev",),
    }
    values.update(overrides)
    return Recommendation(**values)  # type: ignore[arg-type]


def test_final_selection_preserves_auditable_decision_data() -> None:
    recommendation = make_recommendation()

    assert recommendation.stage is PlanStage.FINAL
    assert recommendation.decision is Decision.SELECT
    assert recommendation.odds == Decimal("5.2")


def test_recommendation_normalizes_identifiers_and_reason_codes() -> None:
    recommendation = make_recommendation(
        recommendation_id=" rec-1 ", reason_codes=(" positive_ev ", " model_confident\n")
    )

    assert recommendation.recommendation_id == "rec-1"
    assert recommendation.reason_codes == ("positive_ev", "model_confident")


@pytest.mark.parametrize("recommendation_id", ["", "   ", "\t\n"])
def test_recommendation_rejects_empty_identifier(recommendation_id: str) -> None:
    with pytest.raises(ValueError, match="recommendation id"):
        make_recommendation(recommendation_id=recommendation_id)


@pytest.mark.parametrize("probability", [Decimal("-0.01"), Decimal("1.01")])
def test_recommendation_rejects_probability_outside_unit_interval(
    probability: Decimal,
) -> None:
    with pytest.raises(ValueError, match="probability"):
        make_recommendation(probability=probability)


@pytest.mark.parametrize("stake_units", [-1, True, False])
def test_recommendation_rejects_invalid_stake_units(stake_units: int) -> None:
    with pytest.raises(ValueError, match="stake units"):
        make_recommendation(stake_units=stake_units)


def test_recommendation_rejects_naive_as_of() -> None:
    with pytest.raises(ValueError, match="as_of"):
        make_recommendation(as_of=datetime(2026, 6, 23, 10))


def test_preplan_cannot_be_a_final_selection() -> None:
    with pytest.raises(ValueError, match="preplan"):
        make_recommendation(stage=PlanStage.PREPLAN, decision=Decision.SELECT)


@pytest.mark.parametrize("stage", ["preplan", "final", "draft"])
def test_recommendation_rejects_string_stage(stage: str) -> None:
    with pytest.raises(ValueError, match="stage"):
        make_recommendation(stage=stage, decision=Decision.SELECT)


@pytest.mark.parametrize("decision", ["select", "pass", "hold"])
def test_recommendation_rejects_string_decision(decision: str) -> None:
    with pytest.raises(ValueError, match="decision"):
        make_recommendation(stage=PlanStage.FINAL, decision=decision)


@pytest.mark.parametrize(
    ("odds", "expected_value"),
    [(Decimal("5"), None), (None, Decimal("0.2")), (Decimal("5"), Decimal("0.2"))],
)
def test_preplan_cannot_claim_market_value(
    odds: Decimal | None, expected_value: Decimal | None
) -> None:
    with pytest.raises(ValueError, match="preplan"):
        make_recommendation(
            stage=PlanStage.PREPLAN,
            decision=Decision.PASS,
            odds=odds,
            expected_value=expected_value,
        )


@pytest.mark.parametrize(
    ("odds", "expected_value"),
    [(None, Decimal("0.2")), (Decimal("5"), None), (None, None)],
)
def test_final_selection_requires_odds_and_expected_value(
    odds: Decimal | None, expected_value: Decimal | None
) -> None:
    with pytest.raises(ValueError, match="final selection"):
        make_recommendation(odds=odds, expected_value=expected_value)


def test_final_pass_allows_missing_market_values_when_reason_is_present() -> None:
    recommendation = make_recommendation(
        decision=Decision.PASS,
        odds=None,
        expected_value=None,
        stake_units=0,
        reason_codes=(" odds_unavailable ",),
    )

    assert recommendation.reason_codes == ("odds_unavailable",)


@pytest.mark.parametrize("reason_codes", [(), ("",), ("valid", "   ")])
def test_final_pass_requires_non_empty_reason_codes(reason_codes: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="reason codes"):
        make_recommendation(decision=Decision.PASS, reason_codes=reason_codes)


@pytest.mark.parametrize("odds", [Decimal("0"), Decimal("-0.01")])
def test_recommendation_rejects_non_positive_odds(odds: Decimal) -> None:
    with pytest.raises(ValueError, match="odds"):
        make_recommendation(odds=odds)


def test_recommendation_is_frozen() -> None:
    recommendation = make_recommendation()

    with pytest.raises(FrozenInstanceError):
        recommendation.stake_units = 2  # type: ignore[misc]


def test_recommendation_uses_slots() -> None:
    recommendation = make_recommendation()

    assert not hasattr(recommendation, "__dict__")
