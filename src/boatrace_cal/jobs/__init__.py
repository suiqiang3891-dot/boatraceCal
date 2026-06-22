"""Job identity and lifecycle contracts."""

from boatrace_cal.jobs.contracts import JobKey, JobStatus, SnapshotTarget, transition

__all__ = ["JobKey", "JobStatus", "SnapshotTarget", "transition"]
