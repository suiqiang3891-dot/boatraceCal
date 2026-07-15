"""Confidence intervals for settled paper backtest metrics."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from random import Random

from boatrace_cal.backtest.settlement import BacktestSettlementRow
from boatrace_cal.settlement import SettlementStatus


DEFAULT_CONFIDENCE_LEVEL = Decimal("0.95")
DEFAULT_BOOTSTRAP_ITERATIONS = 1000
DEFAULT_BOOTSTRAP_SEED = 20250101

_SCHEMA_VERSION = "backtest-confidence-intervals-v1"
_METHOD = "bootstrap_percentile"
_METRIC_NAMES = {"net_profit_yen", "return_rate", "hit_rate"}


@dataclass(frozen=True, slots=True)
class BacktestMetricInterval:
    """Percentile interval for one aggregate backtest metric."""

    name: str
    point_estimate: Decimal
    lower: Decimal
    upper: Decimal

    def __post_init__(self) -> None:
        if self.name not in _METRIC_NAMES:
            raise ValueError("metric name must be a supported backtest metric")
        for field_name in ("point_estimate", "lower", "upper"):
            value = getattr(self, field_name)
            if type(value) is not Decimal or not value.is_finite():
                raise TypeError(f"{field_name} must be a finite Decimal")
        if self.lower > self.upper:
            raise ValueError("lower must not exceed upper")


@dataclass(frozen=True, slots=True)
class BacktestConfidenceIntervals:
    """Auditable bootstrap interval set for a backtest report."""

    schema_version: str
    method: str
    confidence_level: Decimal
    iterations: int
    seed: int
    sample_size: int
    metrics: tuple[BacktestMetricInterval, ...]

    def __post_init__(self) -> None:
        if self.schema_version != _SCHEMA_VERSION:
            raise ValueError("schema_version must be backtest-confidence-intervals-v1")
        if self.method != _METHOD:
            raise ValueError("method must be bootstrap_percentile")
        _validate_confidence_level(self.confidence_level)
        _validate_iterations(self.iterations)
        if type(self.seed) is not int:
            raise TypeError("seed must be an integer")
        if type(self.sample_size) is not int or self.sample_size < 0:
            raise ValueError("sample_size must be a non-negative integer")
        if type(self.metrics) is not tuple or any(
            type(metric) is not BacktestMetricInterval for metric in self.metrics
        ):
            raise TypeError("metrics must be a tuple of BacktestMetricInterval instances")
        if tuple(metric.name for metric in self.metrics) != (
            "net_profit_yen",
            "return_rate",
            "hit_rate",
        ):
            raise ValueError("metrics must be ordered as net_profit_yen, return_rate, hit_rate")


def build_backtest_confidence_intervals(
    *,
    rows: Iterable[BacktestSettlementRow],
    confidence_level: Decimal = DEFAULT_CONFIDENCE_LEVEL,
    iterations: int = DEFAULT_BOOTSTRAP_ITERATIONS,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> BacktestConfidenceIntervals:
    """Build deterministic bootstrap percentile intervals from settled paper bets."""

    normalized_rows = _normalize_rows(rows)
    _validate_confidence_level(confidence_level)
    _validate_iterations(iterations)
    if type(seed) is not int:
        raise TypeError("seed must be an integer")

    point_estimates = _metric_values(normalized_rows)
    samples = _bootstrap_metric_values(rows=normalized_rows, iterations=iterations, seed=seed)
    tail_probability = (Decimal("1") - confidence_level) / Decimal("2")
    lower_index = _percentile_index(iterations, tail_probability)
    upper_index = _percentile_index(iterations, Decimal("1") - tail_probability)

    metrics = tuple(
        BacktestMetricInterval(
            name=name,
            point_estimate=point_estimates[name],
            lower=sorted(values)[lower_index],
            upper=sorted(values)[upper_index],
        )
        for name, values in samples.items()
    )
    return BacktestConfidenceIntervals(
        schema_version=_SCHEMA_VERSION,
        method=_METHOD,
        confidence_level=confidence_level,
        iterations=iterations,
        seed=seed,
        sample_size=len(normalized_rows),
        metrics=metrics,
    )


def _bootstrap_metric_values(
    *,
    rows: tuple[BacktestSettlementRow, ...],
    iterations: int,
    seed: int,
) -> dict[str, list[Decimal]]:
    samples: dict[str, list[Decimal]] = {
        "net_profit_yen": [],
        "return_rate": [],
        "hit_rate": [],
    }
    if not rows:
        for _ in range(iterations):
            for values in samples.values():
                values.append(Decimal("0"))
        return samples

    random = Random(seed)
    sample_size = len(rows)
    for _ in range(iterations):
        sample = tuple(rows[random.randrange(sample_size)] for _ in range(sample_size))
        sample_metrics = _metric_values(sample)
        for name, value in sample_metrics.items():
            samples[name].append(value)
    return samples


def _metric_values(rows: tuple[BacktestSettlementRow, ...]) -> dict[str, Decimal]:
    total_stake_yen = sum((row.stake_yen for row in rows), start=Decimal("0"))
    total_returned_yen = sum((row.returned_yen for row in rows), start=Decimal("0"))
    hit_count = sum(1 for row in rows if row.settlement.status is SettlementStatus.HIT)
    selected_bet_count = len(rows)
    return {
        "net_profit_yen": total_returned_yen - total_stake_yen,
        "return_rate": _safe_divide(total_returned_yen, total_stake_yen),
        "hit_rate": _safe_divide(Decimal(hit_count), Decimal(selected_bet_count)),
    }


def _normalize_rows(rows: Iterable[BacktestSettlementRow]) -> tuple[BacktestSettlementRow, ...]:
    normalized = tuple(rows)
    if any(type(row) is not BacktestSettlementRow for row in normalized):
        raise TypeError("rows must contain only BacktestSettlementRow instances")
    return normalized


def _percentile_index(count: int, probability: Decimal) -> int:
    raw_index = probability * Decimal(count - 1)
    return int(raw_index.to_integral_value(rounding="ROUND_HALF_UP"))


def _validate_confidence_level(confidence_level: Decimal) -> None:
    if type(confidence_level) is not Decimal or not confidence_level.is_finite():
        raise TypeError("confidence_level must be a finite Decimal")
    if not Decimal("0") < confidence_level < Decimal("1"):
        raise ValueError("confidence_level must be between 0 and 1")


def _validate_iterations(iterations: int) -> None:
    if type(iterations) is not int or iterations <= 0:
        raise ValueError("iterations must be a positive integer")


def _safe_divide(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == Decimal("0"):
        return Decimal("0")
    return numerator / denominator
