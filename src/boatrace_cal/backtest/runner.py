"""Minimal orchestration for historical paper backtest reports."""

from collections.abc import Iterable
from dataclasses import dataclass

from boatrace_cal.backtest.equity import EquityCurve, build_equity_curve
from boatrace_cal.backtest.preflight import (
    BacktestReadiness,
    check_backtest_inputs_ready,
)
from boatrace_cal.backtest.settlement import (
    BacktestSettlementRow,
    settle_selected_recommendations,
)
from boatrace_cal.backtest.summary import BacktestSummary, summarize_backtest_settlements
from boatrace_cal.domain.bets import BetType
from boatrace_cal.domain.races import RaceId
from boatrace_cal.domain.recommendations import Recommendation
from boatrace_cal.ingestion.payouts import PayoutRecord
from boatrace_cal.ingestion.results import RaceResultRecord


@dataclass(frozen=True, slots=True)
class BacktestReport:
    """Auditable output from one historical paper backtest run."""

    readiness: BacktestReadiness
    settlements: tuple[BacktestSettlementRow, ...] | None
    summary: BacktestSummary | None
    equity_curve: EquityCurve | None

    def __post_init__(self) -> None:
        if type(self.readiness) is not BacktestReadiness:
            raise TypeError("readiness must be a BacktestReadiness")
        if self.settlements is not None and (
            type(self.settlements) is not tuple
            or any(type(row) is not BacktestSettlementRow for row in self.settlements)
        ):
            raise TypeError("settlements must be a tuple of BacktestSettlementRow instances or None")
        if self.summary is not None and type(self.summary) is not BacktestSummary:
            raise TypeError("summary must be a BacktestSummary or None")
        if self.equity_curve is not None and type(self.equity_curve) is not EquityCurve:
            raise TypeError("equity_curve must be an EquityCurve or None")
        if not self.readiness.ready:
            if self.settlements is not None or self.summary is not None or self.equity_curve is not None:
                raise ValueError("blocked reports must not include executed backtest outputs")
        elif self.settlements is None or self.summary is None or self.equity_curve is None:
            raise ValueError("ready reports must include settlements, summary, and equity_curve")


def run_backtest(
    *,
    recommendations: Iterable[Recommendation],
    results: Iterable[RaceResultRecord],
    payouts: Iterable[PayoutRecord],
    expected_races: Iterable[RaceId],
    bet_types: Iterable[BetType],
) -> BacktestReport:
    """Run the minimal historical paper backtest pipeline when inputs pass preflight."""

    normalized_recommendations = tuple(recommendations)
    normalized_results = tuple(results)
    normalized_payouts = tuple(payouts)
    normalized_expected_races = tuple(expected_races)
    normalized_bet_types = tuple(bet_types)

    readiness = check_backtest_inputs_ready(
        results=normalized_results,
        payouts=normalized_payouts,
        expected_races=normalized_expected_races,
        bet_types=normalized_bet_types,
    )
    if not readiness.ready:
        return BacktestReport(
            readiness=readiness,
            settlements=None,
            summary=None,
            equity_curve=None,
        )

    settlements = settle_selected_recommendations(
        recommendations=normalized_recommendations,
        results=normalized_results,
        payouts=normalized_payouts,
    )
    return BacktestReport(
        readiness=readiness,
        settlements=settlements,
        summary=summarize_backtest_settlements(
            rows=settlements,
            expected_race_count=len(normalized_expected_races),
        ),
        equity_curve=build_equity_curve(rows=settlements),
    )
