"""CSV adapters for value strategy candidates and recommendations."""

from collections.abc import Sequence
import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.domain.recommendations import (
    ConfidenceLevel,
    Recommendation,
)
from boatrace_cal.domain.versions import ArtifactVersions
from boatrace_cal.strategies.value import StrategyCandidate


_CANDIDATE_FIELDS = (
    "recommendation_id",
    "race_date",
    "venue",
    "race_no",
    "bet_type",
    "combination",
    "confidence",
    "probability",
    "odds",
    "as_of",
    "data_version",
    "feature_version",
    "model_version",
    "strategy_version",
    "reason_codes",
)

_RECOMMENDATION_FIELDS = (
    "recommendation_id",
    "race_date",
    "venue",
    "race_no",
    "bet_type",
    "combination",
    "stage",
    "decision",
    "confidence",
    "probability",
    "odds",
    "expected_value",
    "as_of",
    "stake_units",
    "data_version",
    "feature_version",
    "model_version",
    "strategy_version",
    "reason_codes",
)


def load_strategy_candidates_csv(path: Path | str) -> tuple[StrategyCandidate, ...]:
    """Load model probability candidates before value strategy gates run."""

    with Path(path).open("r", encoding="utf-8", newline="") as candidates_file:
        reader = csv.DictReader(candidates_file)
        _validate_fields(reader.fieldnames, _CANDIDATE_FIELDS, "strategy candidate CSV")
        return tuple(_candidate_from_row(row) for row in reader)


def export_strategy_candidates_csv(
    candidates: tuple[StrategyCandidate, ...],
    path: Path | str,
) -> None:
    """Write strategy candidates for downstream value gates."""

    if type(candidates) is not tuple or any(
        type(candidate) is not StrategyCandidate for candidate in candidates
    ):
        raise ValueError("candidates must be a tuple of StrategyCandidate")
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as candidates_file:
        writer = csv.DictWriter(candidates_file, fieldnames=_CANDIDATE_FIELDS)
        writer.writeheader()
        writer.writerows(_candidate_to_row(candidate) for candidate in candidates)


def export_recommendations_csv(
    recommendations: tuple[Recommendation, ...],
    path: Path | str,
) -> None:
    """Write recommendations in the existing backtest-ready CSV contract."""

    if type(recommendations) is not tuple or any(
        type(recommendation) is not Recommendation for recommendation in recommendations
    ):
        raise ValueError("recommendations must be a tuple of Recommendation")
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as recommendations_file:
        writer = csv.DictWriter(recommendations_file, fieldnames=_RECOMMENDATION_FIELDS)
        writer.writeheader()
        writer.writerows(_recommendation_to_row(recommendation) for recommendation in recommendations)


def _validate_fields(
    fieldnames: Sequence[str] | None,
    expected_fields: tuple[str, ...],
    name: str,
) -> None:
    if fieldnames is None or tuple(fieldnames) != expected_fields:
        raise ValueError(f"{name} must contain exactly the supported fields")


def _candidate_from_row(row: dict[str, str]) -> StrategyCandidate:
    bet_type = BetType(row["bet_type"])
    return StrategyCandidate(
        recommendation_id=row["recommendation_id"],
        race_id=RaceId(
            race_date=date.fromisoformat(row["race_date"]),
            venue=VenueCode(row["venue"]),
            race_no=_parse_int(row["race_no"], "race_no"),
        ),
        combination=BetCombination.create(bet_type, _parse_lanes(row["combination"])),
        probability=_parse_decimal(row["probability"], "probability"),
        odds=_parse_optional_decimal(row["odds"], "odds"),
        confidence=ConfidenceLevel(row["confidence"]),
        as_of=_parse_datetime(row["as_of"], "as_of"),
        versions=ArtifactVersions(
            data=row["data_version"],
            feature=row["feature_version"],
            model=row["model_version"],
            strategy=row["strategy_version"],
        ),
        reason_codes=_parse_reason_codes(row["reason_codes"]),
    )


def _recommendation_to_row(recommendation: Recommendation) -> dict[str, str]:
    return {
        "recommendation_id": recommendation.recommendation_id,
        "race_date": recommendation.race_id.race_date.isoformat(),
        "venue": recommendation.race_id.venue.value,
        "race_no": str(recommendation.race_id.race_no),
        "bet_type": recommendation.combination.bet_type.value,
        "combination": recommendation.combination.key,
        "stage": recommendation.stage.value,
        "decision": recommendation.decision.value,
        "confidence": recommendation.confidence.value,
        "probability": str(recommendation.probability),
        "odds": "" if recommendation.odds is None else str(recommendation.odds),
        "expected_value": ""
        if recommendation.expected_value is None
        else str(recommendation.expected_value),
        "as_of": recommendation.as_of.isoformat(),
        "stake_units": str(recommendation.stake_units),
        "data_version": recommendation.versions.data,
        "feature_version": recommendation.versions.feature,
        "model_version": recommendation.versions.model,
        "strategy_version": recommendation.versions.strategy,
        "reason_codes": "|".join(recommendation.reason_codes),
    }


def _candidate_to_row(candidate: StrategyCandidate) -> dict[str, str]:
    return {
        "recommendation_id": candidate.recommendation_id,
        "race_date": candidate.race_id.race_date.isoformat(),
        "venue": candidate.race_id.venue.value,
        "race_no": str(candidate.race_id.race_no),
        "bet_type": candidate.combination.bet_type.value,
        "combination": candidate.combination.key,
        "confidence": candidate.confidence.value,
        "probability": str(candidate.probability),
        "odds": "" if candidate.odds is None else str(candidate.odds),
        "as_of": candidate.as_of.isoformat(),
        "data_version": candidate.versions.data,
        "feature_version": candidate.versions.feature,
        "model_version": candidate.versions.model,
        "strategy_version": candidate.versions.strategy,
        "reason_codes": "|".join(candidate.reason_codes),
    }


def _parse_int(value: str, field_name: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an integer") from exc


def _parse_decimal(value: str, field_name: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{field_name} must be a decimal") from exc


def _parse_optional_decimal(value: str, field_name: str) -> Decimal | None:
    if value == "":
        return None
    return _parse_decimal(value, field_name)


def _parse_datetime(value: str, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return parsed


def _parse_lanes(value: str) -> tuple[int, ...]:
    if not value:
        raise ValueError("combination must not be blank")
    return tuple(_parse_int(lane, "combination lane") for lane in value.split("-"))


def _parse_reason_codes(value: str) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(value.split("|"))
