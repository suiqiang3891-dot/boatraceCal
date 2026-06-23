from dataclasses import FrozenInstanceError
from datetime import date, datetime

import pytest

from boatrace_cal.domain.races import RaceId, VenueCode


def test_race_id_is_canonical() -> None:
    assert str(RaceId(date(2026, 6, 23), VenueCode("5"), 1)) == "20260623-05-01"


@pytest.mark.parametrize("value", ["0", "25", "AA"])
def test_venue_code_rejects_invalid_value(value: str) -> None:
    with pytest.raises(ValueError):
        VenueCode(value)


@pytest.mark.parametrize("race_no", [0, 13])
def test_race_id_rejects_invalid_race_number(race_no: int) -> None:
    with pytest.raises(ValueError):
        RaceId(date(2026, 6, 23), VenueCode("5"), race_no)


def test_venue_code_string_is_zero_padded() -> None:
    assert str(VenueCode("5")) == "05"


@pytest.mark.parametrize("value", [b"05", 5])
def test_venue_code_rejects_non_string_values(value: object) -> None:
    with pytest.raises(ValueError, match="string"):
        VenueCode(value)  # type: ignore[arg-type]


def test_venue_code_rejects_string_subclasses() -> None:
    class StringLike(str):
        pass

    with pytest.raises(ValueError, match="string"):
        VenueCode(StringLike("05"))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("race_date", datetime(2026, 6, 23), "race date"),
        ("race_date", "2026-06-23", "race date"),
        ("venue", "05", "venue"),
        ("race_no", True, "race number"),
        ("race_no", 1.0, "race number"),
    ],
)
def test_race_id_rejects_runtime_type_bypasses(
    field: str, value: object, message: str
) -> None:
    values: dict[str, object] = {
        "race_date": date(2026, 6, 23),
        "venue": VenueCode("05"),
        "race_no": 1,
    }
    values[field] = value

    with pytest.raises(ValueError, match=message):
        RaceId(**values)  # type: ignore[arg-type]


def test_race_id_datetime_collision_probe_is_rejected() -> None:
    valid = RaceId(date(2026, 6, 23), VenueCode("05"), 1)

    with pytest.raises(ValueError, match="race date"):
        RaceId(datetime(2026, 6, 23), valid.venue, valid.race_no)


def test_race_id_is_frozen_and_hashable() -> None:
    race_id = RaceId(date(2026, 6, 23), VenueCode("05"), 1)

    assert {race_id: "race"}[RaceId(date(2026, 6, 23), VenueCode("05"), 1)] == "race"
    with pytest.raises(FrozenInstanceError):
        race_id.race_no = 2  # type: ignore[misc]
