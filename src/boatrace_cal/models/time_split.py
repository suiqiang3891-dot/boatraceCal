"""Time-ordered train/validation/test split reports for model inputs."""

from collections.abc import Iterable
from datetime import datetime

from boatrace_cal.ingestion.results import RaceResultRecord


def build_time_split_report(
    results: Iterable[RaceResultRecord],
    *,
    train_until: datetime,
    validation_until: datetime,
    test_until: datetime,
) -> dict[str, object]:
    """Partition result records by available_at without random shuffling."""

    _require_aware_datetime(train_until, "train_until")
    _require_aware_datetime(validation_until, "validation_until")
    _require_aware_datetime(test_until, "test_until")
    if not train_until < validation_until < test_until:
        raise ValueError("train_until must be before validation_until and test_until")

    normalized_results = tuple(results)
    if any(type(result) is not RaceResultRecord for result in normalized_results):
        raise TypeError("results must contain only RaceResultRecord instances")

    train = []
    validation = []
    test = []
    excluded = []
    for result in sorted(
        normalized_results,
        key=lambda item: (item.available_at, str(item.race_id)),
    ):
        if result.available_at <= train_until:
            train.append(result)
        elif result.available_at <= validation_until:
            validation.append(result)
        elif result.available_at <= test_until:
            test.append(result)
        else:
            excluded.append(result)

    return {
        "schema_version": "model-time-split-report-v1",
        "split_field": "available_at",
        "train_until": train_until.isoformat(),
        "validation_until": validation_until.isoformat(),
        "test_until": test_until.isoformat(),
        "train_count": len(train),
        "validation_count": len(validation),
        "test_count": len(test),
        "excluded_count": len(excluded),
        "leakage_check": "passed",
        "train_race_ids": _race_ids(train),
        "validation_race_ids": _race_ids(validation),
        "test_race_ids": _race_ids(test),
        "excluded_race_ids": _race_ids(excluded),
    }


def _race_ids(records: list[RaceResultRecord]) -> list[str]:
    return [str(record.race_id) for record in records]


def _require_aware_datetime(value: datetime, name: str) -> None:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
