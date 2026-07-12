"""Pre-race odds snapshot quality reports for market-data gates."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from itertools import combinations, permutations

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId
from boatrace_cal.ingestion.odds import OddsSnapshotRecord


class OddsQualityIssueCode(StrEnum):
    """Known odds snapshot quality issue codes."""

    ODDS_MISSING = "odds_missing"
    ODDS_STALE = "odds_stale"
    ODDS_TIME_LEAK_RISK = "odds_time_leak_risk"


@dataclass(frozen=True, slots=True)
class OddsQualityIssue:
    """One missing, stale, or time-unsafe odds snapshot."""

    race_id: RaceId
    code: OddsQualityIssueCode
    bet_type: BetType
    combination: BetCombination

    def __post_init__(self) -> None:
        if type(self.race_id) is not RaceId:
            raise TypeError("race_id must be a RaceId")
        if type(self.code) is not OddsQualityIssueCode:
            raise TypeError("code must be an OddsQualityIssueCode")
        if type(self.bet_type) is not BetType:
            raise TypeError("bet_type must be a BetType")
        if type(self.combination) is not BetCombination:
            raise TypeError("combination must be a BetCombination")
        if self.combination.bet_type is not self.bet_type:
            raise ValueError("combination bet_type must match bet_type")


@dataclass(frozen=True, slots=True)
class OddsCoverageRow:
    """Coverage aggregate for one race and bet type at one prediction cutoff."""

    race_id: RaceId
    bet_type: BetType
    expected_combination_count: int
    available_combination_count: int
    stale_combination_count: int
    future_only_combination_count: int

    def __post_init__(self) -> None:
        if type(self.race_id) is not RaceId:
            raise TypeError("race_id must be a RaceId")
        if type(self.bet_type) is not BetType:
            raise TypeError("bet_type must be a BetType")
        for field_name in (
            "expected_combination_count",
            "available_combination_count",
            "stale_combination_count",
            "future_only_combination_count",
        ):
            value = getattr(self, field_name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.available_combination_count > self.expected_combination_count:
            raise ValueError("available_combination_count must not exceed expected")
        if self.stale_combination_count > self.available_combination_count:
            raise ValueError("stale_combination_count must not exceed available")
        if self.future_only_combination_count > self.expected_combination_count:
            raise ValueError("future_only_combination_count must not exceed expected")


@dataclass(frozen=True, slots=True)
class OddsQualityReport:
    """Deterministic quality summary for pre-race odds snapshots."""

    expected_race_count: int
    expected_snapshot_count: int
    available_snapshot_count: int
    stale_snapshot_count: int
    future_only_snapshot_count: int
    issue_count: int
    issues: tuple[OddsQualityIssue, ...]
    coverage: tuple[OddsCoverageRow, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "expected_race_count",
            "expected_snapshot_count",
            "available_snapshot_count",
            "stale_snapshot_count",
            "future_only_snapshot_count",
            "issue_count",
        ):
            value = getattr(self, field_name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if type(self.issues) is not tuple or any(
            type(issue) is not OddsQualityIssue for issue in self.issues
        ):
            raise TypeError("issues must be a tuple of OddsQualityIssue instances")
        if self.issue_count != len(self.issues):
            raise ValueError("issue_count must match issues length")
        if type(self.coverage) is not tuple or any(
            type(row) is not OddsCoverageRow for row in self.coverage
        ):
            raise TypeError("coverage must be a tuple of OddsCoverageRow instances")


def build_odds_quality_report(
    *,
    odds: Iterable[OddsSnapshotRecord],
    expected_races: Iterable[RaceId],
    bet_types: Iterable[BetType],
    prediction_as_of: datetime,
    max_snapshot_age: timedelta,
) -> OddsQualityReport:
    """Build an auditable odds coverage and staleness report."""

    normalized_odds = _normalize_odds(odds)
    races = _normalize_expected_races(expected_races)
    expected_bet_types = _normalize_bet_types(bet_types)
    _validate_prediction_as_of(prediction_as_of)
    _validate_max_snapshot_age(max_snapshot_age)

    issues: list[OddsQualityIssue] = []
    coverage_rows: list[OddsCoverageRow] = []
    for race_id in races:
        for bet_type in expected_bet_types:
            expected_combinations = _expected_combinations(bet_type)
            available_count = 0
            stale_count = 0
            future_only_count = 0
            for combination in expected_combinations:
                matching_records = _matching_records(normalized_odds, race_id, combination)
                available_records = tuple(
                    record
                    for record in matching_records
                    if record.available_at <= prediction_as_of
                )
                future_records = tuple(
                    record
                    for record in matching_records
                    if record.available_at > prediction_as_of
                )
                if not available_records:
                    if future_records:
                        future_only_count += 1
                        issues.append(
                            _issue(
                                race_id,
                                bet_type,
                                combination,
                                OddsQualityIssueCode.ODDS_TIME_LEAK_RISK,
                            )
                        )
                    else:
                        issues.append(
                            _issue(
                                race_id,
                                bet_type,
                                combination,
                                OddsQualityIssueCode.ODDS_MISSING,
                            )
                        )
                    continue

                available_count += 1
                latest = max(available_records, key=_snapshot_sort_key)
                if prediction_as_of - latest.available_at > max_snapshot_age:
                    stale_count += 1
                    issues.append(
                        _issue(
                            race_id,
                            bet_type,
                            combination,
                            OddsQualityIssueCode.ODDS_STALE,
                        )
                    )

            coverage_rows.append(
                OddsCoverageRow(
                    race_id=race_id,
                    bet_type=bet_type,
                    expected_combination_count=len(expected_combinations),
                    available_combination_count=available_count,
                    stale_combination_count=stale_count,
                    future_only_combination_count=future_only_count,
                )
            )

    sorted_issues = tuple(sorted(issues, key=_issue_sort_key))
    sorted_coverage = tuple(sorted(coverage_rows, key=_coverage_sort_key))
    return OddsQualityReport(
        expected_race_count=len(races),
        expected_snapshot_count=sum(
            row.expected_combination_count for row in sorted_coverage
        ),
        available_snapshot_count=sum(
            row.available_combination_count for row in sorted_coverage
        ),
        stale_snapshot_count=sum(row.stale_combination_count for row in sorted_coverage),
        future_only_snapshot_count=sum(
            row.future_only_combination_count for row in sorted_coverage
        ),
        issue_count=len(sorted_issues),
        issues=sorted_issues,
        coverage=sorted_coverage,
    )


def _normalize_odds(
    odds: Iterable[OddsSnapshotRecord],
) -> tuple[OddsSnapshotRecord, ...]:
    normalized = tuple(odds)
    if any(type(record) is not OddsSnapshotRecord for record in normalized):
        raise TypeError("odds must contain only OddsSnapshotRecord instances")
    return normalized


def _normalize_expected_races(expected_races: Iterable[RaceId]) -> tuple[RaceId, ...]:
    races = tuple(expected_races)
    if any(type(race_id) is not RaceId for race_id in races):
        raise TypeError("expected_races must contain only RaceId instances")
    return tuple(sorted(set(races), key=_race_sort_key))


def _normalize_bet_types(bet_types: Iterable[BetType]) -> tuple[BetType, ...]:
    normalized = tuple(bet_types)
    if any(type(bet_type) is not BetType for bet_type in normalized):
        raise TypeError("bet_types must contain only BetType instances")
    return tuple(sorted(set(normalized), key=lambda bet_type: bet_type.value))


def _validate_prediction_as_of(prediction_as_of: datetime) -> None:
    if type(prediction_as_of) is not datetime or not _is_aware(prediction_as_of):
        raise ValueError("prediction_as_of must be timezone-aware")


def _validate_max_snapshot_age(max_snapshot_age: timedelta) -> None:
    if type(max_snapshot_age) is not timedelta:
        raise TypeError("max_snapshot_age must be a timedelta")
    if max_snapshot_age < timedelta(0):
        raise ValueError("max_snapshot_age must not be negative")


def _expected_combinations(bet_type: BetType) -> tuple[BetCombination, ...]:
    lane_numbers = range(1, 7)
    lane_groups = (
        permutations(lane_numbers, bet_type.lane_count)
        if bet_type.ordered
        else combinations(lane_numbers, bet_type.lane_count)
    )
    return tuple(BetCombination(bet_type, tuple(lanes)) for lanes in lane_groups)


def _matching_records(
    records: tuple[OddsSnapshotRecord, ...],
    race_id: RaceId,
    combination: BetCombination,
) -> tuple[OddsSnapshotRecord, ...]:
    return tuple(
        record
        for record in records
        if record.race_id == race_id and record.combination == combination
    )


def _issue(
    race_id: RaceId,
    bet_type: BetType,
    combination: BetCombination,
    code: OddsQualityIssueCode,
) -> OddsQualityIssue:
    return OddsQualityIssue(
        race_id=race_id,
        code=code,
        bet_type=bet_type,
        combination=combination,
    )


def _snapshot_sort_key(record: OddsSnapshotRecord) -> tuple[datetime, datetime, str, str]:
    return (record.available_at, record.observed_at, record.source, record.source_hash)


def _issue_sort_key(
    issue: OddsQualityIssue,
) -> tuple[object, str, int, str, str, str]:
    return (
        issue.race_id.race_date,
        issue.race_id.venue.value,
        issue.race_id.race_no,
        issue.bet_type.value,
        issue.combination.key,
        issue.code.value,
    )


def _coverage_sort_key(row: OddsCoverageRow) -> tuple[object, str, int, str]:
    return (
        row.race_id.race_date,
        row.race_id.venue.value,
        row.race_id.race_no,
        row.bet_type.value,
    )


def _race_sort_key(race_id: RaceId) -> tuple[object, str, int]:
    return (race_id.race_date, race_id.venue.value, race_id.race_no)


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None
