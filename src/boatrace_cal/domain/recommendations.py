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


class ConfidenceLevel(StrEnum):
    """Confidence conveyed with every provisional or final analysis."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class Recommendation:
    """Auditable recommendation without provisional market-value claims."""

    recommendation_id: str
    race_id: RaceId
    combination: BetCombination
    stage: PlanStage
    decision: Decision
    confidence: ConfidenceLevel
    probability: Decimal
    odds: Decimal | None
    expected_value: Decimal | None
    as_of: datetime
    stake_units: int
    versions: ArtifactVersions
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.race_id) is not RaceId:
            raise ValueError("race id must be a RaceId")
        if type(self.combination) is not BetCombination:
            raise ValueError("combination must be a BetCombination")
        if type(self.versions) is not ArtifactVersions:
            raise ValueError("versions must be ArtifactVersions")
        if type(self.stage) is not PlanStage:
            raise ValueError("stage must be a PlanStage")
        if type(self.decision) is not Decision:
            raise ValueError("decision must be a Decision")
        if type(self.confidence) is not ConfidenceLevel:
            raise ValueError("confidence must be a ConfidenceLevel")

        if type(self.recommendation_id) is not str:
            raise ValueError("recommendation id must be a string")
        recommendation_id = self.recommendation_id.strip()
        if not recommendation_id:
            raise ValueError("recommendation id must not be empty")
        object.__setattr__(self, "recommendation_id", recommendation_id)

        if type(self.probability) is not Decimal or not self.probability.is_finite():
            raise ValueError("probability must be a finite Decimal")
        if not Decimal("0") <= self.probability <= Decimal("1"):
            raise ValueError("probability must be between 0 and 1")

        if self.odds is not None:
            if type(self.odds) is not Decimal or not self.odds.is_finite():
                raise ValueError("odds must be a finite Decimal")
            if self.odds <= Decimal("0"):
                raise ValueError("odds must be positive")
        if self.expected_value is not None and (
            type(self.expected_value) is not Decimal or not self.expected_value.is_finite()
        ):
            raise ValueError("expected value must be a finite Decimal")

        if type(self.stake_units) is not int:
            raise ValueError("stake units must be an integer")
        required_units = 1 if (
            self.stage is PlanStage.FINAL and self.decision is Decision.SELECT
        ) else 0
        if self.stake_units != required_units:
            raise ValueError(f"stake units must be {required_units} for this decision")
        if type(self.as_of) is not datetime:
            raise ValueError("as_of must be a datetime")
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")

        if type(self.reason_codes) is not tuple or any(
            type(reason) is not str for reason in self.reason_codes
        ):
            raise ValueError("reason codes must be a tuple of strings")
        normalized_reasons = tuple(reason.strip() for reason in self.reason_codes)
        if any(not reason for reason in normalized_reasons):
            raise ValueError("reason codes must not contain empty values")
        object.__setattr__(self, "reason_codes", normalized_reasons)
        if self.stage is PlanStage.FINAL and not self.reason_codes:
            raise ValueError("final recommendations require reason codes")

        if self.stage is PlanStage.PREPLAN:
            if self.decision is Decision.SELECT:
                raise ValueError("preplan cannot be a final selection")
            if self.odds is not None or self.expected_value is not None:
                raise ValueError("preplan cannot provide odds or expected value")
        elif self.decision is Decision.SELECT:
            if self.odds is None or self.expected_value is None:
                raise ValueError("final selection requires odds and expected value")
