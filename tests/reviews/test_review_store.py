from datetime import UTC, datetime
import json
from pathlib import Path

from boatrace_cal.review_store import FileReviewStore
from boatrace_cal.reviews import RecommendationReview, ReviewDecision


def test_file_review_store_upserts_latest_review_by_recommendation_id(tmp_path: Path) -> None:
    store_path = tmp_path / "server" / "reviews.json"
    store = FileReviewStore(store_path)
    first_review = _review(
        recommendation_id="rec-2",
        race_id="20250102-01-02",
        decision=ReviewDecision.CONFIRMED,
        stake_units=1,
        notes="first",
        reviewed_at=datetime(2026, 7, 11, 3, 30, tzinfo=UTC),
    )
    earlier_review = _review(
        recommendation_id="rec-1",
        race_id="20250102-01-01",
        decision=ReviewDecision.CONFIRMED,
        stake_units=2,
        notes="earlier",
        reviewed_at=datetime(2026, 7, 11, 3, 20, tzinfo=UTC),
    )
    replacement_review = _review(
        recommendation_id="rec-2",
        race_id="20250102-01-02",
        decision=ReviewDecision.PASS,
        stake_units=0,
        notes="odds moved",
        reviewed_at=datetime(2026, 7, 11, 3, 50, tzinfo=UTC),
    )

    assert store.list_reviews() == ()

    store.upsert_reviews((first_review, earlier_review))
    stored_reviews = store.upsert_review(replacement_review)

    assert [review.recommendation_id for review in stored_reviews] == ["rec-1", "rec-2"]
    assert stored_reviews[1].decision is ReviewDecision.PASS
    assert stored_reviews[1].notes == "odds moved"
    assert store.list_reviews() == stored_reviews
    payload = json.loads(store_path.read_text(encoding="utf-8"))
    assert [record["recommendation_id"] for record in payload] == ["rec-1", "rec-2"]
    assert payload[1]["decision"] == "pass"
    assert store_path.read_text(encoding="utf-8").endswith("\n")


def test_file_review_store_builds_confirmed_list_from_persisted_reviews(
    tmp_path: Path,
) -> None:
    store = FileReviewStore(tmp_path / "reviews.json")
    generated_at = datetime(2026, 7, 11, 4, 0, tzinfo=UTC)
    store.upsert_reviews(
        (
            _review(
                recommendation_id="rec-2",
                race_id="20250102-01-02",
                decision=ReviewDecision.PASS,
                stake_units=0,
                notes="skip",
                reviewed_at=datetime(2026, 7, 11, 3, 30, tzinfo=UTC),
            ),
            _review(
                recommendation_id="rec-1",
                race_id="20250102-01-01",
                decision=ReviewDecision.CONFIRMED,
                stake_units=3,
                notes="keep",
                reviewed_at=datetime(2026, 7, 11, 3, 20, tzinfo=UTC),
            ),
        )
    )

    review_list = store.build_confirmed_review_list(
        business_date="2025-01-02",
        generated_at=generated_at,
        generated_by="analyst",
    )

    assert review_list.total_stake_units == 3
    assert [entry.recommendation_id for entry in review_list.entries] == ["rec-1"]
    assert review_list.generated_at == generated_at


def _review(
    *,
    recommendation_id: str,
    race_id: str,
    decision: ReviewDecision,
    stake_units: int,
    notes: str,
    reviewed_at: datetime,
) -> RecommendationReview:
    return RecommendationReview(
        recommendation_id=recommendation_id,
        race_id=race_id,
        decision=decision,
        stake_units=stake_units,
        notes=notes,
        reviewed_at=reviewed_at,
        reviewed_by="analyst",
    )
