from __future__ import annotations

import json
from pathlib import Path
import tomllib

from boatrace_cal.cli import main


def test_historical_quality_report_command_writes_json_report(tmp_path: Path) -> None:
    results_path = tmp_path / "results.csv"
    payouts_path = tmp_path / "payouts.csv"
    output_path = tmp_path / "reports" / "quality.json"
    results_path.write_text(
        "\n".join(
            (
                "race_date,venue,race_no,first,second,third,source,source_hash,"
                "observed_at,available_at,parser_version",
                "2025-01-02,01,1,1,2,3,official-results,result-hash,"
                "2025-01-02T16:00:00+00:00,2025-01-02T16:00:00+00:00,results-v1",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    payouts_path.write_text(
        "\n".join(
            (
                "race_date,venue,race_no,bet_type,combination,payout_yen,source,source_hash,"
                "observed_at,available_at,parser_version",
                "2025-01-02,01,1,trifecta_ordered,1-2-3,1200,official-payouts,"
                "payout-hash,2025-01-02T16:00:00+00:00,"
                "2025-01-02T16:00:00+00:00,payouts-v1",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        (
            "historical-quality-report",
            "--results",
            str(results_path),
            "--payouts",
            str(payouts_path),
            "--expected-race",
            "2025-01-02:01:1",
            "--expected-race",
            "2025-01-02:01:2",
            "--bet-type",
            "trifecta_ordered",
            "--output",
            str(output_path),
        )
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["expected_race_count"] == 2
    assert payload["result_count"] == 1
    assert payload["payout_count"] == 1
    assert payload["issue_count"] == 2
    assert payload["issues"] == [
        {
            "race_id": "20250102-01-02",
            "code": "payout_missing",
            "bet_type": "trifecta_ordered",
        },
        {
            "race_id": "20250102-01-02",
            "code": "result_missing",
            "bet_type": None,
        },
    ]
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_backtest_report_command_writes_json_report(tmp_path: Path) -> None:
    recommendations_path = tmp_path / "recommendations.csv"
    results_path = tmp_path / "results.csv"
    payouts_path = tmp_path / "payouts.csv"
    output_path = tmp_path / "reports" / "backtest.json"
    recommendations_path.write_text(
        "\n".join(
            (
                "recommendation_id,race_date,venue,race_no,bet_type,combination,"
                "stage,decision,confidence,probability,odds,expected_value,as_of,"
                "stake_units,data_version,feature_version,model_version,strategy_version,"
                "reason_codes",
                "rec-1,2025-01-02,01,1,trifecta_ordered,1-2-3,final,select,high,"
                "0.25,5.2,0.30,2025-01-02T10:00:00+00:00,1,data-v1,feature-v1,"
                "model-v1,strategy-v1,positive_ev",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    results_path.write_text(
        "\n".join(
            (
                "race_date,venue,race_no,first,second,third,source,source_hash,"
                "observed_at,available_at,parser_version",
                "2025-01-02,01,1,1,2,3,official-results,result-hash,"
                "2025-01-02T16:00:00+00:00,2025-01-02T16:00:00+00:00,results-v1",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    payouts_path.write_text(
        "\n".join(
            (
                "race_date,venue,race_no,bet_type,combination,payout_yen,source,source_hash,"
                "observed_at,available_at,parser_version",
                "2025-01-02,01,1,trifecta_ordered,1-2-3,1200,official-payouts,"
                "payout-hash,2025-01-02T16:00:00+00:00,"
                "2025-01-02T16:00:00+00:00,payouts-v1",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        (
            "backtest-report",
            "--recommendations",
            str(recommendations_path),
            "--results",
            str(results_path),
            "--payouts",
            str(payouts_path),
            "--expected-race",
            "2025-01-02:01:1",
            "--bet-type",
            "trifecta_ordered",
            "--output",
            str(output_path),
        )
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["readiness"]["status"] == "ready"
    assert payload["summary"]["selected_bet_count"] == 1
    assert payload["summary"]["net_profit_yen"] == "1100"
    assert payload["equity_curve"]["final_equity_yen"] == "1100"
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_pyproject_exposes_console_script() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"]["boatrace-cal"] == "boatrace_cal.cli:main"
