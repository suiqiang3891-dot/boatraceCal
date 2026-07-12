from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.ingestion.odds import (
    OddsSnapshotRecord,
    latest_odds_by_combination,
    load_odds_csv,
)


def _write_csv(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "odds.csv"
    path.write_text(content, encoding="utf-8", newline="")
    return path


def test_loads_odds_csv_into_normalized_snapshot_records(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path,
        "\n".join(
            (
                "race_date,venue,race_no,bet_type,combination,odds,"
                "source,source_hash,observed_at,available_at,parser_version",
                "2026-06-23,5,1,trifecta_ordered,3-1-2,5.2,"
                "official-odds,abc123,2026-06-23T03:50:00+00:00,"
                "2026-06-23T03:51:00+00:00,odds-v1",
            )
        ),
    )

    records = load_odds_csv(path)

    assert records == (
        OddsSnapshotRecord(
            race_id=RaceId(date(2026, 6, 23), VenueCode("05"), 1),
            combination=BetCombination(BetType.TRIFECTA_ORDERED, (3, 1, 2)),
            odds=Decimal("5.2"),
            source="official-odds",
            source_hash="abc123",
            observed_at=datetime(2026, 6, 23, 3, 50, tzinfo=timezone.utc),
            available_at=datetime(2026, 6, 23, 3, 51, tzinfo=timezone.utc),
            parser_version="odds-v1",
        ),
    )


def test_rejects_duplicate_odds_snapshot_keys(tmp_path: Path) -> None:
    header = (
        "race_date,venue,race_no,bet_type,combination,odds,"
        "source,source_hash,observed_at,available_at,parser_version"
    )
    row = (
        "2026-06-23,05,1,trifecta_ordered,3-1-2,5.2,official-odds,abc123,"
        "2026-06-23T03:50:00+00:00,2026-06-23T03:51:00+00:00,odds-v1"
    )
    path = _write_csv(tmp_path, "\n".join((header, row, row)))

    with pytest.raises(ValueError, match="duplicate odds snapshot key"):
        load_odds_csv(path)


def test_rejects_non_positive_odds(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path,
        "\n".join(
            (
                "race_date,venue,race_no,bet_type,combination,odds,"
                "source,source_hash,observed_at,available_at,parser_version",
                "2026-06-23,05,1,trifecta_ordered,3-1-2,0,official-odds,abc123,"
                "2026-06-23T03:50:00+00:00,2026-06-23T03:51:00+00:00,odds-v1",
            )
        ),
    )

    with pytest.raises(ValueError, match="odds must be positive"):
        load_odds_csv(path)


def test_rejects_odds_available_before_observed(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path,
        "\n".join(
            (
                "race_date,venue,race_no,bet_type,combination,odds,"
                "source,source_hash,observed_at,available_at,parser_version",
                "2026-06-23,05,1,trifecta_ordered,3-1-2,5.2,official-odds,abc123,"
                "2026-06-23T03:51:00+00:00,2026-06-23T03:50:00+00:00,odds-v1",
            )
        ),
    )

    with pytest.raises(ValueError, match="available_at must not be before observed_at"):
        load_odds_csv(path)


def test_latest_odds_by_combination_uses_only_snapshots_available_as_of(
    tmp_path: Path,
) -> None:
    header = (
        "race_date,venue,race_no,bet_type,combination,odds,"
        "source,source_hash,observed_at,available_at,parser_version"
    )
    rows = (
        "2026-06-23,05,1,trifecta_ordered,3-1-2,7.0,official-odds,hash-late,"
        "2026-06-23T03:55:00+00:00,2026-06-23T03:56:00+00:00,odds-v1",
        "2026-06-23,05,1,trifecta_ordered,3-1-2,5.2,official-odds,hash-old,"
        "2026-06-23T03:50:00+00:00,2026-06-23T03:51:00+00:00,odds-v1",
        "2026-06-23,05,1,trifecta_ordered,3-1-2,9.9,official-odds,hash-future,"
        "2026-06-23T04:05:00+00:00,2026-06-23T04:06:00+00:00,odds-v1",
        "2026-06-23,05,1,trifecta_ordered,1-2-3,11.0,official-odds,hash-other,"
        "2026-06-23T03:53:00+00:00,2026-06-23T03:54:00+00:00,odds-v1",
        "2026-06-23,05,2,trifecta_ordered,3-1-2,22.0,official-odds,hash-race2,"
        "2026-06-23T03:55:00+00:00,2026-06-23T03:56:00+00:00,odds-v1",
    )
    records = load_odds_csv(_write_csv(tmp_path, "\n".join((header, *rows))))

    latest = latest_odds_by_combination(
        records=records,
        race_id=RaceId(date(2026, 6, 23), VenueCode("05"), 1),
        as_of=datetime(2026, 6, 23, 4, 0, tzinfo=timezone.utc),
    )

    assert {
        combination.key: record.odds for combination, record in latest.items()
    } == {
        "1-2-3": Decimal("11.0"),
        "3-1-2": Decimal("7.0"),
    }
