"""Command line entry points for local BOAT RACE analysis workflows."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import date, datetime
import json
from pathlib import Path

from boatrace_cal.api_contract import export_openapi_spec_json
from boatrace_cal.backtest.export import export_backtest_report_json
from boatrace_cal.backtest.runner import run_backtest
from boatrace_cal.domain.bets import BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.ingestion.payouts import load_payouts_csv
from boatrace_cal.ingestion.recommendations import load_recommendations_csv
from boatrace_cal.ingestion.results import load_results_csv
from boatrace_cal.review_archive import freeze_confirmed_review_list
from boatrace_cal.review_excel import export_confirmed_review_list_xlsx
from boatrace_cal.review_store import FileReviewStore
from boatrace_cal.reviews import (
    build_confirmed_review_list,
    confirmed_review_list_to_dict,
    load_reviews_json,
)
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
    if args.command == "confirmed-review-list":
        return _run_confirmed_review_list(args)
    if args.command == "review-store-import":
        return _run_review_store_import(args)
    if args.command == "confirmed-review-archive":
        return _run_confirmed_review_archive(args)
    if args.command == "confirmed-review-excel":
        return _run_confirmed_review_excel(args)
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


def _run_openapi_spec(args: argparse.Namespace) -> int:
    export_openapi_spec_json(args.output)
    return 0


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


def _race_id_sort_key(race_id: RaceId) -> tuple[date, str, int]:
    return (race_id.race_date, race_id.venue.value, race_id.race_no)
