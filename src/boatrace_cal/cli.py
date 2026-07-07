"""Command line entry points for local BOAT RACE analysis workflows."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import date
import json
from pathlib import Path

from boatrace_cal.backtest.export import export_backtest_report_json
from boatrace_cal.backtest.runner import run_backtest
from boatrace_cal.domain.bets import BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.ingestion.payouts import load_payouts_csv
from boatrace_cal.ingestion.recommendations import load_recommendations_csv
from boatrace_cal.ingestion.results import load_results_csv
from boatrace_cal.validation.data_quality import build_historical_data_quality_report
from boatrace_cal.validation.serialization import historical_data_quality_report_to_dict


def main(argv: Sequence[str] | None = None) -> int:
    """Run the boatrace-cal command line interface."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "backtest-report":
        return _run_backtest_report(args)
    if args.command == "historical-quality-report":
        return _run_historical_quality_report(args)
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
    quality.add_argument("--expected-race", required=True, action="append")
    quality.add_argument("--bet-type", required=True, action="append")
    quality.add_argument("--output", required=True, type=Path)

    backtest = subparsers.add_parser(
        "backtest-report",
        help="Run a historical paper backtest and write a JSON report.",
    )
    backtest.add_argument("--recommendations", required=True, type=Path)
    backtest.add_argument("--results", required=True, type=Path)
    backtest.add_argument("--payouts", required=True, type=Path)
    backtest.add_argument("--expected-race", required=True, action="append")
    backtest.add_argument("--bet-type", required=True, action="append")
    backtest.add_argument("--output", required=True, type=Path)
    return parser


def _run_backtest_report(args: argparse.Namespace) -> int:
    report = run_backtest(
        recommendations=load_recommendations_csv(args.recommendations),
        results=load_results_csv(args.results),
        payouts=load_payouts_csv(args.payouts),
        expected_races=tuple(_parse_race_id(value) for value in args.expected_race),
        bet_types=tuple(BetType(value) for value in args.bet_type),
    )
    export_backtest_report_json(report, args.output)
    return 0


def _run_historical_quality_report(args: argparse.Namespace) -> int:
    report = build_historical_data_quality_report(
        results=load_results_csv(args.results),
        payouts=load_payouts_csv(args.payouts),
        expected_races=tuple(_parse_race_id(value) for value in args.expected_race),
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
