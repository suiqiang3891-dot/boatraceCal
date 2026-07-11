from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

import pytest

from boatrace_cal.review_archive import freeze_confirmed_review_list
from boatrace_cal.reviews import (
    RecommendationReview,
    ReviewDecision,
    build_confirmed_review_list,
    confirmed_review_list_to_dict,
)


def test_freeze_confirmed_review_list_writes_immutable_audit_artifact(
    tmp_path: Path,
) -> None:
    review_list = _review_list()
    frozen_at = datetime(2026, 7, 11, 4, 10, tzinfo=UTC)
    expected_content_hash = hashlib.sha256(
        (json.dumps(confirmed_review_list_to_dict(review_list), ensure_ascii=False, sort_keys=True) + "\n").encode(
            "utf-8"
        )
    ).hexdigest()

    archive = freeze_confirmed_review_list(
        review_list,
        archive_dir=tmp_path / "archives",
        frozen_at=frozen_at,
        frozen_by="analyst",
    )

    assert archive.version_id == f"2025-01-02-{expected_content_hash[:12]}"
    assert archive.content_sha256 == expected_content_hash
    assert archive.path.name == f"{archive.version_id}.json"
    payload = json.loads(archive.path.read_text(encoding="utf-8"))
    assert payload == {
        "artifact_type": "confirmed_review_list",
        "schema_version": "confirmed-review-list-v1",
        "version_id": archive.version_id,
        "content_sha256": expected_content_hash,
        "frozen_at": "2026-07-11T04:10:00+00:00",
        "frozen_by": "analyst",
        "checklist": confirmed_review_list_to_dict(review_list),
    }
    assert archive.path.read_text(encoding="utf-8").endswith("\n")


def test_freeze_confirmed_review_list_is_idempotent_but_rejects_tampered_archive(
    tmp_path: Path,
) -> None:
    review_list = _review_list()
    frozen_at = datetime(2026, 7, 11, 4, 10, tzinfo=UTC)
    archive = freeze_confirmed_review_list(
        review_list,
        archive_dir=tmp_path,
        frozen_at=frozen_at,
        frozen_by="analyst",
    )

    same_archive = freeze_confirmed_review_list(
        review_list,
        archive_dir=tmp_path,
        frozen_at=frozen_at,
        frozen_by="analyst",
    )
    archive.path.write_text("{\"tampered\": true}\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="confirmed review archive already exists"):
        freeze_confirmed_review_list(
            review_list,
            archive_dir=tmp_path,
            frozen_at=frozen_at,
            frozen_by="analyst",
        )

    assert same_archive == archive


def _review_list():
    return build_confirmed_review_list(
        reviews=(
            RecommendationReview(
                recommendation_id="rec-1",
                race_id="20250102-01-01",
                decision=ReviewDecision.CONFIRMED,
                stake_units=3,
                notes="keep",
                reviewed_at=datetime(2026, 7, 11, 3, 20, tzinfo=UTC),
                reviewed_by="analyst",
            ),
        ),
        business_date="2025-01-02",
        generated_at=datetime(2026, 7, 11, 4, 0, tzinfo=UTC),
        generated_by="analyst",
    )
