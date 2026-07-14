from datetime import date, datetime, timezone

import pytest

from boatrace_cal.domain.races import VenueCode
from boatrace_cal.jobs.contracts import JobKey, JobStatus, SnapshotTarget
from boatrace_cal.jobs.ledger import (
    FileJobLedger,
    mark_missed_snapshot_jobs,
    parse_job_key,
    register_due_jobs,
    summarize_job_ledger,
)


def test_file_job_ledger_records_auditable_lifecycle_metadata(tmp_path) -> None:
    ledger = FileJobLedger(tmp_path / "jobs.json")
    job_key = JobKey(
        source="official",
        venue=VenueCode("05"),
        race_date=date(2026, 6, 23),
        race_no=1,
        data_type="odds",
        snapshot_target=SnapshotTarget.T15,
    )

    pending = ledger.record(
        job_key,
        JobStatus.PENDING,
        updated_at=datetime(2026, 6, 23, 4, 14, tzinfo=timezone.utc),
        checkpoint="snapshot-plan-20260623",
    )
    running = ledger.record(
        job_key,
        JobStatus.RUNNING,
        updated_at=datetime(2026, 6, 23, 4, 15, tzinfo=timezone.utc),
        parser_version="odds-v1",
    )
    retry_wait = ledger.record(
        job_key,
        JobStatus.RETRY_WAIT,
        updated_at=datetime(2026, 6, 23, 4, 16, tzinfo=timezone.utc),
        last_error_code="FETCH_TIMEOUT",
        next_retry_at=datetime(2026, 6, 23, 4, 17, tzinfo=timezone.utc),
    )
    running_again = ledger.record(
        job_key,
        JobStatus.RUNNING,
        updated_at=datetime(2026, 6, 23, 4, 17, tzinfo=timezone.utc),
    )
    succeeded = ledger.record(
        job_key,
        JobStatus.SUCCEEDED,
        updated_at=datetime(2026, 6, 23, 4, 18, tzinfo=timezone.utc),
        artifact_id="odds-20260623-05-01-T15",
    )

    assert pending.attempt_count == 0
    assert running.attempt_count == 1
    assert retry_wait.attempt_count == 1
    assert running_again.attempt_count == 2
    assert succeeded.status is JobStatus.SUCCEEDED
    assert succeeded.last_error_code == "FETCH_TIMEOUT"
    assert succeeded.next_retry_at == datetime(2026, 6, 23, 4, 17, tzinfo=timezone.utc)
    assert succeeded.checkpoint == "snapshot-plan-20260623"
    assert succeeded.parser_version == "odds-v1"
    assert succeeded.artifact_id == "odds-20260623-05-01-T15"
    assert ledger.get(job_key) == succeeded


def test_file_job_ledger_rejects_invalid_transition_from_terminal(tmp_path) -> None:
    ledger = FileJobLedger(tmp_path / "jobs.json")
    job_key = parse_job_key("official|05|2026-06-23|1|odds|T10")
    ledger.record(
        job_key,
        JobStatus.PENDING,
        updated_at=datetime(2026, 6, 23, 4, 19, tzinfo=timezone.utc),
    )
    ledger.record(
        job_key,
        JobStatus.RUNNING,
        updated_at=datetime(2026, 6, 23, 4, 20, tzinfo=timezone.utc),
    )
    ledger.record(
        job_key,
        JobStatus.SUCCEEDED,
        updated_at=datetime(2026, 6, 23, 4, 21, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="invalid job transition"):
        ledger.record(
            job_key,
            JobStatus.RUNNING,
            updated_at=datetime(2026, 6, 23, 4, 22, tzinfo=timezone.utc),
        )


def test_parse_job_key_round_trips_canonical_key() -> None:
    job_key = parse_job_key("official|05|2026-06-23|*|entries|historical")

    assert job_key.key == "official|05|2026-06-23|*|entries|historical"
    assert job_key.race_no is None


def test_register_due_jobs_is_idempotent(tmp_path) -> None:
    ledger = FileJobLedger(tmp_path / "jobs.json")
    due_payload = {
        "schema_version": "snapshot-job-due-v1",
        "jobs": [
            {
                "job_key": "official|05|2026-06-23|1|odds|T15",
                "scheduled_at": "2026-06-23T04:15:00+00:00",
            }
        ],
    }

    first = register_due_jobs(
        ledger,
        due_payload,
        updated_at=datetime(2026, 6, 23, 4, 14, tzinfo=timezone.utc),
        checkpoint="snapshot-due-20260623T0414Z",
    )
    second = register_due_jobs(
        ledger,
        due_payload,
        updated_at=datetime(2026, 6, 23, 4, 14, tzinfo=timezone.utc),
        checkpoint="snapshot-due-20260623T0414Z",
    )

    assert first["registered_count"] == 1
    assert first["skipped_existing_count"] == 0
    assert second["registered_count"] == 0
    assert second["skipped_existing_count"] == 1
    record = ledger.get(parse_job_key("official|05|2026-06-23|1|odds|T15"))
    assert record is not None
    assert record.status is JobStatus.PENDING
    assert record.checkpoint == "snapshot-due-20260623T0414Z"


def test_mark_missed_snapshot_jobs_skips_expired_unfinished_jobs(tmp_path) -> None:
    ledger = FileJobLedger(tmp_path / "jobs.json")
    plan_payload = {
        "schema_version": "snapshot-job-plan-v1",
        "jobs": [
            {
                "job_key": "official|05|2026-06-23|1|odds|T30",
                "scheduled_at": "2026-06-23T04:00:00+00:00",
            },
            {
                "job_key": "official|05|2026-06-23|1|odds|T15",
                "scheduled_at": "2026-06-23T04:15:00+00:00",
            },
            {
                "job_key": "official|05|2026-06-23|1|odds|T10",
                "scheduled_at": "2026-06-23T04:20:00+00:00",
            },
        ],
    }
    ledger.record(
        parse_job_key("official|05|2026-06-23|1|odds|T30"),
        JobStatus.PENDING,
        updated_at=datetime(2026, 6, 23, 3, 59, tzinfo=timezone.utc),
    )

    payload = mark_missed_snapshot_jobs(
        ledger,
        plan_payload,
        now=datetime(2026, 6, 23, 4, 17, tzinfo=timezone.utc),
        allowed_lateness_minutes=1,
        checkpoint="missed-window-20260623T0417Z",
    )

    assert payload["schema_version"] == "job-ledger-missed-windows-v1"
    assert payload["missed_count"] == 2
    assert payload["not_yet_due_count"] == 1
    assert [job["job_key"] for job in payload["jobs"]] == [
        "official|05|2026-06-23|1|odds|T30",
        "official|05|2026-06-23|1|odds|T15",
    ]
    t30 = ledger.get(parse_job_key("official|05|2026-06-23|1|odds|T30"))
    t15 = ledger.get(parse_job_key("official|05|2026-06-23|1|odds|T15"))
    t10 = ledger.get(parse_job_key("official|05|2026-06-23|1|odds|T10"))
    assert t30 is not None
    assert t30.status is JobStatus.SKIPPED
    assert t30.last_error_code == "MISSED_WINDOW"
    assert t30.checkpoint == "missed-window-20260623T0417Z"
    assert t15 is not None
    assert t15.status is JobStatus.SKIPPED
    assert t15.last_error_code == "MISSED_WINDOW"
    assert t10 is None


def test_summarize_job_ledger_counts_statuses_errors_and_due_retries(tmp_path) -> None:
    ledger = FileJobLedger(tmp_path / "jobs.json")
    retry_key = parse_job_key("official|05|2026-06-23|1|odds|T15")
    failed_key = parse_job_key("official|05|2026-06-23|2|odds|T15")
    pending_key = parse_job_key("official|05|2026-06-23|3|odds|T15")
    ledger.record(
        retry_key,
        JobStatus.PENDING,
        updated_at=datetime(2026, 6, 23, 4, 14, tzinfo=timezone.utc),
    )
    ledger.record(
        retry_key,
        JobStatus.RUNNING,
        updated_at=datetime(2026, 6, 23, 4, 15, tzinfo=timezone.utc),
    )
    ledger.record(
        retry_key,
        JobStatus.RETRY_WAIT,
        updated_at=datetime(2026, 6, 23, 4, 16, tzinfo=timezone.utc),
        last_error_code="FETCH_TIMEOUT",
        next_retry_at=datetime(2026, 6, 23, 4, 17, tzinfo=timezone.utc),
    )
    ledger.record(
        failed_key,
        JobStatus.PENDING,
        updated_at=datetime(2026, 6, 23, 4, 14, tzinfo=timezone.utc),
    )
    ledger.record(
        failed_key,
        JobStatus.RUNNING,
        updated_at=datetime(2026, 6, 23, 4, 15, tzinfo=timezone.utc),
    )
    ledger.record(
        failed_key,
        JobStatus.FAILED,
        updated_at=datetime(2026, 6, 23, 4, 16, tzinfo=timezone.utc),
        last_error_code="SOURCE_UNAVAILABLE",
    )
    ledger.record(
        pending_key,
        JobStatus.PENDING,
        updated_at=datetime(2026, 6, 23, 4, 14, tzinfo=timezone.utc),
    )

    payload = summarize_job_ledger(
        ledger,
        as_of=datetime(2026, 6, 23, 4, 18, tzinfo=timezone.utc),
    )

    assert payload["schema_version"] == "job-ledger-summary-v1"
    assert payload["job_count"] == 3
    assert payload["status_counts"] == {
        "pending": 1,
        "running": 0,
        "retry_wait": 1,
        "succeeded": 0,
        "failed": 1,
        "skipped": 0,
    }
    assert payload["error_counts"] == {
        "FETCH_TIMEOUT": 1,
        "SOURCE_UNAVAILABLE": 1,
    }
    assert payload["terminal_count"] == 1
    assert payload["retry_due_count"] == 1
    assert payload["retry_due_jobs"] == [retry_key.key]
