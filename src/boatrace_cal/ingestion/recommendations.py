"""Strict CSV ingestion for immutable recommendation records."""

from collections.abc import Iterable, Sequence
import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.domain.recommendations import (
    ConfidenceLevel,
    Decision,
    PlanStage,
    Recommendation,
)
from boatrace_cal.domain.versions import ArtifactVersions


_FIELDS = (
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


def load_recommendations_csv(path: Path | str) -> tuple[Recommendation, ...]:
    """Load and validate a versioned recommendation CSV file."""

    with Path(path).open("r", encoding="utf-8", newline="") as recommendations_file:
        reader = csv.DictReader(recommendations_file)
        _validate_fields(reader.fieldnames)
        records = tuple(_record_from_row(row) for row in reader)

    seen: set[str] = set()
    for record in records:
        if record.recommendation_id in seen:
            raise ValueError(f"duplicate recommendation id: {record.recommendation_id}")
        seen.add(record.recommendation_id)
    return records


def _validate_fields(fieldnames: Sequence[str] | None) -> None:
    if fieldnames is None or tuple(fieldnames) != _FIELDS:
        raise ValueError("recommendation CSV must contain exactly the supported fields")


def _record_from_row(row: dict[str, str]) -> Recommendation:
    bet_type = BetType(row["bet_type"])
    return Recommendation(
        recommendation_id=row["recommendation_id"],
        race_id=RaceId(
            race_date=date.fromisoformat(row["race_date"]),
            venue=VenueCode(row["venue"]),
            race_no=_parse_int(row["race_no"], "race_no"),
        ),
        combination=BetCombination.create(bet_type, _parse_lanes(row["combination"])),
        stage=PlanStage(row["stage"]),
        decision=Decision(row["decision"]),
        confidence=ConfidenceLevel(row["confidence"]),
        probability=_parse_decimal(row["probability"], "probability"),
        odds=_parse_optional_decimal(row["odds"], "odds"),
        expected_value=_parse_optional_decimal(row["expected_value"], "expected_value"),
        as_of=_parse_datetime(row["as_of"], "as_of"),
        stake_units=_parse_int(row["stake_units"], "stake_units"),
        versions=ArtifactVersions(
            data=row["data_version"],
            feature=row["feature_version"],
            model=row["model_version"],
            strategy=row["strategy_version"],
        ),
        reason_codes=_parse_reason_codes(row["reason_codes"]),
    )


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


def _parse_lanes(value: str) -> Iterable[int]:
    if not value:
        raise ValueError("combination must not be blank")
    return (_parse_int(lane, "combination lane") for lane in value.split("-"))


def _parse_reason_codes(value: str) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(value.split("|"))
