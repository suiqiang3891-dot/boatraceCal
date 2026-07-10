"""JSON-ready serialization for historical paper backtest reports."""

from decimal import Decimal
from typing import Any

from boatrace_cal.backtest.equity import EquityCurve, EquityCurvePoint
from boatrace_cal.backtest.runner import BacktestReport
from boatrace_cal.backtest.settlement import BacktestSettlementRow
from boatrace_cal.backtest.summary import BacktestSlice, BacktestSummary
from boatrace_cal.domain.bets import BetCombination
from boatrace_cal.domain.races import RaceId
from boatrace_cal.domain.recommendations import Recommendation
from boatrace_cal.domain.versions import ArtifactVersions
from boatrace_cal.settlement import SettlementResult
from boatrace_cal.validation.data_quality import DataQualityIssue


JsonValue = dict[str, Any] | list[Any] | str | int | bool | None


def backtest_report_to_dict(report: BacktestReport) -> dict[str, JsonValue]:
    """Convert a backtest report to a JSON-ready dictionary."""

    if type(report) is not BacktestReport:
        raise TypeError("report must be a BacktestReport")
    return {
        "readiness": {
            "status": report.readiness.status.value,
            "ready": report.readiness.ready,
            "refusal_reason": report.readiness.refusal_reason,
            "blocker_count": report.readiness.blocker_count,
            "blockers": [_issue_to_dict(issue) for issue in report.readiness.blockers],
            "quality_report": {
                "expected_race_count": report.readiness.quality_report.expected_race_count,
                "result_count": report.readiness.quality_report.result_count,
                "payout_count": report.readiness.quality_report.payout_count,
                "issue_count": report.readiness.quality_report.issue_count,
            },
        },
        "settlements": None
        if report.settlements is None
        else [_settlement_row_to_dict(row) for row in report.settlements],
        "summary": None if report.summary is None else _summary_to_dict(report.summary),
        "equity_curve": None
        if report.equity_curve is None
        else _equity_curve_to_dict(report.equity_curve),
        "slices": None if report.slices is None else [_slice_to_dict(item) for item in report.slices],
    }


def _issue_to_dict(issue: DataQualityIssue) -> dict[str, JsonValue]:
    return {
        "race_id": _race_id_to_str(issue.race_id),
        "code": issue.code.value,
        "bet_type": issue.bet_type.value if issue.bet_type is not None else None,
    }


def _settlement_row_to_dict(row: BacktestSettlementRow) -> dict[str, JsonValue]:
    return {
        "recommendation_id": row.recommendation_id,
        "race_id": _race_id_to_str(row.race_id),
        "stake_units": row.stake_units,
        "stake_yen": _decimal_to_str(row.stake_yen),
        "returned_yen": _decimal_to_str(row.returned_yen),
        "net_profit_yen": _decimal_to_str(row.net_profit_yen),
        "recommendation": _recommendation_to_dict(row.recommendation),
        "settlement": _settlement_to_dict(row.settlement),
    }


def _recommendation_to_dict(recommendation: Recommendation) -> dict[str, JsonValue]:
    return {
        "stage": recommendation.stage.value,
        "decision": recommendation.decision.value,
        "confidence": recommendation.confidence.value,
        "probability": _decimal_to_str(recommendation.probability),
        "odds": None if recommendation.odds is None else _decimal_to_str(recommendation.odds),
        "expected_value": None
        if recommendation.expected_value is None
        else _decimal_to_str(recommendation.expected_value),
        "as_of": recommendation.as_of.isoformat(),
        "stake_units": recommendation.stake_units,
        "versions": _versions_to_dict(recommendation.versions),
        "reason_codes": list(recommendation.reason_codes),
    }


def _versions_to_dict(versions: ArtifactVersions) -> dict[str, JsonValue]:
    return {
        "data": versions.data,
        "feature": versions.feature,
        "model": versions.model,
        "strategy": versions.strategy,
    }


def _settlement_to_dict(settlement: SettlementResult) -> dict[str, JsonValue]:
    return {
        "race_id": _race_id_to_str(settlement.race_id),
        "combination": _combination_to_dict(settlement.combination),
        "status": settlement.status.value,
        "payout_yen": _decimal_to_str(settlement.payout_yen),
    }


def _combination_to_dict(combination: BetCombination) -> dict[str, JsonValue]:
    return {
        "bet_type": combination.bet_type.value,
        "lanes": list(combination.lanes),
    }


def _summary_to_dict(summary: BacktestSummary) -> dict[str, JsonValue]:
    return {
        "expected_race_count": summary.expected_race_count,
        "selected_bet_count": summary.selected_bet_count,
        "selected_race_count": summary.selected_race_count,
        "hit_count": summary.hit_count,
        "miss_count": summary.miss_count,
        "payout_missing_count": summary.payout_missing_count,
        "total_stake_yen": _decimal_to_str(summary.total_stake_yen),
        "total_returned_yen": _decimal_to_str(summary.total_returned_yen),
        "net_profit_yen": _decimal_to_str(summary.net_profit_yen),
        "return_rate": _decimal_to_str(summary.return_rate),
        "hit_rate": _decimal_to_str(summary.hit_rate),
        "coverage_rate": _decimal_to_str(summary.coverage_rate),
    }


def _slice_to_dict(item: BacktestSlice) -> dict[str, JsonValue]:
    return {
        "dimension": item.dimension,
        "key": item.key,
        "selected_bet_count": item.selected_bet_count,
        "selected_race_count": item.selected_race_count,
        "hit_count": item.hit_count,
        "miss_count": item.miss_count,
        "payout_missing_count": item.payout_missing_count,
        "total_stake_yen": _decimal_to_str(item.total_stake_yen),
        "total_returned_yen": _decimal_to_str(item.total_returned_yen),
        "net_profit_yen": _decimal_to_str(item.net_profit_yen),
        "return_rate": _decimal_to_str(item.return_rate),
        "hit_rate": _decimal_to_str(item.hit_rate),
    }


def _equity_curve_to_dict(curve: EquityCurve) -> dict[str, JsonValue]:
    return {
        "points": [_equity_point_to_dict(point) for point in curve.points],
        "final_equity_yen": _decimal_to_str(curve.final_equity_yen),
        "max_drawdown_yen": _decimal_to_str(curve.max_drawdown_yen),
        "max_drawdown_rate": _decimal_to_str(curve.max_drawdown_rate),
    }


def _equity_point_to_dict(point: EquityCurvePoint) -> dict[str, JsonValue]:
    return {
        "race_id": _race_id_to_str(point.race_id),
        "recommendation_id": point.recommendation_id,
        "equity_yen": _decimal_to_str(point.equity_yen),
        "peak_equity_yen": _decimal_to_str(point.peak_equity_yen),
        "drawdown_yen": _decimal_to_str(point.drawdown_yen),
        "drawdown_rate": _decimal_to_str(point.drawdown_rate),
    }


def _race_id_to_str(race_id: RaceId) -> str:
    return str(race_id)


def _decimal_to_str(value: Decimal) -> str:
    return str(value)
