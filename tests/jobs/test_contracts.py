from datetime import date, datetime

import pytest

from boatrace_cal.domain.races import VenueCode
from boatrace_cal.jobs.contracts import JobKey, JobStatus, SnapshotTarget, transition


ALLOWED_TRANSITIONS = {
    (JobStatus.PENDING, JobStatus.RUNNING),
    (JobStatus.RUNNING, JobStatus.SUCCEEDED),
    (JobStatus.RUNNING, JobStatus.RETRY_WAIT),
    (JobStatus.RUNNING, JobStatus.FAILED),
    (JobStatus.RUNNING, JobStatus.SKIPPED),
    (JobStatus.RETRY_WAIT, JobStatus.RUNNING),
}


@pytest.mark.parametrize(("current", "target"), sorted(ALLOWED_TRANSITIONS))
def test_transition_accepts_only_explicit_paths(
    current: JobStatus, target: JobStatus
) -> None:
    assert transition(current, target) is target


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (current, target)
        for current in JobStatus
        for target in JobStatus
        if (current, target) not in ALLOWED_TRANSITIONS
    ],
)
def test_transition_rejects_every_other_status_pair(
    current: JobStatus, target: JobStatus
) -> None:
    with pytest.raises(ValueError, match="invalid job transition"):
        transition(current, target)


@pytest.mark.parametrize("terminal", [JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.SKIPPED])
def test_terminal_job_cannot_be_restarted(terminal: JobStatus) -> None:
    with pytest.raises(ValueError, match="invalid job transition"):
        transition(terminal, JobStatus.RUNNING)


@pytest.mark.parametrize(
    ("current", "target"),
    [("pending", JobStatus.RUNNING), (JobStatus.PENDING, "running")],
)
def test_transition_requires_job_status_instances(current: object, target: object) -> None:
    with pytest.raises(TypeError, match="JobStatus"):
        transition(current, target)  # type: ignore[arg-type]


def test_job_key_has_stable_auditable_representation() -> None:
    job = JobKey(
        source=" official ",
        venue=VenueCode("5"),
        race_date=date(2026, 6, 23),
        race_no=1,
        data_type=" odds ",
        snapshot_target=SnapshotTarget.T15,
    )

    assert job.source == "official"
    assert job.data_type == "odds"
    assert job.key == "official|05|2026-06-23|1|odds|T15"
    assert str(job) == job.key


def test_job_key_uses_wildcard_for_date_level_job() -> None:
    job = JobKey(
        source="official",
        venue=VenueCode("01"),
        race_date=date(2026, 6, 23),
        race_no=None,
        data_type="entries",
        snapshot_target=SnapshotTarget.HISTORICAL,
    )

    assert job.key == "official|01|2026-06-23|*|entries|historical"


@pytest.mark.parametrize("field", ["source", "data_type"])
@pytest.mark.parametrize("value", ["", "   "])
def test_job_key_rejects_blank_text(field: str, value: str) -> None:
    values = {
        "source": "official",
        "venue": VenueCode("01"),
        "race_date": date(2026, 6, 23),
        "race_no": 1,
        "data_type": "odds",
        "snapshot_target": SnapshotTarget.T30,
    }
    values[field] = value

    with pytest.raises(ValueError, match=field):
        JobKey(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source", 1),
        ("venue", "01"),
        ("race_date", datetime(2026, 6, 23)),
        ("race_date", "2026-06-23"),
        ("race_no", True),
        ("race_no", 1.0),
        ("data_type", 1),
        ("snapshot_target", "T30"),
    ],
)
def test_job_key_rejects_non_contract_types(field: str, value: object) -> None:
    values = {
        "source": "official",
        "venue": VenueCode("01"),
        "race_date": date(2026, 6, 23),
        "race_no": 1,
        "data_type": "odds",
        "snapshot_target": SnapshotTarget.T30,
    }
    values[field] = value

    with pytest.raises(TypeError, match=field):
        JobKey(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("race_no", [0, 13, -1])
def test_job_key_rejects_out_of_range_race_number(race_no: int) -> None:
    with pytest.raises(ValueError, match="race_no"):
        JobKey(
            source="official",
            venue=VenueCode("01"),
            race_date=date(2026, 6, 23),
            race_no=race_no,
            data_type="odds",
            snapshot_target=SnapshotTarget.T05,
        )


def test_job_enums_have_unique_values() -> None:
    assert len({target.value for target in SnapshotTarget}) == len(SnapshotTarget)
    assert len({status.value for status in JobStatus}) == len(JobStatus)
