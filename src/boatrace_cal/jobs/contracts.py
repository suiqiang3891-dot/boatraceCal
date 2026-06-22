"""Auditable identities and explicit lifecycle transitions for ingestion jobs."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from boatrace_cal.domain.races import VenueCode


class SnapshotTarget(StrEnum):
    """Supported historical and pre-race collection targets."""

    HISTORICAL = "historical"
    T30 = "T30"
    T15 = "T15"
    T10 = "T10"
    T05 = "T05"


class JobStatus(StrEnum):
    """Persistable lifecycle states for a job attempt."""

    PENDING = "pending"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


_ALLOWED_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.PENDING: frozenset({JobStatus.RUNNING}),
    JobStatus.RUNNING: frozenset(
        {
            JobStatus.SUCCEEDED,
            JobStatus.RETRY_WAIT,
            JobStatus.FAILED,
            JobStatus.SKIPPED,
        }
    ),
    JobStatus.RETRY_WAIT: frozenset({JobStatus.RUNNING}),
}


def transition(current: JobStatus, target: JobStatus) -> JobStatus:
    """Return the target state when the requested transition is explicitly allowed."""

    if type(current) is not JobStatus or type(target) is not JobStatus:
        raise TypeError("current and target must be JobStatus instances")
    if target not in _ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise ValueError(f"invalid job transition: {current} -> {target}")
    return target


@dataclass(frozen=True, slots=True)
class JobKey:
    """Stable, human-readable identity for one collection job."""

    source: str
    venue: VenueCode
    race_date: date
    race_no: int | None
    data_type: str
    snapshot_target: SnapshotTarget

    def __post_init__(self) -> None:
        if type(self.source) is not str:
            raise TypeError("source must be a string")
        if type(self.venue) is not VenueCode:
            raise TypeError("venue must be a VenueCode")
        if type(self.race_date) is not date:
            raise TypeError("race_date must be a date, not a datetime")
        if self.race_no is not None and type(self.race_no) is not int:
            raise TypeError("race_no must be an integer or None")
        if type(self.data_type) is not str:
            raise TypeError("data_type must be a string")
        if type(self.snapshot_target) is not SnapshotTarget:
            raise TypeError("snapshot_target must be a SnapshotTarget")

        source = self.source.strip()
        data_type = self.data_type.strip()
        if not source:
            raise ValueError("source must not be blank")
        if not data_type:
            raise ValueError("data_type must not be blank")
        if self.race_no is not None and not 1 <= self.race_no <= 12:
            raise ValueError("race_no must be between 1 and 12")

        object.__setattr__(self, "source", source)
        object.__setattr__(self, "data_type", data_type)

    @property
    def key(self) -> str:
        """Return the canonical ledger key."""

        race_no = "*" if self.race_no is None else str(self.race_no)
        return "|".join(
            (
                self.source,
                str(self.venue),
                self.race_date.isoformat(),
                race_no,
                self.data_type,
                self.snapshot_target.value,
            )
        )

    def __str__(self) -> str:
        return self.key
