"""Small dependency-free HTTP surface for the local analysis API."""

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from socketserver import BaseServer
from typing import Any
from urllib.parse import urlsplit

from boatrace_cal.api_adapter import ApiRequest, AnalysisApiAdapter
from boatrace_cal.errors import ErrorCode


JsonObject = dict[str, Any]


def create_api_http_handler(
    adapter: AnalysisApiAdapter,
    *,
    allowed_origin: str = "*",
) -> type[BaseHTTPRequestHandler]:
    """Create a request handler bound to one analysis API adapter."""

    if type(adapter) is not AnalysisApiAdapter:
        raise TypeError("adapter must be an AnalysisApiAdapter")
    if type(allowed_origin) is not str or not allowed_origin:
        raise ValueError("allowed_origin must be a non-empty string")

    class AnalysisApiHttpHandler(BaseHTTPRequestHandler):
        server_version = "boatraceCalAPI/0.1"

        def do_OPTIONS(self) -> None:
            self._send_json(HTTPStatus.NO_CONTENT, {})

        def do_GET(self) -> None:
            self._handle_api_request("GET")

        def do_POST(self) -> None:
            try:
                body = self._read_json_body()
            except ValueError as error:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    _api_error_body(
                        ErrorCode.DQ_MISSING_ENTRY,
                        "Request JSON could not be parsed.",
                        detail=str(error),
                    ),
                )
                return
            self._handle_api_request("POST", body=body)

        def log_message(self, format: str, *args: object) -> None:
            return

        def _handle_api_request(self, method: str, body: object | None = None) -> None:
            response = adapter.handle(
                ApiRequest(
                    method=method,
                    path=urlsplit(self.path).path,
                    body=body,
                )
            )
            self._send_json(response.status_code, response.body)

        def _read_json_body(self) -> object:
            content_length = self.headers.get("Content-Length", "0")
            try:
                length = int(content_length)
            except ValueError as exc:
                raise ValueError("Content-Length must be an integer") from exc
            if length <= 0:
                return None
            raw_body = self.rfile.read(length)
            try:
                payload: object = json.loads(raw_body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("request body must be UTF-8 JSON") from exc
            return payload

        def _send_json(self, status_code: int | HTTPStatus, payload: object) -> None:
            body = (
                b""
                if int(status_code) == HTTPStatus.NO_CONTENT
                else json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            )
            self.send_response(int(status_code))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", allowed_origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            if body:
                self.wfile.write(body)

    return AnalysisApiHttpHandler


def create_api_http_server(
    server_address: tuple[str, int],
    handler_class: type[BaseHTTPRequestHandler],
) -> ThreadingHTTPServer:
    """Create a ThreadingHTTPServer for tests and CLI startup."""

    server = ThreadingHTTPServer(server_address, handler_class)
    server.daemon_threads = True
    return server


def serve_api_http(
    server_address: tuple[str, int],
    adapter: AnalysisApiAdapter,
    *,
    allowed_origin: str = "*",
) -> None:
    """Serve the local API until interrupted by the caller."""

    handler_class = create_api_http_handler(adapter, allowed_origin=allowed_origin)
    with create_api_http_server(server_address, handler_class) as server:
        _serve_forever(server)


def _serve_forever(server: BaseServer) -> None:
    server.serve_forever()


def _api_error_body(code: ErrorCode, message: str, *, detail: str) -> JsonObject:
    return {
        "code": code.value,
        "message": message,
        "details": {"detail": detail},
    }
