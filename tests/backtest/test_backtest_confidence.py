from datetime import UTC, date, datetime
from decimal import Decimal

from boatrace_cal.backtest.confidence import build_backtest_confidence_intervals
from boatrace_cal.backtest.settlement import BacktestSettlementRow
from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.domain.recommendations import (
    ConfidenceLevel,
    Decision,
    PlanStage,
    Recommendation,
)
from boatrace_cal.domain.versions import ArtifactVersions
from boatrace_cal.settlement import SettlementResult, SettlementStatus


def test_backtest_confidence_intervals_collapse_for_single_settlement() -> None:
    race = RaceId(date(2025, 1, 2), VenueCode("01"), 1)
    combination = BetCombination.create(BetType.TRIFECTA_ORDERED, (1, 2, 3))

    intervals = build_backtest_confidence_intervals(
        rows=(_row("rec-1", race, combination, SettlementStatus.HIT, "100", "1200"),),
        iterations=25,
        seed=7,
    )

    assert intervals.schema_version == "backtest-confidence-intervals-v1"
    assert intervals.method == "bootstrap_percentile"
    assert intervals.confidence_level == Decimal("0.95")
    assert intervals.iterations == 25
    assert intervals.seed == 7
    assert intervals.sample_size == 1
    assert [(metric.name, metric.point_estimate, metric.lower, metric.upper) for metric in intervals.metrics] == [
        ("net_profit_yen", Decimal("1100"), Decimal("1100"), Decimal("1100")),
        ("return_rate", Decimal("12"), Decimal("12"), Decimal("12")),
        ("hit_rate", Decimal("1"), Decimal("1"), Decimal("1")),
    ]


def test_backtest_confidence_intervals_are_reproducible_and_bound_point_estimates() -> None:
    race_1 = RaceId(date(2025, 1, 2), VenueCode("01"), 1)
    race_2 = RaceId(date(2025, 1, 2), VenueCode("01"), 2)
    race_3 = RaceId(date(2025, 1, 2), VenueCode("01"), 3)
    combination = BetCombination.create(BetType.TRIFECTA_ORDERED, (1, 2, 3))
    rows = (
        _row("rec-1", race_1, combination, SettlementStatus.HIT, "100", "400"),
        _row("rec-2", race_2, combination, SettlementStatus.MISS, "100", "0"),
        _row("rec-3", race_3, combination, SettlementStatus.MISS, "100", "0"),
    )

    first = build_backtest_confidence_intervals(rows=rows, iterations=200, seed=11)
    second = build_backtest_confidence_intervals(rows=rows, iterations=200, seed=11)

    assert first == second
    assert first.sample_size == 3
    for metric in first.metrics:
        assert metric.lower <= metric.point_estimate <= metric.upper


def _row(
    recommendation_id: str,
    race_id: RaceId,
    combination: BetCombination,
    status: SettlementStatus,
    stake_yen: str,
    returned_yen: str,
) -> BacktestSettlementRow:
    stake = Decimal(stake_yen)
    returned = Decimal(returned_yen)
    return BacktestSettlementRow(
        recommendation_id=recommendation_id,
        race_id=race_id,
        stake_units=1,
        stake_yen=stake,
        returned_yen=returned,
        net_profit_yen=returned - stake,
        recommendation=_recommendation(recommendation_id, race_id, combination),
        settlement=SettlementResult(
            race_id=race_id,
            combination=combination,
            status=status,
            payout_yen=returned if status is SettlementStatus.HIT else Decimal("0"),
        ),
    )


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
