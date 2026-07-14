from __future__ import annotations

from http.client import HTTPConnection
import json
from pathlib import Path
from threading import Thread

from boatrace_cal.api_adapter import AnalysisApiAdapter
from boatrace_cal.api_server import create_api_http_handler, create_api_http_server


def test_api_http_server_serves_candidate_status_with_cors(tmp_path: Path) -> None:
    report_path = tmp_path / "reports" / "report.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        json.dumps({"readiness": {"ready": True}, "settlements": []}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    adapter = AnalysisApiAdapter(
        report_paths={"2025-01-02": report_path},
        review_store_path=tmp_path / "server" / "reviews.json",
        archive_dir=tmp_path / "archives",
        export_dir=tmp_path / "exports",
    )

    with create_api_http_server(
        ("127.0.0.1", 0),
        create_api_http_handler(adapter),
    ) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        connection = HTTPConnection("127.0.0.1", server.server_port)
        try:
            connection.request("GET", "/business-dates/2025-01-02/status")
            response = connection.getresponse()
            payload = json.loads(response.read().decode("utf-8"))
        finally:
            connection.close()
            server.shutdown()
            thread.join(timeout=5)

    assert response.status == 200
    assert response.getheader("Access-Control-Allow-Origin") == "*"
    assert response.getheader("Content-Type") == "application/json; charset=utf-8"
    assert payload["status"] == "ready"
    assert payload["business_date"] == "2025-01-02"


def test_api_http_server_serves_empty_cors_preflight(tmp_path: Path) -> None:
    adapter = AnalysisApiAdapter(
        report_paths={},
        review_store_path=tmp_path / "server" / "reviews.json",
        archive_dir=tmp_path / "archives",
        export_dir=tmp_path / "exports",
    )

    with create_api_http_server(
        ("127.0.0.1", 0),
        create_api_http_handler(adapter, allowed_origin="http://127.0.0.1:5176"),
    ) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        connection = HTTPConnection("127.0.0.1", server.server_port)
        try:
            connection.request("OPTIONS", "/reviews/import")
            response = connection.getresponse()
            body = response.read()
        finally:
            connection.close()
            server.shutdown()
            thread.join(timeout=5)

    assert response.status == 204
    assert response.getheader("Access-Control-Allow-Origin") == "http://127.0.0.1:5176"
    assert response.getheader("Access-Control-Allow-Methods") == "GET, POST, OPTIONS"
    assert response.getheader("Access-Control-Allow-Headers") == "Content-Type"
    assert response.getheader("Content-Length") == "0"
    assert body == b""


def test_api_http_server_imports_review_records_from_json_body(tmp_path: Path) -> None:
    store_path = tmp_path / "server" / "reviews.json"
    adapter = AnalysisApiAdapter(
        report_paths={},
        review_store_path=store_path,
        archive_dir=tmp_path / "archives",
        export_dir=tmp_path / "exports",
    )
    body = {
        "reviews": [
            {
                "recommendation_id": "rec-http",
                "race_id": "20250102-01-01",
                "decision": "confirmed",
                "stake_units": 2,
                "notes": "from browser",
                "reviewed_at": "2026-07-12T04:00:00+00:00",
                "reviewed_by": "browser-analyst",
            }
        ]
    }

    with create_api_http_server(
        ("127.0.0.1", 0),
        create_api_http_handler(adapter),
    ) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        connection = HTTPConnection("127.0.0.1", server.server_port)
        try:
            connection.request(
                "POST",
                "/reviews/import",
                body=json.dumps(body),
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            payload = json.loads(response.read().decode("utf-8"))
        finally:
            connection.close()
            server.shutdown()
            thread.join(timeout=5)

    assert response.status == 200
    assert payload == {"stored_count": 1}
    stored_reviews = json.loads(store_path.read_text(encoding="utf-8"))
    assert stored_reviews[0]["recommendation_id"] == "rec-http"


def test_api_http_server_lists_review_records(tmp_path: Path) -> None:
    store_path = tmp_path / "server" / "reviews.json"
    adapter = AnalysisApiAdapter(
        report_paths={},
        review_store_path=store_path,
        archive_dir=tmp_path / "archives",
        export_dir=tmp_path / "exports",
    )
    store_path.parent.mkdir(parents=True)
    store_path.write_text(
        json.dumps(
            [
                {
                    "recommendation_id": "rec-http",
                    "race_id": "20250102-01-01",
                    "decision": "confirmed",
                    "stake_units": 1,
                    "notes": "from store",
                    "reviewed_at": "2026-07-12T04:00:00+00:00",
                    "reviewed_by": "browser-analyst",
                }
            ],
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    with create_api_http_server(
        ("127.0.0.1", 0),
        create_api_http_handler(adapter),
    ) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        connection = HTTPConnection("127.0.0.1", server.server_port)
        try:
            connection.request("GET", "/reviews")
            response = connection.getresponse()
            payload = json.loads(response.read().decode("utf-8"))
        finally:
            connection.close()
            server.shutdown()
            thread.join(timeout=5)

    assert response.status == 200
    assert payload["reviews"][0]["recommendation_id"] == "rec-http"
