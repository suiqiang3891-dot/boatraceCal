"""Strict standard-library configuration loading."""

from dataclasses import dataclass
from pathlib import Path
import tomllib
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from boatrace_cal.domain.races import VenueCode
from boatrace_cal.jobs.contracts import SnapshotTarget


_TABLE_FIELDS = {
    "project": frozenset({"timezone"}),
    "pilot": frozenset({"venue"}),
    "snapshots": frozenset({"targets"}),
    "retention": frozenset({"anomaly_response_days"}),
}
_REALTIME_TARGETS = {
    target.value: target
    for target in (
        SnapshotTarget.T30,
        SnapshotTarget.T15,
        SnapshotTarget.T10,
        SnapshotTarget.T05,
    )
}


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    """Project-wide time semantics."""

    timezone: ZoneInfo


@dataclass(frozen=True, slots=True)
class PilotConfig:
    """Scope of the initial pilot deployment."""

    venue: VenueCode


@dataclass(frozen=True, slots=True)
class SnapshotConfig:
    """Ordered real-time collection targets."""

    targets: tuple[SnapshotTarget, ...]


@dataclass(frozen=True, slots=True)
class RetentionConfig:
    """Retention periods for exceptional source responses."""

    anomaly_response_days: int


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Complete application configuration."""

    project: ProjectConfig
    pilot: PilotConfig
    snapshots: SnapshotConfig
    retention: RetentionConfig


def _validate_shape(data: dict[str, Any]) -> None:
    tables = frozenset(data)
    expected_tables = frozenset(_TABLE_FIELDS)
    if tables != expected_tables:
        raise ValueError("config must contain exactly the supported root tables")

    for table_name, expected_fields in _TABLE_FIELDS.items():
        table = data[table_name]
        if type(table) is not dict:
            raise TypeError(f"{table_name} must be a table")
        if frozenset(table) != expected_fields:
            raise ValueError(f"{table_name} must contain exactly the supported fields")


def _require_string(value: object, field: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{field} must be a string")
    return value


def _load_timezone(value: object) -> ZoneInfo:
    name = _require_string(value, "project.timezone")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"unknown timezone: {name}") from error


def _load_targets(value: object) -> tuple[SnapshotTarget, ...]:
    if type(value) is not list:
        raise TypeError("snapshots.targets must be an array")
    if not value:
        raise ValueError("snapshots.targets must not be empty")
    if any(type(item) is not str for item in value):
        raise TypeError("snapshots.targets entries must be strings")

    names = tuple(value)
    if len(set(names)) != len(names):
        raise ValueError("snapshots.targets must not contain duplicates")
    try:
        return tuple(_REALTIME_TARGETS[name] for name in names)
    except KeyError as error:
        raise ValueError(f"unsupported real-time snapshot target: {error.args[0]}") from error


def _load_retention_days(value: object) -> int:
    if type(value) is not int:
        raise TypeError("retention.anomaly_response_days must be an integer")
    if value < 1:
        raise ValueError("retention.anomaly_response_days must be at least one")
    return value


def load_config(path: Path | str) -> AppConfig:
    """Load and validate the complete TOML configuration at *path*."""

    with Path(path).open("rb") as config_file:
        data = tomllib.load(config_file)

    _validate_shape(data)
    return AppConfig(
        project=ProjectConfig(timezone=_load_timezone(data["project"]["timezone"])),
        pilot=PilotConfig(
            venue=VenueCode(_require_string(data["pilot"]["venue"], "pilot.venue"))
        ),
        snapshots=SnapshotConfig(targets=_load_targets(data["snapshots"]["targets"])),
        retention=RetentionConfig(
            anomaly_response_days=_load_retention_days(
                data["retention"]["anomaly_response_days"]
            )
        ),
    )
