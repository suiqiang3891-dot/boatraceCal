from datetime import date

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
