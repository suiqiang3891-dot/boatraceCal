from datetime import UTC, datetime
import json
from pathlib import Path

import pytest

from boatrace_cal.reviews import (
    RecommendationReview,
    ReviewDecision,
    build_confirmed_review_list,
    confirmed_review_list_to_dict,
    export_reviews_json,
    load_reviews_json,
    review_to_dict,
)


def test_recommendation_review_validates_auditable_fields() -> None:
    review = RecommendationReview(
        recommendation_id=" sample-rec-hit ",
        race_id="20250102-01-01",
        decision=ReviewDecision.CONFIRMED,
        stake_units=2,
        notes=" 盘口复核后保留 ",
        reviewed_at=datetime(2026, 7, 11, 3, 0, tzinfo=UTC),
        reviewed_by=" analyst ",
    )

    assert review.recommendation_id == "sample-rec-hit"
    assert review.notes == "盘口复核后保留"
    assert review.reviewed_by == "analyst"
    assert review_to_dict(review) == {
        "recommendation_id": "sample-rec-hit",
        "race_id": "20250102-01-01",
        "decision": "confirmed",
        "stake_units": 2,
        "notes": "盘口复核后保留",
        "reviewed_at": "2026-07-11T03:00:00+00:00",
        "reviewed_by": "analyst",
    }


def test_recommendation_review_rejects_invalid_pass_stake_units() -> None:
    with pytest.raises(ValueError, match="pass reviews must use zero stake units"):
        RecommendationReview(
            recommendation_id="sample-rec-hit",
            race_id="20250102-01-01",
            decision=ReviewDecision.PASS,
            stake_units=1,
            notes="skip",
            reviewed_at=datetime(2026, 7, 11, 3, 0, tzinfo=UTC),
            reviewed_by="analyst",
        )


def test_build_confirmed_review_list_keeps_only_confirmed_positive_stakes() -> None:
    generated_at = datetime(2026, 7, 11, 4, 0, tzinfo=UTC)
    reviews = (
        RecommendationReview(
            recommendation_id="rec-2",
            race_id="20250102-01-02",
            decision=ReviewDecision.CONFIRMED,
            stake_units=1,
            notes="second",
            reviewed_at=datetime(2026, 7, 11, 3, 30, tzinfo=UTC),
            reviewed_by="analyst",
        ),
        RecommendationReview(
            recommendation_id="rec-pass",
            race_id="20250102-01-03",
            decision=ReviewDecision.PASS,
            stake_units=0,
            notes="odds moved",
            reviewed_at=datetime(2026, 7, 11, 3, 40, tzinfo=UTC),
            reviewed_by="analyst",
        ),
        RecommendationReview(
            recommendation_id="rec-1",
            race_id="20250102-01-01",
            decision=ReviewDecision.CONFIRMED,
            stake_units=3,
            notes="first",
            reviewed_at=datetime(2026, 7, 11, 3, 20, tzinfo=UTC),
            reviewed_by="analyst",
        ),
    )

    review_list = build_confirmed_review_list(
        reviews=reviews,
        business_date="2025-01-02",
        generated_at=generated_at,
        generated_by="analyst",
    )

    assert review_list.business_date == "2025-01-02"
    assert review_list.generated_at == generated_at
    assert review_list.generated_by == "analyst"
    assert review_list.total_stake_units == 4
    assert [entry.recommendation_id for entry in review_list.entries] == ["rec-1", "rec-2"]
    assert review_list.risk_notice == (
        "历史表现不代表未来结果；本系统只提供分析与回测，不承诺盈利，不提供自动下单。"
    )


def test_review_json_round_trips_auditable_records(tmp_path: Path) -> None:
    reviews_path = tmp_path / "reviews" / "reviews.json"
    reviews = (
        RecommendationReview(
            recommendation_id="rec-1",
            race_id="20250102-01-01",
            decision=ReviewDecision.CONFIRMED,
            stake_units=2,
            notes="keep",
            reviewed_at=datetime(2026, 7, 11, 3, 0, tzinfo=UTC),
            reviewed_by="analyst",
        ),
        RecommendationReview(
            recommendation_id="rec-pass",
            race_id="20250102-01-02",
            decision=ReviewDecision.PASS,
            stake_units=0,
            notes="skip",
            reviewed_at=datetime(2026, 7, 11, 3, 5, tzinfo=UTC),
            reviewed_by="analyst",
        ),
    )

    written_path = export_reviews_json(reviews, reviews_path)
    loaded_reviews = load_reviews_json(written_path)

    assert written_path == reviews_path
    assert loaded_reviews == reviews
    payload = json.loads(reviews_path.read_text(encoding="utf-8"))
    assert payload[0]["recommendation_id"] == "rec-1"
    assert reviews_path.read_text(encoding="utf-8").endswith("\n")


def test_review_json_loader_accepts_openapi_import_request_envelope(tmp_path: Path) -> None:
    reviews_path = tmp_path / "browser" / "reviews.json"
    reviews_path.parent.mkdir(parents=True)
    reviews_path.write_text(
        json.dumps(
            {
                "reviews": [
                    {
                        "recommendation_id": "rec-envelope",
                        "race_id": "20250102-01-01",
                        "decision": "confirmed",
                        "stake_units": 2,
                        "notes": "from browser",
                        "reviewed_at": "2026-07-11T03:00:00+00:00",
                        "reviewed_by": "browser-analyst",
                    }
                ]
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    loaded_reviews = load_reviews_json(reviews_path)

    assert len(loaded_reviews) == 1
    assert loaded_reviews[0].recommendation_id == "rec-envelope"
    assert loaded_reviews[0].decision is ReviewDecision.CONFIRMED


def test_confirmed_review_list_to_dict_serializes_totals() -> None:
    generated_at = datetime(2026, 7, 11, 4, 0, tzinfo=UTC)
    review_list = build_confirmed_review_list(
        reviews=(
            RecommendationReview(
                recommendation_id="rec-1",
                race_id="20250102-01-01",
                decision=ReviewDecision.CONFIRMED,
                stake_units=3,
                notes="first",
                reviewed_at=datetime(2026, 7, 11, 3, 20, tzinfo=UTC),
                reviewed_by="analyst",
            ),
        ),
        business_date="2025-01-02",
        generated_at=generated_at,
        generated_by="analyst",
    )

    assert confirmed_review_list_to_dict(review_list) == {
        "business_date": "2025-01-02",
        "generated_at": "2026-07-11T04:00:00+00:00",
        "generated_by": "analyst",
        "risk_notice": (
            "历史表现不代表未来结果；本系统只提供分析与回测，不承诺盈利，不提供自动下单。"
        ),
        "total_stake_units": 3,
        "entries": [
            {
                "recommendation_id": "rec-1",
                "race_id": "20250102-01-01",
                "stake_units": 3,
                "notes": "first",
                "reviewed_at": "2026-07-11T03:20:00+00:00",
                "reviewed_by": "analyst",
            }
        ],
    }
