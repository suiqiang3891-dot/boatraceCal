from datetime import UTC, datetime

import pytest

from boatrace_cal.reviews import (
    RecommendationReview,
    ReviewDecision,
    build_confirmed_review_list,
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
