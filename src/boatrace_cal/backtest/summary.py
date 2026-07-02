"""Aggregate metrics for settled paper backtest rows."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from boatrace_cal.backtest.settlement import BacktestSettlementRow
from boatrace_cal.settlement import SettlementStatus


@dataclass(frozen=True, slots=True)
class BacktestSummary:
    """First-pass aggregate backtest metrics derived from settled rows."""

    expected_race_count: int
    selected_bet_count: int
    selected_race_count: int
    hit_count: int
    miss_count: int
    payout_missing_count: int
    total_stake_yen: Decimal
    total_returned_yen: Decimal
    net_profit_yen: Decimal
    return_rate: Decimal
    hit_rate: Decimal
    coverage_rate: Decimal

    def __post_init__(self) -> None:
        for field_name in (
            "expected_race_count",
            "selected_bet_count",
            "selected_race_count",
            "hit_count",
            "miss_count",
            "payout_missing_count",
        ):
            value = getattr(self, field_name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        for field_name in (
            "total_stake_yen",
            "total_returned_yen",
            "net_profit_yen",
            "return_rate",
            "hit_rate",
            "coverage_rate",
        ):
            value = getattr(self, field_name)
            if type(value) is not Decimal or not value.is_finite():
                raise TypeError(f"{field_name} must be a finite Decimal")
        if self.selected_race_count > self.expected_race_count:
            raise ValueError("selected_race_count must not exceed expected_race_count")
        if self.hit_count + self.miss_count + self.payout_missing_count != self.selected_bet_count:
            raise ValueError("settlement status counts must match selected_bet_count")
        if self.total_stake_yen < Decimal("0"):
            raise ValueError("total_stake_yen must not be negative")
        if self.total_returned_yen < Decimal("0"):
            raise ValueError("total_returned_yen must not be negative")
        if self.net_profit_yen != self.total_returned_yen - self.total_stake_yen:
            raise ValueError("net_profit_yen must equal total_returned_yen minus total_stake_yen")
        _validate_unit_rate(self.hit_rate, "hit_rate")
        _validate_unit_rate(self.coverage_rate, "coverage_rate")
        if self.return_rate < Decimal("0"):
            raise ValueError("return_rate must not be negative")


def summarize_backtest_settlements(
    *,
    rows: Iterable[BacktestSettlementRow],
    expected_race_count: int,
) -> BacktestSummary:
    """Summarize settled paper bets without recomputing settlement outcomes."""

    if type(expected_race_count) is not int or expected_race_count < 0:
        raise ValueError("expected_race_count must be a non-negative integer")

    normalized_rows = _normalize_rows(rows)
    selected_bet_count = len(normalized_rows)
    selected_race_count = len({row.race_id for row in normalized_rows})
    hit_count = sum(1 for row in normalized_rows if row.settlement.status is SettlementStatus.HIT)
    miss_count = sum(1 for row in normalized_rows if row.settlement.status is SettlementStatus.MISS)
    payout_missing_count = sum(
        1 for row in normalized_rows if row.settlement.status is SettlementStatus.PAYOUT_MISSING
    )
    total_stake_yen = sum((row.stake_yen for row in normalized_rows), start=Decimal("0"))
    total_returned_yen = sum((row.returned_yen for row in normalized_rows), start=Decimal("0"))

    return BacktestSummary(
        expected_race_count=expected_race_count,
        selected_bet_count=selected_bet_count,
        selected_race_count=selected_race_count,
        hit_count=hit_count,
        miss_count=miss_count,
        payout_missing_count=payout_missing_count,
        total_stake_yen=total_stake_yen,
        total_returned_yen=total_returned_yen,
        net_profit_yen=total_returned_yen - total_stake_yen,
        return_rate=_safe_divide(total_returned_yen, total_stake_yen),
        hit_rate=_safe_divide(Decimal(hit_count), Decimal(selected_bet_count)),
        coverage_rate=_safe_divide(Decimal(selected_race_count), Decimal(expected_race_count)),
    )


def _normalize_rows(
    rows: Iterable[BacktestSettlementRow],
) -> tuple[BacktestSettlementRow, ...]:
    normalized = tuple(rows)
    if any(type(row) is not BacktestSettlementRow for row in normalized):
        raise TypeError("rows must contain only BacktestSettlementRow instances")
    return normalized


def _safe_divide(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == Decimal("0"):
        return Decimal("0")
    return numerator / denominator


def _validate_unit_rate(value: Decimal, field_name: str) -> None:
    if not Decimal("0") <= value <= Decimal("1"):
        raise ValueError(f"{field_name} must be between 0 and 1")
