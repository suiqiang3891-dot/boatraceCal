from datetime import date, datetime, timezone

import pytest

from boatrace_cal.domain.races import VenueCode
from boatrace_cal.jobs.contracts import JobKey, JobStatus, SnapshotTarget
from boatrace_cal.jobs.ledger import FileJobLedger, parse_job_key


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
