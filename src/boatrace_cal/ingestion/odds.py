"""Strict CSV ingestion for pre-race odds snapshot records."""

from collections.abc import Iterable, Sequence
import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode


_FIELDS = (
    "race_date",
    "venue",
    "race_no",
    "bet_type",
    "combination",
    "odds",
    "source",
    "source_hash",
    "observed_at",
    "available_at",
    "parser_version",
)


@dataclass(frozen=True, slots=True)
class OddsSnapshotRecord:
    """Normalized market odds for one race and bet combination at one snapshot."""

    race_id: RaceId
    combination: BetCombination
    odds: Decimal
    source: str
    source_hash: str
    observed_at: datetime
    available_at: datetime
    parser_version: str

    def __post_init__(self) -> None:
        if type(self.race_id) is not RaceId:
            raise TypeError("race_id must be a RaceId")
        if type(self.combination) is not BetCombination:
            raise TypeError("combination must be a BetCombination")
        if type(self.odds) is not Decimal or not self.odds.is_finite():
            raise TypeError("odds must be a finite Decimal")
        if self.odds <= Decimal("0"):
            raise ValueError("odds must be positive")
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

    @property
    def snapshot_key(self) -> tuple[RaceId, BetCombination, datetime, str]:
        """Immutable source snapshot key that must be unique within one import."""

        return (self.race_id, self.combination, self.available_at, self.source)


def load_odds_csv(path: Path | str) -> tuple[OddsSnapshotRecord, ...]:
    """Load and validate a versioned odds snapshot CSV file."""

    with Path(path).open("r", encoding="utf-8", newline="") as odds_file:
        reader = csv.DictReader(odds_file)
        _validate_fields(reader.fieldnames)
        records = tuple(_record_from_row(row) for row in reader)

    seen: set[tuple[RaceId, BetCombination, datetime, str]] = set()
    for record in records:
        if record.snapshot_key in seen:
            raise ValueError(
                f"duplicate odds snapshot key: {record.race_id}|"
                f"{record.combination.key}|{record.available_at.isoformat()}|{record.source}"
            )
        seen.add(record.snapshot_key)
    return records


def latest_odds_by_combination(
    records: Iterable[OddsSnapshotRecord],
    race_id: RaceId,
    as_of: datetime,
) -> dict[BetCombination, OddsSnapshotRecord]:
    """Return latest odds per combination available at or before prediction time."""

    if type(race_id) is not RaceId:
        raise TypeError("race_id must be a RaceId")
    if type(as_of) is not datetime or not _is_aware(as_of):
        raise ValueError("as_of must be timezone-aware")

    latest: dict[BetCombination, OddsSnapshotRecord] = {}
    for record in records:
        if type(record) is not OddsSnapshotRecord:
            raise TypeError("records must contain only OddsSnapshotRecord instances")
        if record.race_id != race_id or record.available_at > as_of:
            continue

        current = latest.get(record.combination)
        if current is None or _snapshot_sort_key(record) > _snapshot_sort_key(current):
            latest[record.combination] = record

    return dict(
        sorted(
            latest.items(),
            key=lambda item: (item[0].bet_type.value, item[0].key),
        )
    )


def _snapshot_sort_key(record: OddsSnapshotRecord) -> tuple[datetime, datetime, str, str]:
    return (record.available_at, record.observed_at, record.source, record.source_hash)


def _validate_fields(fieldnames: Sequence[str] | None) -> None:
    if fieldnames is None or tuple(fieldnames) != _FIELDS:
        raise ValueError("odds CSV must contain exactly the supported fields")


def _record_from_row(row: dict[str, str]) -> OddsSnapshotRecord:
    race_id = RaceId(
        race_date=date.fromisoformat(row["race_date"]),
        venue=VenueCode(row["venue"]),
        race_no=_parse_int(row["race_no"], "race_no"),
    )
    bet_type = BetType(row["bet_type"])
    return OddsSnapshotRecord(
        race_id=race_id,
        combination=BetCombination.create(bet_type, _parse_lanes(row["combination"])),
        odds=_parse_decimal(row["odds"], "odds"),
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


def _parse_decimal(value: str, field_name: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{field_name} must be a decimal") from exc


def _parse_datetime(value: str, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 datetime") from exc
    if not _is_aware(parsed):
        raise ValueError(f"{field_name} must be timezone-aware")
    return parsed


def _parse_lanes(value: str) -> Iterable[int]:
    if not value:
        raise ValueError("combination must not be blank")
    return (_parse_int(lane, "combination lane") for lane in value.split("-"))


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None
