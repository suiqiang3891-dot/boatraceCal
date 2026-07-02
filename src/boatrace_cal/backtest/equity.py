"""Equity curve and drawdown metrics for settled backtest rows."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from boatrace_cal.backtest.settlement import BacktestSettlementRow
from boatrace_cal.domain.races import RaceId


@dataclass(frozen=True, slots=True)
class EquityCurvePoint:
    """One cumulative equity point after a settled paper bet."""

    race_id: RaceId
    recommendation_id: str
    equity_yen: Decimal
    peak_equity_yen: Decimal
    drawdown_yen: Decimal
    drawdown_rate: Decimal

    def __post_init__(self) -> None:
        if type(self.race_id) is not RaceId:
            raise TypeError("race_id must be a RaceId")
        if type(self.recommendation_id) is not str or not self.recommendation_id.strip():
            raise TypeError("recommendation_id must be a non-empty string")
        object.__setattr__(self, "recommendation_id", self.recommendation_id.strip())
        for field_name in (
            "equity_yen",
            "peak_equity_yen",
            "drawdown_yen",
            "drawdown_rate",
        ):
            value = getattr(self, field_name)
            if type(value) is not Decimal or not value.is_finite():
                raise TypeError(f"{field_name} must be a finite Decimal")
        if self.drawdown_yen < Decimal("0"):
            raise ValueError("drawdown_yen must not be negative")
        if not Decimal("0") <= self.drawdown_rate <= Decimal("1"):
            raise ValueError("drawdown_rate must be between 0 and 1")
        if self.peak_equity_yen < self.equity_yen:
            raise ValueError("peak_equity_yen must not be below equity_yen")
        if self.drawdown_yen != self.peak_equity_yen - self.equity_yen:
            raise ValueError("drawdown_yen must equal peak_equity_yen minus equity_yen")


@dataclass(frozen=True, slots=True)
class EquityCurve:
    """Cumulative equity curve and maximum drawdown summary."""

    points: tuple[EquityCurvePoint, ...]
    final_equity_yen: Decimal
    max_drawdown_yen: Decimal
    max_drawdown_rate: Decimal

    def __post_init__(self) -> None:
        if type(self.points) is not tuple or any(
            type(point) is not EquityCurvePoint for point in self.points
        ):
            raise TypeError("points must be a tuple of EquityCurvePoint instances")
        for field_name in ("final_equity_yen", "max_drawdown_yen", "max_drawdown_rate"):
            value = getattr(self, field_name)
            if type(value) is not Decimal or not value.is_finite():
                raise TypeError(f"{field_name} must be a finite Decimal")
        if self.max_drawdown_yen < Decimal("0"):
            raise ValueError("max_drawdown_yen must not be negative")
        if not Decimal("0") <= self.max_drawdown_rate <= Decimal("1"):
            raise ValueError("max_drawdown_rate must be between 0 and 1")
        if self.points and self.final_equity_yen != self.points[-1].equity_yen:
            raise ValueError("final_equity_yen must match the last curve point")
        if not self.points and self.final_equity_yen != Decimal("0"):
            raise ValueError("empty curves must have zero final equity")


def build_equity_curve(*, rows: Iterable[BacktestSettlementRow]) -> EquityCurve:
    """Build a deterministic cumulative equity curve from settled rows."""

    ordered_rows = _sort_rows(_normalize_rows(rows))
    equity = Decimal("0")
    peak = Decimal("0")
    points: list[EquityCurvePoint] = []

    for row in ordered_rows:
        equity += row.net_profit_yen
        peak = max(peak, equity)
        drawdown = peak - equity
        points.append(
            EquityCurvePoint(
                race_id=row.race_id,
                recommendation_id=row.recommendation_id,
                equity_yen=equity,
                peak_equity_yen=peak,
                drawdown_yen=drawdown,
                drawdown_rate=_safe_drawdown_rate(drawdown, peak),
            )
        )

    max_drawdown_yen = max((point.drawdown_yen for point in points), default=Decimal("0"))
    max_drawdown_rate = max((point.drawdown_rate for point in points), default=Decimal("0"))
    return EquityCurve(
        points=tuple(points),
        final_equity_yen=points[-1].equity_yen if points else Decimal("0"),
        max_drawdown_yen=max_drawdown_yen,
        max_drawdown_rate=max_drawdown_rate,
    )


def _normalize_rows(
    rows: Iterable[BacktestSettlementRow],
) -> tuple[BacktestSettlementRow, ...]:
    normalized = tuple(rows)
    if any(type(row) is not BacktestSettlementRow for row in normalized):
        raise TypeError("rows must contain only BacktestSettlementRow instances")
    return normalized


def _sort_rows(rows: tuple[BacktestSettlementRow, ...]) -> tuple[BacktestSettlementRow, ...]:
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                row.race_id.race_date,
                row.race_id.venue.value,
                row.race_id.race_no,
                row.recommendation_id,
            ),
        )
    )


def _safe_drawdown_rate(drawdown_yen: Decimal, peak_equity_yen: Decimal) -> Decimal:
    if peak_equity_yen <= Decimal("0"):
        return Decimal("0")
    return drawdown_yen / peak_equity_yen
