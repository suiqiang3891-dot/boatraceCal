"""Immutable archive artifacts for confirmed review checklists."""

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from boatrace_cal.reviews import ConfirmedReviewList, confirmed_review_list_to_dict


CONFIRMED_REVIEW_ARCHIVE_SCHEMA = "confirmed-review-list-v1"


@dataclass(frozen=True, slots=True)
class ConfirmedReviewArchive:
    """File identity for one frozen confirmed review checklist."""

    version_id: str
    content_sha256: str
    path: Path


def freeze_confirmed_review_list(
    review_list: ConfirmedReviewList,
    *,
    archive_dir: Path | str,
    frozen_at: datetime,
    frozen_by: str,
) -> ConfirmedReviewArchive:
    """Write a content-addressed immutable confirmed-list archive."""

    if type(review_list) is not ConfirmedReviewList:
        raise TypeError("review_list must be a ConfirmedReviewList")
    if type(frozen_at) is not datetime:
        raise ValueError("frozen_at must be a datetime")
    if frozen_at.tzinfo is None or frozen_at.utcoffset() is None:
        raise ValueError("frozen_at must be timezone-aware")
    frozen_by = _normalize_required_text(frozen_by, "frozen_by")

    checklist = confirmed_review_list_to_dict(review_list)
    content_sha256 = _json_content_sha256(checklist)
    version_id = f"{review_list.business_date}-{content_sha256[:12]}"
    archive_path = Path(archive_dir) / f"{version_id}.json"
    payload = {
        "artifact_type": "confirmed_review_list",
        "schema_version": CONFIRMED_REVIEW_ARCHIVE_SCHEMA,
        "version_id": version_id,
        "content_sha256": content_sha256,
        "frozen_at": frozen_at.isoformat(),
        "frozen_by": frozen_by,
        "checklist": checklist,
    }
    archive_text = _json_dumps(payload)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if archive_path.exists():
        if archive_path.read_text(encoding="utf-8") != archive_text:
            raise FileExistsError("confirmed review archive already exists with different content")
    else:
        archive_path.write_text(archive_text, encoding="utf-8")
    return ConfirmedReviewArchive(
        version_id=version_id,
        content_sha256=content_sha256,
        path=archive_path,
    )


def _json_content_sha256(payload: dict[str, Any]) -> str:
    canonical_json = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _normalize_required_text(value: str, name: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    return normalized
