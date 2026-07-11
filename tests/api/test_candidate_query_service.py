from pathlib import Path

import pytest

from boatrace_cal.api_services import CandidateQueryService


def test_candidate_query_service_lists_candidates_from_backtest_report() -> None:
    service = CandidateQueryService(
        report_paths={
            "2025-01-02": Path("examples/sample_backtest/report.json"),
        }
    )

    status = service.get_business_date_status("2025-01-02")
    candidate_list = service.list_candidates("2025-01-02")

    assert status == {
        "business_date": "2025-01-02",
        "status": "ready",
        "risk_notice": (
            "历史表现不代表未来结果；本系统只提供分析与回测，"
            "不承诺盈利，不提供自动下单。"
        ),
    }
    assert candidate_list == {
        "business_date": "2025-01-02",
        "candidates": [
            {
                "recommendation_id": "sample-rec-hit",
                "race_id": "20250102-01-01",
                "decision": "select",
                "stake_units": 1,
            },
            {
                "recommendation_id": "sample-rec-miss",
                "race_id": "20250102-01-02",
                "decision": "select",
                "stake_units": 1,
            },
        ],
    }


def test_candidate_query_service_returns_candidate_detail_with_versions_and_explanation() -> None:
    service = CandidateQueryService(
        report_paths={
            "2025-01-02": Path("examples/sample_backtest/report.json"),
        }
    )

    detail = service.get_candidate_detail("2025-01-02", "sample-rec-hit")

    assert detail == {
        "recommendation_id": "sample-rec-hit",
        "race_id": "20250102-01-01",
        "decision": "select",
        "stake_units": 1,
        "versions": {
            "data": "sample-data-v1",
            "feature": "sample-feature-v1",
            "model": "sample-model-v1",
            "strategy": "sample-strategy-v1",
        },
        "explanation": (
            "模型概率 25.0%，市场赔率 5.20，期望值 +30.0%；"
            "置信度 high，原因 positive_ev / sample。"
        ),
    }


def test_candidate_query_service_marks_missing_report_date_empty(tmp_path: Path) -> None:
    service = CandidateQueryService(report_paths={})

    assert service.get_business_date_status("2025-01-03") == {
        "business_date": "2025-01-03",
        "status": "empty",
        "risk_notice": (
            "历史表现不代表未来结果；本系统只提供分析与回测，"
            "不承诺盈利，不提供自动下单。"
        ),
    }
    assert service.list_candidates("2025-01-03") == {
        "business_date": "2025-01-03",
        "candidates": [],
    }

    missing_path = tmp_path / "missing.json"
    service_with_missing_file = CandidateQueryService(
        report_paths={"2025-01-03": missing_path}
    )

    assert service_with_missing_file.get_business_date_status("2025-01-03")[
        "status"
    ] == "empty"


def test_candidate_query_service_rejects_unknown_candidate() -> None:
    service = CandidateQueryService(
        report_paths={
            "2025-01-02": Path("examples/sample_backtest/report.json"),
        }
    )

    with pytest.raises(ValueError, match="recommendation_id"):
        service.get_candidate_detail("2025-01-02", "unknown-rec")
