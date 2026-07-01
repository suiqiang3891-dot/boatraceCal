"""Auditable source response metadata and quarantine records."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from boatrace_cal.errors import ErrorCode


@dataclass(frozen=True, slots=True)
class SourceResponseMetadata:
    """Metadata retained for a fetched source response without storing the body."""

    url: str
    fetched_at: datetime
    http_status: int
    content_sha256: str
    parser_version: str

    def __post_init__(self) -> None:
        if type(self.url) is not str:
            raise TypeError("url must be a string")
        url = self.url.strip()
        if not url:
            raise ValueError("url must not be blank")
        object.__setattr__(self, "url", url)

        if type(self.fetched_at) is not datetime or not _is_aware(self.fetched_at):
            raise ValueError("fetched_at must be timezone-aware")
        if type(self.http_status) is not int or not 100 <= self.http_status <= 599:
            raise ValueError("http_status must be between 100 and 599")

        if type(self.content_sha256) is not str:
            raise TypeError("content_sha256 must be a string")
        content_sha256 = self.content_sha256.strip().lower()
        if len(content_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in content_sha256
        ):
            raise ValueError("content_sha256 must be a SHA-256 hex digest")
        object.__setattr__(self, "content_sha256", content_sha256)

        if type(self.parser_version) is not str:
            raise TypeError("parser_version must be a string")
        parser_version = self.parser_version.strip()
        if not parser_version:
            raise ValueError("parser_version must not be blank")
        object.__setattr__(self, "parser_version", parser_version)


@dataclass(frozen=True, slots=True)
class QuarantinedResponse:
    """Exceptional source response retained for a bounded investigation window."""

    metadata: SourceResponseMetadata
    saved_path: Path
    reason_code: ErrorCode
    retained_until: date

    def __post_init__(self) -> None:
        if type(self.metadata) is not SourceResponseMetadata:
            raise TypeError("metadata must be SourceResponseMetadata")
        if not isinstance(self.saved_path, Path):
            raise TypeError("saved_path must be a Path")
        if type(self.reason_code) is not ErrorCode:
            raise TypeError("reason_code must be an ErrorCode")
        if type(self.retained_until) is not date:
            raise TypeError("retained_until must be a date")
        if self.retained_until <= self.metadata.fetched_at.date():
            raise ValueError("retained_until must be after fetched_at date")


@dataclass(frozen=True, slots=True)
class QuarantineCleanupResult:
    """Auditable result of deleting expired quarantined response bodies."""

    deleted_count: int
    deleted_bytes: int
    missing_count: int
    failed_paths: tuple[Path, ...]

    def __post_init__(self) -> None:
        if type(self.deleted_count) is not int or self.deleted_count < 0:
            raise ValueError("deleted_count must be a non-negative integer")
        if type(self.deleted_bytes) is not int or self.deleted_bytes < 0:
            raise ValueError("deleted_bytes must be a non-negative integer")
        if type(self.missing_count) is not int or self.missing_count < 0:
            raise ValueError("missing_count must be a non-negative integer")
        if type(self.failed_paths) is not tuple or any(
            not isinstance(path, Path) for path in self.failed_paths
        ):
            raise TypeError("failed_paths must be a tuple of Path values")


def quarantine_response(
    metadata: SourceResponseMetadata,
    saved_path: Path | str,
    reason_code: ErrorCode,
    retention_days: int,
) -> QuarantinedResponse:
    """Create a quarantine record for an exceptional response body saved elsewhere."""

    if type(metadata) is not SourceResponseMetadata:
        raise TypeError("metadata must be SourceResponseMetadata")
    if type(reason_code) is not ErrorCode:
        raise TypeError("reason_code must be an ErrorCode")
    if type(retention_days) is not int or retention_days < 1:
        raise ValueError("retention_days must be at least one")
    return QuarantinedResponse(
        metadata=metadata,
        saved_path=Path(saved_path),
        reason_code=reason_code,
        retained_until=metadata.fetched_at.date() + timedelta(days=retention_days),
    )


def save_quarantined_response_body(
    metadata: SourceResponseMetadata,
    quarantine_dir: Path | str,
    body: bytes,
    reason_code: ErrorCode,
    retention_days: int,
) -> QuarantinedResponse:
    """Persist an exceptional response body once and return its quarantine record."""

    if type(body) is not bytes:
        raise TypeError("body must be bytes")
    directory = Path(quarantine_dir)
    directory.mkdir(parents=True, exist_ok=True)
    saved_path = directory / _quarantine_filename(metadata, reason_code)
    with saved_path.open("xb") as response_file:
        response_file.write(body)
    return quarantine_response(
        metadata=metadata,
        saved_path=saved_path,
        reason_code=reason_code,
        retention_days=retention_days,
    )


def cleanup_expired_quarantine(
    records: tuple[QuarantinedResponse, ...],
    as_of: date,
) -> QuarantineCleanupResult:
    """Delete expired quarantined response bodies and return audit counters."""

    if type(records) is not tuple or any(
        type(record) is not QuarantinedResponse for record in records
    ):
        raise TypeError("records must be a tuple of QuarantinedResponse values")
    if type(as_of) is not date:
        raise TypeError("as_of must be a date")

    deleted_count = 0
    deleted_bytes = 0
    missing_count = 0
    failed_paths = []
    for record in records:
        if record.retained_until > as_of:
            continue
        try:
            deleted_bytes += record.saved_path.stat().st_size
            record.saved_path.unlink()
            deleted_count += 1
        except FileNotFoundError:
            missing_count += 1
        except OSError:
            failed_paths.append(record.saved_path)

    return QuarantineCleanupResult(
        deleted_count=deleted_count,
        deleted_bytes=deleted_bytes,
        missing_count=missing_count,
        failed_paths=tuple(failed_paths),
    )


def _quarantine_filename(metadata: SourceResponseMetadata, reason_code: ErrorCode) -> str:
    if type(metadata) is not SourceResponseMetadata:
        raise TypeError("metadata must be SourceResponseMetadata")
    if type(reason_code) is not ErrorCode:
        raise TypeError("reason_code must be an ErrorCode")
    fetched_token = metadata.fetched_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{fetched_token}_{reason_code.value}_{metadata.content_sha256}.html"


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None
