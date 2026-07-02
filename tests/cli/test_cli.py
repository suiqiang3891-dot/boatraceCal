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


def test_pyproject_exposes_console_script() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"]["boatrace-cal"] == "boatrace_cal.cli:main"
