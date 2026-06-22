"""Domain value objects for BOAT RACE analysis."""

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.domain.recommendations import Decision, PlanStage, Recommendation
from boatrace_cal.domain.temporal import AvailableRecord
from boatrace_cal.domain.versions import ArtifactVersions

__all__ = [
    "ArtifactVersions",
    "AvailableRecord",
    "BetCombination",
    "BetType",
    "Decision",
    "PlanStage",
    "RaceId",
    "Recommendation",
    "VenueCode",
]
