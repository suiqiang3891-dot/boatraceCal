"""Strict CSV ingestion for official payout settlement records."""

from collections.abc import Iterable, Sequence
import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
from pathlib import Path

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode


_FIELDS = (
    "race_date",
    "venue",
    "race_no",
    "bet_type",
    "combination",
    "payout_yen",
    "source",
    "source_hash",
    "observed_at",
    "available_at",
    "parser_version",
)


@dataclass(frozen=True, slots=True)
class PayoutRecord:
    """Normalized settlement payout for one race and bet combination."""

    race_id: RaceId
    combination: BetCombination
    payout_yen: Decimal
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
        if type(self.payout_yen) is not Decimal or not self.payout_yen.is_finite():
            raise TypeError("payout_yen must be a finite Decimal")
        if self.payout_yen <= Decimal("0") or self.payout_yen != self.payout_yen.to_integral():
            raise ValueError("payout_yen must be a positive whole-yen amount")
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
    def key(self) -> tuple[RaceId, BetCombination]:
        """Business key that must be unique in one imported payout dataset."""

        return (self.race_id, self.combination)


@dataclass(frozen=True, slots=True)
class PayoutCompletenessRow:
    """Completeness aggregate for imported payout records."""

    race_date: date
    venue: VenueCode
    bet_type: BetType
    payout_count: int
    race_count: int
    total_payout_yen: Decimal

    def __post_init__(self) -> None:
        if type(self.race_date) is not date:
            raise TypeError("race_date must be a date")
        if type(self.venue) is not VenueCode:
            raise TypeError("venue must be a VenueCode")
        if type(self.bet_type) is not BetType:
            raise TypeError("bet_type must be a BetType")
        if type(self.payout_count) is not int or self.payout_count < 0:
            raise ValueError("payout_count must be a non-negative integer")
        if type(self.race_count) is not int or self.race_count < 0:
            raise ValueError("race_count must be a non-negative integer")
        if type(self.total_payout_yen) is not Decimal or not self.total_payout_yen.is_finite():
            raise TypeError("total_payout_yen must be a finite Decimal")
        if self.total_payout_yen < Decimal("0"):
            raise ValueError("total_payout_yen must not be negative")


@dataclass(frozen=True, slots=True)
class MissingPayoutRow:
    """Expected race and bet type without an imported payout record."""

    race_id: RaceId
    bet_type: BetType
    reason_code: str

    def __post_init__(self) -> None:
        if type(self.race_id) is not RaceId:
            raise TypeError("race_id must be a RaceId")
        if type(self.bet_type) is not BetType:
            raise TypeError("bet_type must be a BetType")
        if type(self.reason_code) is not str:
            raise TypeError("reason_code must be a string")
        reason_code = self.reason_code.strip()
        if not reason_code:
            raise ValueError("reason_code must not be blank")
        object.__setattr__(self, "reason_code", reason_code)


@dataclass(frozen=True, slots=True)
class PayoutDatasetManifest:
    """Auditable manifest for one imported payout dataset file."""

    source_path: Path
    content_sha256: str
    record_count: int
    parser_versions: tuple[str, ...]
    race_date_start: date | None
    race_date_end: date | None
    observed_at_start: datetime | None
    observed_at_end: datetime | None
    available_at_start: datetime | None
    available_at_end: datetime | None

    def __post_init__(self) -> None:
        if not isinstance(self.source_path, Path):
            raise TypeError("source_path must be a Path")
        if type(self.content_sha256) is not str:
            raise TypeError("content_sha256 must be a string")
        content_sha256 = self.content_sha256.strip().lower()
        if len(content_sha256) != 64 or any(char not in "0123456789abcdef" for char in content_sha256):
            raise ValueError("content_sha256 must be a SHA-256 hex digest")
        object.__setattr__(self, "content_sha256", content_sha256)

        if type(self.record_count) is not int or self.record_count < 0:
            raise ValueError("record_count must be a non-negative integer")
        if type(self.parser_versions) is not tuple or any(
            type(version) is not str for version in self.parser_versions
        ):
            raise TypeError("parser_versions must be a tuple of strings")
        parser_versions = tuple(version.strip() for version in self.parser_versions)
        if any(not version for version in parser_versions):
            raise ValueError("parser_versions must not contain blank values")
        if parser_versions != tuple(sorted(set(parser_versions))):
            raise ValueError("parser_versions must be sorted and unique")
        object.__setattr__(self, "parser_versions", parser_versions)

        _validate_optional_date_range(self.race_date_start, self.race_date_end, "race_date")
        _validate_optional_datetime_range(
            self.observed_at_start,
            self.observed_at_end,
            "observed_at",
        )
        _validate_optional_datetime_range(
            self.available_at_start,
            self.available_at_end,
            "available_at",
        )


def load_payouts_csv(path: Path | str) -> tuple[PayoutRecord, ...]:
    """Load and validate a versioned payout CSV file."""

    with Path(path).open("r", encoding="utf-8", newline="") as payouts_file:
        reader = csv.DictReader(payouts_file)
        _validate_fields(reader.fieldnames)
        records = tuple(_record_from_row(row) for row in reader)

    seen: set[tuple[RaceId, BetCombination]] = set()
    for record in records:
        if record.key in seen:
            raise ValueError(f"duplicate payout key: {record.race_id}|{record.combination.key}")
        seen.add(record.key)
    return records


def summarize_payout_completeness(
    records: Iterable[PayoutRecord],
) -> tuple[PayoutCompletenessRow, ...]:
    """Summarize imported payout coverage by date, venue, and bet type."""

    grouped: dict[tuple[date, VenueCode, BetType], list[PayoutRecord]] = {}
    for record in records:
        if type(record) is not PayoutRecord:
            raise TypeError("records must contain only PayoutRecord instances")
        key = (
            record.race_id.race_date,
            record.race_id.venue,
            record.combination.bet_type,
        )
        grouped.setdefault(key, []).append(record)

    rows = []
    for (race_date, venue, bet_type), group in grouped.items():
        rows.append(
            PayoutCompletenessRow(
                race_date=race_date,
                venue=venue,
                bet_type=bet_type,
                payout_count=len(group),
                race_count=len({record.race_id for record in group}),
                total_payout_yen=sum(
                    (record.payout_yen for record in group),
                    start=Decimal("0"),
                ),
            )
        )
    return tuple(
        sorted(
            rows,
            key=lambda row: (row.race_date, row.venue.value, row.bet_type.value),
        )
    )


def find_missing_payouts(
    records: Iterable[PayoutRecord],
    expected_races: Iterable[RaceId],
    bet_types: Iterable[BetType],
) -> tuple[MissingPayoutRow, ...]:
    """Return expected race and bet-type pairs absent from imported payouts."""

    present = _present_payout_groups(records)
    races = _normalize_expected_races(expected_races)
    expected_bet_types = _normalize_expected_bet_types(bet_types)

    missing = []
    for race_id in races:
        for bet_type in expected_bet_types:
            if (race_id, bet_type) not in present:
                missing.append(
                    MissingPayoutRow(
                        race_id=race_id,
                        bet_type=bet_type,
                        reason_code="PAYOUT_MISSING",
                    )
                )
    return tuple(
        sorted(
            missing,
            key=lambda row: (
                row.race_id.race_date,
                row.race_id.venue.value,
                row.race_id.race_no,
                row.bet_type.value,
            ),
        )
    )


def build_payout_dataset_manifest(
    path: Path | str,
    records: Iterable[PayoutRecord],
) -> PayoutDatasetManifest:
    """Build a deterministic manifest for an imported payout CSV dataset."""

    source_path = Path(path)
    normalized_records = _normalize_records(records)
    race_dates = tuple(record.race_id.race_date for record in normalized_records)
    observed_times = tuple(record.observed_at for record in normalized_records)
    available_times = tuple(record.available_at for record in normalized_records)
    return PayoutDatasetManifest(
        source_path=source_path,
        content_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
        record_count=len(normalized_records),
        parser_versions=tuple(
            sorted({record.parser_version for record in normalized_records})
        ),
        race_date_start=min(race_dates) if race_dates else None,
        race_date_end=max(race_dates) if race_dates else None,
        observed_at_start=min(observed_times) if observed_times else None,
        observed_at_end=max(observed_times) if observed_times else None,
        available_at_start=min(available_times) if available_times else None,
        available_at_end=max(available_times) if available_times else None,
    )


def _normalize_records(records: Iterable[PayoutRecord]) -> tuple[PayoutRecord, ...]:
    normalized = tuple(records)
    if any(type(record) is not PayoutRecord for record in normalized):
        raise TypeError("records must contain only PayoutRecord instances")
    return normalized


def _present_payout_groups(
    records: Iterable[PayoutRecord],
) -> frozenset[tuple[RaceId, BetType]]:
    groups = set()
    for record in records:
        if type(record) is not PayoutRecord:
            raise TypeError("records must contain only PayoutRecord instances")
        groups.add((record.race_id, record.combination.bet_type))
    return frozenset(groups)


def _normalize_expected_races(expected_races: Iterable[RaceId]) -> tuple[RaceId, ...]:
    races = tuple(expected_races)
    if any(type(race_id) is not RaceId for race_id in races):
        raise TypeError("expected_races must contain only RaceId instances")
    return races


def _normalize_expected_bet_types(bet_types: Iterable[BetType]) -> tuple[BetType, ...]:
    values = tuple(bet_types)
    if any(type(bet_type) is not BetType for bet_type in values):
        raise TypeError("bet_types must contain only BetType instances")
    return values


def _validate_optional_date_range(start: date | None, end: date | None, field_name: str) -> None:
    if start is None or end is None:
        if start is not None or end is not None:
            raise ValueError(f"{field_name} range must be fully populated or fully empty")
        return
    if type(start) is not date or type(end) is not date:
        raise TypeError(f"{field_name} range values must be dates")
    if end < start:
        raise ValueError(f"{field_name} range end must not be before start")


def _validate_optional_datetime_range(
    start: datetime | None,
    end: datetime | None,
    field_name: str,
) -> None:
    if start is None or end is None:
        if start is not None or end is not None:
            raise ValueError(f"{field_name} range must be fully populated or fully empty")
        return
    if type(start) is not datetime or type(end) is not datetime:
        raise TypeError(f"{field_name} range values must be datetimes")
    if not _is_aware(start) or not _is_aware(end):
        raise ValueError(f"{field_name} range values must be timezone-aware")
    if end < start:
        raise ValueError(f"{field_name} range end must not be before start")


def _validate_fields(fieldnames: Sequence[str] | None) -> None:
    if fieldnames is None or tuple(fieldnames) != _FIELDS:
        raise ValueError("payout CSV must contain exactly the supported fields")


def _record_from_row(row: dict[str, str]) -> PayoutRecord:
    race_id = RaceId(
        race_date=date.fromisoformat(row["race_date"]),
        venue=VenueCode(row["venue"]),
        race_no=_parse_int(row["race_no"], "race_no"),
    )
    bet_type = BetType(row["bet_type"])
    return PayoutRecord(
        race_id=race_id,
        combination=BetCombination.create(bet_type, _parse_lanes(row["combination"])),
        payout_yen=_parse_decimal(row["payout_yen"], "payout_yen"),
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
