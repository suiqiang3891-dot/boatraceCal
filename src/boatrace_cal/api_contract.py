"""OpenAPI contract for the BOAT RACE analysis workbench."""

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from boatrace_cal.errors import ErrorCode


def build_openapi_spec() -> dict[str, Any]:
    """Return the stable OpenAPI contract for the local analysis API."""

    return deepcopy(_OPENAPI_SPEC)


def export_openapi_spec_json(path: Path | str) -> Path:
    """Write the OpenAPI contract as deterministic UTF-8 JSON."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(build_openapi_spec(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _json_response(schema_ref: str, description: str = "OK") -> dict[str, Any]:
    return {
        "description": description,
        "content": {
            "application/json": {
                "schema": {"$ref": schema_ref},
            },
        },
    }


def _error_response() -> dict[str, Any]:
    return _json_response("#/components/schemas/ApiError", description="Error")


def _json_request(schema_ref: str) -> dict[str, Any]:
    return {
        "required": True,
        "content": {
            "application/json": {
                "schema": {"$ref": schema_ref},
            },
        },
    }


_BUSINESS_DATE_PARAMETER: dict[str, Any] = {
    "name": "business_date",
    "in": "path",
    "required": True,
    "schema": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
}

_RECOMMENDATION_ID_PARAMETER: dict[str, Any] = {
    "name": "recommendation_id",
    "in": "path",
    "required": True,
    "schema": {"type": "string", "minLength": 1},
}

_JOB_ID_PARAMETER: dict[str, Any] = {
    "name": "job_id",
    "in": "path",
    "required": True,
    "schema": {"type": "string", "minLength": 1},
}

_OPENAPI_SPEC: dict[str, Any] = {
    "openapi": "3.1.0",
    "info": {
        "title": "boatraceCal Analysis API",
        "version": "0.1.0",
        "description": (
            "Decision-support API for paper BOAT RACE analysis. "
            "It does not expose automatic wagering operations."
        ),
    },
    "paths": {
        "/business-dates/{business_date}/status": {
            "get": {
                "summary": "Get analysis status for a business date",
                "parameters": [_BUSINESS_DATE_PARAMETER],
                "responses": {
                    "200": _json_response("#/components/schemas/BusinessDateStatus"),
                    "default": _error_response(),
                },
            }
        },
        "/business-dates/{business_date}/candidates": {
            "get": {
                "summary": "List recommendation candidates for a business date",
                "parameters": [_BUSINESS_DATE_PARAMETER],
                "responses": {
                    "200": _json_response("#/components/schemas/CandidateList"),
                    "default": _error_response(),
                },
            }
        },
        "/business-dates/{business_date}/candidates/{recommendation_id}": {
            "get": {
                "summary": "Get one recommendation candidate explanation",
                "parameters": [_BUSINESS_DATE_PARAMETER, _RECOMMENDATION_ID_PARAMETER],
                "responses": {
                    "200": _json_response("#/components/schemas/CandidateDetail"),
                    "default": _error_response(),
                },
            }
        },
        "/reviews": {
            "get": {
                "summary": "List persisted analyst review records",
                "responses": {
                    "200": _json_response("#/components/schemas/ReviewImportRequest"),
                    "default": _error_response(),
                },
            }
        },
        "/reviews/import": {
            "post": {
                "summary": "Import analyst review records",
                "requestBody": _json_request("#/components/schemas/ReviewImportRequest"),
                "responses": {
                    "200": _json_response("#/components/schemas/ReviewImportResponse"),
                    "default": _error_response(),
                },
            }
        },
        "/reviews/confirmed-list": {
            "post": {
                "summary": "Build the current confirmed review checklist",
                "requestBody": _json_request("#/components/schemas/ConfirmedReviewListRequest"),
                "responses": {
                    "200": _json_response("#/components/schemas/ConfirmedReviewList"),
                    "default": _error_response(),
                },
            }
        },
        "/reviews/archives": {
            "post": {
                "summary": "Freeze the current confirmed review checklist",
                "requestBody": _json_request("#/components/schemas/ConfirmedReviewArchiveRequest"),
                "responses": {
                    "201": _json_response(
                        "#/components/schemas/ConfirmedReviewArchive",
                        description="Created",
                    ),
                    "default": _error_response(),
                },
            }
        },
        "/exports/excel": {
            "post": {
                "summary": "Request an Excel-compatible export artifact",
                "requestBody": _json_request("#/components/schemas/ExcelExportRequest"),
                "responses": {
                    "202": _json_response("#/components/schemas/ExportJob"),
                    "default": _error_response(),
                },
            }
        },
        "/exports/{job_id}": {
            "get": {
                "summary": "Get an export artifact status",
                "parameters": [_JOB_ID_PARAMETER],
                "responses": {
                    "200": _json_response("#/components/schemas/ExportJob"),
                    "default": _error_response(),
                },
            }
        },
    },
    "components": {
        "schemas": {
            "ApiError": {
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
            },
            "BusinessDateStatus": {
                "type": "object",
                "required": ["business_date", "status", "risk_notice"],
                "properties": {
                    "business_date": {"type": "string"},
                    "status": {"type": "string", "enum": ["ready", "blocked", "empty"]},
                    "risk_notice": {"type": "string"},
                },
                "additionalProperties": False,
            },
            "CandidateList": {
                "type": "object",
                "required": ["business_date", "candidates"],
                "properties": {
                    "business_date": {"type": "string"},
                    "candidates": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/CandidateSummary"},
                    },
                },
                "additionalProperties": False,
            },
            "CandidateSummary": {
                "type": "object",
                "required": ["recommendation_id", "race_id", "decision", "stake_units"],
                "properties": {
                    "recommendation_id": {"type": "string"},
                    "race_id": {"type": "string"},
                    "decision": {"type": "string", "enum": ["select", "pass"]},
                    "stake_units": {"type": "integer", "minimum": 0},
                },
                "additionalProperties": False,
            },
            "CandidateDetail": {
                "allOf": [
                    {"$ref": "#/components/schemas/CandidateSummary"},
                    {
                        "type": "object",
                        "required": ["versions", "explanation"],
                        "properties": {
                            "versions": {"$ref": "#/components/schemas/ArtifactVersions"},
                            "explanation": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                ]
            },
            "ArtifactVersions": {
                "type": "object",
                "required": ["data", "feature", "model", "strategy"],
                "properties": {
                    "data": {"type": "string"},
                    "feature": {"type": "string"},
                    "model": {"type": "string"},
                    "strategy": {"type": "string"},
                },
                "additionalProperties": False,
            },
            "RecommendationReview": {
                "type": "object",
                "required": [
                    "recommendation_id",
                    "race_id",
                    "decision",
                    "stake_units",
                    "notes",
                    "reviewed_at",
                    "reviewed_by",
                ],
                "properties": {
                    "recommendation_id": {"type": "string"},
                    "race_id": {"type": "string"},
                    "decision": {
                        "type": "string",
                        "enum": ["pending", "confirmed", "pass"],
                    },
                    "stake_units": {"type": "integer", "minimum": 0},
                    "notes": {"type": "string"},
                    "reviewed_at": {"type": "string", "format": "date-time"},
                    "reviewed_by": {"type": "string"},
                },
                "additionalProperties": False,
            },
            "ReviewImportRequest": {
                "type": "object",
                "required": ["reviews"],
                "properties": {
                    "schema_version": {
                        "type": "string",
                        "const": "recommendation-review-import-v1",
                    },
                    "reviews": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/RecommendationReview"},
                    }
                },
                "additionalProperties": False,
            },
            "ReviewImportResponse": {
                "type": "object",
                "required": ["stored_count"],
                "properties": {"stored_count": {"type": "integer", "minimum": 0}},
                "additionalProperties": False,
            },
            "ConfirmedReviewListRequest": {
                "type": "object",
                "required": ["business_date", "generated_at", "generated_by"],
                "properties": {
                    "business_date": {"type": "string"},
                    "generated_at": {"type": "string", "format": "date-time"},
                    "generated_by": {"type": "string"},
                },
                "additionalProperties": False,
            },
            "ConfirmedReviewList": {
                "type": "object",
                "required": [
                    "business_date",
                    "generated_at",
                    "generated_by",
                    "risk_notice",
                    "total_stake_units",
                    "entries",
                ],
                "properties": {
                    "business_date": {"type": "string"},
                    "generated_at": {"type": "string", "format": "date-time"},
                    "generated_by": {"type": "string"},
                    "risk_notice": {"type": "string"},
                    "total_stake_units": {"type": "integer", "minimum": 0},
                    "entries": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/ConfirmedReviewEntry"},
                    },
                },
                "additionalProperties": False,
            },
            "ConfirmedReviewEntry": {
                "type": "object",
                "required": [
                    "recommendation_id",
                    "race_id",
                    "stake_units",
                    "notes",
                    "reviewed_at",
                    "reviewed_by",
                ],
                "properties": {
                    "recommendation_id": {"type": "string"},
                    "race_id": {"type": "string"},
                    "stake_units": {"type": "integer", "minimum": 1},
                    "notes": {"type": "string"},
                    "reviewed_at": {"type": "string", "format": "date-time"},
                    "reviewed_by": {"type": "string"},
                },
                "additionalProperties": False,
            },
            "ConfirmedReviewArchiveRequest": {
                "allOf": [
                    {"$ref": "#/components/schemas/ConfirmedReviewListRequest"},
                    {
                        "type": "object",
                        "required": ["frozen_at", "frozen_by"],
                        "properties": {
                            "frozen_at": {"type": "string", "format": "date-time"},
                            "frozen_by": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                ]
            },
            "ConfirmedReviewArchive": {
                "type": "object",
                "required": [
                    "artifact_type",
                    "schema_version",
                    "version_id",
                    "content_sha256",
                    "frozen_at",
                    "frozen_by",
                    "checklist",
                ],
                "properties": {
                    "artifact_type": {
                        "type": "string",
                        "const": "confirmed_review_list",
                    },
                    "schema_version": {
                        "type": "string",
                        "const": "confirmed-review-list-v1",
                    },
                    "version_id": {"type": "string"},
                    "content_sha256": {"type": "string", "minLength": 64, "maxLength": 64},
                    "frozen_at": {"type": "string", "format": "date-time"},
                    "frozen_by": {"type": "string"},
                    "checklist": {"$ref": "#/components/schemas/ConfirmedReviewList"},
                },
                "additionalProperties": False,
            },
            "ExcelExportRequest": {
                "type": "object",
                "required": [
                    "business_date",
                    "export_type",
                    "generated_at",
                    "generated_by",
                ],
                "properties": {
                    "business_date": {"type": "string"},
                    "export_type": {
                        "type": "string",
                        "enum": ["review_table", "confirmed_list"],
                    },
                    "generated_at": {"type": "string", "format": "date-time"},
                    "generated_by": {"type": "string"},
                },
                "additionalProperties": False,
            },
            "ExportJob": {
                "type": "object",
                "required": ["job_id", "status", "artifact_path", "content_type"],
                "properties": {
                    "job_id": {"type": "string"},
                    "status": {"type": "string", "enum": ["queued", "running", "done", "failed"]},
                    "artifact_path": {"type": "string"},
                    "content_type": {
                        "type": "string",
                        "const": (
                            "application/vnd.openxmlformats-officedocument."
                            "spreadsheetml.sheet"
                        ),
                    },
                },
                "additionalProperties": False,
            },
        }
    },
}
