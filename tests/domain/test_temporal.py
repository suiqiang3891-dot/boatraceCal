from datetime import UTC, datetime, timedelta

import pytest

from boatrace_cal.domain.temporal import AvailableRecord


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


def test_available_record_is_usable_at_exact_availability_time() -> None:
    available_at = datetime(2026, 6, 23, 10, 0, tzinfo=UTC)
    record = AvailableRecord(available_at=available_at)

    record.assert_usable_at(available_at)


def test_available_record_is_usable_after_availability_time() -> None:
    available_at = datetime(2026, 6, 23, 10, 0, tzinfo=UTC)
    record = AvailableRecord(available_at=available_at)

    record.assert_usable_at(available_at + timedelta(seconds=1))
