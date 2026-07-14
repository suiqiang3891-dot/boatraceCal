"""File-backed job ledger for auditable local collection workflows."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path

from boatrace_cal.errors import ErrorCode
from boatrace_cal.domain.races import VenueCode
from boatrace_cal.jobs.contracts import JobKey, JobStatus, SnapshotTarget, transition


@dataclass(frozen=True, slots=True)
class JobLedgerRecord:
    """Persisted current state for one auditable collection job."""

    job_key: JobKey
    status: JobStatus
    attempt_count: int
    updated_at: datetime
    last_error_code: str | None = None
    next_retry_at: datetime | None = None
    checkpoint: str | None = None
    parser_version: str | None = None
    artifact_id: str | None = None

    def __post_init__(self) -> None:
        if type(self.job_key) is not JobKey:
            raise TypeError("job_key must be a JobKey")
        if type(self.status) is not JobStatus:
            raise TypeError("status must be a JobStatus")
        if type(self.attempt_count) is not int or self.attempt_count < 0:
            raise ValueError("attempt_count must be a non-negative integer")
        if type(self.updated_at) is not datetime or _is_naive(self.updated_at):
            raise ValueError("updated_at must be timezone-aware")
        if self.next_retry_at is not None and (
            type(self.next_retry_at) is not datetime or _is_naive(self.next_retry_at)
        ):
            raise ValueError("next_retry_at must be timezone-aware")
        for field_name in (
            "last_error_code",
            "checkpoint",
            "parser_version",
            "artifact_id",
        ):
            value = getattr(self, field_name)
            if value is not None and (type(value) is not str or not value.strip()):
                raise ValueError(f"{field_name} must be a non-blank string")

    def to_dict(self) -> dict[str, object]:
        return {
            "job_key": self.job_key.key,
            "source": self.job_key.source,
            "venue": str(self.job_key.venue),
            "race_date": self.job_key.race_date.isoformat(),
            "race_no": self.job_key.race_no,
            "data_type": self.job_key.data_type,
            "snapshot_target": self.job_key.snapshot_target.value,
            "status": self.status.value,
            "attempt_count": self.attempt_count,
            "updated_at": self.updated_at.isoformat(),
            "last_error_code": self.last_error_code,
            "next_retry_at": None
            if self.next_retry_at is None
            else self.next_retry_at.isoformat(),
            "checkpoint": self.checkpoint,
            "parser_version": self.parser_version,
            "artifact_id": self.artifact_id,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "JobLedgerRecord":
        return cls(
            job_key=parse_job_key(_required_string(payload, "job_key")),
            status=JobStatus(_required_string(payload, "status")),
            attempt_count=_required_int(payload, "attempt_count"),
            updated_at=_parse_aware_datetime(_required_string(payload, "updated_at")),
            last_error_code=_optional_string(payload, "last_error_code"),
            next_retry_at=_optional_datetime(payload, "next_retry_at"),
            checkpoint=_optional_string(payload, "checkpoint"),
            parser_version=_optional_string(payload, "parser_version"),
            artifact_id=_optional_string(payload, "artifact_id"),
        )


class FileJobLedger:
    """Small JSON-file job ledger for local scheduler integration."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    def get(self, job_key: JobKey) -> JobLedgerRecord | None:
        jobs = self._load_jobs()
        payload = jobs.get(job_key.key)
        if payload is None:
            return None
        return JobLedgerRecord.from_dict(payload)

    def list_records(self) -> tuple[JobLedgerRecord, ...]:
        """Return all ledger records sorted by stable job key."""

        jobs = self._load_jobs()
        return tuple(
            JobLedgerRecord.from_dict(payload)
            for _, payload in sorted(jobs.items(), key=lambda item: item[0])
        )

    def record(
        self,
        job_key: JobKey,
        status: JobStatus,
        *,
        updated_at: datetime,
        last_error_code: str | None = None,
        next_retry_at: datetime | None = None,
        checkpoint: str | None = None,
        parser_version: str | None = None,
        artifact_id: str | None = None,
    ) -> JobLedgerRecord:
        if type(job_key) is not JobKey:
            raise TypeError("job_key must be a JobKey")
        if type(status) is not JobStatus:
            raise TypeError("status must be a JobStatus")

        jobs = self._load_jobs()
        current_payload = jobs.get(job_key.key)
        current = (
            None
            if current_payload is None
            else JobLedgerRecord.from_dict(current_payload)
        )
        if current is None:
            if status is not JobStatus.PENDING:
                raise ValueError("new ledger jobs must start as pending")
            attempt_count = 0
            merged = _record_from_parts(
                job_key=job_key,
                status=status,
                attempt_count=attempt_count,
                updated_at=updated_at,
                last_error_code=last_error_code,
                next_retry_at=next_retry_at,
                checkpoint=checkpoint,
                parser_version=parser_version,
                artifact_id=artifact_id,
            )
        else:
            if status is current.status:
                return current
            transition(current.status, status)
            attempt_count = current.attempt_count + (
                1 if status is JobStatus.RUNNING else 0
            )
            merged = _record_from_parts(
                job_key=job_key,
                status=status,
                attempt_count=attempt_count,
                updated_at=updated_at,
                last_error_code=_coalesce(last_error_code, current.last_error_code),
                next_retry_at=_coalesce(next_retry_at, current.next_retry_at),
                checkpoint=_coalesce(checkpoint, current.checkpoint),
                parser_version=_coalesce(parser_version, current.parser_version),
                artifact_id=_coalesce(artifact_id, current.artifact_id),
            )

        jobs[job_key.key] = merged.to_dict()
        self._write_jobs(jobs)
        return merged

    def _load_jobs(self) -> dict[str, dict[str, object]]:
        if not self._path.exists():
            return {}
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("job ledger must be a JSON object")
        if payload.get("schema_version") != "job-ledger-v1":
            raise ValueError("job ledger must use schema_version job-ledger-v1")
        jobs = payload.get("jobs")
        if not isinstance(jobs, dict):
            raise ValueError("job ledger jobs must be an object")
        normalized: dict[str, dict[str, object]] = {}
        for key, value in jobs.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                raise ValueError("job ledger jobs must map keys to objects")
            normalized[key] = dict(value)
        return normalized

    def _write_jobs(self, jobs: dict[str, dict[str, object]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": "job-ledger-v1", "jobs": jobs}
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def parse_job_key(value: str) -> JobKey:
    """Parse the canonical pipe-separated job key string."""

    parts = value.split("|")
    if len(parts) != 6:
        raise ValueError("job key must have 6 pipe-separated parts")
    source, venue, race_date, race_no, data_type, snapshot_target = parts
    return JobKey(
        source=source,
        venue=VenueCode(venue),
        race_date=date.fromisoformat(race_date),
        race_no=None if race_no == "*" else int(race_no),
        data_type=data_type,
        snapshot_target=SnapshotTarget(snapshot_target),
    )


def register_due_jobs(
    ledger: FileJobLedger,
    due_payload: Mapping[str, object],
    *,
    updated_at: datetime,
    checkpoint: str | None = None,
) -> dict[str, object]:
    """Register due jobs as pending without duplicating existing ledger entries."""

    if type(ledger) is not FileJobLedger:
        raise TypeError("ledger must be a FileJobLedger")
    if due_payload.get("schema_version") != "snapshot-job-due-v1":
        raise ValueError("due payload must use schema_version snapshot-job-due-v1")
    raw_jobs = due_payload.get("jobs")
    if not isinstance(raw_jobs, list):
        raise ValueError("due payload jobs must be a list")

    records: list[dict[str, object]] = []
    registered_count = 0
    skipped_existing_count = 0
    for raw_job in raw_jobs:
        if not isinstance(raw_job, dict):
            raise ValueError("due payload jobs must contain objects")
        job_key = parse_job_key(_required_string(raw_job, "job_key"))
        existing = ledger.get(job_key)
        if existing is None:
            record = ledger.record(
                job_key,
                JobStatus.PENDING,
                updated_at=updated_at,
                checkpoint=checkpoint,
            )
            registered_count += 1
        else:
            record = existing
            skipped_existing_count += 1
        records.append(record.to_dict())

    return {
        "schema_version": "job-ledger-register-due-v1",
        "source_schema_version": "snapshot-job-due-v1",
        "registered_count": registered_count,
        "skipped_existing_count": skipped_existing_count,
        "job_count": len(records),
        "jobs": records,
    }


def mark_missed_snapshot_jobs(
    ledger: FileJobLedger,
    plan_payload: Mapping[str, object],
    *,
    now: datetime,
    allowed_lateness_minutes: int,
    checkpoint: str | None = None,
) -> dict[str, object]:
    """Mark expired, unfinished snapshot plan jobs as skipped MISSED_WINDOW."""

    if type(ledger) is not FileJobLedger:
        raise TypeError("ledger must be a FileJobLedger")
    if plan_payload.get("schema_version") != "snapshot-job-plan-v1":
        raise ValueError("plan payload must use schema_version snapshot-job-plan-v1")
    if type(now) is not datetime or _is_naive(now):
        raise ValueError("now must be timezone-aware")
    if type(allowed_lateness_minutes) is not int or allowed_lateness_minutes < 0:
        raise ValueError("allowed_lateness_minutes must be a non-negative integer")
    raw_jobs = plan_payload.get("jobs")
    if not isinstance(raw_jobs, list):
        raise ValueError("plan payload jobs must be a list")

    missed_records: list[dict[str, object]] = []
    skipped_terminal_count = 0
    not_yet_due_count = 0
    for raw_job in raw_jobs:
        if not isinstance(raw_job, dict):
            raise ValueError("plan payload jobs must contain objects")
        scheduled_at = _parse_aware_datetime(_required_string(raw_job, "scheduled_at"))
        if (now - scheduled_at).total_seconds() <= allowed_lateness_minutes * 60:
            not_yet_due_count += 1
            continue

        job_key = parse_job_key(_required_string(raw_job, "job_key"))
        current = ledger.get(job_key)
        if current is not None and current.status in {
            JobStatus.SUCCEEDED,
            JobStatus.FAILED,
            JobStatus.SKIPPED,
        }:
            skipped_terminal_count += 1
            continue

        record = _skip_missed_window(
            ledger,
            job_key,
            current,
            updated_at=now,
            checkpoint=checkpoint,
        )
        missed_records.append(record.to_dict())

    return {
        "schema_version": "job-ledger-missed-windows-v1",
        "source_schema_version": "snapshot-job-plan-v1",
        "missed_count": len(missed_records),
        "skipped_terminal_count": skipped_terminal_count,
        "not_yet_due_count": not_yet_due_count,
        "jobs": missed_records,
    }


def summarize_job_ledger(
    ledger: FileJobLedger,
    *,
    as_of: datetime | None = None,
) -> dict[str, object]:
    """Build a status and retry summary for a local job ledger."""

    if type(ledger) is not FileJobLedger:
        raise TypeError("ledger must be a FileJobLedger")
    if as_of is not None and (type(as_of) is not datetime or _is_naive(as_of)):
        raise ValueError("as_of must be timezone-aware")

    records = ledger.list_records()
    status_counts = {status.value: 0 for status in JobStatus}
    error_counts: dict[str, int] = {}
    retry_due_jobs: list[str] = []
    terminal_count = 0
    for record in records:
        status_counts[record.status.value] += 1
        if record.last_error_code is not None:
            error_counts[record.last_error_code] = (
                error_counts.get(record.last_error_code, 0) + 1
            )
        if record.status in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.SKIPPED}:
            terminal_count += 1
        if (
            as_of is not None
            and record.status is JobStatus.RETRY_WAIT
            and record.next_retry_at is not None
            and record.next_retry_at <= as_of
        ):
            retry_due_jobs.append(record.job_key.key)

    return {
        "schema_version": "job-ledger-summary-v1",
        "as_of": None if as_of is None else as_of.isoformat(),
        "job_count": len(records),
        "status_counts": status_counts,
        "error_counts": dict(sorted(error_counts.items())),
        "terminal_count": terminal_count,
        "retry_due_count": len(retry_due_jobs),
        "retry_due_jobs": retry_due_jobs,
    }


def _record_from_parts(
    *,
    job_key: JobKey,
    status: JobStatus,
    attempt_count: int,
    updated_at: datetime,
    last_error_code: str | None,
    next_retry_at: datetime | None,
    checkpoint: str | None,
    parser_version: str | None,
    artifact_id: str | None,
) -> JobLedgerRecord:
    return JobLedgerRecord(
        job_key=job_key,
        status=status,
        attempt_count=attempt_count,
        updated_at=updated_at,
        last_error_code=_strip_optional(last_error_code),
        next_retry_at=next_retry_at,
        checkpoint=_strip_optional(checkpoint),
        parser_version=_strip_optional(parser_version),
        artifact_id=_strip_optional(artifact_id),
    )


def _skip_missed_window(
    ledger: FileJobLedger,
    job_key: JobKey,
    current: JobLedgerRecord | None,
    *,
    updated_at: datetime,
    checkpoint: str | None,
) -> JobLedgerRecord:
    if current is None:
        ledger.record(job_key, JobStatus.PENDING, updated_at=updated_at, checkpoint=checkpoint)
        current = ledger.get(job_key)
    if current is None:
        raise RuntimeError("ledger failed to create pending record")
    if current.status is JobStatus.PENDING:
        ledger.record(job_key, JobStatus.RUNNING, updated_at=updated_at)
    elif current.status is JobStatus.RETRY_WAIT:
        ledger.record(job_key, JobStatus.RUNNING, updated_at=updated_at)
    return ledger.record(
        job_key,
        JobStatus.SKIPPED,
        updated_at=updated_at,
        last_error_code=ErrorCode.MISSED_WINDOW.value,
        checkpoint=checkpoint,
    )


def _parse_aware_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if _is_naive(parsed):
        raise ValueError("datetime fields must be timezone-aware")
    return parsed


def _is_naive(value: datetime) -> bool:
    return value.tzinfo is None or value.utcoffset() is None


def _coalesce[T](value: T | None, fallback: T | None) -> T | None:
    return fallback if value is None else value


def _strip_optional(value: str | None) -> str | None:
    return None if value is None else value.strip()


def _required_string(payload: dict[str, object], field_name: str) -> str:
    value = payload.get(field_name)
    if type(value) is not str or not value:
        raise ValueError(f"{field_name} must be a string")
    return value


def _optional_string(payload: dict[str, object], field_name: str) -> str | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if type(value) is not str or not value:
        raise ValueError(f"{field_name} must be a string or null")
    return value


def _required_int(payload: dict[str, object], field_name: str) -> int:
    value = payload.get(field_name)
    if type(value) is not int:
        raise ValueError(f"{field_name} must be an integer")
    return value


def _optional_datetime(payload: dict[str, object], field_name: str) -> datetime | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if type(value) is not str:
        raise ValueError(f"{field_name} must be a string or null")
    return _parse_aware_datetime(value)
