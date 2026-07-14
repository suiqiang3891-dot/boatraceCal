from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.ingestion.results import RaceResultRecord
from boatrace_cal.models.lane_position_linear import fit_lane_position_linear_model


def test_lane_position_linear_model_uses_available_results_as_linear_features() -> None:
    model = fit_lane_position_linear_model(
        (
            make_result((1, 2, 3), datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)),
            make_result((4, 5, 6), datetime(2026, 6, 2, 9, 0, tzinfo=timezone.utc)),
        ),
        as_of=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
        smoothing=Decimal("1"),
    )

    observed = BetCombination(BetType.TRIFECTA_ORDERED, (1, 2, 3))
    unseen = BetCombination(BetType.TRIFECTA_ORDERED, (4, 5, 6))

    assert model.training_race_count == 1
    assert len(model.probabilities) == 120
    assert model.probability_for(observed) == model.probability_for(unseen) * Decimal("8")
    assert abs(sum(item.probability for item in model.probabilities) - Decimal("1")) < Decimal(
        "1E-26"
    )


@pytest.mark.parametrize("smoothing", [Decimal("0"), Decimal("-0.1")])
def test_lane_position_linear_model_requires_positive_smoothing(smoothing: Decimal) -> None:
    with pytest.raises(ValueError, match="smoothing"):
        fit_lane_position_linear_model(
            (),
            as_of=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
            smoothing=smoothing,
        )


def make_result(
    finish_order: tuple[int, int, int],
    available_at: datetime,
) -> RaceResultRecord:
    return RaceResultRecord(
        race_id=RaceId(date(2026, 6, 1), VenueCode("05"), finish_order[0]),
        finish_order=finish_order,
        source="official-results",
        source_hash=f"hash-{finish_order[0]}",
        observed_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
        available_at=available_at,
        parser_version="results-v1",
    )
