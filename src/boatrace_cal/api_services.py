"""Dependency-free application services behind the OpenAPI contract."""

from datetime import datetime
import json
from pathlib import Path
from typing import Any, cast

from boatrace_cal.review_archive import freeze_confirmed_review_list
from boatrace_cal.review_excel import (
    XLSX_CONTENT_TYPE,
    export_confirmed_review_list_xlsx,
    export_review_table_xlsx,
)
from boatrace_cal.review_store import FileReviewStore
from boatrace_cal.reviews import (
    ConfirmedReviewList,
    confirmed_review_list_to_dict,
    review_from_dict,
)


class ReviewWorkflowService:
    """Review workflow operations that future HTTP routes can call directly."""

    def __init__(
        self,
        *,
        review_store_path: Path | str,
        archive_dir: Path | str,
        export_dir: Path | str,
    ) -> None:
        self._store = FileReviewStore(review_store_path)
        self._archive_dir = Path(archive_dir)
        self._export_dir = Path(export_dir)

    def import_reviews(self, payload: object) -> dict[str, int]:
        """Import review records using the OpenAPI ReviewImportRequest shape."""

        request = _require_mapping(payload, "review import request")
        reviews_payload = request.get("reviews")
        if type(reviews_payload) is not list:
            raise ValueError("reviews must be a list")
        reviews = tuple(review_from_dict(item) for item in reviews_payload)
        stored_reviews = self._store.upsert_reviews(reviews)
        return {"stored_count": len(stored_reviews)}

    def build_confirmed_review_list(self, payload: object) -> dict[str, Any]:
        """Build a JSON-ready confirmed review checklist from stored reviews."""

        review_list = self._build_confirmed_review_list_object(payload)
        return confirmed_review_list_to_dict(review_list)

    def freeze_confirmed_review_archive(self, payload: object) -> dict[str, Any]:
        """Freeze the current confirmed review checklist and return its artifact body."""

        request = _require_mapping(payload, "confirmed review archive request")
        review_list = self._build_confirmed_review_list_object(request)
        archive = freeze_confirmed_review_list(
            review_list,
            archive_dir=self._archive_dir,
            frozen_at=_parse_aware_datetime(_required_string(request, "frozen_at"), "frozen_at"),
            frozen_by=_required_string(request, "frozen_by"),
        )
        return cast(dict[str, Any], json.loads(archive.path.read_text(encoding="utf-8")))

    def export_excel(self, payload: object) -> dict[str, str]:
        """Export an XLSX workbook artifact for one supported export type."""

        request = _require_mapping(payload, "excel export request")
        business_date = _required_string(request, "business_date")
        export_type = _required_string(request, "export_type")
        generated_at = _parse_aware_datetime(
            _required_string(request, "generated_at"),
            "generated_at",
        )
        generated_by = _required_string(request, "generated_by")

        if export_type == "confirmed_list":
            job_id = f"confirmed-list-{_safe_file_part(business_date)}"
            review_list = self._store.build_confirmed_review_list(
                business_date=business_date,
                generated_at=generated_at,
                generated_by=generated_by,
            )
            artifact_path = self._export_dir / f"{job_id}.xlsx"
            export_confirmed_review_list_xlsx(review_list, artifact_path)
        elif export_type == "review_table":
            job_id = f"review-table-{_safe_file_part(business_date)}"
            artifact_path = self._export_dir / f"{job_id}.xlsx"
            export_review_table_xlsx(
                self._store.list_reviews(),
                artifact_path,
                business_date=business_date,
                generated_at=generated_at.isoformat(),
                generated_by=generated_by,
            )
        else:
            raise ValueError("export_type must be review_table or confirmed_list")

        return {
            "job_id": job_id,
            "status": "done",
            "artifact_path": str(artifact_path),
            "content_type": XLSX_CONTENT_TYPE,
        }

    def _build_confirmed_review_list_object(self, payload: object) -> ConfirmedReviewList:
        request = _require_mapping(payload, "confirmed review list request")
        return self._store.build_confirmed_review_list(
            business_date=_required_string(request, "business_date"),
            generated_at=_parse_aware_datetime(
                _required_string(request, "generated_at"),
                "generated_at",
            ),
            generated_by=_required_string(request, "generated_by"),
        )


def _require_mapping(payload: object, name: str) -> dict[str, object]:
    if type(payload) is not dict:
        raise ValueError(f"{name} must be a dictionary")
    object_mapping = cast(dict[object, object], payload)
    if any(type(key) is not str for key in object_mapping):
        raise ValueError(f"{name} keys must be strings")
    return cast(dict[str, object], object_mapping)


def _required_string(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if type(value) is not str:
        raise ValueError(f"{key} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{key} must not be empty")
    return normalized


def _parse_aware_datetime(value: str, name: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return parsed


def _safe_file_part(value: str) -> str:
    safe = "".join(character if character.isalnum() or character == "-" else "-" for character in value)
    return safe.strip("-") or "draft"
