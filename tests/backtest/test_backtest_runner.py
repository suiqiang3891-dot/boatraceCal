from datetime import UTC, date, datetime
from decimal import Decimal

from boatrace_cal.backtest.runner import run_backtest
from boatrace_cal.backtest.preflight import BacktestReadinessStatus
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


def test_run_backtest_returns_settlements_summary_and_equity_when_ready() -> None:
    race_1 = RaceId(date(2025, 1, 2), VenueCode("01"), 1)
    race_2 = RaceId(date(2025, 1, 2), VenueCode("01"), 2)
    winning_combination = BetCombination.create(BetType.TRIFECTA_ORDERED, (1, 2, 3))
    losing_combination = BetCombination.create(BetType.TRIFECTA_ORDERED, (1, 3, 2))

    report = run_backtest(
        recommendations=(
            _recommendation("rec-hit", race_1, winning_combination, Decision.SELECT),
            _recommendation("rec-pass", race_1, losing_combination, Decision.PASS),
            _recommendation("rec-miss", race_2, losing_combination, Decision.SELECT),
        ),
        results=(
            _result(race_1),
            _result(race_2),
        ),
        payouts=(
            _payout(race_1, winning_combination, "1200"),
            _payout(race_2, winning_combination, "900"),
        ),
        expected_races=(race_1, race_2),
        bet_types=(BetType.TRIFECTA_ORDERED,),
    )

    assert report.readiness.status is BacktestReadinessStatus.READY
    assert report.settlements is not None
    assert report.summary is not None
    assert report.equity_curve is not None
    assert report.slices is not None
    assert tuple(row.recommendation_id for row in report.settlements) == ("rec-hit", "rec-miss")
    assert report.summary.selected_bet_count == 2
    assert report.summary.net_profit_yen == Decimal("1000")
    assert report.equity_curve.final_equity_yen == Decimal("1000")
    assert report.equity_curve.max_drawdown_yen == Decimal("100")
    assert [(item.dimension, item.key) for item in report.slices] == [
        ("venue", "01"),
        ("bet_type", "trifecta_ordered"),
        ("race_month", "2025-01"),
        ("odds_band", "odds_3_to_10"),
    ]


def test_run_backtest_blocks_without_settlement_outputs_when_preflight_fails() -> None:
    race = RaceId(date(2025, 1, 2), VenueCode("01"), 1)
    combination = BetCombination.create(BetType.TRIFECTA_ORDERED, (1, 2, 3))

    report = run_backtest(
        recommendations=(_recommendation("rec-1", race, combination, Decision.SELECT),),
        results=(),
        payouts=(),
        expected_races=(race,),
        bet_types=(BetType.TRIFECTA_ORDERED,),
    )

    assert report.readiness.status is BacktestReadinessStatus.BLOCKED
    assert report.settlements is None
    assert report.summary is None
    assert report.equity_curve is None
    assert report.slices is None


def _recommendation(
    recommendation_id: str,
    race_id: RaceId,
    combination: BetCombination,
    decision: Decision,
) -> Recommendation:
    is_select = decision is Decision.SELECT
    return Recommendation(
        recommendation_id=recommendation_id,
        race_id=race_id,
        combination=combination,
        stage=PlanStage.FINAL,
        decision=decision,
        confidence=ConfidenceLevel.HIGH,
        probability=Decimal("0.25"),
        odds=Decimal("5.2") if is_select else None,
        expected_value=Decimal("0.30") if is_select else None,
        as_of=datetime(2025, 1, 2, 10, 0, tzinfo=UTC),
        stake_units=1 if is_select else 0,
        versions=ArtifactVersions("data-v1", "feature-v1", "model-v1", "strategy-v1"),
        reason_codes=("positive_ev",) if is_select else ("below_threshold",),
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
