"""JSON-ready serialization for historical data quality reports."""

from typing import Any

from boatrace_cal.ingestion.payouts import PayoutCompletenessRow
from boatrace_cal.validation.data_quality import (
    DataQualityIssue,
    HistoricalDataQualityReport,
)


JsonValue = dict[str, Any] | list[Any] | str | int | bool | None


def historical_data_quality_report_to_dict(
    report: HistoricalDataQualityReport,
) -> dict[str, JsonValue]:
    """Convert a historical data quality report to a JSON-ready dictionary."""

    if type(report) is not HistoricalDataQualityReport:
        raise TypeError("report must be a HistoricalDataQualityReport")
    return {
        "expected_race_count": report.expected_race_count,
        "result_count": report.result_count,
        "payout_count": report.payout_count,
        "issue_count": report.issue_count,
        "issues": [_issue_to_dict(issue) for issue in report.issues],
        "payout_completeness": [
            _payout_completeness_row_to_dict(row) for row in report.payout_completeness
        ],
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
