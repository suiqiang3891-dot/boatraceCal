"""File-backed persistence for analyst recommendation reviews."""

from datetime import datetime
from pathlib import Path

from boatrace_cal.reviews import (
    ConfirmedReviewList,
    RecommendationReview,
    build_confirmed_review_list,
    export_reviews_json,
    load_reviews_json,
)


class FileReviewStore:
    """Persist analyst reviews in the public review JSON contract."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def list_reviews(self) -> tuple[RecommendationReview, ...]:
        if not self._path.exists():
            return ()
        return load_reviews_json(self._path)

    def upsert_review(self, review: RecommendationReview) -> tuple[RecommendationReview, ...]:
        if type(review) is not RecommendationReview:
            raise TypeError("review must be a RecommendationReview")
        return self.upsert_reviews((review,))

    def upsert_reviews(
        self,
        reviews: tuple[RecommendationReview, ...],
    ) -> tuple[RecommendationReview, ...]:
        if type(reviews) is not tuple or any(type(review) is not RecommendationReview for review in reviews):
            raise ValueError("reviews must be a tuple of RecommendationReview")

        merged = {review.recommendation_id: review for review in self.list_reviews()}
        for review in reviews:
            merged[review.recommendation_id] = review

        stored_reviews = tuple(
            sorted(merged.values(), key=lambda review: (review.race_id, review.recommendation_id))
        )
        self._write_reviews(stored_reviews)
        return stored_reviews

    def build_confirmed_review_list(
        self,
        *,
        business_date: str,
        generated_at: datetime,
        generated_by: str,
    ) -> ConfirmedReviewList:
        return build_confirmed_review_list(
            reviews=self.list_reviews(),
            business_date=business_date,
            generated_at=generated_at,
            generated_by=generated_by,
        )

    def _write_reviews(self, reviews: tuple[RecommendationReview, ...]) -> None:
        temp_path = self._path.with_name(f"{self._path.name}.tmp")
        export_reviews_json(reviews, temp_path)
        temp_path.replace(self._path)
