from datetime import UTC, date, datetime
from decimal import Decimal
import json
from pathlib import Path

import pytest

from boatrace_cal.backtest.export import export_backtest_report_json
from boatrace_cal.backtest.runner import run_backtest
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


def test_export_backtest_report_json_writes_json_ready_payload(tmp_path: Path) -> None:
    race = RaceId(date(2025, 1, 2), VenueCode("01"), 1)
    combination = BetCombination.create(BetType.TRIFECTA_ORDERED, (1, 2, 3))
    report = run_backtest(
        recommendations=(_recommendation(race, combination),),
        results=(_result(race),),
        payouts=(_payout(race, combination, "1200"),),
        expected_races=(race,),
        bet_types=(BetType.TRIFECTA_ORDERED,),
    )
    output_path = tmp_path / "reports" / "backtest-report.json"

    written_path = export_backtest_report_json(report, output_path)

    assert written_path == output_path
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["readiness"]["status"] == "ready"
    assert payload["summary"]["net_profit_yen"] == "1100"
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_export_backtest_report_json_rejects_non_report(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="report must be a BacktestReport"):
        export_backtest_report_json(object(), tmp_path / "report.json")  # type: ignore[arg-type]


def _recommendation(race_id: RaceId, combination: BetCombination) -> Recommendation:
    return Recommendation(
        recommendation_id="rec-1",
        race_id=race_id,
        combination=combination,
        stage=PlanStage.FINAL,
        decision=Decision.SELECT,
        confidence=ConfidenceLevel.HIGH,
        probability=Decimal("0.25"),
        odds=Decimal("5.2"),
        expected_value=Decimal("0.30"),
        as_of=datetime(2025, 1, 2, 10, 0, tzinfo=UTC),
        stake_units=1,
        versions=ArtifactVersions("data-v1", "feature-v1", "model-v1", "strategy-v1"),
        reason_codes=("positive_ev",),
    )


def _result(race_id: RaceId) -> RaceResultRecord:
    timestamp = datetime(2025, 1, 2, 16, 0, tzinfo=UTC)
    return RaceResultRecord(
        race_id=race_id,
        finish_order=(1, 2, 3),
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
