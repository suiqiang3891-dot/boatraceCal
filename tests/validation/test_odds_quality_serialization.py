from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.ingestion.odds import OddsSnapshotRecord
from boatrace_cal.validation.odds_quality import build_odds_quality_report
from boatrace_cal.validation.serialization import odds_quality_report_to_dict


def test_odds_quality_report_to_dict_serializes_auditable_fields() -> None:
    race_id = RaceId(date(2026, 6, 23), VenueCode("05"), 1)
    as_of = datetime(2026, 6, 23, 4, 0, tzinfo=UTC)
    record = OddsSnapshotRecord(
        race_id=race_id,
        combination=BetCombination(BetType.EXACTA_ORDERED, (1, 2)),
        odds=Decimal("5.2"),
        source="official-odds",
        source_hash="hash-1-2",
        observed_at=as_of - timedelta(minutes=6),
        available_at=as_of - timedelta(minutes=5),
        parser_version="odds-v1",
    )
    report = build_odds_quality_report(
        odds=(record,),
        expected_races=(race_id,),
        bet_types=(BetType.EXACTA_ORDERED,),
        prediction_as_of=as_of,
        max_snapshot_age=timedelta(minutes=10),
    )

    payload = odds_quality_report_to_dict(report)

    assert payload["schema_version"] == "odds-quality-report-v1"
    assert payload["expected_race_count"] == 1
    assert payload["expected_snapshot_count"] == 30
    assert payload["available_snapshot_count"] == 1
    assert payload["issue_count"] == 29
    assert payload["coverage"] == [
        {
            "race_id": "20260623-05-01",
            "bet_type": "exacta_ordered",
            "expected_combination_count": 30,
            "available_combination_count": 1,
            "stale_combination_count": 0,
            "future_only_combination_count": 0,
        }
    ]
    assert payload["issues"][0] == {
        "race_id": "20260623-05-01",
        "code": "odds_missing",
        "bet_type": "exacta_ordered",
        "combination": "1-3",
    }


def test_odds_quality_report_to_dict_rejects_non_report() -> None:
    with pytest.raises(TypeError, match="report must be an OddsQualityReport"):
        odds_quality_report_to_dict(object())  # type: ignore[arg-type]
