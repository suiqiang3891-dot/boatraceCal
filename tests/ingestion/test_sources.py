from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from boatrace_cal.errors import ErrorCode
from boatrace_cal.ingestion.sources import (
    QuarantineCleanupResult,
    QuarantinedResponse,
    SourceResponseMetadata,
    cleanup_expired_quarantine_manifest,
    cleanup_expired_quarantine,
    quarantine_response,
    quarantined_response_to_dict,
    save_quarantined_response_body,
)


def test_source_response_metadata_records_auditable_fetch_identity() -> None:
    metadata = SourceResponseMetadata(
        url=" https://example.test/result?k=1 ",
        fetched_at=datetime(2026, 6, 23, 4, 0, tzinfo=timezone.utc),
        http_status=200,
        content_sha256="A" * 64,
        parser_version=" parser-v1 ",
    )

    assert metadata.url == "https://example.test/result?k=1"
    assert metadata.content_sha256 == "a" * 64
    assert metadata.parser_version == "parser-v1"


def test_quarantines_exceptional_response_with_retention_deadline(tmp_path: Path) -> None:
    metadata = SourceResponseMetadata(
        url="https://example.test/result",
        fetched_at=datetime(2026, 6, 23, 23, 30, tzinfo=timezone.utc),
        http_status=200,
        content_sha256="b" * 64,
        parser_version="parser-v1",
    )
    path = tmp_path / "quarantine" / "response.html"

    quarantined = quarantine_response(
        metadata=metadata,
        saved_path=path,
        reason_code=ErrorCode.PARSE_SCHEMA_CHANGED,
        retention_days=30,
    )

    assert quarantined == QuarantinedResponse(
        metadata=metadata,
        saved_path=path,
        reason_code=ErrorCode.PARSE_SCHEMA_CHANGED,
        retained_until=date(2026, 7, 23),
    )


@pytest.mark.parametrize("status", [99, 600])
def test_source_response_metadata_rejects_invalid_http_status(status: int) -> None:
    with pytest.raises(ValueError, match="http_status"):
        SourceResponseMetadata(
            url="https://example.test/result",
            fetched_at=datetime(2026, 6, 23, 4, 0, tzinfo=timezone.utc),
            http_status=status,
            content_sha256="c" * 64,
            parser_version="parser-v1",
        )


def test_quarantine_response_rejects_non_positive_retention_days(tmp_path: Path) -> None:
    metadata = SourceResponseMetadata(
        url="https://example.test/result",
        fetched_at=datetime(2026, 6, 23, 4, 0, tzinfo=timezone.utc),
        http_status=503,
        content_sha256="d" * 64,
        parser_version="parser-v1",
    )

    with pytest.raises(ValueError, match="retention_days"):
        quarantine_response(
            metadata=metadata,
            saved_path=tmp_path / "response.html",
            reason_code=ErrorCode.SOURCE_UNAVAILABLE,
            retention_days=0,
        )


def test_saves_quarantined_response_body_without_overwriting(tmp_path: Path) -> None:
    body = b"<html>changed</html>"
    metadata = SourceResponseMetadata(
        url="https://example.test/result",
        fetched_at=datetime(2026, 6, 23, 4, 0, tzinfo=timezone.utc),
        http_status=200,
        content_sha256="5a7d06eab7d1e1a1bc6698c347f9fd2c677b1113265b36e52fbca3cf7879815d",
        parser_version="parser-v1",
    )

    quarantined = save_quarantined_response_body(
        metadata=metadata,
        quarantine_dir=tmp_path / "quarantine",
        body=body,
        reason_code=ErrorCode.PARSE_SCHEMA_CHANGED,
        retention_days=30,
    )

    assert quarantined.saved_path.read_bytes() == body
    assert quarantined.saved_path.name == (
        "20260623T040000Z_PARSE_SCHEMA_CHANGED_"
        "5a7d06eab7d1e1a1bc6698c347f9fd2c677b1113265b36e52fbca3cf7879815d.html"
    )
    with pytest.raises(FileExistsError):
        save_quarantined_response_body(
            metadata=metadata,
            quarantine_dir=tmp_path / "quarantine",
            body=body,
            reason_code=ErrorCode.PARSE_SCHEMA_CHANGED,
            retention_days=30,
        )


def test_cleanup_expired_quarantine_deletes_only_expired_files(tmp_path: Path) -> None:
    metadata = SourceResponseMetadata(
        url="https://example.test/result",
        fetched_at=datetime(2026, 6, 1, 4, 0, tzinfo=timezone.utc),
        http_status=503,
        content_sha256="e" * 64,
        parser_version="parser-v1",
    )
    expired_path = tmp_path / "expired.html"
    retained_path = tmp_path / "retained.html"
    missing_path = tmp_path / "missing.html"
    expired_path.write_bytes(b"expired")
    retained_path.write_bytes(b"retained")
    expired = QuarantinedResponse(
        metadata=metadata,
        saved_path=expired_path,
        reason_code=ErrorCode.SOURCE_UNAVAILABLE,
        retained_until=date(2026, 6, 10),
    )
    retained = QuarantinedResponse(
        metadata=metadata,
        saved_path=retained_path,
        reason_code=ErrorCode.SOURCE_UNAVAILABLE,
        retained_until=date(2026, 7, 10),
    )
    missing = QuarantinedResponse(
        metadata=metadata,
        saved_path=missing_path,
        reason_code=ErrorCode.SOURCE_UNAVAILABLE,
        retained_until=date(2026, 6, 10),
    )

    result = cleanup_expired_quarantine(
        records=(retained, expired, missing),
        as_of=date(2026, 6, 30),
    )

    assert result == QuarantineCleanupResult(
        deleted_count=1,
        deleted_bytes=7,
        missing_count=1,
        failed_paths=(),
    )
    assert not expired_path.exists()
    assert retained_path.read_bytes() == b"retained"


def test_cleanup_expired_quarantine_manifest_returns_audit_report(
    tmp_path: Path,
) -> None:
    metadata = SourceResponseMetadata(
        url="https://example.test/result",
        fetched_at=datetime(2026, 6, 1, 4, 0, tzinfo=timezone.utc),
        http_status=503,
        content_sha256="f" * 64,
        parser_version="parser-v1",
    )
    expired_path = tmp_path / "expired.html"
    retained_path = tmp_path / "retained.html"
    expired_path.write_bytes(b"expired")
    retained_path.write_bytes(b"retained")
    expired = QuarantinedResponse(
        metadata=metadata,
        saved_path=expired_path,
        reason_code=ErrorCode.SOURCE_UNAVAILABLE,
        retained_until=date(2026, 6, 10),
    )
    retained = QuarantinedResponse(
        metadata=metadata,
        saved_path=retained_path,
        reason_code=ErrorCode.SOURCE_UNAVAILABLE,
        retained_until=date(2026, 7, 10),
    )

    payload = cleanup_expired_quarantine_manifest(
        {
            "schema_version": "quarantine-manifest-v1",
            "records": [
                quarantined_response_to_dict(retained),
                quarantined_response_to_dict(expired),
            ],
        },
        as_of=date(2026, 6, 30),
    )

    assert payload == {
        "schema_version": "quarantine-cleanup-v1",
        "source_schema_version": "quarantine-manifest-v1",
        "as_of": "2026-06-30",
        "record_count": 2,
        "deleted_count": 1,
        "deleted_bytes": 7,
        "missing_count": 0,
        "failed_count": 0,
        "failed_paths": [],
    }
    assert not expired_path.exists()
    assert retained_path.read_bytes() == b"retained"
