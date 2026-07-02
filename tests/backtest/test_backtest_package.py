from boatrace_cal.backtest import (
    BacktestReadiness,
    BacktestReport,
    BacktestSettlementRow,
    BacktestSummary,
    EquityCurve,
    export_backtest_report_json,
    run_backtest,
)


def test_backtest_package_exposes_stable_entry_points() -> None:
    assert BacktestReadiness.__name__ == "BacktestReadiness"
    assert BacktestReport.__name__ == "BacktestReport"
    assert BacktestSettlementRow.__name__ == "BacktestSettlementRow"
    assert BacktestSummary.__name__ == "BacktestSummary"
    assert EquityCurve.__name__ == "EquityCurve"
    assert run_backtest.__name__ == "run_backtest"
    assert export_backtest_report_json.__name__ == "export_backtest_report_json"
