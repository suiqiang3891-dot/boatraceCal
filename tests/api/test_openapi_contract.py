import json
from pathlib import Path

from boatrace_cal.api_contract import build_openapi_spec, export_openapi_spec_json


def test_openapi_contract_exposes_review_workflow_without_prediction_mutation() -> None:
    spec = build_openapi_spec()

    assert spec["openapi"] == "3.1.0"
    assert spec["info"]["title"] == "boatraceCal Analysis API"
    assert spec["info"]["version"] == "0.1.0"
    assert set(spec["paths"]) == {
        "/business-dates/{business_date}/status",
        "/business-dates/{business_date}/candidates",
        "/business-dates/{business_date}/candidates/{recommendation_id}",
        "/reviews/import",
        "/reviews/confirmed-list",
        "/reviews/archives",
        "/exports/excel",
    }
    assert spec["paths"]["/reviews/import"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"] == {"$ref": "#/components/schemas/ReviewImportRequest"}
    assert spec["paths"]["/reviews/archives"]["post"]["responses"]["201"]["content"][
        "application/json"
    ]["schema"] == {"$ref": "#/components/schemas/ConfirmedReviewArchive"}
    assert "RecommendationReview" in spec["components"]["schemas"]
    assert "ConfirmedReviewList" in spec["components"]["schemas"]
    assert "ConfirmedReviewArchive" in spec["components"]["schemas"]
    for path in spec["paths"].values():
        assert not any(method in path for method in ("put", "patch", "delete"))


def test_export_openapi_spec_json_writes_deterministic_file(tmp_path: Path) -> None:
    output_path = tmp_path / "openapi" / "openapi.json"

    written_path = export_openapi_spec_json(output_path)

    assert written_path == output_path
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload == build_openapi_spec()
    assert output_path.read_text(encoding="utf-8").endswith("\n")
