"""Dependency-free application services behind the OpenAPI contract."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
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
    review_to_dict,
)


RISK_NOTICE = "历史表现不代表未来结果；本系统只提供分析与回测，不承诺盈利，不提供自动下单。"


class CandidateQueryService:
    """Read-only candidate query operations behind the business-date API paths."""

    def __init__(self, *, report_paths: dict[str, Path | str]) -> None:
        self._report_paths = {
            business_date: Path(report_path)
            for business_date, report_path in report_paths.items()
        }

    def get_business_date_status(self, business_date: str) -> dict[str, str]:
        """Return analysis readiness for one business date."""

        report = self._load_report_or_none(business_date)
        if report is None:
            status = "empty"
        elif _report_is_ready(report):
            status = "ready"
        else:
            status = "blocked"
        return {
            "business_date": business_date,
            "status": status,
            "risk_notice": RISK_NOTICE,
        }

    def list_candidates(self, business_date: str) -> dict[str, Any]:
        """Return candidate summaries for one business date."""

        report = self._load_report_or_none(business_date)
        if report is None:
            candidates: list[dict[str, Any]] = []
        else:
            candidates = [
                _candidate_summary_from_settlement(settlement)
                for settlement in _report_settlements(report)
            ]
        return {
            "business_date": business_date,
            "candidates": candidates,
        }

    def get_candidate_detail(self, business_date: str, recommendation_id: str) -> dict[str, Any]:
        """Return one candidate detail with artifact versions and explanation."""

        report = self._load_report_or_none(business_date)
        if report is None:
            raise ValueError("business_date has no report")
        for settlement in _report_settlements(report):
            if _required_string(settlement, "recommendation_id") == recommendation_id:
                return _candidate_detail_from_settlement(settlement)
        raise ValueError(f"recommendation_id not found: {recommendation_id}")

    def _load_report_or_none(self, business_date: str) -> dict[str, object] | None:
        report_path = self._report_paths.get(business_date)
        if report_path is None or not report_path.exists():
            return None
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        return _require_mapping(payload, "backtest report")


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

    def list_reviews(self) -> dict[str, list[dict[str, Any]]]:
        """Return persisted review records using the OpenAPI import envelope shape."""

        return {"reviews": [review_to_dict(review) for review in self._store.list_reviews()]}

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

        export_job = {
            "job_id": job_id,
            "status": "done",
            "artifact_path": str(artifact_path),
            "content_type": XLSX_CONTENT_TYPE,
        }
        self._write_export_job(export_job)
        return export_job

    def get_export_job(self, job_id: str) -> dict[str, str]:
        """Return the last known status for an export artifact."""

        normalized_job_id = _required_plain_string(job_id, "job_id")
        manifest_path = self._export_job_manifest_path(normalized_job_id)
        if not manifest_path.exists():
            raise ValueError(f"job_id not found: {normalized_job_id}")
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        export_job = _require_mapping(payload, "export job")
        return {
            "job_id": _required_string(export_job, "job_id"),
            "status": _required_string(export_job, "status"),
            "artifact_path": _required_string(export_job, "artifact_path"),
            "content_type": _required_string(export_job, "content_type"),
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

    def _write_export_job(self, export_job: dict[str, str]) -> None:
        manifest_path = self._export_job_manifest_path(export_job["job_id"])
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(export_job, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _export_job_manifest_path(self, job_id: str) -> Path:
        return self._export_dir / f"{_safe_file_part(job_id)}.json"


def _require_mapping(payload: object, name: str) -> dict[str, object]:
    if type(payload) is not dict:
        raise ValueError(f"{name} must be a dictionary")
    object_mapping = cast(dict[object, object], payload)
    if any(type(key) is not str for key in object_mapping):
        raise ValueError(f"{name} keys must be strings")
    return cast(dict[str, object], object_mapping)


def _report_is_ready(report: dict[str, object]) -> bool:
    readiness = _require_mapping(report.get("readiness"), "report readiness")
    return readiness.get("ready") is True


def _report_settlements(report: dict[str, object]) -> tuple[dict[str, object], ...]:
    settlements = report.get("settlements")
    if type(settlements) is not list:
        return ()
    return tuple(_require_mapping(settlement, "report settlement") for settlement in settlements)


def _candidate_summary_from_settlement(settlement: dict[str, object]) -> dict[str, Any]:
    recommendation = _require_mapping(settlement.get("recommendation"), "recommendation")
    return {
        "recommendation_id": _required_string(settlement, "recommendation_id"),
        "race_id": _required_string(settlement, "race_id"),
        "decision": _required_string(recommendation, "decision"),
        "stake_units": _required_int(settlement, "stake_units"),
    }


def _candidate_detail_from_settlement(settlement: dict[str, object]) -> dict[str, Any]:
    recommendation = _require_mapping(settlement.get("recommendation"), "recommendation")
    versions = _require_mapping(recommendation.get("versions"), "recommendation versions")
    detail = _candidate_summary_from_settlement(settlement)
    detail["versions"] = {
        "data": _required_string(versions, "data"),
        "feature": _required_string(versions, "feature"),
        "model": _required_string(versions, "model"),
        "strategy": _required_string(versions, "strategy"),
    }
    detail["explanation"] = _candidate_explanation(recommendation)
    return detail


def _candidate_explanation(recommendation: dict[str, object]) -> str:
    probability = _decimal_from_report(recommendation.get("probability"), "probability")
    odds = _optional_decimal_from_report(recommendation.get("odds"), "odds")
    expected_value = _optional_decimal_from_report(
        recommendation.get("expected_value"),
        "expected_value",
    )
    confidence = _required_string(recommendation, "confidence")
    reason_codes = _string_list(recommendation.get("reason_codes"), "reason_codes")

    odds_text = "等待赛前数据" if odds is None else f"{odds:.2f}"
    expected_value_text = (
        "等待赛前数据" if expected_value is None else _format_signed_percent(expected_value)
    )
    reason_text = "未提供" if not reason_codes else " / ".join(reason_codes)
    return (
        f"模型概率 {_format_percent(probability)}，市场赔率 {odds_text}，"
        f"期望值 {expected_value_text}；置信度 {confidence}，原因 {reason_text}。"
    )


def _string_list(value: object, name: str) -> tuple[str, ...]:
    if type(value) is not list or any(type(item) is not str for item in value):
        raise ValueError(f"{name} must be a list of strings")
    return tuple(cast(list[str], value))


def _required_int(mapping: dict[str, object], key: str) -> int:
    value = mapping.get(key)
    if type(value) is not int:
        raise ValueError(f"{key} must be an integer")
    return value


def _optional_decimal_from_report(value: object, name: str) -> Decimal | None:
    if value is None:
        return None
    return _decimal_from_report(value, name)


def _decimal_from_report(value: object, name: str) -> Decimal:
    if type(value) is not str:
        raise ValueError(f"{name} must be a string decimal")
    try:
        decimal_value = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{name} must be a valid decimal") from exc
    if not decimal_value.is_finite():
        raise ValueError(f"{name} must be finite")
    return decimal_value


def _format_percent(value: Decimal) -> str:
    return f"{value * Decimal('100'):.1f}%"


def _format_signed_percent(value: Decimal) -> str:
    prefix = "+" if value > 0 else ""
    return f"{prefix}{_format_percent(value)}"


def _required_string(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    return _required_plain_string(value, key)


def _required_plain_string(value: object, name: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    return normalized


def _parse_aware_datetime(value: str, name: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return parsed


def _safe_file_part(value: str) -> str:
    safe = "".join(character if character.isalnum() or character == "-" else "-" for character in value)
    return safe.strip("-") or "draft"
