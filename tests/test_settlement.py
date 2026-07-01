from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.ingestion.payouts import PayoutRecord
from boatrace_cal.ingestion.results import RaceResultRecord
from boatrace_cal.settlement import SettlementResult, SettlementStatus, settle_bet


RACE_ID = RaceId(date(2026, 6, 23), VenueCode("05"), 1)
AS_OF = datetime(2026, 6, 23, 4, 0, tzinfo=timezone.utc)


def _result() -> RaceResultRecord:
    return RaceResultRecord(
        race_id=RACE_ID,
        finish_order=(3, 1, 2),
        source="official",
        source_hash="result-hash",
        observed_at=AS_OF,
        available_at=AS_OF,
        parser_version="results-v1",
    )


def _payout(combination: BetCombination, amount: str = "1240") -> PayoutRecord:
    return PayoutRecord(
        race_id=RACE_ID,
        combination=combination,
        payout_yen=Decimal(amount),
        source="official",
        source_hash="payout-hash",
        observed_at=AS_OF,
        available_at=AS_OF,
        parser_version="payouts-v1",
    )


@pytest.mark.parametrize(
    "combination",
    [
        BetCombination(BetType.TRIFECTA_ORDERED, (3, 1, 2)),
        BetCombination(BetType.TRIFECTA_BOX, (2, 3, 1)),
        BetCombination(BetType.EXACTA_ORDERED, (3, 1)),
        BetCombination(BetType.EXACTA_BOX, (1, 3)),
        BetCombination(BetType.WIDE_BOX, (1, 2)),
    ],
)
def test_settle_bet_pays_supported_winning_bet_types(
    combination: BetCombination,
) -> None:
    settlement = settle_bet(_result(), combination, (_payout(combination),))

    assert settlement == SettlementResult(
        race_id=RACE_ID,
        combination=combination,
        status=SettlementStatus.HIT,
        payout_yen=Decimal("1240"),
    )


@pytest.mark.parametrize(
    "combination",
    [
        BetCombination(BetType.TRIFECTA_ORDERED, (3, 2, 1)),
        BetCombination(BetType.TRIFECTA_BOX, (3, 1, 4)),
        BetCombination(BetType.EXACTA_ORDERED, (1, 3)),
        BetCombination(BetType.EXACTA_BOX, (2, 3)),
        BetCombination(BetType.WIDE_BOX, (4, 5)),
    ],
)
def test_settle_bet_returns_zero_for_losing_bets(combination: BetCombination) -> None:
    settlement = settle_bet(_result(), combination, ())

    assert settlement == SettlementResult(
        race_id=RACE_ID,
        combination=combination,
        status=SettlementStatus.MISS,
        payout_yen=Decimal("0"),
    )


def test_settle_bet_reports_missing_payout_for_winning_combination() -> None:
    combination = BetCombination(BetType.TRIFECTA_ORDERED, (3, 1, 2))

    settlement = settle_bet(_result(), combination, ())

    assert settlement == SettlementResult(
        race_id=RACE_ID,
        combination=combination,
        status=SettlementStatus.PAYOUT_MISSING,
        payout_yen=Decimal("0"),
    )


def test_settle_bet_ignores_payouts_for_other_races() -> None:
    combination = BetCombination(BetType.EXACTA_ORDERED, (3, 1))
    other_race_payout = PayoutRecord(
        race_id=RaceId(date(2026, 6, 23), VenueCode("05"), 2),
        combination=combination,
        payout_yen=Decimal("540"),
        source="official",
        source_hash="payout-hash",
        observed_at=AS_OF,
        available_at=AS_OF,
        parser_version="payouts-v1",
    )

    settlement = settle_bet(_result(), combination, (other_race_payout,))

    assert settlement.status is SettlementStatus.PAYOUT_MISSING
