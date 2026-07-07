"""Backtesting entry points and guardrails."""

from boatrace_cal.backtest.equity import (
    EquityCurve,
    EquityCurvePoint,
    build_equity_curve,
)
from boatrace_cal.backtest.export import export_backtest_report_json
from boatrace_cal.backtest.preflight import (
    BacktestReadiness,
    BacktestReadinessStatus,
    check_backtest_inputs_ready,
)
from boatrace_cal.backtest.runner import BacktestReport, run_backtest
from boatrace_cal.backtest.serialization import backtest_report_to_dict
from boatrace_cal.backtest.settlement import (
    BacktestSettlementRow,
    settle_selected_recommendations,
)
from boatrace_cal.backtest.summary import (
    BacktestSlice,
    BacktestSummary,
    build_backtest_slices,
    summarize_backtest_settlements,
)

__all__ = [
    "BacktestReadiness",
    "BacktestReadinessStatus",
    "BacktestReport",
    "BacktestSettlementRow",
    "BacktestSlice",
    "BacktestSummary",
    "EquityCurve",
    "EquityCurvePoint",
    "backtest_report_to_dict",
    "build_equity_curve",
    "build_backtest_slices",
    "check_backtest_inputs_ready",
    "export_backtest_report_json",
    "run_backtest",
    "settle_selected_recommendations",
    "summarize_backtest_settlements",
]
