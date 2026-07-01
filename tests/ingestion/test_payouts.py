from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
from pathlib import Path

import pytest

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.ingestion.payouts import (
    MissingPayoutRow,
    PayoutCompletenessRow,
    PayoutDatasetManifest,
    PayoutRecord,
    build_payout_dataset_manifest,
    find_missing_payouts,
    load_payouts_csv,
    summarize_payout_completeness,
)


def _write_csv(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "payouts.csv"
    path.write_text(content, encoding="utf-8", newline="")
    return path


def test_loads_payouts_csv_into_normalized_records(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path,
        "\n".join(
            (
                "race_date,venue,race_no,bet_type,combination,payout_yen,"
                "source,source_hash,observed_at,available_at,parser_version",
                "2026-06-23,5,1,trifecta_ordered,3-1-2,1240,"
                "official,abc123,2026-06-23T04:00:00+00:00,"
                "2026-06-23T04:01:00+00:00,payouts-v1",
            )
        ),
    )

    records = load_payouts_csv(path)

    assert records == (
        PayoutRecord(
            race_id=RaceId(date(2026, 6, 23), VenueCode("05"), 1),
            combination=BetCombination(BetType.TRIFECTA_ORDERED, (3, 1, 2)),
            payout_yen=Decimal("1240"),
            source="official",
            source_hash="abc123",
            observed_at=datetime(2026, 6, 23, 4, 0, tzinfo=timezone.utc),
            available_at=datetime(2026, 6, 23, 4, 1, tzinfo=timezone.utc),
            parser_version="payouts-v1",
        ),
    )


def test_rejects_duplicate_payout_business_keys(tmp_path: Path) -> None:
    header = (
        "race_date,venue,race_no,bet_type,combination,payout_yen,"
        "source,source_hash,observed_at,available_at,parser_version"
    )
    row = (
        "2026-06-23,05,1,exacta_box,2-1,540,official,abc123,"
        "2026-06-23T04:00:00+00:00,2026-06-23T04:01:00+00:00,payouts-v1"
    )
    path = _write_csv(tmp_path, "\n".join((header, row, row)))

    with pytest.raises(ValueError, match="duplicate payout key"):
        load_payouts_csv(path)


def test_rejects_payout_available_before_observed(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path,
        "\n".join(
            (
                "race_date,venue,race_no,bet_type,combination,payout_yen,"
                "source,source_hash,observed_at,available_at,parser_version",
                "2026-06-23,05,1,exacta_ordered,1-2,540,official,abc123,"
                "2026-06-23T04:01:00+00:00,2026-06-23T04:00:00+00:00,payouts-v1",
            )
        ),
    )

    with pytest.raises(ValueError, match="available_at must not be before observed_at"):
        load_payouts_csv(path)


def test_rejects_unknown_payout_csv_fields(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path,
        "\n".join(
            (
                "race_date,venue,race_no,bet_type,combination,payout_yen,"
                "source,source_hash,observed_at,available_at,parser_version,extra",
                "2026-06-23,05,1,exacta_ordered,1-2,540,official,abc123,"
                "2026-06-23T04:00:00+00:00,2026-06-23T04:01:00+00:00,payouts-v1,x",
            )
        ),
    )

    with pytest.raises(ValueError, match="exactly the supported fields"):
        load_payouts_csv(path)


def test_summarizes_payout_completeness_by_date_venue_and_bet_type(
    tmp_path: Path,
) -> None:
    header = (
        "race_date,venue,race_no,bet_type,combination,payout_yen,"
        "source,source_hash,observed_at,available_at,parser_version"
    )
    rows = (
        "2026-06-23,05,2,trifecta_ordered,1-2-3,1800,official,hash-a,"
        "2026-06-23T04:10:00+00:00,2026-06-23T04:11:00+00:00,payouts-v1",
        "2026-06-23,05,1,exacta_ordered,2-1,540,official,hash-b,"
        "2026-06-23T04:00:00+00:00,2026-06-23T04:01:00+00:00,payouts-v1",
        "2026-06-23,05,1,trifecta_ordered,3-1-2,1240,official,hash-c,"
        "2026-06-23T04:00:00+00:00,2026-06-23T04:01:00+00:00,payouts-v1",
    )
    records = load_payouts_csv(_write_csv(tmp_path, "\n".join((header, *rows))))

    report = summarize_payout_completeness(records)

    assert report == (
        PayoutCompletenessRow(
            race_date=date(2026, 6, 23),
            venue=VenueCode("05"),
            bet_type=BetType.EXACTA_ORDERED,
            payout_count=1,
            race_count=1,
            total_payout_yen=Decimal("540"),
        ),
        PayoutCompletenessRow(
            race_date=date(2026, 6, 23),
            venue=VenueCode("05"),
            bet_type=BetType.TRIFECTA_ORDERED,
            payout_count=2,
            race_count=2,
            total_payout_yen=Decimal("3040"),
        ),
    )


def test_finds_expected_races_without_payouts(tmp_path: Path) -> None:
    header = (
        "race_date,venue,race_no,bet_type,combination,payout_yen,"
        "source,source_hash,observed_at,available_at,parser_version"
    )
    row = (
        "2026-06-23,05,1,trifecta_ordered,3-1-2,1240,official,hash-a,"
        "2026-06-23T04:00:00+00:00,2026-06-23T04:01:00+00:00,payouts-v1"
    )
    records = load_payouts_csv(_write_csv(tmp_path, "\n".join((header, row))))
    expected_races = (
        RaceId(date(2026, 6, 23), VenueCode("05"), 2),
        RaceId(date(2026, 6, 23), VenueCode("05"), 1),
    )

    missing = find_missing_payouts(
        records=records,
        expected_races=expected_races,
        bet_types=(BetType.TRIFECTA_ORDERED, BetType.EXACTA_ORDERED),
    )

    assert missing == (
        MissingPayoutRow(
            race_id=RaceId(date(2026, 6, 23), VenueCode("05"), 1),
            bet_type=BetType.EXACTA_ORDERED,
            reason_code="PAYOUT_MISSING",
        ),
        MissingPayoutRow(
            race_id=RaceId(date(2026, 6, 23), VenueCode("05"), 2),
            bet_type=BetType.EXACTA_ORDERED,
            reason_code="PAYOUT_MISSING",
        ),
        MissingPayoutRow(
            race_id=RaceId(date(2026, 6, 23), VenueCode("05"), 2),
            bet_type=BetType.TRIFECTA_ORDERED,
            reason_code="PAYOUT_MISSING",
        ),
    )


def test_builds_payout_dataset_manifest_from_source_file(tmp_path: Path) -> None:
    header = (
        "race_date,venue,race_no,bet_type,combination,payout_yen,"
        "source,source_hash,observed_at,available_at,parser_version"
    )
    rows = (
        "2026-06-23,05,1,trifecta_ordered,3-1-2,1240,official,hash-a,"
        "2026-06-23T04:00:00+00:00,2026-06-23T04:01:00+00:00,payouts-v2",
        "2026-06-24,05,2,exacta_ordered,1-2,540,official,hash-b,"
        "2026-06-24T04:10:00+00:00,2026-06-24T04:12:00+00:00,payouts-v1",
    )
    path = _write_csv(tmp_path, "\n".join((header, *rows)))
    records = load_payouts_csv(path)

    manifest = build_payout_dataset_manifest(path, records)

    assert manifest == PayoutDatasetManifest(
        source_path=path,
        content_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        record_count=2,
        parser_versions=("payouts-v1", "payouts-v2"),
        race_date_start=date(2026, 6, 23),
        race_date_end=date(2026, 6, 24),
        observed_at_start=datetime(2026, 6, 23, 4, 0, tzinfo=timezone.utc),
        observed_at_end=datetime(2026, 6, 24, 4, 10, tzinfo=timezone.utc),
        available_at_start=datetime(2026, 6, 23, 4, 1, tzinfo=timezone.utc),
        available_at_end=datetime(2026, 6, 24, 4, 12, tzinfo=timezone.utc),
    )
