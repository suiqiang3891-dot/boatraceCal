import json
from pathlib import Path

from boatrace_cal.api_adapter import ApiRequest, AnalysisApiAdapter
from boatrace_cal.errors import ErrorCode


def test_api_adapter_routes_review_workflow_requests(tmp_path: Path) -> None:
    adapter = AnalysisApiAdapter(
        report_paths={},
        review_store_path=tmp_path / "server" / "reviews.json",
        archive_dir=tmp_path / "archives",
        export_dir=tmp_path / "exports",
    )

    import_response = adapter.handle(
        ApiRequest(
            method="POST",
            path="/reviews/import",
            body={
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
            },
        )
    )
    confirmed_response = adapter.handle(
        ApiRequest(
            method="POST",
            path="/reviews/confirmed-list",
            body={
                "business_date": "2025-01-02",
                "generated_at": "2026-07-11T04:00:00+00:00",
                "generated_by": "analyst",
            },
        )
    )
    list_response = adapter.handle(ApiRequest(method="GET", path="/reviews"))
    archive_response = adapter.handle(
        ApiRequest(
            method="POST",
            path="/reviews/archives",
            body={
                "business_date": "2025-01-02",
                "generated_at": "2026-07-11T04:00:00+00:00",
                "generated_by": "analyst",
                "frozen_at": "2026-07-11T04:10:00+00:00",
                "frozen_by": "analyst",
            },
        )
    )
    export_response = adapter.handle(
        ApiRequest(
            method="POST",
            path="/exports/excel",
            body={
                "business_date": "2025-01-02",
                "export_type": "confirmed_list",
                "generated_at": "2026-07-11T04:00:00+00:00",
                "generated_by": "analyst",
            },
        )
    )
    status_response = adapter.handle(
        ApiRequest(method="GET", path=f"/exports/{export_response.body['job_id']}")
    )

    assert import_response.status_code == 200
    assert import_response.body == {"stored_count": 2}
    assert list_response.status_code == 200
    assert [review["recommendation_id"] for review in list_response.body["reviews"]] == [
        "rec-confirmed",
        "rec-pass",
    ]
    assert confirmed_response.status_code == 200
    assert confirmed_response.body["artifact_type"] == "confirmed_review_list"
    assert confirmed_response.body["schema_version"] == "confirmed-review-list-v1"
    assert confirmed_response.body["total_stake_units"] == 2
    assert [entry["recommendation_id"] for entry in confirmed_response.body["entries"]] == [
        "rec-confirmed"
    ]
    assert archive_response.status_code == 201
    assert archive_response.body["artifact_type"] == "confirmed_review_list"
    assert export_response.status_code == 202
    assert export_response.body["status"] == "done"
    assert status_response.status_code == 200
    assert status_response.body == export_response.body


def test_api_adapter_routes_candidate_queries_from_report(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "readiness": {"ready": True},
                "settlements": [
                    {
                        "recommendation_id": "rec-1",
                        "race_id": "20250102-01-01",
                        "stake_units": 1,
                        "recommendation": {
                            "decision": "select",
                            "probability": "0.25",
                            "odds": "5.2",
                            "expected_value": "0.30",
                            "confidence": "high",
                            "versions": {
                                "data": "data-v1",
                                "feature": "feature-v1",
                                "model": "model-v1",
                                "strategy": "strategy-v1",
                            },
                            "reason_codes": ["positive_ev"],
                        },
                    }
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    adapter = AnalysisApiAdapter(
        report_paths={"2025-01-02": report_path},
        review_store_path=tmp_path / "reviews.json",
        archive_dir=tmp_path / "archives",
        export_dir=tmp_path / "exports",
    )

    status_response = adapter.handle(
        ApiRequest(method="GET", path="/business-dates/2025-01-02/status")
    )
    list_response = adapter.handle(
        ApiRequest(method="GET", path="/business-dates/2025-01-02/candidates")
    )
    detail_response = adapter.handle(
        ApiRequest(method="GET", path="/business-dates/2025-01-02/candidates/rec-1")
    )

    assert status_response.status_code == 200
    assert status_response.body["status"] == "ready"
    assert list_response.status_code == 200
    assert list_response.body["candidates"] == [
        {
            "recommendation_id": "rec-1",
            "race_id": "20250102-01-01",
            "decision": "select",
            "stake_units": 1,
        }
    ]
    assert detail_response.status_code == 200
    assert detail_response.body["versions"] == {
        "data": "data-v1",
        "feature": "feature-v1",
        "model": "model-v1",
        "strategy": "strategy-v1",
    }


def test_api_adapter_returns_stable_api_error_for_unknown_resources(tmp_path: Path) -> None:
    adapter = AnalysisApiAdapter(
        report_paths={},
        review_store_path=tmp_path / "reviews.json",
        archive_dir=tmp_path / "archives",
        export_dir=tmp_path / "exports",
    )

    response = adapter.handle(
        ApiRequest(method="GET", path="/business-dates/2025-01-02/candidates/missing")
    )
    unknown_route = adapter.handle(ApiRequest(method="DELETE", path="/reviews/import"))

    assert response.status_code == 404
    assert response.body == {
        "code": ErrorCode.DQ_MISSING_ENTRY.value,
        "message": "未找到请求的资源。",
        "details": {
            "method": "GET",
            "path": "/business-dates/2025-01-02/candidates/missing",
        },
    }
    assert unknown_route.status_code == 404
    assert unknown_route.body["code"] == ErrorCode.DQ_MISSING_ENTRY.value
