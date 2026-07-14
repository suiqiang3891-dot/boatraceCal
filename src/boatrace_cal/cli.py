"""Command line entry points for local BOAT RACE analysis workflows."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

from boatrace_cal.api_adapter import ApiRequest, AnalysisApiAdapter
from boatrace_cal.api_contract import export_openapi_spec_json
from boatrace_cal.api_server import serve_api_http
from boatrace_cal.api_services import CandidateQueryService, ReviewWorkflowService
from boatrace_cal.backtest.export import export_backtest_report_json
from boatrace_cal.backtest.runner import run_backtest
from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.domain.recommendations import ConfidenceLevel
from boatrace_cal.domain.versions import ArtifactVersions
from boatrace_cal.ingestion.odds import (
    OddsSnapshotRecord,
    latest_odds_by_combination,
    load_odds_csv,
)
from boatrace_cal.ingestion.payouts import load_payouts_csv
from boatrace_cal.ingestion.recommendations import load_recommendations_csv
from boatrace_cal.ingestion.results import load_results_csv
from boatrace_cal.jobs.snapshot_plan import (
    build_prerace_snapshot_plan,
    export_snapshot_plan_json,
    load_race_starts_csv,
)
from boatrace_cal.models.evaluation import (
    evaluate_probability_candidates,
    probability_evaluation_report_to_dict,
)
from boatrace_cal.models.market_implied import build_market_implied_model
from boatrace_cal.models.trifecta_frequency import fit_trifecta_frequency_model
from boatrace_cal.review_archive import freeze_confirmed_review_list
from boatrace_cal.review_excel import (
    export_confirmed_review_list_xlsx,
    export_review_table_xlsx,
)
from boatrace_cal.review_store import FileReviewStore
from boatrace_cal.reviews import (
    build_confirmed_review_list,
    confirmed_review_list_to_dict,
    load_reviews_json,
)
from boatrace_cal.strategies.csv import (
    export_recommendations_csv,
    export_strategy_candidates_csv,
    load_strategy_candidates_csv,
)
from boatrace_cal.strategies.risk_budget import RiskBudgetConfig, apply_risk_budget
from boatrace_cal.strategies.value import (
    StrategyCandidate,
    ValueStrategyConfig,
    build_value_recommendation,
)
from boatrace_cal.validation.data_quality import build_historical_data_quality_report
from boatrace_cal.validation.odds_quality import build_odds_quality_report
from boatrace_cal.validation.odds_change_alert import (
    build_odds_change_alert_report,
    odds_change_alert_report_to_dict,
)
from boatrace_cal.validation.serialization import (
    historical_data_quality_report_to_dict,
    odds_quality_report_to_dict,
)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the boatrace-cal command line interface."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "backtest-report":
        return _run_backtest_report(args)
    if args.command == "candidate-status":
        return _run_candidate_status(args)
    if args.command == "candidate-list":
        return _run_candidate_list(args)
    if args.command == "candidate-detail":
        return _run_candidate_detail(args)
    if args.command == "historical-quality-report":
        return _run_historical_quality_report(args)
    if args.command == "odds-quality-report":
        return _run_odds_quality_report(args)
    if args.command == "snapshot-job-plan":
        return _run_snapshot_job_plan(args)
    if args.command == "odds-change-alert":
        return _run_odds_change_alert(args)
    if args.command == "frequency-model-candidates":
        return _run_frequency_model_candidates(args)
    if args.command == "market-implied-candidates":
        return _run_market_implied_candidates(args)
    if args.command == "probability-report":
        return _run_probability_report(args)
    if args.command == "attach-odds-to-candidates":
        return _run_attach_odds_to_candidates(args)
    if args.command == "value-strategy-recommendations":
        return _run_value_strategy_recommendations(args)
    if args.command == "confirmed-review-list":
        return _run_confirmed_review_list(args)
    if args.command == "review-store-import":
        return _run_review_store_import(args)
    if args.command == "review-workflow-import":
        return _run_review_workflow_import(args)
    if args.command == "review-workflow-confirmed-list":
        return _run_review_workflow_confirmed_list(args)
    if args.command == "review-workflow-archive":
        return _run_review_workflow_archive(args)
    if args.command == "confirmed-review-archive":
        return _run_confirmed_review_archive(args)
    if args.command == "confirmed-review-excel":
        return _run_confirmed_review_excel(args)
    if args.command == "review-table-excel":
        return _run_review_table_excel(args)
    if args.command == "review-workflow-export":
        return _run_review_workflow_export(args)
    if args.command == "export-job-status":
        return _run_export_job_status(args)
    if args.command == "api-request":
        return _run_api_request(args)
    if args.command == "serve-api":
        return _run_serve_api(args)
    if args.command == "openapi-spec":
        return _run_openapi_spec(args)
    parser.print_help()
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="boatrace-cal",
        description="Local BOAT RACE analysis and audit utilities.",
    )
    subparsers = parser.add_subparsers(dest="command")
    quality = subparsers.add_parser(
        "historical-quality-report",
        help="Build a JSON quality report from historical result and payout CSV files.",
    )
    quality.add_argument("--results", required=True, type=Path)
    quality.add_argument("--payouts", required=True, type=Path)
    _add_expected_race_arguments(quality)
    quality.add_argument("--bet-type", required=True, action="append")
    quality.add_argument("--output", required=True, type=Path)

    odds_quality = subparsers.add_parser(
        "odds-quality-report",
        help="Build a JSON quality report from pre-race odds snapshot CSV files.",
    )
    odds_quality.add_argument("--odds", required=True, type=Path)
    _add_expected_race_arguments(odds_quality)
    odds_quality.add_argument("--bet-type", required=True, action="append")
    odds_quality.add_argument("--prediction-as-of", required=True)
    odds_quality.add_argument("--max-age-minutes", required=True, type=int)
    odds_quality.add_argument("--output", required=True, type=Path)

    snapshot_plan = subparsers.add_parser(
        "snapshot-job-plan",
        help="Build a T-30/T-15/T-10/T-5 pre-race snapshot job plan JSON.",
    )
    snapshot_plan.add_argument("--race-starts", required=True, type=Path)
    snapshot_plan.add_argument("--source", required=True)
    snapshot_plan.add_argument("--data-type", default="odds")
    snapshot_plan.add_argument("--output", required=True, type=Path)

    odds_change_alert = subparsers.add_parser(
        "odds-change-alert",
        help="Write an alert-only report for odds moves after the frozen decision point.",
    )
    odds_change_alert.add_argument("--odds", required=True, type=Path)
    odds_change_alert.add_argument("--race-date", required=True)
    odds_change_alert.add_argument("--venue", required=True)
    odds_change_alert.add_argument("--race-no", required=True, type=int)
    odds_change_alert.add_argument("--bet-type", required=True)
    odds_change_alert.add_argument("--frozen-as-of", required=True)
    odds_change_alert.add_argument("--alert-as-of", required=True)
    odds_change_alert.add_argument("--min-relative-change", default="0.10")
    odds_change_alert.add_argument("--output", required=True, type=Path)

    backtest = subparsers.add_parser(
        "backtest-report",
        help="Run a historical paper backtest and write a JSON report.",
    )
    backtest.add_argument("--recommendations", required=True, type=Path)
    backtest.add_argument("--results", required=True, type=Path)
    backtest.add_argument("--payouts", required=True, type=Path)
    _add_expected_race_arguments(backtest)
    backtest.add_argument("--bet-type", required=True, action="append")
    backtest.add_argument("--output", required=True, type=Path)

    frequency_model = subparsers.add_parser(
        "frequency-model-candidates",
        help="Fit the ordered-trifecta frequency baseline and write strategy candidates.",
    )
    frequency_model.add_argument("--results", required=True, type=Path)
    frequency_model.add_argument("--prediction-as-of", required=True)
    frequency_model.add_argument("--race-date", required=True)
    frequency_model.add_argument("--venue", required=True)
    frequency_model.add_argument("--race-no", required=True, type=int)
    frequency_model.add_argument("--smoothing", default="1")
    frequency_model.add_argument("--confidence", default="medium")
    frequency_model.add_argument("--data-version", required=True)
    frequency_model.add_argument("--feature-version", required=True)
    frequency_model.add_argument("--model-version", required=True)
    frequency_model.add_argument("--strategy-version", required=True)
    frequency_model.add_argument("--output", required=True, type=Path)

    market_implied = subparsers.add_parser(
        "market-implied-candidates",
        help="Build market-implied baseline candidates from latest odds snapshots.",
    )
    market_implied.add_argument("--odds", required=True, type=Path)
    market_implied.add_argument("--prediction-as-of", required=True)
    market_implied.add_argument("--race-date", required=True)
    market_implied.add_argument("--venue", required=True)
    market_implied.add_argument("--race-no", required=True, type=int)
    market_implied.add_argument("--bet-type", required=True)
    market_implied.add_argument("--confidence", default="medium")
    market_implied.add_argument("--data-version", required=True)
    market_implied.add_argument("--feature-version", required=True)
    market_implied.add_argument("--model-version", required=True)
    market_implied.add_argument("--strategy-version", required=True)
    market_implied.add_argument("--output", required=True, type=Path)

    probability_report = subparsers.add_parser(
        "probability-report",
        help="Evaluate candidate probabilities against official results.",
    )
    probability_report.add_argument("--candidates", required=True, type=Path)
    probability_report.add_argument("--results", required=True, type=Path)
    probability_report.add_argument("--bet-type", required=True)
    probability_report.add_argument("--ece-bins", default=10, type=int)
    probability_report.add_argument("--output", required=True, type=Path)

    value_strategy = subparsers.add_parser(
        "value-strategy-recommendations",
        help="Apply EV and conservative EV gates to strategy candidates.",
    )
    value_strategy.add_argument("--candidates", required=True, type=Path)
    value_strategy.add_argument("--min-probability", default="0")
    value_strategy.add_argument("--min-expected-value", default="0")
    value_strategy.add_argument("--conservative-margin", default="0.05")
    value_strategy.add_argument("--min-conservative-expected-value", default="0")
    value_strategy.add_argument("--max-odds")
    value_strategy.add_argument("--max-selects-per-race", type=int)
    value_strategy.add_argument("--max-daily-stake-units", type=int)
    value_strategy.add_argument("--output", required=True, type=Path)

    attach_odds = subparsers.add_parser(
        "attach-odds-to-candidates",
        help="Attach latest time-safe odds snapshots to strategy candidates.",
    )
    attach_odds.add_argument("--candidates", required=True, type=Path)
    attach_odds.add_argument("--odds", required=True, type=Path)
    attach_odds.add_argument("--max-age-minutes", type=int)
    attach_odds.add_argument("--output", required=True, type=Path)

    candidate_status = subparsers.add_parser(
        "candidate-status",
        help="Write the analysis status for one business date from a backtest report.",
    )
    _add_candidate_report_arguments(candidate_status)

    candidate_list = subparsers.add_parser(
        "candidate-list",
        help="Write candidate summaries for one business date from a backtest report.",
    )
    _add_candidate_report_arguments(candidate_list)

    candidate_detail = subparsers.add_parser(
        "candidate-detail",
        help="Write one candidate explanation from a backtest report.",
    )
    _add_candidate_report_arguments(candidate_detail)
    candidate_detail.add_argument("--recommendation-id", required=True)

    confirmed = subparsers.add_parser(
        "confirmed-review-list",
        help="Build a JSON checklist from analyst-confirmed recommendation reviews.",
    )
    confirmed.add_argument("--reviews", required=True, type=Path)
    confirmed.add_argument("--business-date", required=True)
    confirmed.add_argument("--generated-at", required=True)
    confirmed.add_argument("--generated-by", required=True)
    confirmed.add_argument("--output", required=True, type=Path)

    review_import = subparsers.add_parser(
        "review-store-import",
        help="Import review JSON records into a file-backed review store.",
    )
    review_import.add_argument("--store", required=True, type=Path)
    review_import.add_argument("--reviews", required=True, type=Path)

    review_workflow_import = subparsers.add_parser(
        "review-workflow-import",
        help="Import review records through the OpenAPI review workflow service.",
    )
    _add_review_workflow_service_arguments(review_workflow_import)
    review_workflow_import.add_argument("--reviews", required=True, type=Path)
    review_workflow_import.add_argument("--output", required=True, type=Path)

    review_workflow_confirmed = subparsers.add_parser(
        "review-workflow-confirmed-list",
        help="Build the confirmed review checklist through the OpenAPI workflow service.",
    )
    _add_review_workflow_service_arguments(review_workflow_confirmed)
    _add_review_list_request_arguments(review_workflow_confirmed)

    review_workflow_archive = subparsers.add_parser(
        "review-workflow-archive",
        help="Freeze a confirmed review checklist through the OpenAPI workflow service.",
    )
    _add_review_workflow_service_arguments(review_workflow_archive)
    _add_review_list_request_arguments(review_workflow_archive)
    review_workflow_archive.add_argument("--frozen-at", required=True)
    review_workflow_archive.add_argument("--frozen-by", required=True)

    archive = subparsers.add_parser(
        "confirmed-review-archive",
        help="Freeze confirmed review store entries as an immutable archive artifact.",
    )
    archive.add_argument("--store", required=True, type=Path)
    archive.add_argument("--business-date", required=True)
    archive.add_argument("--generated-at", required=True)
    archive.add_argument("--generated-by", required=True)
    archive.add_argument("--frozen-at", required=True)
    archive.add_argument("--frozen-by", required=True)
    archive.add_argument("--archive-dir", required=True, type=Path)

    review_excel = subparsers.add_parser(
        "confirmed-review-excel",
        help="Export analyst-confirmed review store entries as an XLSX checklist.",
    )
    review_excel.add_argument("--store", required=True, type=Path)
    review_excel.add_argument("--business-date", required=True)
    review_excel.add_argument("--generated-at", required=True)
    review_excel.add_argument("--generated-by", required=True)
    review_excel.add_argument("--output", required=True, type=Path)

    review_table_excel = subparsers.add_parser(
        "review-table-excel",
        help="Export all review store entries as an XLSX audit table.",
    )
    review_table_excel.add_argument("--store", required=True, type=Path)
    review_table_excel.add_argument("--business-date", required=True)
    review_table_excel.add_argument("--generated-at", required=True)
    review_table_excel.add_argument("--generated-by", required=True)
    review_table_excel.add_argument("--output", required=True, type=Path)

    review_workflow_export = subparsers.add_parser(
        "review-workflow-export",
        help="Export a review workflow XLSX artifact and persist its job status.",
    )
    _add_review_workflow_service_arguments(review_workflow_export)
    review_workflow_export.add_argument("--business-date", required=True)
    review_workflow_export.add_argument(
        "--export-type",
        required=True,
        choices=("review_table", "confirmed_list"),
    )
    review_workflow_export.add_argument("--generated-at", required=True)
    review_workflow_export.add_argument("--generated-by", required=True)

    export_job_status = subparsers.add_parser(
        "export-job-status",
        help="Write the current status of a persisted export job.",
    )
    _add_review_workflow_service_arguments(export_job_status)
    export_job_status.add_argument("--job-id", required=True)
    export_job_status.add_argument("--output", required=True, type=Path)

    api_request = subparsers.add_parser(
        "api-request",
        help="Execute one OpenAPI-shaped request through the local dependency-free adapter.",
    )
    api_request.add_argument("--method", required=True)
    api_request.add_argument("--path", required=True)
    api_request.add_argument("--body", type=Path)
    api_request.add_argument("--report-business-date")
    api_request.add_argument("--report", type=Path)
    api_request.add_argument(
        "--store",
        type=Path,
        default=Path("data/reviews/reviews.json"),
    )
    api_request.add_argument(
        "--archive-dir",
        type=Path,
        default=Path("artifacts/review-archives"),
    )
    api_request.add_argument(
        "--export-dir",
        type=Path,
        default=Path("artifacts/review-exports"),
    )
    api_request.add_argument("--output", required=True, type=Path)

    serve_api = subparsers.add_parser(
        "serve-api",
        help="Serve the local dependency-free analysis API over HTTP.",
    )
    serve_api.add_argument("--host", default="127.0.0.1")
    serve_api.add_argument("--port", default=8765, type=int)
    serve_api.add_argument("--report-business-date", action="append", default=[])
    serve_api.add_argument("--report", action="append", default=[], type=Path)
    serve_api.add_argument(
        "--store",
        type=Path,
        default=Path("data/reviews/reviews.json"),
    )
    serve_api.add_argument(
        "--archive-dir",
        type=Path,
        default=Path("artifacts/review-archives"),
    )
    serve_api.add_argument(
        "--export-dir",
        type=Path,
        default=Path("artifacts/review-exports"),
    )
    serve_api.add_argument("--allowed-origin", default="*")

    openapi = subparsers.add_parser(
        "openapi-spec",
        help="Write the OpenAPI contract JSON for the analysis API.",
    )
    openapi.add_argument("--output", required=True, type=Path)
    return parser


def _add_expected_race_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--expected-race", action="append", default=[])
    parser.add_argument("--expected-date")
    parser.add_argument("--venue")
    parser.add_argument("--race-nos")


def _add_candidate_report_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--business-date", required=True)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)


def _add_review_workflow_service_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--archive-dir", required=True, type=Path)
    parser.add_argument("--export-dir", required=True, type=Path)


def _add_review_list_request_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--business-date", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--generated-by", required=True)
    parser.add_argument("--output", required=True, type=Path)


def _run_backtest_report(args: argparse.Namespace) -> int:
    report = run_backtest(
        recommendations=load_recommendations_csv(args.recommendations),
        results=load_results_csv(args.results),
        payouts=load_payouts_csv(args.payouts),
        expected_races=_collect_expected_races(args),
        bet_types=tuple(BetType(value) for value in args.bet_type),
    )
    export_backtest_report_json(report, args.output)
    return 0


def _run_historical_quality_report(args: argparse.Namespace) -> int:
    report = build_historical_data_quality_report(
        results=load_results_csv(args.results),
        payouts=load_payouts_csv(args.payouts),
        expected_races=_collect_expected_races(args),
        bet_types=tuple(BetType(value) for value in args.bet_type),
    )
    output_path: Path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = historical_data_quality_report_to_dict(report)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


def _run_odds_quality_report(args: argparse.Namespace) -> int:
    report = build_odds_quality_report(
        odds=load_odds_csv(args.odds),
        expected_races=_collect_expected_races(args),
        bet_types=tuple(BetType(value) for value in args.bet_type),
        prediction_as_of=_parse_datetime(args.prediction_as_of, "prediction-as-of"),
        max_snapshot_age=timedelta(minutes=args.max_age_minutes),
    )
    _write_json(args.output, odds_quality_report_to_dict(report))
    return 0


def _run_snapshot_job_plan(args: argparse.Namespace) -> int:
    plan = build_prerace_snapshot_plan(
        load_race_starts_csv(args.race_starts),
        source=args.source,
        data_type=args.data_type,
    )
    export_snapshot_plan_json(plan, args.output)
    return 0


def _run_odds_change_alert(args: argparse.Namespace) -> int:
    report = build_odds_change_alert_report(
        records=load_odds_csv(args.odds),
        race_id=RaceId(
            race_date=date.fromisoformat(args.race_date),
            venue=VenueCode(args.venue),
            race_no=args.race_no,
        ),
        bet_type=BetType(args.bet_type),
        frozen_as_of=_parse_datetime(args.frozen_as_of, "frozen-as-of"),
        alert_as_of=_parse_datetime(args.alert_as_of, "alert-as-of"),
        min_relative_change=_parse_decimal_argument(
            args.min_relative_change,
            "min-relative-change",
        ),
    )
    _write_json(args.output, odds_change_alert_report_to_dict(report))
    return 0


def _run_frequency_model_candidates(args: argparse.Namespace) -> int:
    prediction_as_of = _parse_datetime(args.prediction_as_of, "prediction-as-of")
    model = fit_trifecta_frequency_model(
        load_results_csv(args.results),
        as_of=prediction_as_of,
        smoothing=_parse_decimal_argument(args.smoothing, "smoothing"),
    )
    race_id = RaceId(
        race_date=date.fromisoformat(args.race_date),
        venue=VenueCode(args.venue),
        race_no=args.race_no,
    )
    versions = ArtifactVersions(
        data=args.data_version,
        feature=args.feature_version,
        model=args.model_version,
        strategy=args.strategy_version,
    )
    candidates = tuple(
        StrategyCandidate(
            recommendation_id=f"freq-{race_id}-{item.combination.key}",
            race_id=race_id,
            combination=BetCombination(
                BetType.TRIFECTA_ORDERED,
                item.combination.lanes,
            ),
            probability=item.probability,
            odds=None,
            confidence=ConfidenceLevel(args.confidence),
            as_of=prediction_as_of,
            versions=versions,
            reason_codes=(
                "frequency_baseline",
                f"training_races_{model.training_race_count}",
            ),
        )
        for item in model.probabilities
    )
    export_strategy_candidates_csv(candidates, args.output)
    return 0


def _run_market_implied_candidates(args: argparse.Namespace) -> int:
    prediction_as_of = _parse_datetime(args.prediction_as_of, "prediction-as-of")
    race_id = RaceId(
        race_date=date.fromisoformat(args.race_date),
        venue=VenueCode(args.venue),
        race_no=args.race_no,
    )
    bet_type = BetType(args.bet_type)
    model = build_market_implied_model(
        load_odds_csv(args.odds),
        race_id=race_id,
        bet_type=bet_type,
        as_of=prediction_as_of,
    )
    versions = ArtifactVersions(
        data=args.data_version,
        feature=args.feature_version,
        model=args.model_version,
        strategy=args.strategy_version,
    )
    candidates = tuple(
        StrategyCandidate(
            recommendation_id=f"market-{race_id}-{item.combination.key}",
            race_id=race_id,
            combination=item.combination,
            probability=item.probability,
            odds=item.odds,
            confidence=ConfidenceLevel(args.confidence),
            as_of=prediction_as_of,
            versions=versions,
            reason_codes=(
                "market_implied_baseline",
                f"odds_snapshots_{model.snapshot_count}",
            ),
        )
        for item in model.probabilities
    )
    export_strategy_candidates_csv(candidates, args.output)
    return 0


def _run_probability_report(args: argparse.Namespace) -> int:
    report = evaluate_probability_candidates(
        candidates=load_strategy_candidates_csv(args.candidates),
        results=load_results_csv(args.results),
        bet_type=BetType(args.bet_type),
        ece_bins=args.ece_bins,
    )
    _write_json(args.output, probability_evaluation_report_to_dict(report))
    return 0


def _run_value_strategy_recommendations(args: argparse.Namespace) -> int:
    config = ValueStrategyConfig(
        min_probability=_parse_decimal_argument(args.min_probability, "min-probability"),
        min_expected_value=_parse_decimal_argument(
            args.min_expected_value,
            "min-expected-value",
        ),
        conservative_margin=_parse_decimal_argument(
            args.conservative_margin,
            "conservative-margin",
        ),
        min_conservative_expected_value=_parse_decimal_argument(
            args.min_conservative_expected_value,
            "min-conservative-expected-value",
        ),
        max_odds=None
        if args.max_odds is None
        else _parse_decimal_argument(args.max_odds, "max-odds"),
    )
    recommendations = apply_risk_budget(
        (
            build_value_recommendation(candidate, config)
            for candidate in load_strategy_candidates_csv(args.candidates)
        ),
        RiskBudgetConfig(
            max_selects_per_race=args.max_selects_per_race,
            max_daily_stake_units=args.max_daily_stake_units,
        ),
    )
    export_recommendations_csv(recommendations, args.output)
    return 0


def _run_attach_odds_to_candidates(args: argparse.Namespace) -> int:
    odds_records = load_odds_csv(args.odds)
    max_age = (
        None
        if args.max_age_minutes is None
        else timedelta(minutes=args.max_age_minutes)
    )
    candidates = tuple(
        _candidate_with_latest_odds(candidate, odds_records, max_age)
        for candidate in load_strategy_candidates_csv(args.candidates)
    )
    export_strategy_candidates_csv(candidates, args.output)
    return 0


def _candidate_with_latest_odds(
    candidate: StrategyCandidate,
    odds_records: tuple[OddsSnapshotRecord, ...],
    max_age: timedelta | None,
) -> StrategyCandidate:
    latest = latest_odds_by_combination(
        records=odds_records,
        race_id=candidate.race_id,
        as_of=candidate.as_of,
    )
    odds_record = latest.get(candidate.combination)
    if odds_record is None:
        return candidate
    if max_age is not None and candidate.as_of - odds_record.available_at > max_age:
        return _candidate_with_replaced_odds(
            candidate,
            odds=None,
            reason_code="odds_snapshot_stale",
        )

    return _candidate_with_replaced_odds(
        candidate,
        odds=odds_record.odds,
        reason_code="odds_snapshot_attached",
    )


def _candidate_with_replaced_odds(
    candidate: StrategyCandidate,
    *,
    odds: Decimal | None,
    reason_code: str,
) -> StrategyCandidate:
    return StrategyCandidate(
        recommendation_id=candidate.recommendation_id,
        race_id=candidate.race_id,
        combination=candidate.combination,
        probability=candidate.probability,
        odds=odds,
        confidence=candidate.confidence,
        as_of=candidate.as_of,
        versions=candidate.versions,
        reason_codes=_append_reason_once(candidate.reason_codes, reason_code),
    )


def _append_reason_once(reason_codes: tuple[str, ...], reason_code: str) -> tuple[str, ...]:
    if reason_code in reason_codes:
        return reason_codes
    return reason_codes + (reason_code,)


def _run_candidate_status(args: argparse.Namespace) -> int:
    payload = _candidate_service(args).get_business_date_status(args.business_date)
    _write_json(args.output, payload)
    return 0


def _run_candidate_list(args: argparse.Namespace) -> int:
    payload = _candidate_service(args).list_candidates(args.business_date)
    _write_json(args.output, payload)
    return 0


def _run_candidate_detail(args: argparse.Namespace) -> int:
    payload = _candidate_service(args).get_candidate_detail(
        args.business_date,
        args.recommendation_id,
    )
    _write_json(args.output, payload)
    return 0


def _run_confirmed_review_list(args: argparse.Namespace) -> int:
    review_list = build_confirmed_review_list(
        reviews=load_reviews_json(args.reviews),
        business_date=args.business_date,
        generated_at=_parse_datetime(args.generated_at, "generated-at"),
        generated_by=args.generated_by,
    )
    output_path: Path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = confirmed_review_list_to_dict(review_list)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


def _run_review_store_import(args: argparse.Namespace) -> int:
    FileReviewStore(args.store).upsert_reviews(load_reviews_json(args.reviews))
    return 0


def _run_review_workflow_import(args: argparse.Namespace) -> int:
    request_payload = json.loads(args.reviews.read_text(encoding="utf-8"))
    payload = _review_workflow_service(args).import_reviews(request_payload)
    _write_json(args.output, payload)
    return 0


def _run_review_workflow_confirmed_list(args: argparse.Namespace) -> int:
    payload = _review_workflow_service(args).build_confirmed_review_list(
        {
            "business_date": args.business_date,
            "generated_at": args.generated_at,
            "generated_by": args.generated_by,
        }
    )
    _write_json(args.output, payload)
    return 0


def _run_review_workflow_archive(args: argparse.Namespace) -> int:
    payload = _review_workflow_service(args).freeze_confirmed_review_archive(
        {
            "business_date": args.business_date,
            "generated_at": args.generated_at,
            "generated_by": args.generated_by,
            "frozen_at": args.frozen_at,
            "frozen_by": args.frozen_by,
        }
    )
    _write_json(args.output, payload)
    return 0


def _run_confirmed_review_archive(args: argparse.Namespace) -> int:
    review_list = FileReviewStore(args.store).build_confirmed_review_list(
        business_date=args.business_date,
        generated_at=_parse_datetime(args.generated_at, "generated-at"),
        generated_by=args.generated_by,
    )
    freeze_confirmed_review_list(
        review_list,
        archive_dir=args.archive_dir,
        frozen_at=_parse_datetime(args.frozen_at, "frozen-at"),
        frozen_by=args.frozen_by,
    )
    return 0


def _run_confirmed_review_excel(args: argparse.Namespace) -> int:
    review_list = FileReviewStore(args.store).build_confirmed_review_list(
        business_date=args.business_date,
        generated_at=_parse_datetime(args.generated_at, "generated-at"),
        generated_by=args.generated_by,
    )
    export_confirmed_review_list_xlsx(review_list, args.output)
    return 0


def _run_review_table_excel(args: argparse.Namespace) -> int:
    generated_at = _parse_datetime(args.generated_at, "generated-at")
    export_review_table_xlsx(
        FileReviewStore(args.store).list_reviews(),
        args.output,
        business_date=args.business_date,
        generated_at=generated_at.isoformat(),
        generated_by=args.generated_by,
    )
    return 0


def _run_review_workflow_export(args: argparse.Namespace) -> int:
    payload = _review_workflow_service(args).export_excel(
        {
            "business_date": args.business_date,
            "export_type": args.export_type,
            "generated_at": args.generated_at,
            "generated_by": args.generated_by,
        }
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def _run_export_job_status(args: argparse.Namespace) -> int:
    payload = _review_workflow_service(args).get_export_job(args.job_id)
    _write_json(args.output, payload)
    return 0


def _run_api_request(args: argparse.Namespace) -> int:
    adapter = AnalysisApiAdapter(
        report_paths=_api_request_report_paths(args),
        review_store_path=args.store,
        archive_dir=args.archive_dir,
        export_dir=args.export_dir,
    )
    response = adapter.handle(
        ApiRequest(
            method=args.method,
            path=args.path,
            body=_read_optional_json_body(args.body),
        )
    )
    _write_json(
        args.output,
        {
            "status_code": response.status_code,
            "body": response.body,
        },
    )
    return 0


def _run_serve_api(args: argparse.Namespace) -> int:
    adapter = AnalysisApiAdapter(
        report_paths=_serve_api_report_paths(args),
        review_store_path=args.store,
        archive_dir=args.archive_dir,
        export_dir=args.export_dir,
    )
    serve_api_http(
        (args.host, args.port),
        adapter,
        allowed_origin=args.allowed_origin,
    )
    return 0


def _run_openapi_spec(args: argparse.Namespace) -> int:
    export_openapi_spec_json(args.output)
    return 0


def _candidate_service(args: argparse.Namespace) -> CandidateQueryService:
    return CandidateQueryService(report_paths={args.business_date: args.report})


def _review_workflow_service(args: argparse.Namespace) -> ReviewWorkflowService:
    return ReviewWorkflowService(
        review_store_path=args.store,
        archive_dir=args.archive_dir,
        export_dir=args.export_dir,
    )


def _api_request_report_paths(args: argparse.Namespace) -> dict[str, Path | str]:
    if args.report_business_date is None and args.report is None:
        return {}
    if args.report_business_date is None or args.report is None:
        raise ValueError("report-business-date and report must be provided together")
    return {args.report_business_date: args.report}


def _serve_api_report_paths(args: argparse.Namespace) -> dict[str, Path | str]:
    if len(args.report_business_date) != len(args.report):
        raise ValueError("serve-api requires one --report for each --report-business-date")
    return dict(zip(args.report_business_date, args.report, strict=True))


def _read_optional_json_body(path: Path | None) -> object | None:
    if path is None:
        return None
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    return payload


def _write_json(output_path: Path, payload: object) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _collect_expected_races(args: argparse.Namespace) -> tuple[RaceId, ...]:
    races = [_parse_race_id(value) for value in args.expected_race]
    if args.expected_date is not None or args.venue is not None or args.race_nos is not None:
        if args.expected_date is None or args.venue is None or args.race_nos is None:
            raise ValueError("expected-date, venue, and race-nos must be provided together")
        race_date = date.fromisoformat(args.expected_date)
        venue = VenueCode(args.venue)
        races.extend(
            RaceId(race_date=race_date, venue=venue, race_no=race_no)
            for race_no in _parse_race_numbers(args.race_nos)
        )
    if not races:
        raise ValueError("expected races require --expected-race or expected date range arguments")
    return tuple(sorted(set(races), key=_race_id_sort_key))


def _parse_race_id(value: str) -> RaceId:
    parts = value.split(":")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            "expected race must use YYYY-MM-DD:venue:race_no format"
        )
    race_date, venue, race_no = parts
    return RaceId(
        race_date=date.fromisoformat(race_date),
        venue=VenueCode(venue),
        race_no=int(race_no),
    )


def _parse_race_numbers(value: str) -> tuple[int, ...]:
    race_numbers: list[int] = []
    for part in value.split(","):
        token = part.strip()
        if not token:
            raise ValueError("race-nos must not contain empty entries")
        if "-" in token:
            start_text, end_text = token.split("-", maxsplit=1)
            start = int(start_text)
            end = int(end_text)
            if end < start:
                raise ValueError("race-nos range end must not be before start")
            race_numbers.extend(range(start, end + 1))
        else:
            race_numbers.append(int(token))
    return tuple(race_numbers)


def _parse_datetime(value: str, name: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return parsed


def _parse_decimal_argument(value: str, name: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{name} must be a decimal") from exc


def _race_id_sort_key(race_id: RaceId) -> tuple[date, str, int]:
    return (race_id.race_date, race_id.venue.value, race_id.race_no)
