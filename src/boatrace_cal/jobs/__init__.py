"""Job identity and lifecycle contracts."""

from boatrace_cal.jobs.contracts import JobKey, JobStatus, SnapshotTarget, transition
from boatrace_cal.jobs.ledger import FileJobLedger, JobLedgerRecord, parse_job_key
from boatrace_cal.jobs.snapshot_plan import (
    RaceStart,
    SnapshotDecisionMode,
    SnapshotPlanItem,
    build_prerace_snapshot_plan,
    export_snapshot_plan_json,
    load_race_starts_csv,
    select_due_snapshot_jobs,
    snapshot_plan_to_dict,
)

__all__ = [
    "FileJobLedger",
    "JobKey",
    "JobLedgerRecord",
    "JobStatus",
    "RaceStart",
    "SnapshotDecisionMode",
    "SnapshotPlanItem",
    "SnapshotTarget",
    "build_prerace_snapshot_plan",
    "export_snapshot_plan_json",
    "load_race_starts_csv",
    "parse_job_key",
    "select_due_snapshot_jobs",
    "snapshot_plan_to_dict",
    "transition",
]
