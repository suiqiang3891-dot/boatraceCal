"""Retry decisions for auditable local collection jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from boatrace_cal.errors import ErrorCode
from boatrace_cal.jobs.contracts import JobKey, JobStatus
from boatrace_cal.jobs.ledger import FileJobLedger


_RETRYABLE_ERROR_CODES = frozenset(
    {
        ErrorCode.FETCH_TIMEOUT,
        ErrorCode.RATE_LIMITED,
    }
)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bounded retry configuration for one failed collection attempt."""

    max_attempts: int
    base_delay_seconds: int
    max_delay_seconds: int

    def __post_init__(self) -> None:
        if type(self.max_attempts) is not int or self.max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")
        if type(self.base_delay_seconds) is not int or self.base_delay_seconds < 1:
            raise ValueError("base_delay_seconds must be a positive integer")
        if type(self.max_delay_seconds) is not int or self.max_delay_seconds < 1:
            raise ValueError("max_delay_seconds must be a positive integer")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("max_delay_seconds must not be less than base_delay_seconds")


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """A persistable action selected by the retry policy."""

    error_code: ErrorCode
    attempt_count: int
    action_status: JobStatus
    retryable: bool
    reason_code: str
    next_retry_at: datetime | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "error_code": self.error_code.value,
            "attempt_count": self.attempt_count,
            "action_status": self.action_status.value,
            "retryable": self.retryable,
            "reason_code": self.reason_code,
            "next_retry_at": None
            if self.next_retry_at is None
            else self.next_retry_at.isoformat(),
        }


def build_retry_decision(
    error_code: ErrorCode | str,
    *,
    attempt_count: int,
    observed_at: datetime,
    policy: RetryPolicy,
    window_expires_at: datetime | None = None,
    retry_after_seconds: int | None = None,
) -> RetryDecision:
    """Choose the next ledger status for a failed job attempt."""

    normalized_error_code = _normalize_error_code(error_code)
    _validate_attempt_count(attempt_count)
    _validate_aware_datetime(observed_at, "observed_at")
    if window_expires_at is not None:
        _validate_aware_datetime(window_expires_at, "window_expires_at")
    if retry_after_seconds is not None and (
        type(retry_after_seconds) is not int or retry_after_seconds < 0
    ):
        raise ValueError("retry_after_seconds must be a non-negative integer")

    retryable = normalized_error_code in _RETRYABLE_ERROR_CODES
    if not retryable:
        return RetryDecision(
            error_code=normalized_error_code,
            attempt_count=attempt_count,
            action_status=JobStatus.FAILED,
            retryable=False,
            reason_code="non_retryable_error",
        )

    if attempt_count >= policy.max_attempts:
        return RetryDecision(
            error_code=normalized_error_code,
            attempt_count=attempt_count,
            action_status=JobStatus.FAILED,
            retryable=True,
            reason_code="max_attempts_exhausted",
        )

    delay_seconds = _retry_delay_seconds(
        attempt_count=attempt_count,
        policy=policy,
        retry_after_seconds=retry_after_seconds,
    )
    next_retry_at = observed_at + timedelta(seconds=delay_seconds)
    if window_expires_at is not None and next_retry_at > window_expires_at:
        return RetryDecision(
            error_code=normalized_error_code,
            attempt_count=attempt_count,
            action_status=JobStatus.SKIPPED,
            retryable=True,
            reason_code="retry_window_expired",
        )

    return RetryDecision(
        error_code=normalized_error_code,
        attempt_count=attempt_count,
        action_status=JobStatus.RETRY_WAIT,
        retryable=True,
        reason_code="transient_retry_scheduled",
        next_retry_at=next_retry_at,
    )


def record_failed_job_attempt(
    ledger: FileJobLedger,
    job_key: JobKey,
    error_code: ErrorCode | str,
    *,
    observed_at: datetime,
    policy: RetryPolicy,
    window_expires_at: datetime | None = None,
    retry_after_seconds: int | None = None,
    checkpoint: str | None = None,
) -> dict[str, object]:
    """Record a running job failure according to the bounded retry policy."""

    if type(ledger) is not FileJobLedger:
        raise TypeError("ledger must be a FileJobLedger")
    if type(job_key) is not JobKey:
        raise TypeError("job_key must be a JobKey")
    current = ledger.get(job_key)
    if current is None:
        raise ValueError("failed job attempt must already exist in the ledger")
    if current.status is not JobStatus.RUNNING:
        raise ValueError("failed job attempt must be recorded from running status")

    decision = build_retry_decision(
        error_code,
        attempt_count=current.attempt_count,
        observed_at=observed_at,
        policy=policy,
        window_expires_at=window_expires_at,
        retry_after_seconds=retry_after_seconds,
    )
    record = ledger.record(
        job_key,
        decision.action_status,
        updated_at=observed_at,
        last_error_code=decision.error_code.value,
        next_retry_at=decision.next_retry_at,
        checkpoint=checkpoint,
    )
    return {
        "schema_version": "job-retry-decision-v1",
        "decision": decision.to_dict(),
        "record": record.to_dict(),
    }


def _retry_delay_seconds(
    *,
    attempt_count: int,
    policy: RetryPolicy,
    retry_after_seconds: int | None,
) -> int:
    if retry_after_seconds is not None:
        return int(retry_after_seconds)
    multiplier: int = 2 ** max(0, attempt_count - 1)
    delay_seconds: int = min(
        policy.base_delay_seconds * multiplier,
        policy.max_delay_seconds,
    )
    return delay_seconds


def _normalize_error_code(value: ErrorCode | str) -> ErrorCode:
    if type(value) is ErrorCode:
        return value
    if type(value) is not str:
        raise TypeError("error_code must be an ErrorCode or string")
    return ErrorCode(value)


def _validate_attempt_count(value: int) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("attempt_count must be a non-negative integer")


def _validate_aware_datetime(value: datetime, field_name: str) -> None:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
