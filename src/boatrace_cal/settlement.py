"""Local settlement for completed race results and imported payouts."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId
from boatrace_cal.ingestion.payouts import PayoutRecord
from boatrace_cal.ingestion.results import RaceResultRecord


class SettlementStatus(StrEnum):
    """Settlement outcome for one bet combination."""

    HIT = "hit"
    MISS = "miss"
    PAYOUT_MISSING = "payout_missing"


@dataclass(frozen=True, slots=True)
class SettlementResult:
    """Auditable settlement result for one race and combination."""

    race_id: RaceId
    combination: BetCombination
    status: SettlementStatus
    payout_yen: Decimal

    def __post_init__(self) -> None:
        if type(self.race_id) is not RaceId:
            raise TypeError("race_id must be a RaceId")
        if type(self.combination) is not BetCombination:
            raise TypeError("combination must be a BetCombination")
        if type(self.status) is not SettlementStatus:
            raise TypeError("status must be a SettlementStatus")
        if type(self.payout_yen) is not Decimal or not self.payout_yen.is_finite():
            raise TypeError("payout_yen must be a finite Decimal")
        if self.payout_yen < Decimal("0"):
            raise ValueError("payout_yen must not be negative")
        if self.status is SettlementStatus.HIT and self.payout_yen <= Decimal("0"):
            raise ValueError("hit settlements require a positive payout")
        if self.status is not SettlementStatus.HIT and self.payout_yen != Decimal("0"):
            raise ValueError("non-hit settlements must have zero payout")


def settle_bet(
    result: RaceResultRecord,
    combination: BetCombination,
    payouts: Iterable[PayoutRecord],
) -> SettlementResult:
    """Settle one combination against a completed race result."""

    if type(result) is not RaceResultRecord:
        raise TypeError("result must be a RaceResultRecord")
    if type(combination) is not BetCombination:
        raise TypeError("combination must be a BetCombination")
    if not _is_winning_combination(result.finish_order, combination):
        return SettlementResult(
            race_id=result.race_id,
            combination=combination,
            status=SettlementStatus.MISS,
            payout_yen=Decimal("0"),
        )

    payout = _find_payout(result.race_id, combination, payouts)
    if payout is None:
        return SettlementResult(
            race_id=result.race_id,
            combination=combination,
            status=SettlementStatus.PAYOUT_MISSING,
            payout_yen=Decimal("0"),
        )
    return SettlementResult(
        race_id=result.race_id,
        combination=combination,
        status=SettlementStatus.HIT,
        payout_yen=payout.payout_yen,
    )


def _is_winning_combination(
    finish_order: tuple[int, int, int],
    combination: BetCombination,
) -> bool:
    if combination.bet_type is BetType.TRIFECTA_ORDERED:
        return combination.lanes == finish_order
    if combination.bet_type is BetType.TRIFECTA_BOX:
        return set(combination.lanes) == set(finish_order)
    if combination.bet_type is BetType.EXACTA_ORDERED:
        return combination.lanes == finish_order[:2]
    if combination.bet_type is BetType.EXACTA_BOX:
        return set(combination.lanes) == set(finish_order[:2])
    if combination.bet_type is BetType.WIDE_BOX:
        return set(combination.lanes).issubset(set(finish_order))
    raise AssertionError(f"unsupported bet type: {combination.bet_type}")


def _find_payout(
    race_id: RaceId,
    combination: BetCombination,
    payouts: Iterable[PayoutRecord],
) -> PayoutRecord | None:
    for payout in payouts:
        if type(payout) is not PayoutRecord:
            raise TypeError("payouts must contain only PayoutRecord instances")
        if payout.race_id == race_id and payout.combination == combination:
            return payout
    return None
