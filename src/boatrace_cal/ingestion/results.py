"""Strict CSV ingestion for official race result records."""

from collections.abc import Sequence
import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from boatrace_cal.domain.races import RaceId, VenueCode


_FIELDS = (
    "race_date",
    "venue",
    "race_no",
    "first",
    "second",
    "third",
    "source",
    "source_hash",
    "observed_at",
    "available_at",
    "parser_version",
)


@dataclass(frozen=True, slots=True)
class RaceResultRecord:
    """Normalized finish order for one completed race."""

    race_id: RaceId
    finish_order: tuple[int, int, int]
    source: str
    source_hash: str
    observed_at: datetime
    available_at: datetime
    parser_version: str

    def __post_init__(self) -> None:
        if type(self.race_id) is not RaceId:
            raise TypeError("race_id must be a RaceId")
        if type(self.finish_order) is not tuple:
            raise TypeError("finish_order must be a tuple")
        if len(self.finish_order) != 3:
            raise ValueError("finish_order must contain first, second, and third")
        if any(type(lane) is not int for lane in self.finish_order):
            raise TypeError("finish_order lanes must be integers")
        if len(set(self.finish_order)) != 3:
            raise ValueError("finish_order lanes must be unique")
        if any(not 1 <= lane <= 6 for lane in self.finish_order):
            raise ValueError("finish_order lanes must be between 1 and 6")
        if type(self.observed_at) is not datetime or not _is_aware(self.observed_at):
            raise ValueError("observed_at must be timezone-aware")
        if type(self.available_at) is not datetime or not _is_aware(self.available_at):
            raise ValueError("available_at must be timezone-aware")
        if self.available_at < self.observed_at:
            raise ValueError("available_at must not be before observed_at")

        for field_name in ("source", "source_hash", "parser_version"):
            value = getattr(self, field_name)
            if type(value) is not str:
                raise TypeError(f"{field_name} must be a string")
            normalized = value.strip()
            if not normalized:
                raise ValueError(f"{field_name} must not be blank")
            object.__setattr__(self, field_name, normalized)


def load_results_csv(path: Path | str) -> tuple[RaceResultRecord, ...]:
    """Load and validate a versioned race result CSV file."""

    with Path(path).open("r", encoding="utf-8", newline="") as results_file:
        reader = csv.DictReader(results_file)
        _validate_fields(reader.fieldnames)
        records = tuple(_record_from_row(row) for row in reader)

    seen: set[RaceId] = set()
    for record in records:
        if record.race_id in seen:
            raise ValueError(f"duplicate race result: {record.race_id}")
        seen.add(record.race_id)
    return records


def _validate_fields(fieldnames: Sequence[str] | None) -> None:
    if fieldnames is None or tuple(fieldnames) != _FIELDS:
        raise ValueError("result CSV must contain exactly the supported fields")


def _record_from_row(row: dict[str, str]) -> RaceResultRecord:
    return RaceResultRecord(
        race_id=RaceId(
            race_date=date.fromisoformat(row["race_date"]),
            venue=VenueCode(row["venue"]),
            race_no=_parse_int(row["race_no"], "race_no"),
        ),
        finish_order=(
            _parse_int(row["first"], "first"),
            _parse_int(row["second"], "second"),
            _parse_int(row["third"], "third"),
        ),
        source=row["source"],
        source_hash=row["source_hash"],
        observed_at=_parse_datetime(row["observed_at"], "observed_at"),
        available_at=_parse_datetime(row["available_at"], "available_at"),
        parser_version=row["parser_version"],
    )


def _parse_int(value: str, field_name: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an integer") from exc


def _parse_datetime(value: str, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 datetime") from exc
    if not _is_aware(parsed):
        raise ValueError(f"{field_name} must be timezone-aware")
    return parsed


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None
