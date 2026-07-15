from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.ingestion.payouts import PayoutRecord
from boatrace_cal.ingestion.results import RaceResultRecord
from boatrace_cal.validation.data_quality import build_historical_data_quality_report
from boatrace_cal.validation.serialization import historical_data_quality_report_to_dict


def test_historical_data_quality_report_to_dict_serializes_auditable_fields() -> None:
    race_1 = RaceId(date(2025, 1, 2), VenueCode("01"), 1)
    race_2 = RaceId(date(2025, 1, 2), VenueCode("01"), 2)
    timestamp = datetime(2025, 1, 2, 16, 0, tzinfo=UTC)
    report = build_historical_data_quality_report(
        results=(
            RaceResultRecord(
                race_id=race_1,
                finish_order=(1, 2, 3),
                source="official-results",
                source_hash="result-hash",
                observed_at=timestamp,
                available_at=timestamp,
                parser_version="results-v1",
            ),
        ),
        payouts=(
            PayoutRecord(
                race_id=race_1,
                combination=BetCombination.create(BetType.TRIFECTA_ORDERED, (1, 2, 3)),
                payout_yen=Decimal("1200"),
                source="official-payouts",
                source_hash="payout-hash",
                observed_at=timestamp,
                available_at=timestamp,
                parser_version="payouts-v1",
            ),
        ),
        expected_races=(race_1, race_2),
        bet_types=(BetType.TRIFECTA_ORDERED,),
    )

    payload = historical_data_quality_report_to_dict(report)

    assert payload == {
        "schema_version": "historical-data-quality-report-v1",
        "expected_race_count": 2,
        "result_count": 1,
        "payout_count": 1,
        "issue_count": 2,
        "issues": [
            {
                "race_id": "20250102-01-02",
                "code": "payout_missing",
                "bet_type": "trifecta_ordered",
            },
            {
                "race_id": "20250102-01-02",
                "code": "result_missing",
                "bet_type": None,
            },
        ],
        "payout_completeness": [
            {
                "race_date": "2025-01-02",
                "venue": "01",
                "bet_type": "trifecta_ordered",
                "payout_count": 1,
                "race_count": 1,
                "total_payout_yen": "1200",
            },
        ],
    }


def test_historical_data_quality_report_to_dict_rejects_non_report() -> None:
    with pytest.raises(TypeError, match="report must be a HistoricalDataQualityReport"):
        historical_data_quality_report_to_dict(object())  # type: ignore[arg-type]
