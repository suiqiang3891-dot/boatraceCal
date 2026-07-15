"""JSON-ready serialization for historical data quality reports."""

from typing import Any

from boatrace_cal.ingestion.payouts import PayoutCompletenessRow
from boatrace_cal.validation.data_quality import (
    DataQualityIssue,
    HistoricalDataQualityReport,
)
from boatrace_cal.validation.odds_quality import (
    OddsCoverageRow,
    OddsQualityIssue,
    OddsQualityReport,
)


JsonValue = dict[str, Any] | list[Any] | str | int | bool | None


def historical_data_quality_report_to_dict(
    report: HistoricalDataQualityReport,
) -> dict[str, JsonValue]:
    """Convert a historical data quality report to a JSON-ready dictionary."""

    if type(report) is not HistoricalDataQualityReport:
        raise TypeError("report must be a HistoricalDataQualityReport")
    return {
        "schema_version": "historical-data-quality-report-v1",
        "expected_race_count": report.expected_race_count,
        "result_count": report.result_count,
        "payout_count": report.payout_count,
        "issue_count": report.issue_count,
        "issues": [_issue_to_dict(issue) for issue in report.issues],
        "payout_completeness": [
            _payout_completeness_row_to_dict(row) for row in report.payout_completeness
        ],
    }


def odds_quality_report_to_dict(report: OddsQualityReport) -> dict[str, JsonValue]:
    """Convert an odds quality report to a JSON-ready dictionary."""

    if type(report) is not OddsQualityReport:
        raise TypeError("report must be an OddsQualityReport")
    return {
        "schema_version": "odds-quality-report-v1",
        "expected_race_count": report.expected_race_count,
        "expected_snapshot_count": report.expected_snapshot_count,
        "available_snapshot_count": report.available_snapshot_count,
        "stale_snapshot_count": report.stale_snapshot_count,
        "future_only_snapshot_count": report.future_only_snapshot_count,
        "issue_count": report.issue_count,
        "issues": [_odds_issue_to_dict(issue) for issue in report.issues],
        "coverage": [_odds_coverage_row_to_dict(row) for row in report.coverage],
    }


def _issue_to_dict(issue: DataQualityIssue) -> dict[str, JsonValue]:
    return {
        "race_id": str(issue.race_id),
        "code": issue.code.value,
        "bet_type": issue.bet_type.value if issue.bet_type is not None else None,
    }


def _payout_completeness_row_to_dict(
    row: PayoutCompletenessRow,
) -> dict[str, JsonValue]:
    return {
        "race_date": row.race_date.isoformat(),
        "venue": row.venue.value,
        "bet_type": row.bet_type.value,
        "payout_count": row.payout_count,
        "race_count": row.race_count,
        "total_payout_yen": str(row.total_payout_yen),
    }


def _odds_issue_to_dict(issue: OddsQualityIssue) -> dict[str, JsonValue]:
    return {
        "race_id": str(issue.race_id),
        "code": issue.code.value,
        "bet_type": issue.bet_type.value,
        "combination": issue.combination.key,
    }


def _odds_coverage_row_to_dict(row: OddsCoverageRow) -> dict[str, JsonValue]:
    return {
        "race_id": str(row.race_id),
        "bet_type": row.bet_type.value,
        "expected_combination_count": row.expected_combination_count,
        "available_combination_count": row.available_combination_count,
        "stale_combination_count": row.stale_combination_count,
        "future_only_combination_count": row.future_only_combination_count,
    }
