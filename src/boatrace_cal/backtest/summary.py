"""Aggregate metrics for settled paper backtest rows."""

from collections.abc import Callable, Iterable
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


@dataclass(frozen=True, slots=True)
class BacktestSlice:
    """UI-ready aggregate metrics for one settled backtest segment."""

    dimension: str
    key: str
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

    def __post_init__(self) -> None:
        if self.dimension not in {"venue", "bet_type", "race_month", "odds_band"}:
            raise ValueError("dimension must be venue, bet_type, race_month, or odds_band")
        if type(self.key) is not str or not self.key:
            raise ValueError("key must be a non-empty string")
        for field_name in (
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
        ):
            value = getattr(self, field_name)
            if type(value) is not Decimal or not value.is_finite():
                raise TypeError(f"{field_name} must be a finite Decimal")
        if self.hit_count + self.miss_count + self.payout_missing_count != self.selected_bet_count:
            raise ValueError("settlement status counts must match selected_bet_count")
        if self.total_stake_yen < Decimal("0"):
            raise ValueError("total_stake_yen must not be negative")
        if self.total_returned_yen < Decimal("0"):
            raise ValueError("total_returned_yen must not be negative")
        if self.net_profit_yen != self.total_returned_yen - self.total_stake_yen:
            raise ValueError("net_profit_yen must equal total_returned_yen minus total_stake_yen")
        _validate_unit_rate(self.hit_rate, "hit_rate")
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


def build_backtest_slices(*, rows: Iterable[BacktestSettlementRow]) -> tuple[BacktestSlice, ...]:
    """Build stable venue and bet-type slices for report tables."""

    normalized_rows = _normalize_rows(rows)
    return _build_dimension_slices(
        rows=normalized_rows,
        dimension="venue",
        key_for_row=lambda row: row.race_id.venue.value,
    ) + _build_dimension_slices(
        rows=normalized_rows,
        dimension="bet_type",
        key_for_row=lambda row: row.settlement.combination.bet_type.value,
    ) + _build_dimension_slices(
        rows=normalized_rows,
        dimension="race_month",
        key_for_row=lambda row: f"{row.race_id.race_date:%Y-%m}",
    ) + _build_dimension_slices(
        rows=normalized_rows,
        dimension="odds_band",
        key_for_row=_odds_band_key,
    )


def _normalize_rows(
    rows: Iterable[BacktestSettlementRow],
) -> tuple[BacktestSettlementRow, ...]:
    normalized = tuple(rows)
    if any(type(row) is not BacktestSettlementRow for row in normalized):
        raise TypeError("rows must contain only BacktestSettlementRow instances")
    return normalized


def _build_dimension_slices(
    *,
    rows: tuple[BacktestSettlementRow, ...],
    dimension: str,
    key_for_row: Callable[[BacktestSettlementRow], str],
) -> tuple[BacktestSlice, ...]:
    grouped: dict[str, list[BacktestSettlementRow]] = {}
    for row in rows:
        key = key_for_row(row)
        if type(key) is not str or not key:
            raise ValueError("slice key must be a non-empty string")
        grouped.setdefault(key, []).append(row)
    return tuple(
        _build_slice(dimension=dimension, key=key, rows=tuple(grouped[key]))
        for key in sorted(grouped)
    )


def _build_slice(
    *,
    dimension: str,
    key: str,
    rows: tuple[BacktestSettlementRow, ...],
) -> BacktestSlice:
    hit_count = sum(1 for row in rows if row.settlement.status is SettlementStatus.HIT)
    miss_count = sum(1 for row in rows if row.settlement.status is SettlementStatus.MISS)
    payout_missing_count = sum(
        1 for row in rows if row.settlement.status is SettlementStatus.PAYOUT_MISSING
    )
    total_stake_yen = sum((row.stake_yen for row in rows), start=Decimal("0"))
    total_returned_yen = sum((row.returned_yen for row in rows), start=Decimal("0"))
    selected_bet_count = len(rows)
    return BacktestSlice(
        dimension=dimension,
        key=key,
        selected_bet_count=selected_bet_count,
        selected_race_count=len({row.race_id for row in rows}),
        hit_count=hit_count,
        miss_count=miss_count,
        payout_missing_count=payout_missing_count,
        total_stake_yen=total_stake_yen,
        total_returned_yen=total_returned_yen,
        net_profit_yen=total_returned_yen - total_stake_yen,
        return_rate=_safe_divide(total_returned_yen, total_stake_yen),
        hit_rate=_safe_divide(Decimal(hit_count), Decimal(selected_bet_count)),
    )


def _odds_band_key(row: BacktestSettlementRow) -> str:
    odds = row.recommendation.odds
    if odds is None:
        return "odds_missing"
    if odds < Decimal("3"):
        return "odds_lt_3"
    if odds < Decimal("10"):
        return "odds_3_to_10"
    return "odds_10_plus"


def _safe_divide(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == Decimal("0"):
        return Decimal("0")
    return numerator / denominator


def _validate_unit_rate(value: Decimal, field_name: str) -> None:
    if not Decimal("0") <= value <= Decimal("1"):
        raise ValueError(f"{field_name} must be between 0 and 1")
