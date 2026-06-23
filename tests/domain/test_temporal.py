from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from boatrace_cal.domain.temporal import AvailableRecord


class DateTimeSubclass(datetime):
    pass


class AwareDateTimeDuck:
    tzinfo = UTC

    def utcoffset(self) -> timedelta:
        return timedelta(0)


def test_available_record_rejects_future_availability() -> None:
    as_of = datetime(2026, 6, 23, 10, 0, tzinfo=UTC)
    record = AvailableRecord(available_at=as_of + timedelta(seconds=1))

    with pytest.raises(ValueError):
        record.assert_usable_at(as_of)


def test_available_record_rejects_naive_available_at() -> None:
    with pytest.raises(ValueError):
        AvailableRecord(available_at=datetime(2026, 6, 23, 10, 0))


def test_available_record_rejects_naive_as_of() -> None:
    record = AvailableRecord(available_at=datetime(2026, 6, 23, 10, 0, tzinfo=UTC))

    with pytest.raises(ValueError):
        record.assert_usable_at(datetime(2026, 6, 23, 10, 0))


@pytest.mark.parametrize(
    "value",
    [
        "2026-06-23T10:00:00+00:00",
        AwareDateTimeDuck(),
        DateTimeSubclass(2026, 6, 23, 10, 0, tzinfo=UTC),
    ],
)
def test_available_record_rejects_non_exact_datetime(value: object) -> None:
    with pytest.raises(ValueError):
        AvailableRecord(available_at=value)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "value",
    [
        "2026-06-23T10:00:00+00:00",
        AwareDateTimeDuck(),
        DateTimeSubclass(2026, 6, 23, 10, 0, tzinfo=UTC),
    ],
)
def test_assert_usable_at_rejects_non_exact_datetime(value: object) -> None:
    record = AvailableRecord(available_at=datetime(2026, 6, 23, 10, 0, tzinfo=UTC))

    with pytest.raises(ValueError):
        record.assert_usable_at(value)  # type: ignore[arg-type]


def test_available_record_remains_hashable() -> None:
    record = AvailableRecord(available_at=datetime(2026, 6, 23, 10, 0, tzinfo=UTC))

    assert hash(record)


def test_available_record_is_usable_at_exact_availability_time() -> None:
    available_at = datetime(2026, 6, 23, 10, 0, tzinfo=UTC)
    record = AvailableRecord(available_at=available_at)

    record.assert_usable_at(available_at)


def test_available_record_is_usable_after_availability_time() -> None:
    available_at = datetime(2026, 6, 23, 10, 0, tzinfo=UTC)
    record = AvailableRecord(available_at=available_at)

    record.assert_usable_at(available_at + timedelta(seconds=1))


def test_available_record_rejects_later_dst_fold_in_same_timezone() -> None:
    new_york = ZoneInfo("America/New_York")
    available_at = datetime(2024, 11, 3, 1, 30, tzinfo=new_york, fold=1)
    as_of = datetime(2024, 11, 3, 1, 45, tzinfo=new_york, fold=0)
    record = AvailableRecord(available_at=available_at)

    with pytest.raises(ValueError):
        record.assert_usable_at(as_of)


def test_available_record_accepts_same_instant_in_another_timezone() -> None:
    record = AvailableRecord(available_at=datetime(2026, 6, 23, 1, 0, tzinfo=UTC))
    japan_standard_time = timezone(timedelta(hours=9))

    record.assert_usable_at(datetime(2026, 6, 23, 10, 0, tzinfo=japan_standard_time))


def test_available_record_accepts_earlier_instant_across_timezones() -> None:
    record = AvailableRecord(available_at=datetime(2026, 6, 23, 0, 30, tzinfo=UTC))
    japan_standard_time = timezone(timedelta(hours=9))

    record.assert_usable_at(datetime(2026, 6, 23, 10, 0, tzinfo=japan_standard_time))
