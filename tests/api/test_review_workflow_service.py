from datetime import UTC, datetime
import json
from pathlib import Path
from zipfile import ZipFile

from boatrace_cal.api_services import ReviewWorkflowService


def test_review_workflow_service_imports_reviews_and_exports_confirmed_artifacts(
    tmp_path: Path,
) -> None:
    service = ReviewWorkflowService(
        review_store_path=tmp_path / "server" / "reviews.json",
        archive_dir=tmp_path / "archives",
        export_dir=tmp_path / "exports",
    )

    import_response = service.import_reviews(
        {
            "reviews": [
                {
                    "recommendation_id": "rec-confirmed",
                    "race_id": "20250102-01-01",
                    "decision": "confirmed",
                    "stake_units": 2,
                    "notes": "keep",
                    "reviewed_at": "2026-07-11T03:20:00+00:00",
                    "reviewed_by": "analyst",
                },
                {
                    "recommendation_id": "rec-pass",
                    "race_id": "20250102-01-02",
                    "decision": "pass",
                    "stake_units": 0,
                    "notes": "skip",
                    "reviewed_at": "2026-07-11T03:30:00+00:00",
                    "reviewed_by": "analyst",
                },
            ]
        }
    )

    assert import_response == {"stored_count": 2}
    confirmed_list = service.build_confirmed_review_list(
        {
            "business_date": "2025-01-02",
            "generated_at": "2026-07-11T04:00:00+00:00",
            "generated_by": "analyst",
        }
    )
    assert confirmed_list["total_stake_units"] == 2
    assert [entry["recommendation_id"] for entry in confirmed_list["entries"]] == [
        "rec-confirmed"
    ]

    archive = service.freeze_confirmed_review_archive(
        {
            "business_date": "2025-01-02",
            "generated_at": "2026-07-11T04:00:00+00:00",
            "generated_by": "analyst",
            "frozen_at": "2026-07-11T04:10:00+00:00",
            "frozen_by": "analyst",
        }
    )
    assert archive["artifact_type"] == "confirmed_review_list"
    assert archive["schema_version"] == "confirmed-review-list-v1"
    assert archive["checklist"] == confirmed_list

    export_job = service.export_excel(
        {
            "business_date": "2025-01-02",
            "export_type": "confirmed_list",
            "generated_at": "2026-07-11T04:00:00+00:00",
            "generated_by": "analyst",
        }
    )
    assert export_job["status"] == "done"
    assert export_job["content_type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    artifact_path = Path(export_job["artifact_path"])
    assert artifact_path.name == "confirmed-list-2025-01-02.xlsx"
    with ZipFile(artifact_path) as workbook:
        sheet_xml = workbook.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "rec-confirmed" in sheet_xml
    assert "rec-pass" not in sheet_xml
    assert service.get_export_job("confirmed-list-2025-01-02") == export_job
    manifest_path = tmp_path / "exports" / "confirmed-list-2025-01-02.json"
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == export_job


def test_review_workflow_service_exports_full_review_table_xlsx(tmp_path: Path) -> None:
    service = ReviewWorkflowService(
        review_store_path=tmp_path / "reviews.json",
        archive_dir=tmp_path / "archives",
        export_dir=tmp_path / "exports",
    )
    service.import_reviews(
        {
            "reviews": [
                {
                    "recommendation_id": "rec-pending",
                    "race_id": "20250102-01-01",
                    "decision": "pending",
                    "stake_units": 1,
                    "notes": "watch",
                    "reviewed_at": "2026-07-11T03:00:00+00:00",
                    "reviewed_by": "analyst",
                },
                {
                    "recommendation_id": "rec-pass",
                    "race_id": "20250102-01-02",
                    "decision": "pass",
                    "stake_units": 0,
                    "notes": "skip",
                    "reviewed_at": "2026-07-11T03:30:00+00:00",
                    "reviewed_by": "analyst",
                },
            ]
        }
    )

    export_job = service.export_excel(
        {
            "business_date": "2025-01-02",
            "export_type": "review_table",
            "generated_at": datetime(2026, 7, 11, 4, 0, tzinfo=UTC).isoformat(),
            "generated_by": "analyst",
        }
    )

    assert export_job["job_id"] == "review-table-2025-01-02"
    artifact_path = Path(export_job["artifact_path"])
    assert artifact_path.name == "review-table-2025-01-02.xlsx"
    with ZipFile(artifact_path) as workbook:
        sheet_xml = workbook.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "rec-pending" in sheet_xml
    assert "rec-pass" in sheet_xml
    assert "decision" in sheet_xml


def test_review_workflow_service_rejects_unknown_export_type(tmp_path: Path) -> None:
    service = ReviewWorkflowService(
        review_store_path=tmp_path / "reviews.json",
        archive_dir=tmp_path / "archives",
        export_dir=tmp_path / "exports",
    )

    try:
        service.export_excel(
            {
                "business_date": "2025-01-02",
                "export_type": "raw_predictions",
                "generated_at": "2026-07-11T04:00:00+00:00",
                "generated_by": "analyst",
            }
        )
    except ValueError as error:
        assert "export_type" in str(error)
    else:
        raise AssertionError("unknown export_type should be rejected")


def test_review_workflow_service_rejects_unknown_export_job(tmp_path: Path) -> None:
    service = ReviewWorkflowService(
        review_store_path=tmp_path / "reviews.json",
        archive_dir=tmp_path / "archives",
        export_dir=tmp_path / "exports",
    )

    try:
        service.get_export_job("missing-job")
    except ValueError as error:
        assert "job_id" in str(error)
    else:
        raise AssertionError("missing export job should be rejected")


def test_review_workflow_service_archive_response_matches_written_file(tmp_path: Path) -> None:
    service = ReviewWorkflowService(
        review_store_path=tmp_path / "reviews.json",
        archive_dir=tmp_path / "archives",
        export_dir=tmp_path / "exports",
    )
    service.import_reviews(
        {
            "reviews": [
                {
                    "recommendation_id": "rec-confirmed",
                    "race_id": "20250102-01-01",
                    "decision": "confirmed",
                    "stake_units": 1,
                    "notes": "keep",
                    "reviewed_at": "2026-07-11T03:20:00+00:00",
                    "reviewed_by": "analyst",
                }
            ]
        }
    )

    archive = service.freeze_confirmed_review_archive(
        {
            "business_date": "2025-01-02",
            "generated_at": "2026-07-11T04:00:00+00:00",
            "generated_by": "analyst",
            "frozen_at": "2026-07-11T04:10:00+00:00",
            "frozen_by": "analyst",
        }
    )

    archive_path = tmp_path / "archives" / f"{archive['version_id']}.json"
    assert json.loads(archive_path.read_text(encoding="utf-8")) == archive
