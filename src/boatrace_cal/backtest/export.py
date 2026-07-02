"""File export helpers for historical paper backtest reports."""

import json
from pathlib import Path

from boatrace_cal.backtest.runner import BacktestReport
from boatrace_cal.backtest.serialization import backtest_report_to_dict


def export_backtest_report_json(report: BacktestReport, path: Path | str) -> Path:
    """Write a backtest report as deterministic UTF-8 JSON and return the path."""

    if type(report) is not BacktestReport:
        raise TypeError("report must be a BacktestReport")
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = backtest_report_to_dict(report)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path
