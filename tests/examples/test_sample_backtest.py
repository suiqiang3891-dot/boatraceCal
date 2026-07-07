import json
from pathlib import Path

from boatrace_cal.cli import main


def test_sample_backtest_inputs_generate_ready_report(tmp_path: Path) -> None:
    sample_dir = Path("examples/sample_backtest")
    output_path = tmp_path / "sample-backtest-report.json"

    exit_code = main(
        (
            "backtest-report",
            "--recommendations",
            str(sample_dir / "recommendations.csv"),
            "--results",
            str(sample_dir / "results.csv"),
            "--payouts",
            str(sample_dir / "payouts.csv"),
            "--expected-date",
            "2025-01-02",
            "--venue",
            "01",
            "--race-nos",
            "1-2",
            "--bet-type",
            "trifecta_ordered",
            "--output",
            str(output_path),
        )
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["readiness"]["status"] == "ready"
    assert payload["summary"]["expected_race_count"] == 2
    assert payload["summary"]["selected_bet_count"] == 2
    assert payload["summary"]["net_profit_yen"] == "900"
    assert payload["equity_curve"]["final_equity_yen"] == "900"
