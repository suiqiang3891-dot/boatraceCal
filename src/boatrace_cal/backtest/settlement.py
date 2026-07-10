"""Batch settlement rows for paper backtest recommendations."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from boatrace_cal.domain.races import RaceId
from boatrace_cal.domain.recommendations import Decision, PlanStage, Recommendation
from boatrace_cal.ingestion.payouts import PayoutRecord
from boatrace_cal.ingestion.results import RaceResultRecord
from boatrace_cal.settlement import SettlementResult, SettlementStatus, settle_bet


@dataclass(frozen=True, slots=True)
class BacktestSettlementRow:
    """One settled paper bet selected by a final recommendation."""

    recommendation_id: str
    race_id: RaceId
    stake_units: int
    stake_yen: Decimal
    returned_yen: Decimal
    net_profit_yen: Decimal
    recommendation: Recommendation
    settlement: SettlementResult

    def __post_init__(self) -> None:
        if type(self.recommendation_id) is not str or not self.recommendation_id.strip():
            raise TypeError("recommendation_id must be a non-empty string")
        object.__setattr__(self, "recommendation_id", self.recommendation_id.strip())
        if type(self.race_id) is not RaceId:
            raise TypeError("race_id must be a RaceId")
        if type(self.stake_units) is not int or self.stake_units <= 0:
            raise ValueError("stake_units must be a positive integer")
        for field_name in ("stake_yen", "returned_yen", "net_profit_yen"):
            value = getattr(self, field_name)
            if type(value) is not Decimal or not value.is_finite():
                raise TypeError(f"{field_name} must be a finite Decimal")
        if self.stake_yen <= Decimal("0"):
            raise ValueError("stake_yen must be positive")
        if self.returned_yen < Decimal("0"):
            raise ValueError("returned_yen must not be negative")
        if self.net_profit_yen != self.returned_yen - self.stake_yen:
            raise ValueError("net_profit_yen must equal returned_yen minus stake_yen")
        if type(self.recommendation) is not Recommendation:
            raise TypeError("recommendation must be a Recommendation")
        if self.recommendation.recommendation_id != self.recommendation_id:
            raise ValueError("recommendation id must match row recommendation_id")
        if self.recommendation.race_id != self.race_id:
            raise ValueError("recommendation race_id must match row race_id")
        if self.recommendation.stage is not PlanStage.FINAL:
            raise ValueError("settlement rows require a final recommendation")
        if self.recommendation.decision is not Decision.SELECT:
            raise ValueError("settlement rows require a selected recommendation")
        if self.recommendation.stake_units != self.stake_units:
            raise ValueError("recommendation stake units must match row stake_units")
        if type(self.settlement) is not SettlementResult:
            raise TypeError("settlement must be a SettlementResult")
        if self.settlement.race_id != self.race_id:
            raise ValueError("settlement race_id must match row race_id")
        if self.settlement.combination != self.recommendation.combination:
            raise ValueError("settlement combination must match recommendation combination")


def settle_selected_recommendations(
    *,
    recommendations: Iterable[Recommendation],
    results: Iterable[RaceResultRecord],
    payouts: Iterable[PayoutRecord],
    stake_unit_yen: Decimal = Decimal("100"),
) -> tuple[BacktestSettlementRow, ...]:
    """Settle final selected recommendations into deterministic paper bet rows."""

    selected = _normalize_selected_recommendations(recommendations)
    result_by_race = _index_results(results)
    normalized_payouts = _normalize_payouts(payouts)
    unit_stake = _normalize_stake_unit(stake_unit_yen)

    rows = []
    for recommendation in selected:
        result = result_by_race.get(recommendation.race_id)
        if result is None:
            raise ValueError(f"missing result for selected recommendation: {recommendation.race_id}")
        settlement = settle_bet(result, recommendation.combination, normalized_payouts)
        stake_yen = unit_stake * recommendation.stake_units
        returned_yen = _returned_yen(settlement, recommendation.stake_units)
        rows.append(
            BacktestSettlementRow(
                recommendation_id=recommendation.recommendation_id,
                race_id=recommendation.race_id,
                stake_units=recommendation.stake_units,
                stake_yen=stake_yen,
                returned_yen=returned_yen,
                net_profit_yen=returned_yen - stake_yen,
                recommendation=recommendation,
                settlement=settlement,
            )
        )
    return tuple(rows)


def _normalize_selected_recommendations(
    recommendations: Iterable[Recommendation],
) -> tuple[Recommendation, ...]:
    normalized = tuple(recommendations)
    if any(type(recommendation) is not Recommendation for recommendation in normalized):
        raise TypeError("recommendations must contain only Recommendation instances")
    return tuple(
        recommendation
        for recommendation in normalized
        if recommendation.stage is PlanStage.FINAL
        and recommendation.decision is Decision.SELECT
    )


def _index_results(
    results: Iterable[RaceResultRecord],
) -> dict[RaceId, RaceResultRecord]:
    indexed: dict[RaceId, RaceResultRecord] = {}
    for result in results:
        if type(result) is not RaceResultRecord:
            raise TypeError("results must contain only RaceResultRecord instances")
        if result.race_id in indexed:
            raise ValueError(f"duplicate result for race: {result.race_id}")
        indexed[result.race_id] = result
    return indexed


def _normalize_payouts(payouts: Iterable[PayoutRecord]) -> tuple[PayoutRecord, ...]:
    normalized = tuple(payouts)
    if any(type(payout) is not PayoutRecord for payout in normalized):
        raise TypeError("payouts must contain only PayoutRecord instances")
    return normalized


def _normalize_stake_unit(stake_unit_yen: Decimal) -> Decimal:
    if type(stake_unit_yen) is not Decimal or not stake_unit_yen.is_finite():
        raise TypeError("stake_unit_yen must be a finite Decimal")
    if stake_unit_yen <= Decimal("0") or stake_unit_yen != stake_unit_yen.to_integral():
        raise ValueError("stake_unit_yen must be a positive whole-yen amount")
    return stake_unit_yen


def _returned_yen(settlement: SettlementResult, stake_units: int) -> Decimal:
    if settlement.status is SettlementStatus.HIT:
        return settlement.payout_yen * stake_units
    return Decimal("0")
