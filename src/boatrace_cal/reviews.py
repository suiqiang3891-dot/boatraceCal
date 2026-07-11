"""Analyst review records for recommendations and confirmed paper lists."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import json
from pathlib import Path
from typing import Any
from typing import cast


RISK_NOTICE = "历史表现不代表未来结果；本系统只提供分析与回测，不承诺盈利，不提供自动下单。"


class ReviewDecision(StrEnum):
    """Analyst disposition for one recommendation."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    PASS = "pass"


@dataclass(frozen=True, slots=True)
class RecommendationReview:
    """Auditable human review state kept separate from model recommendations."""

    recommendation_id: str
    race_id: str
    decision: ReviewDecision
    stake_units: int
    notes: str
    reviewed_at: datetime
    reviewed_by: str

    def __post_init__(self) -> None:
        if type(self.recommendation_id) is not str:
            raise ValueError("recommendation id must be a string")
        recommendation_id = self.recommendation_id.strip()
        if not recommendation_id:
            raise ValueError("recommendation id must not be empty")
        object.__setattr__(self, "recommendation_id", recommendation_id)

        if type(self.race_id) is not str:
            raise ValueError("race id must be a string")
        race_id = self.race_id.strip()
        if not race_id:
            raise ValueError("race id must not be empty")
        object.__setattr__(self, "race_id", race_id)

        if type(self.decision) is not ReviewDecision:
            raise ValueError("decision must be a ReviewDecision")
        if type(self.stake_units) is not int:
            raise ValueError("stake units must be an integer")
        if self.stake_units < 0:
            raise ValueError("stake units must not be negative")
        if self.decision is ReviewDecision.PASS and self.stake_units != 0:
            raise ValueError("pass reviews must use zero stake units")

        if type(self.notes) is not str:
            raise ValueError("notes must be a string")
        object.__setattr__(self, "notes", self.notes.strip())

        if type(self.reviewed_at) is not datetime:
            raise ValueError("reviewed_at must be a datetime")
        if self.reviewed_at.tzinfo is None or self.reviewed_at.utcoffset() is None:
            raise ValueError("reviewed_at must be timezone-aware")

        if type(self.reviewed_by) is not str:
            raise ValueError("reviewed_by must be a string")
        reviewed_by = self.reviewed_by.strip()
        if not reviewed_by:
            raise ValueError("reviewed_by must not be empty")
        object.__setattr__(self, "reviewed_by", reviewed_by)


@dataclass(frozen=True, slots=True)
class ConfirmedReviewEntry:
    """One confirmed recommendation in an analyst-produced list."""

    recommendation_id: str
    race_id: str
    stake_units: int
    notes: str
    reviewed_at: datetime
    reviewed_by: str


@dataclass(frozen=True, slots=True)
class ConfirmedReviewList:
    """Paper execution checklist produced from confirmed analyst reviews."""

    business_date: str
    generated_at: datetime
    generated_by: str
    risk_notice: str
    entries: tuple[ConfirmedReviewEntry, ...]

    @property
    def total_stake_units(self) -> int:
        return sum(entry.stake_units for entry in self.entries)


def review_to_dict(review: RecommendationReview) -> dict[str, Any]:
    """Serialize a review record to a JSON-ready mapping."""

    if type(review) is not RecommendationReview:
        raise TypeError("review must be a RecommendationReview")
    return {
        "recommendation_id": review.recommendation_id,
        "race_id": review.race_id,
        "decision": review.decision.value,
        "stake_units": review.stake_units,
        "notes": review.notes,
        "reviewed_at": review.reviewed_at.isoformat(),
        "reviewed_by": review.reviewed_by,
    }


def export_reviews_json(
    reviews: tuple[RecommendationReview, ...],
    path: Path | str,
) -> Path:
    """Write review records as deterministic UTF-8 JSON and return the path."""

    if type(reviews) is not tuple or any(type(review) is not RecommendationReview for review in reviews):
        raise ValueError("reviews must be a tuple of RecommendationReview")
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [review_to_dict(review) for review in reviews]
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def load_reviews_json(path: Path | str) -> tuple[RecommendationReview, ...]:
    """Load review records from a JSON file using the public review contract."""

    raw_payload: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    if type(raw_payload) is not list:
        raise ValueError("review JSON must be a list")
    return tuple(review_from_dict(item) for item in raw_payload)


def review_from_dict(payload: object) -> RecommendationReview:
    """Parse one review record from a JSON-ready mapping."""

    if type(payload) is not dict:
        raise ValueError("review record must be a dictionary")
    object_mapping = cast(dict[object, object], payload)
    if any(type(key) is not str for key in object_mapping):
        raise ValueError("review record keys must be strings")
    mapping = cast(dict[str, object], object_mapping)
    return RecommendationReview(
        recommendation_id=_required_string(mapping, "recommendation_id"),
        race_id=_required_string(mapping, "race_id"),
        decision=ReviewDecision(_required_string(mapping, "decision")),
        stake_units=_required_int(mapping, "stake_units"),
        notes=_required_string(mapping, "notes"),
        reviewed_at=_parse_aware_datetime(_required_string(mapping, "reviewed_at"), "reviewed_at"),
        reviewed_by=_required_string(mapping, "reviewed_by"),
    )


def build_confirmed_review_list(
    *,
    reviews: tuple[RecommendationReview, ...],
    business_date: str,
    generated_at: datetime,
    generated_by: str,
) -> ConfirmedReviewList:
    """Build a stable checklist from confirmed non-zero-stake reviews."""

    if type(reviews) is not tuple or any(type(review) is not RecommendationReview for review in reviews):
        raise ValueError("reviews must be a tuple of RecommendationReview")
    business_date = _normalize_required_text(business_date, "business_date")
    generated_by = _normalize_required_text(generated_by, "generated_by")
    if type(generated_at) is not datetime:
        raise ValueError("generated_at must be a datetime")
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")

    confirmed = tuple(
        ConfirmedReviewEntry(
            recommendation_id=review.recommendation_id,
            race_id=review.race_id,
            stake_units=review.stake_units,
            notes=review.notes,
            reviewed_at=review.reviewed_at,
            reviewed_by=review.reviewed_by,
        )
        for review in sorted(reviews, key=lambda item: (item.race_id, item.recommendation_id))
        if review.decision is ReviewDecision.CONFIRMED and review.stake_units > 0
    )
    return ConfirmedReviewList(
        business_date=business_date,
        generated_at=generated_at,
        generated_by=generated_by,
        risk_notice=RISK_NOTICE,
        entries=confirmed,
    )


def confirmed_review_list_to_dict(review_list: ConfirmedReviewList) -> dict[str, Any]:
    """Serialize a confirmed review checklist to a JSON-ready mapping."""

    if type(review_list) is not ConfirmedReviewList:
        raise TypeError("review_list must be a ConfirmedReviewList")
    return {
        "business_date": review_list.business_date,
        "generated_at": review_list.generated_at.isoformat(),
        "generated_by": review_list.generated_by,
        "risk_notice": review_list.risk_notice,
        "total_stake_units": review_list.total_stake_units,
        "entries": [
            {
                "recommendation_id": entry.recommendation_id,
                "race_id": entry.race_id,
                "stake_units": entry.stake_units,
                "notes": entry.notes,
                "reviewed_at": entry.reviewed_at.isoformat(),
                "reviewed_by": entry.reviewed_by,
            }
            for entry in review_list.entries
        ],
    }


def _normalize_required_text(value: str, name: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    return normalized


def _required_string(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if type(value) is not str:
        raise ValueError(f"{key} must be a string")
    return value


def _required_int(mapping: dict[str, object], key: str) -> int:
    value = mapping.get(key)
    if type(value) is not int:
        raise ValueError(f"{key} must be an integer")
    return value


def _parse_aware_datetime(value: str, name: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return parsed
