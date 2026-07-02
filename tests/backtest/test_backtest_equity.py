from datetime import date
from decimal import Decimal

from boatrace_cal.backtest.equity import build_equity_curve
from boatrace_cal.backtest.settlement import BacktestSettlementRow
from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.settlement import SettlementResult, SettlementStatus


def test_build_equity_curve_orders_rows_and_reports_max_drawdown() -> None:
    race_1 = RaceId(date(2025, 1, 2), VenueCode("01"), 1)
    race_2 = RaceId(date(2025, 1, 2), VenueCode("01"), 2)
    race_3 = RaceId(date(2025, 1, 2), VenueCode("01"), 3)
    combination = BetCombination.create(BetType.TRIFECTA_ORDERED, (1, 2, 3))

    curve = build_equity_curve(
        rows=(
            _row("rec-3", race_3, combination, SettlementStatus.HIT, "100", "350"),
            _row("rec-1", race_1, combination, SettlementStatus.HIT, "100", "300"),
            _row("rec-2", race_2, combination, SettlementStatus.MISS, "100", "0"),
        )
    )

    assert tuple(point.recommendation_id for point in curve.points) == ("rec-1", "rec-2", "rec-3")
    assert tuple(point.equity_yen for point in curve.points) == (
        Decimal("200"),
        Decimal("100"),
        Decimal("350"),
    )
    assert tuple(point.peak_equity_yen for point in curve.points) == (
        Decimal("200"),
        Decimal("200"),
        Decimal("350"),
    )
    assert tuple(point.drawdown_yen for point in curve.points) == (
        Decimal("0"),
        Decimal("100"),
        Decimal("0"),
    )
    assert curve.final_equity_yen == Decimal("350")
    assert curve.max_drawdown_yen == Decimal("100")
    assert curve.max_drawdown_rate == Decimal("0.5")


def test_build_equity_curve_handles_no_settled_rows() -> None:
    curve = build_equity_curve(rows=())

    assert curve.points == ()
    assert curve.final_equity_yen == Decimal("0")
    assert curve.max_drawdown_yen == Decimal("0")
    assert curve.max_drawdown_rate == Decimal("0")


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
        settlement=SettlementResult(
            race_id=race_id,
            combination=combination,
            status=status,
            payout_yen=returned if status is SettlementStatus.HIT else Decimal("0"),
        ),
    )
