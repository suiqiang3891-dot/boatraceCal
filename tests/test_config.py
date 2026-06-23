from dataclasses import FrozenInstanceError
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from boatrace_cal.config import (
    AppConfig,
    PilotConfig,
    ProjectConfig,
    RetentionConfig,
    SnapshotConfig,
    load_config,
)
from boatrace_cal.domain.races import VenueCode
from boatrace_cal.jobs.contracts import SnapshotTarget


DEFAULT_CONFIG = Path(__file__).parents[1] / "configs" / "default.toml"


def _write_config(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(content, encoding="utf-8")
    return path


def test_loads_default_config() -> None:
    config = load_config(DEFAULT_CONFIG)

    assert config == AppConfig(
        project=ProjectConfig(timezone=ZoneInfo("Asia/Tokyo")),
        pilot=PilotConfig(venue=VenueCode("01")),
        snapshots=SnapshotConfig(
            targets=(
                SnapshotTarget.T30,
                SnapshotTarget.T15,
                SnapshotTarget.T10,
                SnapshotTarget.T05,
            )
        ),
        retention=RetentionConfig(anomaly_response_days=30),
    )


def test_config_dataclasses_are_frozen_and_slotted() -> None:
    config = load_config(DEFAULT_CONFIG)

    with pytest.raises(FrozenInstanceError):
        config.retention.anomaly_response_days = 31  # type: ignore[misc]
    assert not hasattr(config, "__dict__")
    assert not hasattr(config.project, "__dict__")
    assert not hasattr(config.pilot, "__dict__")
    assert not hasattr(config.snapshots, "__dict__")
    assert not hasattr(config.retention, "__dict__")


def test_missing_config_file_raises_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        load_config("missing.toml")


@pytest.mark.parametrize(
    "content",
    [
        """
[project]
timezone = "Asia/Tokyo"
[pilot]
venue = "01"
[snapshots]
targets = ["T30"]
""",
        """
[project]
timezone = "Asia/Tokyo"
[pilot]
venue = "01"
[snapshots]
targets = ["T30"]
[retention]
anomaly_response_days = 30
[unexpected]
enabled = true
""",
        """
[project]
timezone = "Asia/Tokyo"
typo = "ignored"
[pilot]
venue = "01"
[snapshots]
targets = ["T30"]
[retention]
anomaly_response_days = 30
""",
    ],
)
def test_rejects_missing_or_unknown_tables_and_fields(tmp_path: Path, content: str) -> None:
    with pytest.raises(ValueError):
        load_config(_write_config(tmp_path, content))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project.timezone", "123"),
        ("pilot.venue", "1"),
        ("snapshots.targets", '"T30"'),
        ("retention.anomaly_response_days", '"30"'),
        ("retention.anomaly_response_days", "true"),
    ],
)
def test_rejects_invalid_field_types(tmp_path: Path, field: str, value: str) -> None:
    table, name = field.split(".")
    values = {
        "project": {"timezone": '"Asia/Tokyo"'},
        "pilot": {"venue": '"01"'},
        "snapshots": {"targets": '["T30"]'},
        "retention": {"anomaly_response_days": "30"},
    }
    values[table][name] = value
    content = "\n".join(
        f"[{section}]\n" + "\n".join(f"{key} = {item}" for key, item in fields.items())
        for section, fields in values.items()
    )

    with pytest.raises((TypeError, ValueError)):
        load_config(_write_config(tmp_path, content))


@pytest.mark.parametrize(
    "targets",
    [
        "[]",
        '["T30", "T30"]',
        '["historical"]',
        '["T30", 15]',
        '["T00"]',
    ],
)
def test_rejects_invalid_realtime_snapshot_targets(tmp_path: Path, targets: str) -> None:
    content = f"""
[project]
timezone = "Asia/Tokyo"
[pilot]
venue = "01"
[snapshots]
targets = {targets}
[retention]
anomaly_response_days = 30
"""

    with pytest.raises((TypeError, ValueError)):
        load_config(_write_config(tmp_path, content))


@pytest.mark.parametrize("days", [0, -1])
def test_rejects_retention_below_one_day(tmp_path: Path, days: int) -> None:
    content = f"""
[project]
timezone = "Asia/Tokyo"
[pilot]
venue = "01"
[snapshots]
targets = ["T30"]
[retention]
anomaly_response_days = {days}
"""

    with pytest.raises(ValueError):
        load_config(_write_config(tmp_path, content))


def test_rejects_unknown_timezone(tmp_path: Path) -> None:
    content = """
[project]
timezone = "Mars/Olympus"
[pilot]
venue = "01"
[snapshots]
targets = ["T30"]
[retention]
anomaly_response_days = 30
"""

    with pytest.raises(ValueError):
        load_config(_write_config(tmp_path, content))
