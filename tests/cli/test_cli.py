from __future__ import annotations

import json
from pathlib import Path
import tomllib
from zipfile import ZipFile

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


def test_historical_quality_report_command_accepts_expected_race_range(
    tmp_path: Path,
) -> None:
    results_path = tmp_path / "results.csv"
    payouts_path = tmp_path / "payouts.csv"
    output_path = tmp_path / "reports" / "quality-range.json"
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
    assert payload["expected_race_count"] == 2
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


def test_candidate_status_command_writes_business_date_status(tmp_path: Path) -> None:
    output_path = tmp_path / "api" / "status.json"

    exit_code = main(
        (
            "candidate-status",
            "--business-date",
            "2025-01-02",
            "--report",
            "examples/sample_backtest/report.json",
            "--output",
            str(output_path),
        )
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload == {
        "business_date": "2025-01-02",
        "status": "ready",
        "risk_notice": (
            "历史表现不代表未来结果；本系统只提供分析与回测，"
            "不承诺盈利，不提供自动下单。"
        ),
    }
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_candidate_list_command_writes_candidate_summaries(tmp_path: Path) -> None:
    output_path = tmp_path / "api" / "candidates.json"

    exit_code = main(
        (
            "candidate-list",
            "--business-date",
            "2025-01-02",
            "--report",
            "examples/sample_backtest/report.json",
            "--output",
            str(output_path),
        )
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["business_date"] == "2025-01-02"
    assert [candidate["recommendation_id"] for candidate in payload["candidates"]] == [
        "sample-rec-hit",
        "sample-rec-miss",
    ]
    assert payload["candidates"][0]["decision"] == "select"
    assert payload["candidates"][0]["stake_units"] == 1
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_candidate_detail_command_writes_explanation(tmp_path: Path) -> None:
    output_path = tmp_path / "api" / "candidate-detail.json"

    exit_code = main(
        (
            "candidate-detail",
            "--business-date",
            "2025-01-02",
            "--recommendation-id",
            "sample-rec-hit",
            "--report",
            "examples/sample_backtest/report.json",
            "--output",
            str(output_path),
        )
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["recommendation_id"] == "sample-rec-hit"
    assert payload["race_id"] == "20250102-01-01"
    assert payload["versions"] == {
        "data": "sample-data-v1",
        "feature": "sample-feature-v1",
        "model": "sample-model-v1",
        "strategy": "sample-strategy-v1",
    }
    assert payload["explanation"] == (
        "模型概率 25.0%，市场赔率 5.20，期望值 +30.0%；"
        "置信度 high，原因 positive_ev / sample。"
    )
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_confirmed_review_list_command_writes_confirmed_reviews(tmp_path: Path) -> None:
    reviews_path = tmp_path / "reviews.json"
    output_path = tmp_path / "reviews" / "confirmed-list.json"
    reviews_path.write_text(
        json.dumps(
            [
                {
                    "recommendation_id": "rec-2",
                    "race_id": "20250102-01-02",
                    "decision": "confirmed",
                    "stake_units": 1,
                    "notes": "second",
                    "reviewed_at": "2026-07-11T03:30:00+00:00",
                    "reviewed_by": "analyst",
                },
                {
                    "recommendation_id": "rec-pass",
                    "race_id": "20250102-01-03",
                    "decision": "pass",
                    "stake_units": 0,
                    "notes": "odds moved",
                    "reviewed_at": "2026-07-11T03:40:00+00:00",
                    "reviewed_by": "analyst",
                },
                {
                    "recommendation_id": "rec-1",
                    "race_id": "20250102-01-01",
                    "decision": "confirmed",
                    "stake_units": 3,
                    "notes": "first",
                    "reviewed_at": "2026-07-11T03:20:00+00:00",
                    "reviewed_by": "analyst",
                },
            ],
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        (
            "confirmed-review-list",
            "--reviews",
            str(reviews_path),
            "--business-date",
            "2025-01-02",
            "--generated-at",
            "2026-07-11T04:00:00+00:00",
            "--generated-by",
            "analyst",
            "--output",
            str(output_path),
        )
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["business_date"] == "2025-01-02"
    assert payload["total_stake_units"] == 4
    assert [entry["recommendation_id"] for entry in payload["entries"]] == ["rec-1", "rec-2"]
    assert "历史表现不代表未来结果" in payload["risk_notice"]
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_review_store_import_command_upserts_browser_review_export(tmp_path: Path) -> None:
    store_path = tmp_path / "server" / "reviews.json"
    import_path = tmp_path / "browser" / "reviews.json"
    store_path.parent.mkdir(parents=True)
    import_path.parent.mkdir(parents=True)
    store_path.write_text(
        json.dumps(
            [
                {
                    "recommendation_id": "rec-1",
                    "race_id": "20250102-01-01",
                    "decision": "pending",
                    "stake_units": 1,
                    "notes": "old",
                    "reviewed_at": "2026-07-11T03:00:00+00:00",
                    "reviewed_by": "analyst",
                }
            ],
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    import_path.write_text(
        json.dumps(
            {
                "reviews": [
                    {
                        "recommendation_id": "rec-2",
                        "race_id": "20250102-01-02",
                        "decision": "pass",
                        "stake_units": 0,
                        "notes": "odds moved",
                        "reviewed_at": "2026-07-11T03:30:00+00:00",
                        "reviewed_by": "browser-analyst",
                    },
                    {
                        "recommendation_id": "rec-1",
                        "race_id": "20250102-01-01",
                        "decision": "confirmed",
                        "stake_units": 3,
                        "notes": "replace old",
                        "reviewed_at": "2026-07-11T03:20:00+00:00",
                        "reviewed_by": "browser-analyst",
                    },
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        (
            "review-store-import",
            "--store",
            str(store_path),
            "--reviews",
            str(import_path),
        )
    )

    assert exit_code == 0
    payload = json.loads(store_path.read_text(encoding="utf-8"))
    assert [record["recommendation_id"] for record in payload] == ["rec-1", "rec-2"]
    assert payload[0]["decision"] == "confirmed"
    assert payload[0]["stake_units"] == 3
    assert payload[0]["notes"] == "replace old"
    assert payload[1]["decision"] == "pass"
    assert payload[1]["stake_units"] == 0
    assert store_path.read_text(encoding="utf-8").endswith("\n")


def test_review_workflow_import_command_writes_openapi_response(tmp_path: Path) -> None:
    store_path = tmp_path / "server" / "reviews.json"
    input_path = tmp_path / "browser" / "reviews.json"
    output_path = tmp_path / "responses" / "review-import.json"
    input_path.parent.mkdir(parents=True)
    input_path.write_text(
        json.dumps(
            {
                "reviews": [
                    {
                        "recommendation_id": "rec-api-1",
                        "race_id": "20250102-01-01",
                        "decision": "confirmed",
                        "stake_units": 2,
                        "notes": "api handoff",
                        "reviewed_at": "2026-07-11T03:20:00+00:00",
                        "reviewed_by": "browser-analyst",
                    },
                    {
                        "recommendation_id": "rec-api-pass",
                        "race_id": "20250102-01-02",
                        "decision": "pass",
                        "stake_units": 0,
                        "notes": "skip",
                        "reviewed_at": "2026-07-11T03:30:00+00:00",
                        "reviewed_by": "browser-analyst",
                    },
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        (
            "review-workflow-import",
            "--store",
            str(store_path),
            "--archive-dir",
            str(tmp_path / "archives"),
            "--export-dir",
            str(tmp_path / "exports"),
            "--reviews",
            str(input_path),
            "--output",
            str(output_path),
        )
    )

    assert exit_code == 0
    assert json.loads(output_path.read_text(encoding="utf-8")) == {"stored_count": 2}
    stored_reviews = json.loads(store_path.read_text(encoding="utf-8"))
    assert [review["recommendation_id"] for review in stored_reviews] == [
        "rec-api-1",
        "rec-api-pass",
    ]
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_confirmed_review_archive_command_freezes_store_checklist(tmp_path: Path) -> None:
    store_path = tmp_path / "server" / "reviews.json"
    archive_dir = tmp_path / "archives"
    store_path.parent.mkdir(parents=True)
    store_path.write_text(
        json.dumps(
            [
                {
                    "recommendation_id": "rec-1",
                    "race_id": "20250102-01-01",
                    "decision": "confirmed",
                    "stake_units": 3,
                    "notes": "keep",
                    "reviewed_at": "2026-07-11T03:20:00+00:00",
                    "reviewed_by": "analyst",
                },
                {
                    "recommendation_id": "rec-pass",
                    "race_id": "20250102-01-02",
                    "decision": "pass",
                    "stake_units": 0,
                    "notes": "skip",
                    "reviewed_at": "2026-07-11T03:30:00+00:00",
                    "reviewed_by": "analyst",
                },
            ],
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        (
            "confirmed-review-archive",
            "--store",
            str(store_path),
            "--business-date",
            "2025-01-02",
            "--generated-at",
            "2026-07-11T04:00:00+00:00",
            "--generated-by",
            "analyst",
            "--frozen-at",
            "2026-07-11T04:10:00+00:00",
            "--frozen-by",
            "analyst",
            "--archive-dir",
            str(archive_dir),
        )
    )

    assert exit_code == 0
    archive_paths = list(archive_dir.glob("2025-01-02-*.json"))
    assert len(archive_paths) == 1
    payload = json.loads(archive_paths[0].read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "confirmed_review_list"
    assert payload["schema_version"] == "confirmed-review-list-v1"
    assert payload["frozen_by"] == "analyst"
    assert payload["checklist"]["total_stake_units"] == 3
    assert [entry["recommendation_id"] for entry in payload["checklist"]["entries"]] == [
        "rec-1"
    ]


def test_confirmed_review_excel_command_exports_store_checklist(tmp_path: Path) -> None:
    store_path = tmp_path / "server" / "reviews.json"
    output_path = tmp_path / "exports" / "confirmed.xlsx"
    store_path.parent.mkdir(parents=True)
    store_path.write_text(
        json.dumps(
            [
                {
                    "recommendation_id": "rec-1",
                    "race_id": "20250102-01-01",
                    "decision": "confirmed",
                    "stake_units": 3,
                    "notes": "keep",
                    "reviewed_at": "2026-07-11T03:20:00+00:00",
                    "reviewed_by": "analyst",
                },
                {
                    "recommendation_id": "rec-pass",
                    "race_id": "20250102-01-02",
                    "decision": "pass",
                    "stake_units": 0,
                    "notes": "skip",
                    "reviewed_at": "2026-07-11T03:30:00+00:00",
                    "reviewed_by": "analyst",
                },
            ],
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        (
            "confirmed-review-excel",
            "--store",
            str(store_path),
            "--business-date",
            "2025-01-02",
            "--generated-at",
            "2026-07-11T04:00:00+00:00",
            "--generated-by",
            "analyst",
            "--output",
            str(output_path),
        )
    )

    assert exit_code == 0
    with ZipFile(output_path) as workbook:
        sheet_xml = workbook.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "boatraceCal confirmed review list" in sheet_xml
    assert "rec-1" in sheet_xml
    assert "rec-pass" not in sheet_xml


def test_review_table_excel_command_exports_all_store_reviews(tmp_path: Path) -> None:
    store_path = tmp_path / "server" / "reviews.json"
    output_path = tmp_path / "exports" / "review-table.xlsx"
    store_path.parent.mkdir(parents=True)
    store_path.write_text(
        json.dumps(
            [
                {
                    "recommendation_id": "rec-pending",
                    "race_id": "20250102-01-01",
                    "decision": "pending",
                    "stake_units": 1,
                    "notes": "watch",
                    "reviewed_at": "2026-07-11T03:00:00+00:00",
                    "reviewed_by": "analyst",
                },
                {
                    "recommendation_id": "rec-pass",
                    "race_id": "20250102-01-02",
                    "decision": "pass",
                    "stake_units": 0,
                    "notes": "skip",
                    "reviewed_at": "2026-07-11T03:30:00+00:00",
                    "reviewed_by": "analyst",
                },
            ],
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        (
            "review-table-excel",
            "--store",
            str(store_path),
            "--business-date",
            "2025-01-02",
            "--generated-at",
            "2026-07-11T04:00:00+00:00",
            "--generated-by",
            "analyst",
            "--output",
            str(output_path),
        )
    )

    assert exit_code == 0
    with ZipFile(output_path) as workbook:
        sheet_xml = workbook.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "boatraceCal review table" in sheet_xml
    assert "rec-pending" in sheet_xml
    assert "rec-pass" in sheet_xml
    assert "review_count" in sheet_xml


def test_review_workflow_export_command_writes_queryable_export_job(tmp_path: Path) -> None:
    store_path = tmp_path / "server" / "reviews.json"
    export_dir = tmp_path / "exports"
    job_status_path = tmp_path / "api" / "job-status.json"
    store_path.parent.mkdir(parents=True)
    store_path.write_text(
        json.dumps(
            [
                {
                    "recommendation_id": "rec-confirmed",
                    "race_id": "20250102-01-01",
                    "decision": "confirmed",
                    "stake_units": 2,
                    "notes": "keep",
                    "reviewed_at": "2026-07-11T03:20:00+00:00",
                    "reviewed_by": "analyst",
                }
            ],
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    export_exit_code = main(
        (
            "review-workflow-export",
            "--store",
            str(store_path),
            "--archive-dir",
            str(tmp_path / "archives"),
            "--export-dir",
            str(export_dir),
            "--business-date",
            "2025-01-02",
            "--export-type",
            "confirmed_list",
            "--generated-at",
            "2026-07-11T04:00:00+00:00",
            "--generated-by",
            "analyst",
        )
    )
    status_exit_code = main(
        (
            "export-job-status",
            "--store",
            str(store_path),
            "--archive-dir",
            str(tmp_path / "archives"),
            "--export-dir",
            str(export_dir),
            "--job-id",
            "confirmed-list-2025-01-02",
            "--output",
            str(job_status_path),
        )
    )

    assert export_exit_code == 0
    assert status_exit_code == 0
    payload = json.loads(job_status_path.read_text(encoding="utf-8"))
    assert payload["job_id"] == "confirmed-list-2025-01-02"
    assert payload["status"] == "done"
    assert payload["artifact_path"].endswith("confirmed-list-2025-01-02.xlsx")
    assert payload["content_type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert (export_dir / "confirmed-list-2025-01-02.json").exists()
    assert job_status_path.read_text(encoding="utf-8").endswith("\n")


def test_openapi_spec_command_writes_contract(tmp_path: Path) -> None:
    output_path = tmp_path / "api" / "openapi.json"

    exit_code = main(("openapi-spec", "--output", str(output_path)))

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["openapi"] == "3.1.0"
    assert "/reviews/import" in payload["paths"]
    assert "/reviews/archives" in payload["paths"]
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_pyproject_exposes_console_script() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"]["boatrace-cal"] == "boatrace_cal.cli:main"
