from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.ingestion.odds import OddsSnapshotRecord
from boatrace_cal.validation.odds_quality import (
    OddsQualityIssueCode,
    build_odds_quality_report,
)


def _odds_record(
    race_id: RaceId,
    combination: BetCombination,
    odds: str,
    available_at: datetime,
) -> OddsSnapshotRecord:
    return OddsSnapshotRecord(
        race_id=race_id,
        combination=combination,
        odds=Decimal(odds),
        source="official-odds",
        source_hash=f"hash-{combination.key}-{available_at.minute}",
        observed_at=available_at - timedelta(minutes=1),
        available_at=available_at,
        parser_version="odds-v1",
    )


def test_odds_quality_report_lists_missing_stale_and_future_only_snapshots() -> None:
    race_id = RaceId(date(2026, 6, 23), VenueCode("05"), 1)
    as_of = datetime(2026, 6, 23, 4, 0, tzinfo=UTC)
    records = (
        _odds_record(
            race_id,
            BetCombination(BetType.EXACTA_ORDERED, (1, 2)),
            "5.2",
            as_of - timedelta(minutes=5),
        ),
        _odds_record(
            race_id,
            BetCombination(BetType.EXACTA_ORDERED, (2, 1)),
            "7.0",
            as_of - timedelta(minutes=20),
        ),
        _odds_record(
            race_id,
            BetCombination(BetType.EXACTA_ORDERED, (3, 4)),
            "9.9",
            as_of + timedelta(minutes=1),
        ),
    )

    report = build_odds_quality_report(
        odds=records,
        expected_races=(race_id,),
        bet_types=(BetType.EXACTA_ORDERED,),
        prediction_as_of=as_of,
        max_snapshot_age=timedelta(minutes=10),
    )

    assert report.expected_race_count == 1
    assert report.expected_snapshot_count == 30
    assert report.available_snapshot_count == 2
    assert report.stale_snapshot_count == 1
    assert report.future_only_snapshot_count == 1
    assert report.issue_count == 29
    assert report.coverage[0].expected_combination_count == 30
    assert report.coverage[0].available_combination_count == 2
    assert report.coverage[0].stale_combination_count == 1
    assert report.coverage[0].future_only_combination_count == 1
    assert (
        race_id,
        BetCombination(BetType.EXACTA_ORDERED, (2, 1)),
        OddsQualityIssueCode.ODDS_STALE,
    ) in {
        (issue.race_id, issue.combination, issue.code) for issue in report.issues
    }
    assert (
        race_id,
        BetCombination(BetType.EXACTA_ORDERED, (3, 4)),
        OddsQualityIssueCode.ODDS_TIME_LEAK_RISK,
    ) in {
        (issue.race_id, issue.combination, issue.code) for issue in report.issues
    }
    assert (
        race_id,
        BetCombination(BetType.EXACTA_ORDERED, (1, 3)),
        OddsQualityIssueCode.ODDS_MISSING,
    ) in {
        (issue.race_id, issue.combination, issue.code) for issue in report.issues
    }


def test_odds_quality_report_rejects_non_odds_records() -> None:
    race_id = RaceId(date(2026, 6, 23), VenueCode("05"), 1)

    with pytest.raises(TypeError, match="odds must contain only OddsSnapshotRecord"):
        build_odds_quality_report(
            odds=(object(),),
            expected_races=(race_id,),
            bet_types=(BetType.EXACTA_ORDERED,),
            prediction_as_of=datetime(2026, 6, 23, 4, 0, tzinfo=UTC),
            max_snapshot_age=timedelta(minutes=10),
        )
