from datetime import UTC, date, datetime
from decimal import Decimal

from boatrace_cal.backtest.runner import run_backtest
from boatrace_cal.backtest.serialization import backtest_report_to_dict
from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.domain.recommendations import (
    ConfidenceLevel,
    Decision,
    PlanStage,
    Recommendation,
)
from boatrace_cal.domain.versions import ArtifactVersions
from boatrace_cal.ingestion.payouts import PayoutRecord
from boatrace_cal.ingestion.results import RaceResultRecord


def test_backtest_report_to_dict_serializes_ready_report_for_json_output() -> None:
    race = RaceId(date(2025, 1, 2), VenueCode("01"), 1)
    combination = BetCombination.create(BetType.TRIFECTA_ORDERED, (1, 2, 3))
    report = run_backtest(
        recommendations=(_recommendation("rec-1", race, combination),),
        results=(_result(race),),
        payouts=(_payout(race, combination, "1200"),),
        expected_races=(race,),
        bet_types=(BetType.TRIFECTA_ORDERED,),
    )

    payload = backtest_report_to_dict(report)

    assert payload["readiness"]["status"] == "ready"
    assert payload["readiness"]["ready"] is True
    assert payload["readiness"]["blockers"] == []
    assert payload["summary"]["selected_bet_count"] == 1
    assert payload["summary"]["net_profit_yen"] == "1100"
    assert payload["confidence_intervals"] == {
        "schema_version": "backtest-confidence-intervals-v1",
        "method": "bootstrap_percentile",
        "confidence_level": "0.95",
        "iterations": 1000,
        "seed": 20250101,
        "sample_size": 1,
        "metrics": [
            {
                "name": "net_profit_yen",
                "point_estimate": "1100",
                "lower": "1100",
                "upper": "1100",
            },
            {
                "name": "return_rate",
                "point_estimate": "12",
                "lower": "12",
                "upper": "12",
            },
            {
                "name": "hit_rate",
                "point_estimate": "1",
                "lower": "1",
                "upper": "1",
            },
        ],
    }
    assert payload["equity_curve"]["final_equity_yen"] == "1100"
    assert payload["slices"] == [
        {
            "dimension": "venue",
            "key": "01",
            "selected_bet_count": 1,
            "selected_race_count": 1,
            "hit_count": 1,
            "miss_count": 0,
            "payout_missing_count": 0,
            "total_stake_yen": "100",
            "total_returned_yen": "1200",
            "net_profit_yen": "1100",
            "return_rate": "12",
            "hit_rate": "1",
        },
        {
            "dimension": "bet_type",
            "key": "trifecta_ordered",
            "selected_bet_count": 1,
            "selected_race_count": 1,
            "hit_count": 1,
            "miss_count": 0,
            "payout_missing_count": 0,
            "total_stake_yen": "100",
            "total_returned_yen": "1200",
            "net_profit_yen": "1100",
            "return_rate": "12",
            "hit_rate": "1",
        },
        {
            "dimension": "race_month",
            "key": "2025-01",
            "selected_bet_count": 1,
            "selected_race_count": 1,
            "hit_count": 1,
            "miss_count": 0,
            "payout_missing_count": 0,
            "total_stake_yen": "100",
            "total_returned_yen": "1200",
            "net_profit_yen": "1100",
            "return_rate": "12",
            "hit_rate": "1",
        },
        {
            "dimension": "odds_band",
            "key": "odds_3_to_10",
            "selected_bet_count": 1,
            "selected_race_count": 1,
            "hit_count": 1,
            "miss_count": 0,
            "payout_missing_count": 0,
            "total_stake_yen": "100",
            "total_returned_yen": "1200",
            "net_profit_yen": "1100",
            "return_rate": "12",
            "hit_rate": "1",
        },
    ]
    assert payload["settlements"] == [
        {
            "recommendation_id": "rec-1",
            "race_id": "20250102-01-01",
            "stake_units": 1,
            "stake_yen": "100",
            "returned_yen": "1200",
            "net_profit_yen": "1100",
            "recommendation": {
                "stage": "final",
                "decision": "select",
                "confidence": "high",
                "probability": "0.25",
                "odds": "5.2",
                "expected_value": "0.30",
                "as_of": "2025-01-02T10:00:00+00:00",
                "stake_units": 1,
                "versions": {
                    "data": "data-v1",
                    "feature": "feature-v1",
                    "model": "model-v1",
                    "strategy": "strategy-v1",
                },
                "reason_codes": ["positive_ev"],
            },
            "settlement": {
                "race_id": "20250102-01-01",
                "combination": {
                    "bet_type": "trifecta_ordered",
                    "lanes": [1, 2, 3],
                },
                "status": "hit",
                "payout_yen": "1200",
            },
        }
    ]


def test_backtest_report_to_dict_serializes_blocked_report_without_execution_outputs() -> None:
    race = RaceId(date(2025, 1, 2), VenueCode("01"), 1)
    combination = BetCombination.create(BetType.TRIFECTA_ORDERED, (1, 2, 3))
    report = run_backtest(
        recommendations=(_recommendation("rec-1", race, combination),),
        results=(),
        payouts=(),
        expected_races=(race,),
        bet_types=(BetType.TRIFECTA_ORDERED,),
    )

    payload = backtest_report_to_dict(report)

    assert payload["readiness"]["status"] == "blocked"
    assert payload["readiness"]["ready"] is False
    assert payload["readiness"]["refusal_reason"] == "historical_data_quality_issues"
    assert payload["summary"] is None
    assert payload["confidence_intervals"] is None
    assert payload["equity_curve"] is None
    assert payload["slices"] is None
    assert payload["settlements"] is None
    assert payload["readiness"]["blockers"] == [
        {
            "race_id": "20250102-01-01",
            "code": "payout_missing",
            "bet_type": "trifecta_ordered",
        },
        {
            "race_id": "20250102-01-01",
            "code": "result_missing",
            "bet_type": None,
        },
    ]


def _recommendation(
    recommendation_id: str,
    race_id: RaceId,
    combination: BetCombination,
) -> Recommendation:
    return Recommendation(
        recommendation_id=recommendation_id,
        race_id=race_id,
        combination=combination,
        stage=PlanStage.FINAL,
        decision=Decision.SELECT,
        confidence=ConfidenceLevel.HIGH,
        probability=Decimal("0.25"),
        odds=Decimal("5.2"),
        expected_value=Decimal("0.30"),
        as_of=datetime(2025, 1, 2, 10, 0, tzinfo=UTC),
        stake_units=1,
        versions=ArtifactVersions("data-v1", "feature-v1", "model-v1", "strategy-v1"),
        reason_codes=("positive_ev",),
    )


def _result(race_id: RaceId) -> RaceResultRecord:
    timestamp = datetime(2025, 1, 2, 16, 0, tzinfo=UTC)
    return RaceResultRecord(
        race_id=race_id,
        finish_order=(1, 2, 3),
        source="official-results",
        source_hash=f"result-{race_id}",
        observed_at=timestamp,
        available_at=timestamp,
        parser_version="results-v1",
    )


def _payout(
    race_id: RaceId,
    combination: BetCombination,
    payout_yen: str,
) -> PayoutRecord:
    timestamp = datetime(2025, 1, 2, 16, 0, tzinfo=UTC)
    return PayoutRecord(
        race_id=race_id,
        combination=combination,
        payout_yen=Decimal(payout_yen),
        source="official-payouts",
        source_hash=f"payout-{race_id}",
        observed_at=timestamp,
        available_at=timestamp,
        parser_version="payouts-v1",
    )
