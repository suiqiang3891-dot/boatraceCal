from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.ingestion.payouts import PayoutCompletenessRow, PayoutRecord
from boatrace_cal.ingestion.results import RaceResultRecord
from boatrace_cal.validation.data_quality import (
    DataQualityIssueCode,
    build_historical_data_quality_report,
)


def test_historical_quality_report_lists_missing_results_and_payouts() -> None:
    race_1 = RaceId(date(2025, 1, 2), VenueCode("01"), 1)
    race_2 = RaceId(date(2025, 1, 2), VenueCode("01"), 2)
    timestamp = datetime(2025, 1, 2, 16, 0, tzinfo=UTC)

    result = RaceResultRecord(
        race_id=race_1,
        finish_order=(1, 2, 3),
        source="official-results",
        source_hash="result-hash",
        observed_at=timestamp,
        available_at=timestamp,
        parser_version="results-v1",
    )
    payout = PayoutRecord(
        race_id=race_1,
        combination=BetCombination.create(BetType.TRIFECTA_ORDERED, (1, 2, 3)),
        payout_yen=Decimal("1200"),
        source="official-payouts",
        source_hash="payout-hash",
        observed_at=timestamp,
        available_at=timestamp,
        parser_version="payouts-v1",
    )

    report = build_historical_data_quality_report(
        results=(result,),
        payouts=(payout,),
        expected_races=(race_1, race_2),
        bet_types=(BetType.TRIFECTA_ORDERED, BetType.EXACTA_ORDERED),
    )

    assert report.expected_race_count == 2
    assert report.result_count == 1
    assert report.payout_count == 1
    assert report.issue_count == 4
    assert tuple((issue.race_id, issue.code, issue.bet_type) for issue in report.issues) == (
        (race_1, DataQualityIssueCode.PAYOUT_MISSING, BetType.EXACTA_ORDERED),
        (race_2, DataQualityIssueCode.PAYOUT_MISSING, BetType.EXACTA_ORDERED),
        (race_2, DataQualityIssueCode.PAYOUT_MISSING, BetType.TRIFECTA_ORDERED),
        (race_2, DataQualityIssueCode.RESULT_MISSING, None),
    )
    assert report.payout_completeness == (
        PayoutCompletenessRow(
            race_date=date(2025, 1, 2),
            venue=VenueCode("01"),
            bet_type=BetType.TRIFECTA_ORDERED,
            payout_count=1,
            race_count=1,
            total_payout_yen=Decimal("1200"),
        ),
    )


def test_historical_quality_report_rejects_non_result_records() -> None:
    race = RaceId(date(2025, 1, 2), VenueCode("01"), 1)

    with pytest.raises(TypeError, match="results must contain only RaceResultRecord instances"):
        build_historical_data_quality_report(
            results=(object(),),
            payouts=(),
            expected_races=(race,),
            bet_types=(BetType.TRIFECTA_ORDERED,),
        )
