from datetime import UTC, date, datetime
from decimal import Decimal

from boatrace_cal.backtest.preflight import BacktestReadinessStatus, check_backtest_inputs_ready
from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.ingestion.payouts import PayoutRecord
from boatrace_cal.ingestion.results import RaceResultRecord
from boatrace_cal.validation.data_quality import DataQualityIssueCode


def test_preflight_allows_backtest_when_historical_inputs_are_complete() -> None:
    race = RaceId(date(2025, 1, 2), VenueCode("01"), 1)
    result = _result(race)
    payouts = (
        _payout(race, BetType.TRIFECTA_ORDERED, (1, 2, 3), "1200"),
        _payout(race, BetType.EXACTA_ORDERED, (1, 2), "450"),
    )

    readiness = check_backtest_inputs_ready(
        results=(result,),
        payouts=payouts,
        expected_races=(race,),
        bet_types=(BetType.TRIFECTA_ORDERED, BetType.EXACTA_ORDERED),
    )

    assert readiness.status is BacktestReadinessStatus.READY
    assert readiness.ready is True
    assert readiness.blocker_count == 0
    assert readiness.refusal_reason is None
    assert readiness.blockers == ()
    assert readiness.quality_report.issue_count == 0


def test_preflight_blocks_backtest_with_auditable_quality_issues() -> None:
    race_1 = RaceId(date(2025, 1, 2), VenueCode("01"), 1)
    race_2 = RaceId(date(2025, 1, 2), VenueCode("01"), 2)
    payouts = (_payout(race_1, BetType.TRIFECTA_ORDERED, (1, 2, 3), "1200"),)

    readiness = check_backtest_inputs_ready(
        results=(_result(race_1),),
        payouts=payouts,
        expected_races=(race_1, race_2),
        bet_types=(BetType.TRIFECTA_ORDERED,),
    )

    assert readiness.status is BacktestReadinessStatus.BLOCKED
    assert readiness.ready is False
    assert readiness.blocker_count == 2
    assert readiness.refusal_reason == "historical_data_quality_issues"
    assert tuple((issue.race_id, issue.code, issue.bet_type) for issue in readiness.blockers) == (
        (race_2, DataQualityIssueCode.PAYOUT_MISSING, BetType.TRIFECTA_ORDERED),
        (race_2, DataQualityIssueCode.RESULT_MISSING, None),
    )
    assert readiness.quality_report.issue_count == 2


def _result(race_id: RaceId) -> RaceResultRecord:
    timestamp = datetime(2025, 1, 2, 16, 0, tzinfo=UTC)
    return RaceResultRecord(
        race_id=race_id,
        finish_order=(1, 2, 3),
        source="official-results",
        source_hash=f"result-{race_id}",
        observed_at=timestamp,
        available_at=timestamp,
        parser_version="results-v1",
    )


def _payout(
    race_id: RaceId,
    bet_type: BetType,
    lanes: tuple[int, ...],
    payout_yen: str,
) -> PayoutRecord:
    timestamp = datetime(2025, 1, 2, 16, 0, tzinfo=UTC)
    return PayoutRecord(
        race_id=race_id,
        combination=BetCombination.create(bet_type, lanes),
        payout_yen=Decimal(payout_yen),
        source="official-payouts",
        source_hash=f"payout-{race_id}-{bet_type.value}",
        observed_at=timestamp,
        available_at=timestamp,
        parser_version="payouts-v1",
    )
