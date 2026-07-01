"""Historical dataset quality reports for pre-backtest audit checks."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from boatrace_cal.domain.bets import BetType
from boatrace_cal.domain.races import RaceId
from boatrace_cal.ingestion.payouts import (
    PayoutCompletenessRow,
    PayoutRecord,
    find_missing_payouts,
    summarize_payout_completeness,
)
from boatrace_cal.ingestion.results import RaceResultRecord


class DataQualityIssueCode(StrEnum):
    """Known historical dataset quality issue codes."""

    PAYOUT_MISSING = "payout_missing"
    RESULT_MISSING = "result_missing"


@dataclass(frozen=True, slots=True)
class DataQualityIssue:
    """One missing or invalid historical data point needed for backtesting."""

    race_id: RaceId
    code: DataQualityIssueCode
    bet_type: BetType | None

    def __post_init__(self) -> None:
        if type(self.race_id) is not RaceId:
            raise TypeError("race_id must be a RaceId")
        if type(self.code) is not DataQualityIssueCode:
            raise TypeError("code must be a DataQualityIssueCode")
        if self.bet_type is not None and type(self.bet_type) is not BetType:
            raise TypeError("bet_type must be a BetType or None")


@dataclass(frozen=True, slots=True)
class HistoricalDataQualityReport:
    """Deterministic quality summary for historical result and payout imports."""

    expected_race_count: int
    result_count: int
    payout_count: int
    issue_count: int
    issues: tuple[DataQualityIssue, ...]
    payout_completeness: tuple[PayoutCompletenessRow, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "expected_race_count",
            "result_count",
            "payout_count",
            "issue_count",
        ):
            value = getattr(self, field_name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if type(self.issues) is not tuple or any(
            type(issue) is not DataQualityIssue for issue in self.issues
        ):
            raise TypeError("issues must be a tuple of DataQualityIssue instances")
        if self.issue_count != len(self.issues):
            raise ValueError("issue_count must match issues length")
        if type(self.payout_completeness) is not tuple or any(
            type(row) is not PayoutCompletenessRow for row in self.payout_completeness
        ):
            raise TypeError(
                "payout_completeness must be a tuple of PayoutCompletenessRow instances"
            )


def build_historical_data_quality_report(
    *,
    results: Iterable[RaceResultRecord],
    payouts: Iterable[PayoutRecord],
    expected_races: Iterable[RaceId],
    bet_types: Iterable[BetType],
) -> HistoricalDataQualityReport:
    """Build an auditable quality report for completed historical race imports."""

    normalized_results = _normalize_results(results)
    normalized_payouts = _normalize_payouts(payouts)
    races = _normalize_expected_races(expected_races)
    expected_bet_types = _normalize_bet_types(bet_types)

    present_result_races = {result.race_id for result in normalized_results}
    issues = [
        DataQualityIssue(
            race_id=race_id,
            code=DataQualityIssueCode.RESULT_MISSING,
            bet_type=None,
        )
        for race_id in races
        if race_id not in present_result_races
    ]
    issues.extend(
        DataQualityIssue(
            race_id=row.race_id,
            code=DataQualityIssueCode.PAYOUT_MISSING,
            bet_type=row.bet_type,
        )
        for row in find_missing_payouts(
            normalized_payouts,
            races,
            expected_bet_types,
        )
    )
    sorted_issues = tuple(sorted(issues, key=_issue_sort_key))

    return HistoricalDataQualityReport(
        expected_race_count=len(races),
        result_count=len(normalized_results),
        payout_count=len(normalized_payouts),
        issue_count=len(sorted_issues),
        issues=sorted_issues,
        payout_completeness=summarize_payout_completeness(normalized_payouts),
    )


def _normalize_results(
    results: Iterable[RaceResultRecord],
) -> tuple[RaceResultRecord, ...]:
    normalized = tuple(results)
    if any(type(result) is not RaceResultRecord for result in normalized):
        raise TypeError("results must contain only RaceResultRecord instances")
    return normalized


def _normalize_payouts(payouts: Iterable[PayoutRecord]) -> tuple[PayoutRecord, ...]:
    normalized = tuple(payouts)
    if any(type(payout) is not PayoutRecord for payout in normalized):
        raise TypeError("payouts must contain only PayoutRecord instances")
    return normalized


def _normalize_expected_races(expected_races: Iterable[RaceId]) -> tuple[RaceId, ...]:
    races = tuple(expected_races)
    if any(type(race_id) is not RaceId for race_id in races):
        raise TypeError("expected_races must contain only RaceId instances")
    return races


def _normalize_bet_types(bet_types: Iterable[BetType]) -> tuple[BetType, ...]:
    normalized = tuple(bet_types)
    if any(type(bet_type) is not BetType for bet_type in normalized):
        raise TypeError("bet_types must contain only BetType instances")
    return normalized


def _issue_sort_key(
    issue: DataQualityIssue,
) -> tuple[object, str, int, str, str]:
    return (
        issue.race_id.race_date,
        issue.race_id.venue.value,
        issue.race_id.race_no,
        issue.code.value,
        issue.bet_type.value if issue.bet_type is not None else "",
    )
