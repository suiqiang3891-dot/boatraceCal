from dataclasses import FrozenInstanceError
from datetime import timedelta, timezone
import os
from pathlib import Path
import subprocess
import sys

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
        project=ProjectConfig(timezone=config.project.timezone),
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
    assert config.project.timezone.utcoffset(None) == timedelta(hours=9)
    assert config.project.timezone.tzname(None) == "Asia/Tokyo"


def test_default_config_loads_without_site_packages() -> None:
    source_root = Path(__file__).parents[1] / "src"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(source_root), environment.get("PYTHONPATH", "")))
    )

    result = subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            (
                "from boatrace_cal.config import load_config; "
                f"config = load_config({str(DEFAULT_CONFIG)!r}); "
                "print(config.project.timezone.tzname(None))"
            ),
        ],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "Asia/Tokyo"


def test_config_dataclasses_are_frozen_and_slotted() -> None:
    config = load_config(DEFAULT_CONFIG)

    with pytest.raises(FrozenInstanceError):
        config.retention.anomaly_response_days = 31  # type: ignore[misc]
    assert not hasattr(config, "__dict__")
    assert not hasattr(config.project, "__dict__")
    assert not hasattr(config.pilot, "__dict__")
    assert not hasattr(config.snapshots, "__dict__")
    assert not hasattr(config.retention, "__dict__")


def test_public_config_constructors_enforce_domain_types() -> None:
    business_timezone = timezone(timedelta(hours=9), name="Asia/Tokyo")
    project = ProjectConfig(timezone=business_timezone)
    pilot = PilotConfig(venue=VenueCode("01"))
    snapshots = SnapshotConfig(targets=[SnapshotTarget.T30, SnapshotTarget.T05])  # type: ignore[arg-type]
    retention = RetentionConfig(anomaly_response_days=1)

    assert snapshots.targets == (SnapshotTarget.T30, SnapshotTarget.T05)
    assert hash(project)
    assert hash(pilot)
    assert hash(snapshots)
    assert hash(retention)
    assert hash(
        AppConfig(
            project=project,
            pilot=pilot,
            snapshots=snapshots,
            retention=retention,
        )
    )


def test_snapshot_config_copies_list_input() -> None:
    targets = [SnapshotTarget.T30]
    config = SnapshotConfig(targets=targets)  # type: ignore[arg-type]

    targets.append(SnapshotTarget.T15)

    assert config.targets == (SnapshotTarget.T30,)


@pytest.mark.parametrize(
    "value",
    [
        "Asia/Tokyo",
        timezone(timedelta(hours=9)),
        timezone(timedelta(hours=8), name="Asia/Tokyo"),
    ],
)
def test_project_config_rejects_noncanonical_timezone(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        ProjectConfig(timezone=value)  # type: ignore[arg-type]


def test_nested_config_constructors_reject_lookalike_values() -> None:
    with pytest.raises(TypeError):
        PilotConfig(venue="01")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        SnapshotConfig(targets=("T30",))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        SnapshotConfig(targets=())
    with pytest.raises(ValueError):
        SnapshotConfig(targets=(SnapshotTarget.T30, SnapshotTarget.T30))
    with pytest.raises(ValueError):
        SnapshotConfig(targets=(SnapshotTarget.HISTORICAL,))
    with pytest.raises(TypeError):
        RetentionConfig(anomaly_response_days=True)
    with pytest.raises(ValueError):
        RetentionConfig(anomaly_response_days=0)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project", object()),
        ("pilot", object()),
        ("snapshots", object()),
        ("retention", object()),
    ],
)
def test_app_config_rejects_invalid_nested_type(field: str, value: object) -> None:
    values = {
        "project": ProjectConfig(
            timezone=timezone(timedelta(hours=9), name="Asia/Tokyo")
        ),
        "pilot": PilotConfig(venue=VenueCode("01")),
        "snapshots": SnapshotConfig(targets=(SnapshotTarget.T30,)),
        "retention": RetentionConfig(anomaly_response_days=30),
    }
    values[field] = value

    with pytest.raises(TypeError):
        AppConfig(**values)  # type: ignore[arg-type]


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


def test_rejects_unsupported_business_timezone(tmp_path: Path) -> None:
    content = """
[project]
timezone = "Asia/Shanghai"
[pilot]
venue = "01"
[snapshots]
targets = ["T30"]
[retention]
anomaly_response_days = 30
"""

    with pytest.raises(ValueError, match="unsupported business timezone"):
        load_config(_write_config(tmp_path, content))
