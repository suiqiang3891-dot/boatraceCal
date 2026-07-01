from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.ingestion.results import RaceResultRecord, load_results_csv


def _write_csv(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "results.csv"
    path.write_text(content, encoding="utf-8", newline="")
    return path


def test_loads_results_csv_into_normalized_records(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path,
        "\n".join(
            (
                "race_date,venue,race_no,first,second,third,"
                "source,source_hash,observed_at,available_at,parser_version",
                "2026-06-23,5,1,3,1,2,official,abc123,"
                "2026-06-23T04:00:00+00:00,2026-06-23T04:01:00+00:00,results-v1",
            )
        ),
    )

    records = load_results_csv(path)

    assert records == (
        RaceResultRecord(
            race_id=RaceId(date(2026, 6, 23), VenueCode("05"), 1),
            finish_order=(3, 1, 2),
            source="official",
            source_hash="abc123",
            observed_at=datetime(2026, 6, 23, 4, 0, tzinfo=timezone.utc),
            available_at=datetime(2026, 6, 23, 4, 1, tzinfo=timezone.utc),
            parser_version="results-v1",
        ),
    )


def test_rejects_duplicate_result_race_ids(tmp_path: Path) -> None:
    header = (
        "race_date,venue,race_no,first,second,third,"
        "source,source_hash,observed_at,available_at,parser_version"
    )
    row = (
        "2026-06-23,05,1,3,1,2,official,abc123,"
        "2026-06-23T04:00:00+00:00,2026-06-23T04:01:00+00:00,results-v1"
    )
    path = _write_csv(tmp_path, "\n".join((header, row, row)))

    with pytest.raises(ValueError, match="duplicate race result"):
        load_results_csv(path)


@pytest.mark.parametrize(
    "row",
    [
        "2026-06-23,05,1,3,3,2,official,abc123,"
        "2026-06-23T04:00:00+00:00,2026-06-23T04:01:00+00:00,results-v1",
        "2026-06-23,05,1,0,1,2,official,abc123,"
        "2026-06-23T04:00:00+00:00,2026-06-23T04:01:00+00:00,results-v1",
    ],
)
def test_rejects_invalid_finish_order(tmp_path: Path, row: str) -> None:
    header = (
        "race_date,venue,race_no,first,second,third,"
        "source,source_hash,observed_at,available_at,parser_version"
    )
    path = _write_csv(tmp_path, "\n".join((header, row)))

    with pytest.raises(ValueError, match="finish_order"):
        load_results_csv(path)


def test_rejects_result_available_before_observed(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path,
        "\n".join(
            (
                "race_date,venue,race_no,first,second,third,"
                "source,source_hash,observed_at,available_at,parser_version",
                "2026-06-23,05,1,3,1,2,official,abc123,"
                "2026-06-23T04:01:00+00:00,2026-06-23T04:00:00+00:00,results-v1",
            )
        ),
    )

    with pytest.raises(ValueError, match="available_at must not be before observed_at"):
        load_results_csv(path)


def test_rejects_unknown_result_csv_fields(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path,
        "\n".join(
            (
                "race_date,venue,race_no,first,second,third,"
                "source,source_hash,observed_at,available_at,parser_version,extra",
                "2026-06-23,05,1,3,1,2,official,abc123,"
                "2026-06-23T04:00:00+00:00,2026-06-23T04:01:00+00:00,results-v1,x",
            )
        ),
    )

    with pytest.raises(ValueError, match="exactly the supported fields"):
        load_results_csv(path)
