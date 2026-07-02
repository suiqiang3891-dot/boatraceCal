from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from boatrace_cal.backtest.settlement import settle_selected_recommendations
from boatrace_cal.domain.bets import BetCombination, BetType
from boatrace_cal.domain.races import RaceId, VenueCode
from boatrace_cal.domain.recommendations import (
    ConfidenceLevel,
    Decision,
    PlanStage,
    Recommendation,
)
from boatrace_cal.domain.versions import ArtifactVersions
from boatrace_cal.ingestion.payouts import PayoutRecord
from boatrace_cal.ingestion.results import RaceResultRecord
from boatrace_cal.settlement import SettlementStatus


def test_settle_selected_recommendations_returns_auditable_paper_bet_rows() -> None:
    race_1 = RaceId(date(2025, 1, 2), VenueCode("01"), 1)
    race_2 = RaceId(date(2025, 1, 2), VenueCode("01"), 2)
    winning_combination = BetCombination.create(BetType.TRIFECTA_ORDERED, (1, 2, 3))
    losing_combination = BetCombination.create(BetType.TRIFECTA_ORDERED, (1, 3, 2))

    rows = settle_selected_recommendations(
        recommendations=(
            _recommendation("hit-rec", race_1, winning_combination, Decision.SELECT),
            _recommendation("pass-rec", race_1, losing_combination, Decision.PASS),
            _recommendation("miss-rec", race_2, losing_combination, Decision.SELECT),
        ),
        results=(
            _result(race_1, (1, 2, 3)),
            _result(race_2, (1, 2, 3)),
        ),
        payouts=(_payout(race_1, winning_combination, "1200"),),
    )

    assert tuple(row.recommendation_id for row in rows) == ("hit-rec", "miss-rec")
    assert rows[0].settlement.status is SettlementStatus.HIT
    assert rows[0].stake_yen == Decimal("100")
    assert rows[0].returned_yen == Decimal("1200")
    assert rows[0].net_profit_yen == Decimal("1100")
    assert rows[1].settlement.status is SettlementStatus.MISS
    assert rows[1].stake_yen == Decimal("100")
    assert rows[1].returned_yen == Decimal("0")
    assert rows[1].net_profit_yen == Decimal("-100")


def test_settle_selected_recommendations_rejects_missing_results() -> None:
    race = RaceId(date(2025, 1, 2), VenueCode("01"), 1)
    combination = BetCombination.create(BetType.TRIFECTA_ORDERED, (1, 2, 3))

    with pytest.raises(ValueError, match="missing result"):
        settle_selected_recommendations(
            recommendations=(_recommendation("rec-1", race, combination, Decision.SELECT),),
            results=(),
            payouts=(),
        )


def _recommendation(
    recommendation_id: str,
    race_id: RaceId,
    combination: BetCombination,
    decision: Decision,
) -> Recommendation:
    is_select = decision is Decision.SELECT
    return Recommendation(
        recommendation_id=recommendation_id,
        race_id=race_id,
        combination=combination,
        stage=PlanStage.FINAL,
        decision=decision,
        confidence=ConfidenceLevel.HIGH,
        probability=Decimal("0.25"),
        odds=Decimal("5.2") if is_select else None,
        expected_value=Decimal("0.30") if is_select else None,
        as_of=datetime(2025, 1, 2, 10, 0, tzinfo=UTC),
        stake_units=1 if is_select else 0,
        versions=ArtifactVersions("data-v1", "feature-v1", "model-v1", "strategy-v1"),
        reason_codes=("positive_ev",) if is_select else ("below_threshold",),
    )


def _result(race_id: RaceId, finish_order: tuple[int, int, int]) -> RaceResultRecord:
    timestamp = datetime(2025, 1, 2, 16, 0, tzinfo=UTC)
    return RaceResultRecord(
        race_id=race_id,
        finish_order=finish_order,
        source="official-results",
        source_hash=f"result-{race_id}",
        observed_at=timestamp,
        available_at=timestamp,
        parser_version="results-v1",
    )


def _payout(
    race_id: RaceId,
    combination: BetCombination,
    payout_yen: str,
) -> PayoutRecord:
    timestamp = datetime(2025, 1, 2, 16, 0, tzinfo=UTC)
    return PayoutRecord(
        race_id=race_id,
        combination=combination,
        payout_yen=Decimal(payout_yen),
        source="official-payouts",
        source_hash=f"payout-{race_id}",
        observed_at=timestamp,
        available_at=timestamp,
        parser_version="payouts-v1",
    )
