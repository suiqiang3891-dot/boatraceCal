from datetime import date, datetime, timezone

import pytest

from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.ingestion.results import RaceResultRecord
from boatrace_cal.models.time_split import build_time_split_report


def test_build_time_split_report_partitions_results_by_available_at() -> None:
    payload = build_time_split_report(
        (
            make_result(1, datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)),
            make_result(2, datetime(2026, 6, 10, 9, 0, tzinfo=timezone.utc)),
            make_result(3, datetime(2026, 6, 20, 9, 0, tzinfo=timezone.utc)),
            make_result(4, datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)),
        ),
        train_until=datetime(2026, 6, 5, 0, 0, tzinfo=timezone.utc),
        validation_until=datetime(2026, 6, 15, 0, 0, tzinfo=timezone.utc),
        test_until=datetime(2026, 6, 30, 0, 0, tzinfo=timezone.utc),
    )

    assert payload == {
        "schema_version": "model-time-split-report-v1",
        "split_field": "available_at",
        "train_until": "2026-06-05T00:00:00+00:00",
        "validation_until": "2026-06-15T00:00:00+00:00",
        "test_until": "2026-06-30T00:00:00+00:00",
        "train_count": 1,
        "validation_count": 1,
        "test_count": 1,
        "excluded_count": 1,
        "leakage_check": "passed",
        "train_race_ids": ["20260601-05-01"],
        "validation_race_ids": ["20260601-05-02"],
        "test_race_ids": ["20260601-05-03"],
        "excluded_race_ids": ["20260601-05-04"],
    }


def test_build_time_split_report_rejects_overlapping_boundaries() -> None:
    with pytest.raises(ValueError, match="train_until"):
        build_time_split_report(
            (),
            train_until=datetime(2026, 6, 10, tzinfo=timezone.utc),
            validation_until=datetime(2026, 6, 5, tzinfo=timezone.utc),
            test_until=datetime(2026, 6, 30, tzinfo=timezone.utc),
        )


def make_result(race_no: int, available_at: datetime) -> RaceResultRecord:
    return RaceResultRecord(
        race_id=RaceId(date(2026, 6, 1), VenueCode("05"), race_no),
        finish_order=(1, 2, 3),
        source="official-results",
        source_hash=f"hash-{race_no}",
        observed_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
        available_at=available_at,
        parser_version="results-v1",
    )
