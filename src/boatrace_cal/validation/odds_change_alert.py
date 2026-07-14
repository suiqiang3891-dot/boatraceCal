"""Alert-only reports for odds changes after the frozen decision point."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId
from boatrace_cal.ingestion.odds import OddsSnapshotRecord, latest_odds_by_combination


class OddsChangeAlertCode(StrEnum):
    """Alert categories emitted after the frozen decision point."""

    ODDS_CHANGED = "odds_changed"
    ODDS_NEWLY_AVAILABLE = "odds_newly_available"


@dataclass(frozen=True, slots=True)
class OddsChangeAlert:
    """One combination that needs review but must not overwrite the frozen decision."""

    code: OddsChangeAlertCode
    combination: BetCombination
    baseline: OddsSnapshotRecord | None
    comparison: OddsSnapshotRecord
    absolute_change: Decimal | None
    relative_change: Decimal | None


@dataclass(frozen=True, slots=True)
class OddsChangeAlertReport:
    """Alert-only comparison between frozen and near-start odds snapshots."""

    race_id: RaceId
    bet_type: BetType
    frozen_as_of: datetime
    alert_as_of: datetime
    min_relative_change: Decimal
    alerts: tuple[OddsChangeAlert, ...]

    @property
    def alert_count(self) -> int:
        return len(self.alerts)


def build_odds_change_alert_report(
    *,
    records: Iterable[OddsSnapshotRecord],
    race_id: RaceId,
    bet_type: BetType,
    frozen_as_of: datetime,
    alert_as_of: datetime,
    min_relative_change: Decimal,
) -> OddsChangeAlertReport:
    """Compare frozen-time odds with alert-time odds and emit review-only alerts."""

    _validate_inputs(race_id, bet_type, frozen_as_of, alert_as_of, min_relative_change)
    frozen_records = _latest_for_bet_type(records, race_id, bet_type, frozen_as_of)
    alert_records = _latest_for_bet_type(records, race_id, bet_type, alert_as_of)
    alerts: list[OddsChangeAlert] = []

    for combination, comparison in alert_records.items():
        baseline = frozen_records.get(combination)
        if baseline is None:
            alerts.append(
                OddsChangeAlert(
                    code=OddsChangeAlertCode.ODDS_NEWLY_AVAILABLE,
                    combination=combination,
                    baseline=None,
                    comparison=comparison,
                    absolute_change=None,
                    relative_change=None,
                )
            )
            continue

        if baseline.snapshot_key == comparison.snapshot_key:
            continue
        absolute_change = comparison.odds - baseline.odds
        relative_change = absolute_change / baseline.odds
        if abs(relative_change) < min_relative_change:
            continue
        alerts.append(
            OddsChangeAlert(
                code=OddsChangeAlertCode.ODDS_CHANGED,
                combination=combination,
                baseline=baseline,
                comparison=comparison,
                absolute_change=absolute_change,
                relative_change=relative_change,
            )
        )

    return OddsChangeAlertReport(
        race_id=race_id,
        bet_type=bet_type,
        frozen_as_of=frozen_as_of,
        alert_as_of=alert_as_of,
        min_relative_change=min_relative_change,
        alerts=tuple(sorted(alerts, key=lambda alert: alert.combination.key)),
    )


def odds_change_alert_report_to_dict(
    report: OddsChangeAlertReport,
) -> dict[str, Any]:
    """Serialize an alert-only odds change report to JSON-ready data."""

    if type(report) is not OddsChangeAlertReport:
        raise TypeError("report must be an OddsChangeAlertReport")
    return {
        "schema_version": "odds-change-alert-v1",
        "race_id": str(report.race_id),
        "bet_type": report.bet_type.value,
        "frozen_as_of": report.frozen_as_of.isoformat(),
        "alert_as_of": report.alert_as_of.isoformat(),
        "min_relative_change": str(report.min_relative_change),
        "alert_only": True,
        "action": "review_required_no_overwrite",
        "alert_count": report.alert_count,
        "alerts": [_alert_to_dict(alert) for alert in report.alerts],
    }


def _latest_for_bet_type(
    records: Iterable[OddsSnapshotRecord],
    race_id: RaceId,
    bet_type: BetType,
    as_of: datetime,
) -> dict[BetCombination, OddsSnapshotRecord]:
    return {
        combination: record
        for combination, record in latest_odds_by_combination(records, race_id, as_of).items()
        if combination.bet_type is bet_type
    }


def _alert_to_dict(alert: OddsChangeAlert) -> dict[str, Any]:
    baseline = alert.baseline
    comparison = alert.comparison
    return {
        "code": alert.code.value,
        "combination": alert.combination.key,
        "baseline_odds": None if baseline is None else str(baseline.odds),
        "comparison_odds": str(comparison.odds),
        "absolute_change": _optional_decimal(alert.absolute_change),
        "relative_change": _optional_relative_change(alert.relative_change),
        "baseline_available_at": None
        if baseline is None
        else baseline.available_at.isoformat(),
        "comparison_available_at": comparison.available_at.isoformat(),
    }


def _optional_decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _optional_relative_change(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value.quantize(Decimal("0.01")))


def _validate_inputs(
    race_id: RaceId,
    bet_type: BetType,
    frozen_as_of: datetime,
    alert_as_of: datetime,
    min_relative_change: Decimal,
) -> None:
    if type(race_id) is not RaceId:
        raise TypeError("race_id must be a RaceId")
    if type(bet_type) is not BetType:
        raise TypeError("bet_type must be a BetType")
    if type(frozen_as_of) is not datetime or _is_naive(frozen_as_of):
        raise ValueError("frozen_as_of must be timezone-aware")
    if type(alert_as_of) is not datetime or _is_naive(alert_as_of):
        raise ValueError("alert_as_of must be timezone-aware")
    if alert_as_of <= frozen_as_of:
        raise ValueError("alert_as_of must be after frozen_as_of")
    if type(min_relative_change) is not Decimal or min_relative_change < Decimal("0"):
        raise ValueError("min_relative_change must be a non-negative Decimal")


def _is_naive(value: datetime) -> bool:
    return value.tzinfo is None or value.utcoffset() is None
