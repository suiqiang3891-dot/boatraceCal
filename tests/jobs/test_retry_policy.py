from datetime import date, datetime, timezone

from boatrace_cal.domain.races import VenueCode
from boatrace_cal.errors import ErrorCode
from boatrace_cal.jobs.contracts import JobKey, JobStatus, SnapshotTarget
from boatrace_cal.jobs.ledger import FileJobLedger
from boatrace_cal.jobs.retry_policy import RetryPolicy, record_failed_job_attempt


def test_record_failed_job_attempt_schedules_retry_for_transient_timeout(tmp_path) -> None:
    ledger = FileJobLedger(tmp_path / "jobs.json")
    job_key = JobKey(
        source="official",
        venue=VenueCode("05"),
        race_date=date(2026, 6, 23),
        race_no=1,
        data_type="odds",
        snapshot_target=SnapshotTarget.T15,
    )
    ledger.record(
        job_key,
        JobStatus.PENDING,
        updated_at=datetime(2026, 6, 23, 4, 14, tzinfo=timezone.utc),
    )
    ledger.record(
        job_key,
        JobStatus.RUNNING,
        updated_at=datetime(2026, 6, 23, 4, 15, tzinfo=timezone.utc),
    )

    payload = record_failed_job_attempt(
        ledger,
        job_key,
        ErrorCode.FETCH_TIMEOUT,
        observed_at=datetime(2026, 6, 23, 4, 16, tzinfo=timezone.utc),
        policy=RetryPolicy(max_attempts=3, base_delay_seconds=60, max_delay_seconds=300),
        checkpoint="retry-policy-20260623T0416Z",
    )

    assert payload["schema_version"] == "job-retry-decision-v1"
    assert payload["decision"]["action_status"] == "retry_wait"
    assert payload["decision"]["retryable"] is True
    assert payload["decision"]["reason_code"] == "transient_retry_scheduled"
    assert payload["record"]["status"] == "retry_wait"
    assert payload["record"]["last_error_code"] == "FETCH_TIMEOUT"
    assert payload["record"]["next_retry_at"] == "2026-06-23T04:17:00+00:00"
    assert payload["record"]["checkpoint"] == "retry-policy-20260623T0416Z"


def test_record_failed_job_attempt_fails_non_retryable_source_error(tmp_path) -> None:
    ledger = FileJobLedger(tmp_path / "jobs.json")
    job_key = JobKey(
        source="official",
        venue=VenueCode("05"),
        race_date=date(2026, 6, 23),
        race_no=1,
        data_type="odds",
        snapshot_target=SnapshotTarget.T10,
    )
    ledger.record(
        job_key,
        JobStatus.PENDING,
        updated_at=datetime(2026, 6, 23, 4, 18, tzinfo=timezone.utc),
    )
    ledger.record(
        job_key,
        JobStatus.RUNNING,
        updated_at=datetime(2026, 6, 23, 4, 19, tzinfo=timezone.utc),
    )

    payload = record_failed_job_attempt(
        ledger,
        job_key,
        ErrorCode.SOURCE_UNAVAILABLE,
        observed_at=datetime(2026, 6, 23, 4, 20, tzinfo=timezone.utc),
        policy=RetryPolicy(max_attempts=3, base_delay_seconds=60, max_delay_seconds=300),
    )

    assert payload["decision"]["action_status"] == "failed"
    assert payload["decision"]["retryable"] is False
    assert payload["decision"]["reason_code"] == "non_retryable_error"
    assert payload["record"]["status"] == "failed"
    assert payload["record"]["last_error_code"] == "SOURCE_UNAVAILABLE"


def test_record_failed_job_attempt_skips_retry_after_snapshot_window(tmp_path) -> None:
    ledger = FileJobLedger(tmp_path / "jobs.json")
    job_key = JobKey(
        source="official",
        venue=VenueCode("05"),
        race_date=date(2026, 6, 23),
        race_no=1,
        data_type="odds",
        snapshot_target=SnapshotTarget.T05,
    )
    ledger.record(
        job_key,
        JobStatus.PENDING,
        updated_at=datetime(2026, 6, 23, 4, 23, tzinfo=timezone.utc),
    )
    ledger.record(
        job_key,
        JobStatus.RUNNING,
        updated_at=datetime(2026, 6, 23, 4, 24, tzinfo=timezone.utc),
    )

    payload = record_failed_job_attempt(
        ledger,
        job_key,
        ErrorCode.FETCH_TIMEOUT,
        observed_at=datetime(2026, 6, 23, 4, 25, tzinfo=timezone.utc),
        policy=RetryPolicy(max_attempts=3, base_delay_seconds=300, max_delay_seconds=300),
        window_expires_at=datetime(2026, 6, 23, 4, 26, tzinfo=timezone.utc),
    )

    assert payload["decision"]["action_status"] == "skipped"
    assert payload["decision"]["retryable"] is True
    assert payload["decision"]["reason_code"] == "retry_window_expired"
    assert payload["record"]["status"] == "skipped"
    assert payload["record"]["last_error_code"] == "FETCH_TIMEOUT"
