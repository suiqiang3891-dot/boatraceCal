from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import tomllib
from zipfile import ZipFile

import boatrace_cal.cli as cli_module
from boatrace_cal.cli import main
from boatrace_cal.api_adapter import ApiRequest
from boatrace_cal.domain.recommendations import Decision
from boatrace_cal.ingestion.recommendations import load_recommendations_csv
from boatrace_cal.strategies.csv import load_strategy_candidates_csv


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


def test_odds_quality_report_command_writes_snapshot_coverage_report(
    tmp_path: Path,
) -> None:
    odds_path = tmp_path / "market" / "odds.csv"
    output_path = tmp_path / "reports" / "odds-quality.json"
    odds_path.parent.mkdir(parents=True)
    odds_path.write_text(
        "\n".join(
            (
                "race_date,venue,race_no,bet_type,combination,odds,"
                "source,source_hash,observed_at,available_at,parser_version",
                "2026-06-23,05,1,exacta_ordered,1-2,5.2,official-odds,hash-good,"
                "2026-06-23T03:54:00+00:00,2026-06-23T03:55:00+00:00,odds-v1",
                "2026-06-23,05,1,exacta_ordered,2-1,7.0,official-odds,hash-stale,"
                "2026-06-23T03:39:00+00:00,2026-06-23T03:40:00+00:00,odds-v1",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        (
            "odds-quality-report",
            "--odds",
            str(odds_path),
            "--expected-race",
            "2026-06-23:05:1",
            "--bet-type",
            "exacta_ordered",
            "--prediction-as-of",
            "2026-06-23T04:00:00+00:00",
            "--max-age-minutes",
            "10",
            "--output",
            str(output_path),
        )
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["expected_snapshot_count"] == 30
    assert payload["available_snapshot_count"] == 2
    assert payload["stale_snapshot_count"] == 1
    assert payload["issue_count"] == 29
    assert payload["coverage"] == [
        {
            "race_id": "20260623-05-01",
            "bet_type": "exacta_ordered",
            "expected_combination_count": 30,
            "available_combination_count": 2,
            "stale_combination_count": 1,
            "future_only_combination_count": 0,
        }
    ]
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_snapshot_job_plan_command_writes_timed_prerace_jobs(tmp_path: Path) -> None:
    race_starts_path = tmp_path / "inputs" / "race-starts.csv"
    output_path = tmp_path / "jobs" / "snapshot-plan.json"
    race_starts_path.parent.mkdir(parents=True)
    race_starts_path.write_text(
        "\n".join(
            (
                "race_date,venue,race_no,starts_at",
                "2026-06-23,05,1,2026-06-23T04:30:00+00:00",
                "2026-06-23,05,2,2026-06-23T05:00:00+00:00",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        (
            "snapshot-job-plan",
            "--race-starts",
            str(race_starts_path),
            "--source",
            "official",
            "--data-type",
            "odds",
            "--output",
            str(output_path),
        )
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "snapshot-job-plan-v1"
    assert payload["job_count"] == 8
    assert payload["jobs"][0]["job_key"] == "official|05|2026-06-23|1|odds|T30"
    assert payload["jobs"][0]["scheduled_at"] == "2026-06-23T04:00:00+00:00"
    assert payload["jobs"][2]["decision_mode"] == "freeze_final_decision"
    assert payload["jobs"][3]["decision_mode"] == "change_alert_only"
    assert payload["jobs"][4]["job_key"] == "official|05|2026-06-23|2|odds|T30"
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_snapshot_job_due_command_writes_due_window_jobs(tmp_path: Path) -> None:
    race_starts_path = tmp_path / "inputs" / "race-starts.csv"
    plan_path = tmp_path / "jobs" / "snapshot-plan.json"
    due_path = tmp_path / "jobs" / "snapshot-due.json"
    race_starts_path.parent.mkdir(parents=True)
    race_starts_path.write_text(
        "\n".join(
            (
                "race_date,venue,race_no,starts_at",
                "2026-06-23,05,1,2026-06-23T04:30:00+00:00",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    assert (
        main(
            (
                "snapshot-job-plan",
                "--race-starts",
                str(race_starts_path),
                "--source",
                "official",
                "--output",
                str(plan_path),
            )
        )
        == 0
    )

    exit_code = main(
        (
            "snapshot-job-due",
            "--plan",
            str(plan_path),
            "--now",
            "2026-06-23T04:14:00+00:00",
            "--lookahead-minutes",
            "1",
            "--output",
            str(due_path),
        )
    )

    assert exit_code == 0
    payload = json.loads(due_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "snapshot-job-due-v1"
    assert payload["job_count"] == 1
    assert payload["jobs"][0]["snapshot_target"] == "T15"
    assert due_path.read_text(encoding="utf-8").endswith("\n")


def test_odds_change_alert_command_writes_alert_only_report(tmp_path: Path) -> None:
    odds_path = tmp_path / "market" / "odds.csv"
    output_path = tmp_path / "reports" / "odds-change-alert.json"
    odds_path.parent.mkdir(parents=True)
    odds_path.write_text(
        "\n".join(
            (
                "race_date,venue,race_no,bet_type,combination,odds,"
                "source,source_hash,observed_at,available_at,parser_version",
                "2026-06-23,05,1,exacta_ordered,1-2,5.0,official-odds,hash-t10,"
                "2026-06-23T04:19:00+00:00,2026-06-23T04:20:00+00:00,odds-v1",
                "2026-06-23,05,1,exacta_ordered,1-2,6.0,official-odds,hash-t05,"
                "2026-06-23T04:24:00+00:00,2026-06-23T04:25:00+00:00,odds-v1",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        (
            "odds-change-alert",
            "--odds",
            str(odds_path),
            "--race-date",
            "2026-06-23",
            "--venue",
            "05",
            "--race-no",
            "1",
            "--bet-type",
            "exacta_ordered",
            "--frozen-as-of",
            "2026-06-23T04:20:00+00:00",
            "--alert-as-of",
            "2026-06-23T04:25:00+00:00",
            "--min-relative-change",
            "0.10",
            "--output",
            str(output_path),
        )
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "odds-change-alert-v1"
    assert payload["alert_only"] is True
    assert payload["action"] == "review_required_no_overwrite"
    assert payload["alerts"][0]["combination"] == "1-2"
    assert payload["alerts"][0]["relative_change"] == "0.20"
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


def test_value_strategy_recommendations_command_writes_backtest_ready_csv(
    tmp_path: Path,
) -> None:
    candidates_path = tmp_path / "strategy" / "candidates.csv"
    output_path = tmp_path / "strategy" / "recommendations.csv"
    candidates_path.parent.mkdir(parents=True)
    candidates_path.write_text(
        "\n".join(
            (
                "recommendation_id,race_date,venue,race_no,bet_type,combination,"
                "confidence,probability,odds,as_of,data_version,feature_version,"
                "model_version,strategy_version,reason_codes",
                "strategy-rec-select,2025-01-02,01,1,trifecta_ordered,1-2-3,high,"
                "0.25,5.2,2025-01-02T10:00:00+00:00,data-v1,feature-v1,"
                "model-v1,strategy-v1,model_signal",
                "strategy-rec-pass,2025-01-02,01,2,trifecta_ordered,1-3-2,medium,"
                "0.18,,2025-01-02T10:05:00+00:00,data-v1,feature-v1,"
                "model-v1,strategy-v1,night_preplan",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        (
            "value-strategy-recommendations",
            "--candidates",
            str(candidates_path),
            "--min-expected-value",
            "0.10",
            "--conservative-margin",
            "0.05",
            "--min-conservative-expected-value",
            "0.05",
            "--output",
            str(output_path),
        )
    )

    assert exit_code == 0
    recommendations = load_recommendations_csv(output_path)
    assert [record.recommendation_id for record in recommendations] == [
        "strategy-rec-select",
        "strategy-rec-pass",
    ]
    assert recommendations[0].decision is Decision.SELECT
    assert recommendations[0].expected_value == Decimal("0.300")
    assert recommendations[0].reason_codes == (
        "model_signal",
        "positive_ev",
        "conservative_ev_ok",
        "risk_ok",
    )
    assert recommendations[1].decision is Decision.PASS
    assert recommendations[1].expected_value is None
    assert recommendations[1].reason_codes == ("night_preplan", "odds_unavailable")
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_value_strategy_recommendations_command_applies_risk_budget_caps(
    tmp_path: Path,
) -> None:
    candidates_path = tmp_path / "strategy" / "candidates.csv"
    output_path = tmp_path / "strategy" / "recommendations.csv"
    candidates_path.parent.mkdir(parents=True)
    candidates_path.write_text(
        "\n".join(
            (
                "recommendation_id,race_date,venue,race_no,bet_type,combination,"
                "confidence,probability,odds,as_of,data_version,feature_version,"
                "model_version,strategy_version,reason_codes",
                "low-ev,2025-01-02,01,1,trifecta_ordered,1-2-3,high,"
                "0.25,5.2,2025-01-02T10:00:00+00:00,data-v1,feature-v1,"
                "model-v1,strategy-v1,model_signal",
                "high-ev,2025-01-02,01,1,trifecta_ordered,1-3-2,high,"
                "0.30,6.0,2025-01-02T10:00:00+00:00,data-v1,feature-v1,"
                "model-v1,strategy-v1,model_signal",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        (
            "value-strategy-recommendations",
            "--candidates",
            str(candidates_path),
            "--min-expected-value",
            "0.10",
            "--conservative-margin",
            "0.05",
            "--max-selects-per-race",
            "1",
            "--output",
            str(output_path),
        )
    )

    assert exit_code == 0
    recommendations = load_recommendations_csv(output_path)
    assert [record.recommendation_id for record in recommendations] == [
        "low-ev",
        "high-ev",
    ]
    assert recommendations[0].decision is Decision.PASS
    assert recommendations[0].reason_codes == (
        "model_signal",
        "positive_ev",
        "conservative_ev_ok",
        "race_risk_limit",
    )
    assert recommendations[1].decision is Decision.SELECT


def test_frequency_model_candidates_command_writes_strategy_candidate_csv(
    tmp_path: Path,
) -> None:
    results_path = tmp_path / "models" / "results.csv"
    output_path = tmp_path / "models" / "candidates.csv"
    results_path.parent.mkdir(parents=True)
    results_path.write_text(
        "\n".join(
            (
                "race_date,venue,race_no,first,second,third,source,source_hash,"
                "observed_at,available_at,parser_version",
                "2025-01-01,01,1,1,2,3,official-results,result-hash-1,"
                "2025-01-01T08:00:00+00:00,2025-01-01T08:01:00+00:00,results-v1",
                "2025-01-02,01,1,4,5,6,official-results,result-hash-2,"
                "2025-01-02T08:00:00+00:00,2025-01-02T10:01:00+00:00,results-v1",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        (
            "frequency-model-candidates",
            "--results",
            str(results_path),
            "--prediction-as-of",
            "2025-01-02T10:00:00+00:00",
            "--race-date",
            "2025-01-03",
            "--venue",
            "01",
            "--race-no",
            "1",
            "--data-version",
            "data-v1",
            "--feature-version",
            "feature-v1",
            "--model-version",
            "trifecta-frequency-v1",
            "--strategy-version",
            "strategy-v1",
            "--output",
            str(output_path),
        )
    )

    assert exit_code == 0
    rows = output_path.read_text(encoding="utf-8").splitlines()
    assert rows[0] == (
        "recommendation_id,race_date,venue,race_no,bet_type,combination,confidence,"
        "probability,odds,as_of,data_version,feature_version,model_version,"
        "strategy_version,reason_codes"
    )
    assert len(rows) == 121
    assert rows[1] == (
        "freq-20250103-01-01-1-2-3,2025-01-03,01,1,trifecta_ordered,1-2-3,"
        "medium,0.01652892561983471074380165289,,2025-01-02T10:00:00+00:00,"
        "data-v1,feature-v1,trifecta-frequency-v1,strategy-v1,"
        "frequency_baseline|training_races_1"
    )
    assert rows[-1].startswith("freq-20250103-01-01-6-5-4,")
    probabilities = [Decimal(row.split(",")[7]) for row in rows[1:]]
    assert abs(sum(probabilities) - Decimal("1")) < Decimal("1E-26")


def test_market_implied_candidates_command_writes_strategy_candidate_csv(
    tmp_path: Path,
) -> None:
    odds_path = tmp_path / "models" / "odds.csv"
    output_path = tmp_path / "models" / "market-candidates.csv"
    odds_path.parent.mkdir(parents=True)
    odds_path.write_text(
        "\n".join(
            (
                "race_date,venue,race_no,bet_type,combination,odds,"
                "source,source_hash,observed_at,available_at,parser_version",
                "2026-06-23,05,1,exacta_ordered,1-2,2,official-odds,hash-a,"
                "2026-06-23T03:55:00+00:00,2026-06-23T03:55:00+00:00,odds-v1",
                "2026-06-23,05,1,exacta_ordered,2-1,4,official-odds,hash-b,"
                "2026-06-23T03:56:00+00:00,2026-06-23T03:56:00+00:00,odds-v1",
                "2026-06-23,05,1,exacta_ordered,1-2,9,official-odds,hash-future,"
                "2026-06-23T04:01:00+00:00,2026-06-23T04:01:00+00:00,odds-v1",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        (
            "market-implied-candidates",
            "--odds",
            str(odds_path),
            "--prediction-as-of",
            "2026-06-23T04:00:00+00:00",
            "--race-date",
            "2026-06-23",
            "--venue",
            "05",
            "--race-no",
            "1",
            "--bet-type",
            "exacta_ordered",
            "--data-version",
            "data-v1",
            "--feature-version",
            "feature-v1",
            "--model-version",
            "market-implied-v1",
            "--strategy-version",
            "strategy-v1",
            "--output",
            str(output_path),
        )
    )

    assert exit_code == 0
    candidates = load_strategy_candidates_csv(output_path)
    assert [candidate.recommendation_id for candidate in candidates] == [
        "market-20260623-05-01-1-2",
        "market-20260623-05-01-2-1",
    ]
    assert candidates[0].probability == Decimal("0.6666666666666666666666666667")
    assert candidates[0].odds == Decimal("2")
    assert candidates[0].reason_codes == (
        "market_implied_baseline",
        "odds_snapshots_2",
    )
    assert candidates[1].probability == Decimal("0.3333333333333333333333333333")
    assert candidates[1].odds == Decimal("4")


def test_probability_report_command_writes_model_quality_metrics(tmp_path: Path) -> None:
    candidates_path = tmp_path / "models" / "candidates.csv"
    results_path = tmp_path / "models" / "results.csv"
    output_path = tmp_path / "reports" / "probability.json"
    candidates_path.parent.mkdir(parents=True)
    candidates_path.write_text(
        "\n".join(
            (
                "recommendation_id,race_date,venue,race_no,bet_type,combination,"
                "confidence,probability,odds,as_of,data_version,feature_version,"
                "model_version,strategy_version,reason_codes",
                "race-1-hit,2026-06-23,05,1,trifecta_ordered,1-2-3,medium,"
                "0.8,,2026-06-23T04:00:00+00:00,data-v1,feature-v1,"
                "model-v1,strategy-v1,test",
                "race-1-miss,2026-06-23,05,1,trifecta_ordered,1-3-2,medium,"
                "0.2,,2026-06-23T04:00:00+00:00,data-v1,feature-v1,"
                "model-v1,strategy-v1,test",
                "race-2-miss,2026-06-23,05,2,trifecta_ordered,1-2-3,medium,"
                "0.7,,2026-06-23T04:00:00+00:00,data-v1,feature-v1,"
                "model-v1,strategy-v1,test",
                "race-2-hit,2026-06-23,05,2,trifecta_ordered,2-1-3,medium,"
                "0.3,,2026-06-23T04:00:00+00:00,data-v1,feature-v1,"
                "model-v1,strategy-v1,test",
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
                "2026-06-23,05,1,1,2,3,official-results,result-hash-1,"
                "2026-06-23T08:00:00+00:00,2026-06-23T08:01:00+00:00,results-v1",
                "2026-06-23,05,2,2,1,3,official-results,result-hash-2,"
                "2026-06-23T08:00:00+00:00,2026-06-23T08:01:00+00:00,results-v1",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        (
            "probability-report",
            "--candidates",
            str(candidates_path),
            "--results",
            str(results_path),
            "--bet-type",
            "trifecta_ordered",
            "--ece-bins",
            "2",
            "--output",
            str(output_path),
        )
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload == {
        "average_brier_score": "0.53",
        "average_log_loss": "0.713558177820072874194520654",
        "bet_type": "trifecta_ordered",
        "candidate_count": 4,
        "ece_bins": 2,
        "evaluated_race_count": 2,
        "expected_calibration_error": "0.25",
        "top1_accuracy": "0.5",
    }


def test_attach_odds_to_candidates_command_writes_latest_available_odds(
    tmp_path: Path,
) -> None:
    candidates_path = tmp_path / "strategy" / "candidates.csv"
    odds_path = tmp_path / "market" / "odds.csv"
    output_path = tmp_path / "strategy" / "candidates-with-odds.csv"
    candidates_path.parent.mkdir(parents=True)
    odds_path.parent.mkdir(parents=True)
    candidates_path.write_text(
        "\n".join(
            (
                "recommendation_id,race_date,venue,race_no,bet_type,combination,"
                "confidence,probability,odds,as_of,data_version,feature_version,"
                "model_version,strategy_version,reason_codes",
                "freq-rec-1,2026-06-23,05,1,trifecta_ordered,3-1-2,medium,"
                "0.25,,2026-06-23T04:00:00+00:00,data-v1,feature-v1,"
                "model-v1,strategy-v1,frequency_baseline",
                "freq-rec-2,2026-06-23,05,1,trifecta_ordered,1-2-3,medium,"
                "0.10,,2026-06-23T03:53:00+00:00,data-v1,feature-v1,"
                "model-v1,strategy-v1,frequency_baseline",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    odds_path.write_text(
        "\n".join(
            (
                "race_date,venue,race_no,bet_type,combination,odds,"
                "source,source_hash,observed_at,available_at,parser_version",
                "2026-06-23,05,1,trifecta_ordered,3-1-2,5.2,official-odds,hash-old,"
                "2026-06-23T03:50:00+00:00,2026-06-23T03:51:00+00:00,odds-v1",
                "2026-06-23,05,1,trifecta_ordered,3-1-2,7.0,official-odds,hash-late,"
                "2026-06-23T03:55:00+00:00,2026-06-23T03:56:00+00:00,odds-v1",
                "2026-06-23,05,1,trifecta_ordered,3-1-2,9.9,official-odds,hash-future,"
                "2026-06-23T04:05:00+00:00,2026-06-23T04:06:00+00:00,odds-v1",
                "2026-06-23,05,1,trifecta_ordered,1-2-3,11.0,official-odds,hash-other,"
                "2026-06-23T03:54:00+00:00,2026-06-23T03:55:00+00:00,odds-v1",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        (
            "attach-odds-to-candidates",
            "--candidates",
            str(candidates_path),
            "--odds",
            str(odds_path),
            "--output",
            str(output_path),
        )
    )

    assert exit_code == 0
    candidates = load_strategy_candidates_csv(output_path)
    assert candidates[0].odds == Decimal("7.0")
    assert candidates[0].reason_codes == (
        "frequency_baseline",
        "odds_snapshot_attached",
    )
    assert candidates[1].odds is None
    assert candidates[1].reason_codes == ("frequency_baseline",)
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_attach_odds_to_candidates_command_marks_stale_odds_unavailable(
    tmp_path: Path,
) -> None:
    candidates_path = tmp_path / "strategy" / "candidates.csv"
    odds_path = tmp_path / "market" / "odds.csv"
    output_path = tmp_path / "strategy" / "candidates-with-odds.csv"
    candidates_path.parent.mkdir(parents=True)
    odds_path.parent.mkdir(parents=True)
    candidates_path.write_text(
        "\n".join(
            (
                "recommendation_id,race_date,venue,race_no,bet_type,combination,"
                "confidence,probability,odds,as_of,data_version,feature_version,"
                "model_version,strategy_version,reason_codes",
                "freq-rec-stale,2026-06-23,05,1,trifecta_ordered,3-1-2,medium,"
                "0.25,5.2,2026-06-23T04:00:00+00:00,data-v1,feature-v1,"
                "model-v1,strategy-v1,frequency_baseline",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    odds_path.write_text(
        "\n".join(
            (
                "race_date,venue,race_no,bet_type,combination,odds,"
                "source,source_hash,observed_at,available_at,parser_version",
                "2026-06-23,05,1,trifecta_ordered,3-1-2,7.0,official-odds,hash-stale,"
                "2026-06-23T03:39:00+00:00,2026-06-23T03:40:00+00:00,odds-v1",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        (
            "attach-odds-to-candidates",
            "--candidates",
            str(candidates_path),
            "--odds",
            str(odds_path),
            "--max-age-minutes",
            "10",
            "--output",
            str(output_path),
        )
    )

    assert exit_code == 0
    candidates = load_strategy_candidates_csv(output_path)
    assert candidates[0].odds is None
    assert candidates[0].reason_codes == (
        "frequency_baseline",
        "odds_snapshot_stale",
    )


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


def test_review_workflow_confirmed_list_command_writes_openapi_response(
    tmp_path: Path,
) -> None:
    store_path = tmp_path / "server" / "reviews.json"
    output_path = tmp_path / "responses" / "confirmed-list.json"
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
            "review-workflow-confirmed-list",
            "--store",
            str(store_path),
            "--archive-dir",
            str(tmp_path / "archives"),
            "--export-dir",
            str(tmp_path / "exports"),
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
    assert payload["total_stake_units"] == 2
    assert [entry["recommendation_id"] for entry in payload["entries"]] == ["rec-confirmed"]
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_review_workflow_archive_command_writes_openapi_response(tmp_path: Path) -> None:
    store_path = tmp_path / "server" / "reviews.json"
    archive_dir = tmp_path / "archives"
    output_path = tmp_path / "responses" / "archive.json"
    store_path.parent.mkdir(parents=True)
    store_path.write_text(
        json.dumps(
            [
                {
                    "recommendation_id": "rec-confirmed",
                    "race_id": "20250102-01-01",
                    "decision": "confirmed",
                    "stake_units": 1,
                    "notes": "freeze",
                    "reviewed_at": "2026-07-11T03:20:00+00:00",
                    "reviewed_by": "analyst",
                }
            ],
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        (
            "review-workflow-archive",
            "--store",
            str(store_path),
            "--archive-dir",
            str(archive_dir),
            "--export-dir",
            str(tmp_path / "exports"),
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
            "--output",
            str(output_path),
        )
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "confirmed_review_list"
    assert payload["schema_version"] == "confirmed-review-list-v1"
    assert payload["checklist"]["total_stake_units"] == 1
    assert (archive_dir / f"{payload['version_id']}.json").exists()
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_api_request_command_routes_review_import_through_adapter(tmp_path: Path) -> None:
    store_path = tmp_path / "server" / "reviews.json"
    input_path = tmp_path / "browser" / "reviews.json"
    output_path = tmp_path / "responses" / "api-request.json"
    input_path.parent.mkdir(parents=True)
    input_path.write_text(
        json.dumps(
            {
                "reviews": [
                    {
                        "recommendation_id": "rec-api-request",
                        "race_id": "20250102-01-01",
                        "decision": "confirmed",
                        "stake_units": 2,
                        "notes": "local route",
                        "reviewed_at": "2026-07-11T03:20:00+00:00",
                        "reviewed_by": "browser-analyst",
                    }
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        (
            "api-request",
            "--method",
            "POST",
            "--path",
            "/reviews/import",
            "--store",
            str(store_path),
            "--archive-dir",
            str(tmp_path / "archives"),
            "--export-dir",
            str(tmp_path / "exports"),
            "--body",
            str(input_path),
            "--output",
            str(output_path),
        )
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload == {"status_code": 200, "body": {"stored_count": 1}}
    stored_reviews = json.loads(store_path.read_text(encoding="utf-8"))
    assert stored_reviews[0]["recommendation_id"] == "rec-api-request"
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_api_request_command_writes_stable_error_response(tmp_path: Path) -> None:
    output_path = tmp_path / "responses" / "api-error.json"

    exit_code = main(
        (
            "api-request",
            "--method",
            "GET",
            "--path",
            "/business-dates/2025-01-02/candidates/missing",
            "--store",
            str(tmp_path / "server" / "reviews.json"),
            "--archive-dir",
            str(tmp_path / "archives"),
            "--export-dir",
            str(tmp_path / "exports"),
            "--output",
            str(output_path),
        )
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status_code"] == 404
    assert payload["body"]["code"] == "DQ_MISSING_ENTRY"
    assert payload["body"]["details"] == {
        "method": "GET",
        "path": "/business-dates/2025-01-02/candidates/missing",
    }
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_serve_api_command_starts_dependency_free_http_server(monkeypatch, tmp_path: Path) -> None:
    report_path = tmp_path / "reports" / "report.json"
    store_path = tmp_path / "server" / "reviews.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        json.dumps({"readiness": {"ready": True}, "settlements": []}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    calls: list[dict[str, object]] = []

    def fake_serve_api_http(address, adapter, *, allowed_origin):
        response = adapter.handle(
            ApiRequest(method="GET", path="/business-dates/2025-01-02/status")
        )
        calls.append(
            {
                "address": address,
                "allowed_origin": allowed_origin,
                "status_code": response.status_code,
                "status": response.body["status"],
            }
        )

    monkeypatch.setattr(cli_module, "serve_api_http", fake_serve_api_http, raising=False)

    exit_code = cli_module.main(
        (
            "serve-api",
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
            "--report-business-date",
            "2025-01-02",
            "--report",
            str(report_path),
            "--store",
            str(store_path),
            "--archive-dir",
            str(tmp_path / "archives"),
            "--export-dir",
            str(tmp_path / "exports"),
            "--allowed-origin",
            "http://127.0.0.1:5174",
        )
    )

    assert exit_code == 0
    assert calls == [
        {
            "address": ("127.0.0.1", 8765),
            "allowed_origin": "http://127.0.0.1:5174",
            "status_code": 200,
            "status": "ready",
        }
    ]


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
