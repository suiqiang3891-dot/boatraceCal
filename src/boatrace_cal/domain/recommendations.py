"""Immutable recommendation decisions and their audit context."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from boatrace_cal.domain.bets import BetCombination
from boatrace_cal.domain.races import RaceId
from boatrace_cal.domain.versions import ArtifactVersions


class PlanStage(StrEnum):
    """Lifecycle stage of an analysis result."""

    PREPLAN = "preplan"
    FINAL = "final"


class Decision(StrEnum):
    """Final strategy disposition for a combination."""

    SELECT = "select"
    PASS = "pass"


@dataclass(frozen=True, slots=True)
class Recommendation:
    """Auditable recommendation without provisional market-value claims."""

    recommendation_id: str
    race_id: RaceId
    combination: BetCombination
    stage: PlanStage
    decision: Decision
    probability: Decimal
    odds: Decimal | None
    expected_value: Decimal | None
    as_of: datetime
    stake_units: int
    versions: ArtifactVersions
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        recommendation_id = self.recommendation_id.strip()
        if not recommendation_id:
            raise ValueError("recommendation id must not be empty")
        object.__setattr__(self, "recommendation_id", recommendation_id)

        if not Decimal("0") <= self.probability <= Decimal("1"):
            raise ValueError("probability must be between 0 and 1")
        if type(self.stake_units) is not int or self.stake_units < 0:
            raise ValueError("stake units must be a non-negative integer")
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")

        normalized_reasons = tuple(reason.strip() for reason in self.reason_codes)
        if any(not reason for reason in normalized_reasons):
            raise ValueError("reason codes must not contain empty values")
        object.__setattr__(self, "reason_codes", normalized_reasons)

        if self.odds is not None and self.odds <= Decimal("0"):
            raise ValueError("odds must be positive")
        if self.stage is PlanStage.PREPLAN:
            if self.decision is Decision.SELECT:
                raise ValueError("preplan cannot be a final selection")
            if self.odds is not None or self.expected_value is not None:
                raise ValueError("preplan cannot provide odds or expected value")
        elif self.decision is Decision.SELECT:
            if self.odds is None or self.expected_value is None:
                raise ValueError("final selection requires odds and expected value")
        elif not self.reason_codes:
            raise ValueError("final pass requires reason codes")
