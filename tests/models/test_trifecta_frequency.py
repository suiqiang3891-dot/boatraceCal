from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.ingestion.results import RaceResultRecord
from boatrace_cal.models.trifecta_frequency import fit_trifecta_frequency_model


def make_result(
    finish_order: tuple[int, int, int],
    available_at: datetime,
) -> RaceResultRecord:
    return RaceResultRecord(
        race_id=RaceId(date(2025, 1, 1), VenueCode("01"), finish_order[0]),
        finish_order=finish_order,
        source="official-results",
        source_hash=f"hash-{finish_order[0]}",
        observed_at=datetime(2025, 1, 1, 8, 0, tzinfo=timezone.utc),
        available_at=available_at,
        parser_version="results-v1",
    )


def test_trifecta_frequency_model_uses_only_available_results() -> None:
    as_of = datetime(2025, 1, 2, 10, 0, tzinfo=timezone.utc)
    model = fit_trifecta_frequency_model(
        (
            make_result((1, 2, 3), datetime(2025, 1, 1, 8, 1, tzinfo=timezone.utc)),
            make_result((4, 5, 6), datetime(2025, 1, 2, 10, 1, tzinfo=timezone.utc)),
        ),
        as_of=as_of,
        smoothing=Decimal("1"),
    )

    observed = BetCombination(BetType.TRIFECTA_ORDERED, (1, 2, 3))
    future_only = BetCombination(BetType.TRIFECTA_ORDERED, (4, 5, 6))

    assert model.training_race_count == 1
    assert len(model.probabilities) == 120
    assert model.probability_for(observed) == Decimal("2") / Decimal("121")
    assert model.probability_for(future_only) == Decimal("1") / Decimal("121")
    assert abs(sum(item.probability for item in model.probabilities) - Decimal("1")) < Decimal(
        "1E-26"
    )


@pytest.mark.parametrize("smoothing", [Decimal("0"), Decimal("-0.1")])
def test_trifecta_frequency_model_requires_positive_smoothing(smoothing: Decimal) -> None:
    with pytest.raises(ValueError, match="smoothing"):
        fit_trifecta_frequency_model(
            (),
            as_of=datetime(2025, 1, 2, 10, 0, tzinfo=timezone.utc),
            smoothing=smoothing,
        )


def test_trifecta_frequency_model_rejects_naive_as_of() -> None:
    with pytest.raises(ValueError, match="as_of"):
        fit_trifecta_frequency_model((), as_of=datetime(2025, 1, 2, 10, 0))
