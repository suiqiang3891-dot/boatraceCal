from datetime import date, datetime, timezone
from decimal import Decimal

from boatrace_cal.domain.bets import BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.ingestion.odds import load_odds_csv
from boatrace_cal.validation.odds_change_alert import (
    build_odds_change_alert_report,
    odds_change_alert_report_to_dict,
)


def test_odds_change_alert_reports_large_t05_moves_without_overwriting_freeze(
    tmp_path,
) -> None:
    records = load_odds_csv(
        _write_odds_csv(
            tmp_path,
            (
                "2026-06-23,05,1,trifecta_ordered,3-1-2,5.0,official-odds,"
                "hash-frozen,2026-06-23T04:19:00+00:00,"
                "2026-06-23T04:20:00+00:00,odds-v1",
                "2026-06-23,05,1,trifecta_ordered,3-1-2,6.0,official-odds,"
                "hash-alert,2026-06-23T04:24:00+00:00,"
                "2026-06-23T04:25:00+00:00,odds-v1",
                "2026-06-23,05,1,trifecta_ordered,1-2-3,10.0,official-odds,"
                "hash-stable,2026-06-23T04:20:00+00:00,"
                "2026-06-23T04:20:00+00:00,odds-v1",
            ),
        )
    )

    report = build_odds_change_alert_report(
        records=records,
        race_id=RaceId(date(2026, 6, 23), VenueCode("05"), 1),
        bet_type=BetType.TRIFECTA_ORDERED,
        frozen_as_of=datetime(2026, 6, 23, 4, 20, tzinfo=timezone.utc),
        alert_as_of=datetime(2026, 6, 23, 4, 25, tzinfo=timezone.utc),
        min_relative_change=Decimal("0.10"),
    )
    payload = odds_change_alert_report_to_dict(report)

    assert payload["schema_version"] == "odds-change-alert-v1"
    assert payload["alert_only"] is True
    assert payload["action"] == "review_required_no_overwrite"
    assert payload["alert_count"] == 1
    assert payload["alerts"] == [
        {
            "code": "odds_changed",
            "combination": "3-1-2",
            "baseline_odds": "5.0",
            "comparison_odds": "6.0",
            "absolute_change": "1.0",
            "relative_change": "0.20",
            "baseline_available_at": "2026-06-23T04:20:00+00:00",
            "comparison_available_at": "2026-06-23T04:25:00+00:00",
        }
    ]


def test_odds_change_alert_reports_newly_available_combination(tmp_path) -> None:
    records = load_odds_csv(
        _write_odds_csv(
            tmp_path,
            (
                "2026-06-23,05,1,exacta_ordered,1-2,8.0,official-odds,"
                "hash-new,2026-06-23T04:24:00+00:00,"
                "2026-06-23T04:25:00+00:00,odds-v1",
            ),
        )
    )

    report = build_odds_change_alert_report(
        records=records,
        race_id=RaceId(date(2026, 6, 23), VenueCode("05"), 1),
        bet_type=BetType.EXACTA_ORDERED,
        frozen_as_of=datetime(2026, 6, 23, 4, 20, tzinfo=timezone.utc),
        alert_as_of=datetime(2026, 6, 23, 4, 25, tzinfo=timezone.utc),
        min_relative_change=Decimal("0.10"),
    )

    assert odds_change_alert_report_to_dict(report)["alerts"] == [
        {
            "code": "odds_newly_available",
            "combination": "1-2",
            "baseline_odds": None,
            "comparison_odds": "8.0",
            "absolute_change": None,
            "relative_change": None,
            "baseline_available_at": None,
            "comparison_available_at": "2026-06-23T04:25:00+00:00",
        }
    ]


def _write_odds_csv(tmp_path, rows: tuple[str, ...]) -> str:
    path = tmp_path / "odds.csv"
    path.write_text(
        "\n".join(
            (
                "race_date,venue,race_no,bet_type,combination,odds,"
                "source,source_hash,observed_at,available_at,parser_version",
                *rows,
            )
        )
        + "\n",
        encoding="utf-8",
    )
    return str(path)
