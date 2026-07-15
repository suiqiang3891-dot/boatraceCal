import json
from pathlib import Path

from boatrace_cal.api_contract import build_openapi_spec, export_openapi_spec_json
from boatrace_cal.errors import ErrorCode


def test_openapi_contract_exposes_review_workflow_without_prediction_mutation() -> None:
    spec = build_openapi_spec()

    assert spec["openapi"] == "3.1.0"
    assert spec["info"]["title"] == "boatraceCal Analysis API"
    assert spec["info"]["version"] == "0.1.0"
    assert set(spec["paths"]) == {
        "/business-dates/{business_date}/status",
        "/business-dates/{business_date}/candidates",
        "/business-dates/{business_date}/candidates/{recommendation_id}",
        "/reviews",
        "/reviews/import",
        "/reviews/confirmed-list",
        "/reviews/archives",
        "/exports/excel",
        "/exports/{job_id}",
    }
    assert spec["paths"]["/exports/{job_id}"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"] == {"$ref": "#/components/schemas/ExportJob"}
    assert spec["paths"]["/reviews/import"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"] == {"$ref": "#/components/schemas/ReviewImportRequest"}
    assert spec["paths"]["/reviews"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"] == {"$ref": "#/components/schemas/ReviewImportRequest"}
    assert spec["paths"]["/reviews/archives"]["post"]["responses"]["201"]["content"][
        "application/json"
    ]["schema"] == {"$ref": "#/components/schemas/ConfirmedReviewArchive"}
    assert "RecommendationReview" in spec["components"]["schemas"]
    assert "ConfirmedReviewList" in spec["components"]["schemas"]
    assert "ConfirmedReviewArchive" in spec["components"]["schemas"]
    review_import = spec["components"]["schemas"]["ReviewImportRequest"]
    assert review_import["properties"]["schema_version"] == {
        "type": "string",
        "const": "recommendation-review-import-v1",
    }
    confirmed_list = spec["components"]["schemas"]["ConfirmedReviewList"]
    assert confirmed_list["required"][:2] == ["artifact_type", "schema_version"]
    assert confirmed_list["properties"]["artifact_type"] == {
        "type": "string",
        "const": "confirmed_review_list",
    }
    assert confirmed_list["properties"]["schema_version"] == {
        "type": "string",
        "const": "confirmed-review-list-v1",
    }
    excel_request = spec["components"]["schemas"]["ExcelExportRequest"]
    assert excel_request["required"] == [
        "business_date",
        "export_type",
        "generated_at",
        "generated_by",
    ]
    assert excel_request["properties"]["export_type"]["enum"] == [
        "review_table",
        "confirmed_list",
    ]
    export_job = spec["components"]["schemas"]["ExportJob"]
    assert export_job["required"][0] == "schema_version"
    assert export_job["properties"]["schema_version"] == {
        "type": "string",
        "const": "export-job-v1",
    }
    assert export_job["properties"]["artifact_path"]["type"] == "string"
    assert export_job["properties"]["content_type"]["const"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    for path in spec["paths"].values():
        assert not any(method in path for method in ("put", "patch", "delete"))


def test_export_openapi_spec_json_writes_deterministic_file(tmp_path: Path) -> None:
    output_path = tmp_path / "openapi" / "openapi.json"

    written_path = export_openapi_spec_json(output_path)

    assert written_path == output_path
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload == build_openapi_spec()
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_openapi_contract_declares_stable_error_responses() -> None:
    spec = build_openapi_spec()

    assert spec["components"]["schemas"]["ApiError"] == {
        "type": "object",
        "required": ["code", "message"],
        "properties": {
            "code": {
                "type": "string",
                "enum": [code.value for code in ErrorCode],
            },
            "message": {"type": "string"},
            "details": {
                "type": "object",
                "additionalProperties": True,
            },
        },
        "additionalProperties": False,
    }

    for path_item in spec["paths"].values():
        for operation in path_item.values():
            assert operation["responses"]["default"] == {
                "description": "Error",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ApiError"},
                    },
                },
            }
