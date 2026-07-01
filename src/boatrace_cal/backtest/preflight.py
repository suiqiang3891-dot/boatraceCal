"""Preflight checks that gate historical backtest execution."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from boatrace_cal.domain.bets import BetType
from boatrace_cal.domain.races import RaceId
from boatrace_cal.ingestion.payouts import PayoutRecord
from boatrace_cal.ingestion.results import RaceResultRecord
from boatrace_cal.validation.data_quality import (
    DataQualityIssue,
    HistoricalDataQualityReport,
    build_historical_data_quality_report,
)


class BacktestReadinessStatus(StrEnum):
    """Whether historical inputs are safe to pass into backtest execution."""

    READY = "ready"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class BacktestReadiness:
    """Auditable preflight decision for one backtest input set."""

    status: BacktestReadinessStatus
    refusal_reason: str | None
    blockers: tuple[DataQualityIssue, ...]
    quality_report: HistoricalDataQualityReport

    def __post_init__(self) -> None:
        if type(self.status) is not BacktestReadinessStatus:
            raise TypeError("status must be a BacktestReadinessStatus")
        if self.refusal_reason is not None and type(self.refusal_reason) is not str:
            raise TypeError("refusal_reason must be a string or None")
        if type(self.blockers) is not tuple or any(
            type(blocker) is not DataQualityIssue for blocker in self.blockers
        ):
            raise TypeError("blockers must be a tuple of DataQualityIssue instances")
        if type(self.quality_report) is not HistoricalDataQualityReport:
            raise TypeError("quality_report must be a HistoricalDataQualityReport")
        if self.status is BacktestReadinessStatus.READY:
            if self.refusal_reason is not None:
                raise ValueError("ready preflight decisions must not have a refusal_reason")
            if self.blockers:
                raise ValueError("ready preflight decisions must not have blockers")
        if self.status is BacktestReadinessStatus.BLOCKED:
            if self.refusal_reason is None or not self.refusal_reason.strip():
                raise ValueError("blocked preflight decisions require a refusal_reason")
            if not self.blockers:
                raise ValueError("blocked preflight decisions require blockers")

    @property
    def ready(self) -> bool:
        return self.status is BacktestReadinessStatus.READY

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)


def check_backtest_inputs_ready(
    *,
    results: Iterable[RaceResultRecord],
    payouts: Iterable[PayoutRecord],
    expected_races: Iterable[RaceId],
    bet_types: Iterable[BetType],
) -> BacktestReadiness:
    """Return the preflight decision for historical backtest inputs."""

    quality_report = build_historical_data_quality_report(
        results=results,
        payouts=payouts,
        expected_races=expected_races,
        bet_types=bet_types,
    )
    if quality_report.issues:
        return BacktestReadiness(
            status=BacktestReadinessStatus.BLOCKED,
            refusal_reason="historical_data_quality_issues",
            blockers=quality_report.issues,
            quality_report=quality_report,
        )
    return BacktestReadiness(
        status=BacktestReadinessStatus.READY,
        refusal_reason=None,
        blockers=(),
        quality_report=quality_report,
    )
