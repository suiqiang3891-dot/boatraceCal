"""Domain value objects for BOAT RACE analysis."""

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode

__all__ = ["BetCombination", "BetType", "RaceId", "VenueCode"]
