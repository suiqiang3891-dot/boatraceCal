from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.ingestion.odds import OddsSnapshotRecord
from boatrace_cal.models.market_implied import build_market_implied_model


def make_odds(
    combination: BetCombination,
    odds: str,
    available_at: datetime,
) -> OddsSnapshotRecord:
    return OddsSnapshotRecord(
        race_id=RaceId(date(2026, 6, 23), VenueCode("05"), 1),
        combination=combination,
        odds=Decimal(odds),
        source="official-odds",
        source_hash=f"hash-{combination.key}-{odds}",
        observed_at=available_at,
        available_at=available_at,
        parser_version="odds-v1",
    )


def test_market_implied_model_normalizes_latest_available_inverse_odds() -> None:
    race_id = RaceId(date(2026, 6, 23), VenueCode("05"), 1)
    as_of = datetime(2026, 6, 23, 4, 0, tzinfo=timezone.utc)
    combo_a = BetCombination(BetType.EXACTA_ORDERED, (1, 2))
    combo_b = BetCombination(BetType.EXACTA_ORDERED, (2, 1))
    model = build_market_implied_model(
        (
            make_odds(combo_a, "4", datetime(2026, 6, 23, 3, 50, tzinfo=timezone.utc)),
            make_odds(combo_a, "2", datetime(2026, 6, 23, 3, 55, tzinfo=timezone.utc)),
            make_odds(combo_b, "4", datetime(2026, 6, 23, 3, 56, tzinfo=timezone.utc)),
            make_odds(combo_b, "1.5", datetime(2026, 6, 23, 4, 1, tzinfo=timezone.utc)),
        ),
        race_id=race_id,
        bet_type=BetType.EXACTA_ORDERED,
        as_of=as_of,
    )

    assert model.snapshot_count == 2
    assert [item.combination for item in model.probabilities] == [combo_a, combo_b]
    assert model.probability_for(combo_a) == Decimal("0.6666666666666666666666666667")
    assert model.probability_for(combo_b) == Decimal("0.3333333333333333333333333333")
    assert abs(sum(item.probability for item in model.probabilities) - Decimal("1")) < Decimal(
        "1E-26"
    )


def test_market_implied_model_rejects_missing_available_odds() -> None:
    with pytest.raises(ValueError, match="available odds"):
        build_market_implied_model(
            (),
            race_id=RaceId(date(2026, 6, 23), VenueCode("05"), 1),
            bet_type=BetType.EXACTA_ORDERED,
            as_of=datetime(2026, 6, 23, 4, 0, tzinfo=timezone.utc),
        )
