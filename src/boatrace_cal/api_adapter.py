"""Dependency-free request adapter for the OpenAPI-backed services."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from boatrace_cal.api_services import CandidateQueryService, ReviewWorkflowService
from boatrace_cal.errors import ErrorCode


@dataclass(frozen=True, slots=True)
class ApiRequest:
    """A small request shape that future HTTP adapters can translate into."""

    method: str
    path: str
    body: object | None = None


@dataclass(frozen=True, slots=True)
class ApiResponse:
    """A JSON-ready response with an HTTP-compatible status code."""

    status_code: int
    body: dict[str, Any]


class AnalysisApiAdapter:
    """Route OpenAPI operations to dependency-free application services."""

    def __init__(
        self,
        *,
        report_paths: dict[str, Path | str],
        review_store_path: Path | str,
        archive_dir: Path | str,
        export_dir: Path | str,
    ) -> None:
        self._candidate_service = CandidateQueryService(report_paths=report_paths)
        self._review_service = ReviewWorkflowService(
            review_store_path=review_store_path,
            archive_dir=archive_dir,
            export_dir=export_dir,
        )

    def handle(self, request: ApiRequest) -> ApiResponse:
        """Return a response for one OpenAPI operation."""

        if type(request) is not ApiRequest:
            raise TypeError("request must be an ApiRequest")
        method = request.method.upper()
        path_parts = _path_parts(request.path)
        try:
            return self._handle_known_route(method, path_parts, request)
        except ValueError as error:
            if _is_missing_resource_error(error):
                return _not_found_response(method=method, path=request.path)
            return _api_error_response(
                status_code=400,
                code=ErrorCode.DQ_MISSING_ENTRY,
                message="请求无法处理。",
                method=method,
                path=request.path,
                detail=str(error),
            )

    def _handle_known_route(
        self,
        method: str,
        path_parts: tuple[str, ...],
        request: ApiRequest,
    ) -> ApiResponse:
        if method == "GET" and _matches(path_parts, ("business-dates", None, "status")):
            return ApiResponse(
                200,
                self._candidate_service.get_business_date_status(path_parts[1]),
            )
        if method == "GET" and _matches(path_parts, ("business-dates", None, "candidates")):
            return ApiResponse(200, self._candidate_service.list_candidates(path_parts[1]))
        if method == "GET" and _matches(
            path_parts,
            ("business-dates", None, "candidates", None),
        ):
            return ApiResponse(
                200,
                self._candidate_service.get_candidate_detail(path_parts[1], path_parts[3]),
            )
        if method == "POST" and path_parts == ("reviews", "import"):
            return ApiResponse(200, self._review_service.import_reviews(_body(request)))
        if method == "POST" and path_parts == ("reviews", "confirmed-list"):
            return ApiResponse(
                200,
                self._review_service.build_confirmed_review_list(_body(request)),
            )
        if method == "POST" and path_parts == ("reviews", "archives"):
            return ApiResponse(
                201,
                self._review_service.freeze_confirmed_review_archive(_body(request)),
            )
        if method == "POST" and path_parts == ("exports", "excel"):
            return ApiResponse(202, self._review_service.export_excel(_body(request)))
        if method == "GET" and _matches(path_parts, ("exports", None)):
            return ApiResponse(200, self._review_service.get_export_job(path_parts[1]))
        return _not_found_response(method=method, path=request.path)


def _path_parts(path: str) -> tuple[str, ...]:
    if type(path) is not str:
        raise TypeError("path must be a string")
    return tuple(part for part in path.strip("/").split("/") if part)


def _matches(parts: tuple[str, ...], pattern: tuple[str | None, ...]) -> bool:
    return len(parts) == len(pattern) and all(
        expected is None or actual == expected
        for actual, expected in zip(parts, pattern, strict=True)
    )


def _body(request: ApiRequest) -> object:
    if request.body is None:
        raise ValueError("request body is required")
    return request.body


def _is_missing_resource_error(error: ValueError) -> bool:
    message = str(error)
    return message == "business_date has no report" or message.startswith(
        ("recommendation_id not found:", "job_id not found:"),
    )


def _not_found_response(*, method: str, path: str) -> ApiResponse:
    return _api_error_response(
        status_code=404,
        code=ErrorCode.DQ_MISSING_ENTRY,
        message="未找到请求的资源。",
        method=method,
        path=path,
    )


def _api_error_response(
    *,
    status_code: int,
    code: ErrorCode,
    message: str,
    method: str,
    path: str,
    detail: str | None = None,
) -> ApiResponse:
    details: dict[str, object] = {"method": method, "path": path}
    if detail is not None:
        details["detail"] = detail
    return ApiResponse(
        status_code,
        {
            "code": code.value,
            "message": message,
            "details": details,
        },
    )
