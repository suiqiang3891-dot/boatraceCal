from datetime import date
from decimal import Decimal

from boatrace_cal.backtest.settlement import BacktestSettlementRow
from boatrace_cal.backtest.summary import build_backtest_slices, summarize_backtest_settlements
from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.settlement import SettlementResult, SettlementStatus


def test_summarize_backtest_settlements_reports_core_rates_and_totals() -> None:
    race_1 = RaceId(date(2025, 1, 2), VenueCode("01"), 1)
    race_2 = RaceId(date(2025, 1, 2), VenueCode("01"), 2)
    combination = BetCombination.create(BetType.TRIFECTA_ORDERED, (1, 2, 3))

    summary = summarize_backtest_settlements(
        rows=(
            _row("hit-rec", race_1, combination, SettlementStatus.HIT, "100", "300"),
            _row("miss-rec", race_2, combination, SettlementStatus.MISS, "100", "0"),
        ),
        expected_race_count=4,
    )

    assert summary.expected_race_count == 4
    assert summary.selected_bet_count == 2
    assert summary.selected_race_count == 2
    assert summary.hit_count == 1
    assert summary.miss_count == 1
    assert summary.payout_missing_count == 0
    assert summary.total_stake_yen == Decimal("200")
    assert summary.total_returned_yen == Decimal("300")
    assert summary.net_profit_yen == Decimal("100")
    assert summary.return_rate == Decimal("1.5")
    assert summary.hit_rate == Decimal("0.5")
    assert summary.coverage_rate == Decimal("0.5")


def test_summarize_backtest_settlements_handles_no_selected_bets() -> None:
    summary = summarize_backtest_settlements(rows=(), expected_race_count=3)

    assert summary.expected_race_count == 3
    assert summary.selected_bet_count == 0
    assert summary.selected_race_count == 0
    assert summary.total_stake_yen == Decimal("0")
    assert summary.return_rate == Decimal("0")
    assert summary.hit_rate == Decimal("0")
    assert summary.coverage_rate == Decimal("0")


def test_build_backtest_slices_groups_selected_bets_for_ui_reports() -> None:
    race_1 = RaceId(date(2025, 1, 2), VenueCode("01"), 1)
    race_2 = RaceId(date(2025, 1, 2), VenueCode("02"), 1)
    trifecta = BetCombination.create(BetType.TRIFECTA_ORDERED, (1, 2, 3))
    exacta = BetCombination.create(BetType.EXACTA_ORDERED, (1, 2))

    slices = build_backtest_slices(
        rows=(
            _row("hit-rec", race_1, trifecta, SettlementStatus.HIT, "100", "300"),
            _row("miss-rec", race_2, exacta, SettlementStatus.MISS, "100", "0"),
        )
    )

    assert [(item.dimension, item.key) for item in slices] == [
        ("venue", "01"),
        ("venue", "02"),
        ("bet_type", "exacta_ordered"),
        ("bet_type", "trifecta_ordered"),
    ]
    assert slices[0].selected_bet_count == 1
    assert slices[0].hit_count == 1
    assert slices[0].net_profit_yen == Decimal("200")
    assert slices[0].return_rate == Decimal("3")
    assert slices[1].miss_count == 1
    assert slices[1].net_profit_yen == Decimal("-100")
    assert slices[1].return_rate == Decimal("0")


def _row(
    recommendation_id: str,
    race_id: RaceId,
    combination: BetCombination,
    status: SettlementStatus,
    stake_yen: str,
    returned_yen: str,
) -> BacktestSettlementRow:
    returned = Decimal(returned_yen)
    stake = Decimal(stake_yen)
    return BacktestSettlementRow(
        recommendation_id=recommendation_id,
        race_id=race_id,
        stake_units=1,
        stake_yen=stake,
        returned_yen=returned,
        net_profit_yen=returned - stake,
        settlement=SettlementResult(
            race_id=race_id,
            combination=combination,
            status=status,
            payout_yen=returned if status is SettlementStatus.HIT else Decimal("0"),
        ),
    )
