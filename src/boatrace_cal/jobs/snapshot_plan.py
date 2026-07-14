"""Build auditable pre-race snapshot job plans from race start times."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
import json
from pathlib import Path
from typing import Any

from boatrace_cal.domain.races import VenueCode
from boatrace_cal.jobs.contracts import JobKey, SnapshotTarget


class SnapshotDecisionMode(StrEnum):
    """How a snapshot may affect the analyst-facing decision workflow."""

    REFRESH = "refresh"
    FREEZE_FINAL_DECISION = "freeze_final_decision"
    CHANGE_ALERT_ONLY = "change_alert_only"


_PRERACE_TARGETS: tuple[tuple[SnapshotTarget, int, SnapshotDecisionMode], ...] = (
    (SnapshotTarget.T30, 30, SnapshotDecisionMode.REFRESH),
    (SnapshotTarget.T15, 15, SnapshotDecisionMode.REFRESH),
    (SnapshotTarget.T10, 10, SnapshotDecisionMode.FREEZE_FINAL_DECISION),
    (SnapshotTarget.T05, 5, SnapshotDecisionMode.CHANGE_ALERT_ONLY),
)
_RACE_START_COLUMNS = ("race_date", "venue", "race_no", "starts_at")


@dataclass(frozen=True, slots=True)
class RaceStart:
    """Start time for one race in the race-day calendar."""

    race_date: date
    venue: VenueCode
    race_no: int
    starts_at: datetime

    def __post_init__(self) -> None:
        if type(self.race_date) is not date:
            raise TypeError("race_date must be a date, not a datetime")
        if type(self.venue) is not VenueCode:
            raise TypeError("venue must be a VenueCode")
        if type(self.race_no) is not int:
            raise TypeError("race_no must be an integer")
        if type(self.starts_at) is not datetime:
            raise TypeError("starts_at must be a datetime")
        if not 1 <= self.race_no <= 12:
            raise ValueError("race_no must be between 1 and 12")
        if self.starts_at.tzinfo is None or self.starts_at.utcoffset() is None:
            raise ValueError("starts_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class SnapshotPlanItem:
    """One scheduled pre-race snapshot job."""

    job_key: JobKey
    scheduled_at: datetime
    starts_at: datetime
    minutes_before_start: int
    decision_mode: SnapshotDecisionMode

    @property
    def snapshot_target(self) -> SnapshotTarget:
        return self.job_key.snapshot_target

    def to_dict(self) -> dict[str, object]:
        return {
            "job_key": self.job_key.key,
            "source": self.job_key.source,
            "venue": str(self.job_key.venue),
            "race_date": self.job_key.race_date.isoformat(),
            "race_no": self.job_key.race_no,
            "data_type": self.job_key.data_type,
            "snapshot_target": self.job_key.snapshot_target.value,
            "scheduled_at": self.scheduled_at.isoformat(),
            "starts_at": self.starts_at.isoformat(),
            "minutes_before_start": self.minutes_before_start,
            "decision_mode": self.decision_mode.value,
        }


def build_prerace_snapshot_plan(
    race_starts: Iterable[RaceStart],
    *,
    source: str,
    data_type: str = "odds",
) -> tuple[SnapshotPlanItem, ...]:
    """Return T-30/T-15/T-10/T-5 snapshot jobs for each race start."""

    plan: list[SnapshotPlanItem] = []
    for race_start in sorted(race_starts, key=_race_start_sort_key):
        for target, minutes_before_start, decision_mode in _PRERACE_TARGETS:
            plan.append(
                SnapshotPlanItem(
                    job_key=JobKey(
                        source=source,
                        venue=race_start.venue,
                        race_date=race_start.race_date,
                        race_no=race_start.race_no,
                        data_type=data_type,
                        snapshot_target=target,
                    ),
                    scheduled_at=race_start.starts_at
                    - timedelta(minutes=minutes_before_start),
                    starts_at=race_start.starts_at,
                    minutes_before_start=minutes_before_start,
                    decision_mode=decision_mode,
                )
            )
    return tuple(plan)


def snapshot_plan_to_dict(items: Iterable[SnapshotPlanItem]) -> dict[str, Any]:
    """Serialize a snapshot plan to a deterministic JSON-ready payload."""

    jobs = [item.to_dict() for item in items]
    return {
        "schema_version": "snapshot-job-plan-v1",
        "job_count": len(jobs),
        "jobs": jobs,
    }


def select_due_snapshot_jobs(
    plan_payload: Mapping[str, Any],
    *,
    now: datetime,
    lookahead: timedelta,
    past_tolerance: timedelta = timedelta(0),
) -> dict[str, Any]:
    """Return plan jobs scheduled inside the explicit execution window."""

    if plan_payload.get("schema_version") != "snapshot-job-plan-v1":
        raise ValueError("snapshot plan must use schema_version snapshot-job-plan-v1")
    if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if lookahead < timedelta(0):
        raise ValueError("lookahead must not be negative")
    if past_tolerance < timedelta(0):
        raise ValueError("past_tolerance must not be negative")

    window_start = now - past_tolerance
    window_end = now + lookahead
    jobs = tuple(_due_jobs(plan_payload.get("jobs"), window_start, window_end))
    return {
        "schema_version": "snapshot-job-due-v1",
        "source_schema_version": "snapshot-job-plan-v1",
        "now": now.isoformat(),
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "job_count": len(jobs),
        "jobs": jobs,
    }


def export_snapshot_plan_json(items: Iterable[SnapshotPlanItem], output_path: Path) -> None:
    """Write the snapshot plan as newline-terminated UTF-8 JSON."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(snapshot_plan_to_dict(items), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def load_race_starts_csv(path: Path) -> tuple[RaceStart, ...]:
    """Load race start times from a strict CSV contract."""

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != _RACE_START_COLUMNS:
            raise ValueError(
                "race starts CSV columns must be: " + ",".join(_RACE_START_COLUMNS)
            )
        return tuple(_race_start_from_row(row) for row in reader)


def _race_start_from_row(row: dict[str, str]) -> RaceStart:
    return RaceStart(
        race_date=date.fromisoformat(row["race_date"]),
        venue=VenueCode(row["venue"]),
        race_no=int(row["race_no"]),
        starts_at=_parse_aware_datetime(row["starts_at"], "starts_at"),
    )


def _parse_aware_datetime(value: str, field_name: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return parsed


def _due_jobs(
    raw_jobs: object,
    window_start: datetime,
    window_end: datetime,
) -> tuple[dict[str, Any], ...]:
    if not isinstance(raw_jobs, list):
        raise ValueError("snapshot plan jobs must be a list")
    jobs: list[dict[str, Any]] = []
    for raw_job in raw_jobs:
        if not isinstance(raw_job, dict):
            raise ValueError("snapshot plan jobs must contain objects")
        scheduled_at = _parse_aware_datetime(str(raw_job.get("scheduled_at")), "scheduled_at")
        if window_start <= scheduled_at <= window_end:
            jobs.append(dict(raw_job))
    return tuple(sorted(jobs, key=lambda job: str(job["scheduled_at"])))


def _race_start_sort_key(race_start: RaceStart) -> tuple[datetime, date, str, int]:
    return (
        race_start.starts_at,
        race_start.race_date,
        race_start.venue.value,
        race_start.race_no,
    )
