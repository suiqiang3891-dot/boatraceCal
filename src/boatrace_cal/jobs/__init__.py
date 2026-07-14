"""Job identity and lifecycle contracts."""

from boatrace_cal.jobs.contracts import JobKey, JobStatus, SnapshotTarget, transition
from boatrace_cal.jobs.snapshot_plan import (
    RaceStart,
    SnapshotDecisionMode,
    SnapshotPlanItem,
    build_prerace_snapshot_plan,
    export_snapshot_plan_json,
    load_race_starts_csv,
    snapshot_plan_to_dict,
)

__all__ = [
    "JobKey",
    "JobStatus",
    "RaceStart",
    "SnapshotDecisionMode",
    "SnapshotPlanItem",
    "SnapshotTarget",
    "build_prerace_snapshot_plan",
    "export_snapshot_plan_json",
    "load_race_starts_csv",
    "snapshot_plan_to_dict",
    "transition",
]
