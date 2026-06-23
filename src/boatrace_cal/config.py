"""Strict standard-library configuration loading."""

from dataclasses import dataclass
from datetime import timedelta, timezone
from pathlib import Path
import tomllib
from typing import Any

from boatrace_cal.domain.races import VenueCode
from boatrace_cal.jobs.contracts import SnapshotTarget


_TABLE_FIELDS = {
    "project": frozenset({"timezone"}),
    "pilot": frozenset({"venue"}),
    "snapshots": frozenset({"targets"}),
    "retention": frozenset({"anomaly_response_days"}),
}
_BUSINESS_TIMEZONE_NAME = "Asia/Tokyo"
_BUSINESS_TIMEZONE = timezone(timedelta(hours=9), name=_BUSINESS_TIMEZONE_NAME)
_REALTIME_TARGETS = frozenset(
    (
        SnapshotTarget.T30,
        SnapshotTarget.T15,
        SnapshotTarget.T10,
        SnapshotTarget.T05,
    )
)


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    """Project-wide time semantics."""

    timezone: timezone

    def __post_init__(self) -> None:
        if type(self.timezone) is not timezone:
            raise TypeError("project timezone must be a datetime.timezone")
        if (
            self.timezone.utcoffset(None) != timedelta(hours=9)
            or self.timezone.tzname(None) != _BUSINESS_TIMEZONE_NAME
        ):
            raise ValueError("project timezone must be Asia/Tokyo at UTC+09:00")


@dataclass(frozen=True, slots=True)
class PilotConfig:
    """Scope of the initial pilot deployment."""

    venue: VenueCode

    def __post_init__(self) -> None:
        if type(self.venue) is not VenueCode:
            raise TypeError("pilot venue must be a VenueCode")


@dataclass(frozen=True, slots=True)
class SnapshotConfig:
    """Ordered real-time collection targets."""

    targets: tuple[SnapshotTarget, ...]

    def __post_init__(self) -> None:
        if type(self.targets) not in (list, tuple):
            raise TypeError("snapshot targets must be a list or tuple")
        targets = tuple(self.targets)
        if not targets:
            raise ValueError("snapshot targets must not be empty")
        if any(type(target) is not SnapshotTarget for target in targets):
            raise TypeError("snapshot targets must be SnapshotTarget instances")
        if len(set(targets)) != len(targets):
            raise ValueError("snapshot targets must not contain duplicates")
        if any(target not in _REALTIME_TARGETS for target in targets):
            raise ValueError("snapshot targets must contain only real-time targets")
        object.__setattr__(self, "targets", targets)


@dataclass(frozen=True, slots=True)
class RetentionConfig:
    """Retention periods for exceptional source responses."""

    anomaly_response_days: int

    def __post_init__(self) -> None:
        if type(self.anomaly_response_days) is not int:
            raise TypeError("retention days must be an integer")
        if self.anomaly_response_days < 1:
            raise ValueError("retention days must be at least one")


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Complete application configuration."""

    project: ProjectConfig
    pilot: PilotConfig
    snapshots: SnapshotConfig
    retention: RetentionConfig

    def __post_init__(self) -> None:
        expected_types = (
            ("project", self.project, ProjectConfig),
            ("pilot", self.pilot, PilotConfig),
            ("snapshots", self.snapshots, SnapshotConfig),
            ("retention", self.retention, RetentionConfig),
        )
        for name, value, expected_type in expected_types:
            if type(value) is not expected_type:
                raise TypeError(f"{name} must be a {expected_type.__name__}")


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


def _load_timezone(value: object) -> timezone:
    name = _require_string(value, "project.timezone")
    if name != _BUSINESS_TIMEZONE_NAME:
        raise ValueError(f"unsupported business timezone: {name}")
    return _BUSINESS_TIMEZONE


def _load_targets(value: object) -> tuple[SnapshotTarget, ...]:
    if type(value) is not list:
        raise TypeError("snapshots.targets must be an array")
    if any(type(item) is not str for item in value):
        raise TypeError("snapshots.targets entries must be strings")
    try:
        return tuple(SnapshotTarget(item) for item in value)
    except ValueError as error:
        raise ValueError(f"unsupported snapshot target: {error.args[0]}") from error


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
            anomaly_response_days=data["retention"]["anomaly_response_days"]
        ),
    )
